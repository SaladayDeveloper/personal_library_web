from models import db, Book, Author, ReadingSession, ReadingGoal
from datetime import datetime


def init_db():
    """Инициализация базы данных с тестовыми данными"""
    db.create_all()

    # Добавляем тестовых авторов
    authors = [
        Author(name="Фёдор Достоевский", biography="Русский писатель, мыслитель, философ и публицист."),
        Author(name="Лев Толстой", biography="Один из наиболее известных русских писателей и мыслителей."),
        Author(name="Антон Чехов", biography="Русский писатель, прозаик, драматург.")
    ]

    for author in authors:
        db.session.add(author)

    db.session.commit()

    # Добавляем тестовые книги
    books = [
        Book(
            title="Преступление и наказание",
            author="Фёдор Достоевский",
            author_id=authors[0].id,
            genre="Роман",
            tags="классика, психология, философия",
            description="Роман о моральных страданиях и психической боли.",
            page_count=551,
            reading_status="прочитана",
            my_rating=9,
            date_added=datetime(2023, 1, 15),
            date_finished_reading=datetime(2023, 2, 10)
        ),
        Book(
            title="Война и мир",
            author="Лев Толстой",
            author_id=authors[1].id,
            genre="Роман-эпопея",
            tags="классика, исторический, философия",
            description="Роман-эпопея, описывающий русское общество в эпоху войн против Наполеона.",
            page_count=1225,
            reading_status="читаю",
            my_rating=8,
            date_added=datetime(2023, 3, 1),
            date_started_reading=datetime(2023, 3, 5),
            current_page=350
        )
    ]

    for book in books:
        db.session.add(book)

    db.session.commit()

    # Добавляем тестовые сессии чтения
    sessions = [
        ReadingSession(
            book_id=books[1].id,
            pages_read=50,
            duration_minutes=120,
            start_time=datetime(2023, 3, 5, 19, 0)
        ),
        ReadingSession(
            book_id=books[1].id,
            pages_read=75,
            duration_minutes=180,
            start_time=datetime(2023, 3, 7, 20, 30)
        )
    ]

    for session in sessions:
        db.session.add(session)

    # Добавляем тестовые цели
    goals = [
        ReadingGoal(year=2024, goal_type="books", target=50),
        ReadingGoal(year=2024, goal_type="pages", target=10000)
    ]

    for goal in goals:
        db.session.add(goal)

    db.session.commit()
    print("База данных инициализирована с тестовыми данными!")