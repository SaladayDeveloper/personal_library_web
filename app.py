from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from models import db, Book, Author, ReadingSession, ReadingGoal
from book_api import get_book_by_isbn
from datetime import datetime, timedelta
import json
import csv
import io
from sqlalchemy import func, extract, and_
from sqlalchemy.orm import joinedload

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# Фильтры для Jinja2
@app.template_filter('datetime')
def format_datetime(value, format='%d.%m.%Y %H:%M'):
    if value is None:
        return ""
    return value.strftime(format)


@app.template_filter('date')
def format_date(value, format='%d.%m.%Y'):
    if value is None:
        return ""
    return value.strftime(format)


@app.template_filter('tags_list')
def tags_list(value):
    if value:
        return [tag.strip() for tag in value.split(',')]
    return []


@app.context_processor
def utility_processor():
    def now():
        return datetime.now()

    return dict(now=now)


# Главная страница
@app.route('/')
def index():
    # Статистика для сводки
    total_books = Book.query.count()
    reading_books = Book.query.filter_by(reading_status='читаю').count()
    completed_books = Book.query.filter_by(reading_status='прочитана').count()

    # Последние добавленные книги
    recent_books = Book.query.order_by(Book.date_added.desc()).limit(5).all()

    # Текущие книги в чтении
    current_reading = Book.query.filter_by(reading_status='читаю').all()

    # Недавно прочитанные книги
    recently_finished = Book.query.filter(
        Book.reading_status == 'прочитана',
        Book.date_finished_reading.isnot(None)
    ).order_by(Book.date_finished_reading.desc()).limit(5).all()

    return render_template('index.html',
                           total_books=total_books,
                           reading_books=reading_books,
                           completed_books=completed_books,
                           recent_books=recent_books,
                           current_reading=current_reading,
                           recently_finished=recently_finished)


# Каталог книг
@app.route('/books')
def books():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Фильтры
    status_filter = request.args.get('status')
    genre_filter = request.args.get('genre')
    author_filter = request.args.get('author')
    tag_filter = request.args.get('tag')
    rating_filter = request.args.get('rating')

    query = Book.query

    if status_filter:
        query = query.filter(Book.reading_status == status_filter)
    if genre_filter:
        query = query.filter(Book.genre == genre_filter)
    if author_filter:
        query = query.filter(Book.author == author_filter)
    if tag_filter:
        query = query.filter(Book.tags.contains(tag_filter))
    if rating_filter:
        query = query.filter(Book.my_rating == rating_filter)

    # Сортировка
    sort_by = request.args.get('sort', 'date_added')
    sort_order = request.args.get('order', 'desc')

    sort_mapping = {
        'title': Book.title,
        'author': Book.author,
        'rating': Book.my_rating,
        'date_added': Book.date_added,
        'publication_year': Book.publication_year,
        'page_count': Book.page_count
    }

    sort_field = sort_mapping.get(sort_by, Book.date_added)

    if sort_order == 'asc':
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    books_pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Получаем уникальные значения для фильтров
    genres = db.session.query(Book.genre).filter(Book.genre.isnot(None)).distinct().all()
    authors = db.session.query(Book.author).distinct().all()
    statuses = db.session.query(Book.reading_status).distinct().all()

    # Извлекаем все теги
    all_tags = set()
    for book in Book.query.with_entities(Book.tags).all():
        if book.tags:
            all_tags.update(tag.strip() for tag in book.tags.split(','))

    return render_template('books.html',
                           books=books_pagination.items,
                           pagination=books_pagination,
                           genres=[g[0] for g in genres if g[0]],
                           authors=[a[0] for a in authors if a[0]],
                           statuses=[s[0] for s in statuses if s[0]],
                           all_tags=sorted(all_tags),
                           current_filters=request.args)


# Детальная страница книги
@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    reading_sessions = ReadingSession.query.filter_by(book_id=book_id).order_by(ReadingSession.start_time.desc()).all()

    # Подготавливаем данные для графика прогресса
    progress_data = []
    if reading_sessions and book.reading_status == 'читаю':
        cumulative_pages = 0
        for session in sorted(reading_sessions, key=lambda x: x.start_time):
            cumulative_pages += session.pages_read
            progress_data.append({
                'date': session.start_time.strftime('%Y-%m-%d'),
                'pages': cumulative_pages,
                'session_pages': session.pages_read
            })

    return render_template('book_detail.html',
                           book=book,
                           reading_sessions=reading_sessions,
                           progress_data=json.dumps(progress_data))


# Быстрое обновление статуса книги
@app.route('/book/<int:book_id>/update_status', methods=['POST'])
def update_book_status(book_id):
    book = Book.query.get_or_404(book_id)
    new_status = request.form.get('status')

    if new_status in ['не начата', 'читаю', 'прочитана', 'брошена', 'в планах']:
        book.reading_status = new_status

        if new_status == 'читаю' and not book.date_started_reading:
            book.date_started_reading = datetime.utcnow()
            book.current_page = 0
        elif new_status == 'прочитана':
            if not book.date_finished_reading:
                book.date_finished_reading = datetime.utcnow()
            book.current_page = book.page_count
        elif new_status == 'не начата':
            book.date_started_reading = None
            book.date_finished_reading = None
            book.current_page = 0

        db.session.commit()
        flash('Статус книги обновлен', 'success')

    return redirect(url_for('book_detail', book_id=book_id))


# Обновление рейтинга книги
@app.route('/book/<int:book_id>/update_rating', methods=['POST'])
def update_book_rating(book_id):
    book = Book.query.get_or_404(book_id)
    new_rating = request.form.get('rating', type=int)

    if new_rating and 1 <= new_rating <= 10:
        book.my_rating = new_rating
        db.session.commit()
        flash('Рейтинг обновлен', 'success')

    return redirect(url_for('book_detail', book_id=book_id))


# Добавление сессии чтения
@app.route('/book/<int:book_id>/add_session', methods=['POST'])
def add_reading_session(book_id):
    book = Book.query.get_or_404(book_id)

    pages_read = request.form.get('pages_read', type=int)
    duration = request.form.get('duration_minutes', type=int)

    if pages_read and pages_read > 0:
        session = ReadingSession(
            book_id=book_id,
            pages_read=pages_read,
            duration_minutes=duration,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow()
        )

        # Обновляем текущую страницу в книге
        if book.current_page + pages_read <= book.page_count:
            book.current_page += pages_read
        else:
            book.current_page = book.page_count

        # Если книга еще не начата, меняем статус
        if book.reading_status == 'не начата':
            book.reading_status = 'читаю'
            book.date_started_reading = datetime.utcnow()

        db.session.add(session)
        db.session.commit()
        flash('Сессия чтения добавлена', 'success')

    return redirect(url_for('book_detail', book_id=book_id))


# Добавление новой книги
@app.route('/book/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        # Обработка формы добавления книги
        book_data = {
            'title': request.form.get('title'),
            'author': request.form.get('author'),
            'isbn': request.form.get('isbn'),
            'publication_year': request.form.get('publication_year', type=int),
            'publisher': request.form.get('publisher'),
            'genre': request.form.get('genre'),
            'tags': request.form.get('tags'),
            'description': request.form.get('description'),
            'cover_image_url': request.form.get('cover_image_url'),
            'language': request.form.get('language', 'Russian'),
            'page_count': request.form.get('page_count', type=int),
            'physical_location': request.form.get('physical_location'),
            'reading_status': request.form.get('reading_status', 'не начата'),
            'my_rating': request.form.get('my_rating', type=int),
            'notes': request.form.get('notes')
        }

        # Обработка дат в зависимости от статуса
        reading_status = book_data['reading_status']
        if reading_status == 'читаю':
            book_data['date_started_reading'] = datetime.utcnow()
        elif reading_status == 'прочитана':
            book_data['date_started_reading'] = datetime.utcnow()
            book_data['date_finished_reading'] = datetime.utcnow()
            book_data['current_page'] = book_data['page_count']

        book = Book(**book_data)
        db.session.add(book)
        db.session.commit()

        flash('Книга успешно добавлена', 'success')
        return redirect(url_for('book_detail', book_id=book.id))

    return render_template('add_book.html')


# Редактирование книги
@app.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.isbn = request.form.get('isbn')
        book.publication_year = request.form.get('publication_year', type=int)
        book.publisher = request.form.get('publisher')
        book.genre = request.form.get('genre')
        book.tags = request.form.get('tags')
        book.description = request.form.get('description')
        book.cover_image_url = request.form.get('cover_image_url')
        book.language = request.form.get('language')
        book.page_count = request.form.get('page_count', type=int)
        book.physical_location = request.form.get('physical_location')
        book.reading_status = request.form.get('reading_status')
        book.my_rating = request.form.get('my_rating', type=int)
        book.notes = request.form.get('notes')

        db.session.commit()
        flash('Книга успешно обновлена', 'success')
        return redirect(url_for('book_detail', book_id=book.id))

    return render_template('edit_book.html', book=book)


# Удаление книги
@app.route('/book/<int:book_id>/delete', methods=['POST'])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    # Удаляем связанные сессии чтения
    ReadingSession.query.filter_by(book_id=book_id).delete()

    db.session.delete(book)
    db.session.commit()

    flash('Книга удалена', 'success')
    return redirect(url_for('books'))


# Поиск книги по ISBN
@app.route('/book/search_isbn')
def search_isbn():
    isbn = request.args.get('isbn')
    if isbn:
        book_data = get_book_by_isbn(isbn)
        if book_data:
            return jsonify(book_data)
    return jsonify({'error': 'Книга не найдена'}), 404


# Массовые операции
@app.route('/books/bulk_operations', methods=['POST'])
def bulk_operations():
    book_ids = request.form.getlist('book_ids')
    operation = request.form.get('operation')

    if not book_ids:
        flash('Не выбрано ни одной книги', 'warning')
        return redirect(url_for('books'))

    books = Book.query.filter(Book.id.in_(book_ids)).all()

    if operation == 'change_status':
        new_status = request.form.get('new_status')
        for book in books:
            book.reading_status = new_status
            if new_status == 'прочитана' and not book.date_finished_reading:
                book.date_finished_reading = datetime.utcnow()
                book.current_page = book.page_count
    elif operation == 'add_tag':
        new_tag = request.form.get('new_tag')
        for book in books:
            current_tags = [tag.strip() for tag in book.tags.split(',')] if book.tags else []
            if new_tag and new_tag not in current_tags:
                current_tags.append(new_tag)
                book.tags = ','.join(current_tags)
    elif operation == 'delete':
        for book in books:
            # Удаляем связанные сессии
            ReadingSession.query.filter_by(book_id=book.id).delete()
            db.session.delete(book)

    db.session.commit()
    flash(f'Операция выполнена для {len(books)} книг', 'success')
    return redirect(url_for('books'))


# Авторы
@app.route('/authors')
def authors():
    authors = Author.query.options(joinedload(Author.books)).all()
    return render_template('authors.html', authors=authors)


# Статистика
@app.route('/stats')
def stats():
    # Базовая статистика
    total_books = Book.query.count()
    total_pages = db.session.query(func.sum(Book.page_count)).scalar() or 0
    total_authors = db.session.query(func.count(Book.author.distinct())).scalar()

    books_by_status = db.session.query(
        Book.reading_status,
        func.count(Book.id)
    ).group_by(Book.reading_status).all()

    books_by_genre = db.session.query(
        Book.genre,
        func.count(Book.id)
    ).filter(Book.genre.isnot(None)).group_by(Book.genre).order_by(func.count(Book.id).desc()).limit(10).all()

    # Рейтинги
    average_rating = db.session.query(func.avg(Book.my_rating)).filter(Book.my_rating.isnot(None)).scalar()

    # Темп чтения (страниц в месяц)
    current_year = datetime.now().year
    monthly_pages = db.session.query(
        extract('month', ReadingSession.start_time).label('month'),
        func.sum(ReadingSession.pages_read).label('total_pages')
    ).filter(
        extract('year', ReadingSession.start_time) == current_year
    ).group_by('month').all()

    # Заполняем все месяцы
    monthly_data = [0] * 12
    for data in monthly_pages:
        monthly_data[data.month - 1] = data.total_pages

    # Активность по сезонам
    seasonal_activity = {
        'Winter': 0, 'Spring': 0, 'Summer': 0, 'Autumn': 0
    }

    for month, pages in enumerate(monthly_data):
        if month in [11, 0, 1]:  # Dec, Jan, Feb
            seasonal_activity['Winter'] += pages
        elif month in [2, 3, 4]:  # Mar, Apr, May
            seasonal_activity['Spring'] += pages
        elif month in [5, 6, 7]:  # Jun, Jul, Aug
            seasonal_activity['Summer'] += pages
        elif month in [8, 9, 10]:  # Sep, Oct, Nov
            seasonal_activity['Autumn'] += pages

    # Топ авторов
    top_authors = db.session.query(
        Book.author,
        func.count(Book.id).label('book_count')
    ).group_by(Book.author).order_by(func.count(Book.id).desc()).limit(10).all()

    return render_template('stats.html',
                           total_books=total_books,
                           total_pages=total_pages,
                           total_authors=total_authors,
                           average_rating=round(average_rating, 2) if average_rating else None,
                           books_by_status=books_by_status,
                           books_by_genre=books_by_genre,
                           monthly_data=monthly_data,
                           seasonal_activity=seasonal_activity,
                           top_authors=top_authors,
                           current_year=current_year)


# Цели чтения
@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if request.method == 'POST':
        year = request.form.get('year', type=int)
        goal_type = request.form.get('goal_type')
        target = request.form.get('target', type=int)

        # Проверяем, нет ли уже цели на этот год и тип
        existing_goal = ReadingGoal.query.filter_by(year=year, goal_type=goal_type).first()
        if existing_goal:
            flash('Цель на этот год и тип уже существует', 'warning')
            return redirect(url_for('goals'))

        goal = ReadingGoal(year=year, goal_type=goal_type, target=target)
        db.session.add(goal)
        db.session.commit()
        flash('Цель добавлена', 'success')
        return redirect(url_for('goals'))

    goals = ReadingGoal.query.all()
    current_year = datetime.now().year

    # Обновляем прогресс для целей
    for goal in goals:
        if goal.goal_type == 'books':
            goal.current_progress = Book.query.filter(
                Book.reading_status == 'прочитана',
                extract('year', Book.date_finished_reading) == goal.year
            ).count()
        elif goal.goal_type == 'pages':
            result = db.session.query(func.sum(ReadingSession.pages_read)).filter(
                extract('year', ReadingSession.start_time) == goal.year
            ).first()
            goal.current_progress = result[0] or 0

    db.session.commit()

    return render_template('goals.html', goals=goals, current_year=current_year)


# Удаление цели
@app.route('/goal/<int:goal_id>/delete', methods=['POST'])
def delete_goal(goal_id):
    goal = ReadingGoal.query.get_or_404(goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash('Цель удалена', 'success')
    return redirect(url_for('goals'))


# Импорт/экспорт
@app.route('/import_export')
def import_export():
    return render_template('import_export.html')


# Экспорт в CSV
@app.route('/export/csv')
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)

    # Заголовки
    writer.writerow(['Title', 'Author', 'ISBN', 'Publication Year', 'Publisher',
                     'Genre', 'Tags', 'Description', 'Language', 'Page Count',
                     'Reading Status', 'Rating', 'Date Added', 'Date Started',
                     'Date Finished', 'Notes'])

    # Данные
    books = Book.query.all()
    for book in books:
        writer.writerow([
            book.title,
            book.author,
            book.isbn or '',
            book.publication_year or '',
            book.publisher or '',
            book.genre or '',
            book.tags or '',
            book.description or '',
            book.language or '',
            book.page_count or '',
            book.reading_status,
            book.my_rating or '',
            book.date_added.strftime('%Y-%m-%d') if book.date_added else '',
            book.date_started_reading.strftime('%Y-%m-%d') if book.date_started_reading else '',
            book.date_finished_reading.strftime('%Y-%m-%d') if book.date_finished_reading else '',
            book.notes or ''
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'library_export_{datetime.now().strftime("%Y%m%d")}.csv'
    )


# Экспорт в JSON
@app.route('/export/json')
def export_json():
    books_data = []
    books = Book.query.all()

    for book in books:
        book_data = {
            'title': book.title,
            'author': book.author,
            'isbn': book.isbn,
            'publication_year': book.publication_year,
            'publisher': book.publisher,
            'genre': book.genre,
            'tags': book.tags,
            'description': book.description,
            'cover_image_url': book.cover_image_url,
            'language': book.language,
            'page_count': book.page_count,
            'physical_location': book.physical_location,
            'reading_status': book.reading_status,
            'my_rating': book.my_rating,
            'date_added': book.date_added.isoformat() if book.date_added else None,
            'date_started_reading': book.date_started_reading.isoformat() if book.date_started_reading else None,
            'date_finished_reading': book.date_finished_reading.isoformat() if book.date_finished_reading else None,
            'notes': book.notes,
            'current_page': book.current_page
        }
        books_data.append(book_data)

    return jsonify(books_data)


# API для получения статистики (для AJAX запросов)
@app.route('/api/stats/reading_activity')
def api_reading_activity():
    # Статистика чтения за последние 6 месяцев
    six_months_ago = datetime.now() - timedelta(days=180)

    activity_data = db.session.query(
        func.date(ReadingSession.start_time).label('date'),
        func.sum(ReadingSession.pages_read).label('pages')
    ).filter(
        ReadingSession.start_time >= six_months_ago
    ).group_by(
        func.date(ReadingSession.start_time)
    ).order_by('date').all()

    result = {
        'dates': [item.date.strftime('%Y-%m-%d') for item in activity_data],
        'pages': [item.pages for item in activity_data]
    }

    return jsonify(result)


# Обработка ошибки 404
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


# Обработка ошибки 500
@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)