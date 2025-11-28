from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

db = SQLAlchemy()


class Author(db.Model):
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    biography = db.Column(db.Text)
    photo_url = db.Column(db.String(500))

    books = relationship('Book', back_populates='author_rel')

    def __repr__(self):
        return f'<Author {self.name}>'


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id'))
    isbn = db.Column(db.String(20))
    publication_year = db.Column(db.Integer)
    publisher = db.Column(db.String(100))
    genre = db.Column(db.String(50), index=True)
    tags = db.Column(db.String(500))  # CSV формат для простоты
    description = db.Column(db.Text)
    cover_image_url = db.Column(db.String(500))
    language = db.Column(db.String(20), default='Russian')
    page_count = db.Column(db.Integer)
    physical_location = db.Column(db.String(100))

    reading_status = db.Column(db.String(20), default='не начата', index=True)
    my_rating = db.Column(db.Integer)  # 1-10
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_started_reading = db.Column(db.DateTime)
    date_finished_reading = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    current_page = db.Column(db.Integer, default=0)

    # Связи
    author_rel = relationship('Author', back_populates='books')
    reading_sessions = relationship('ReadingSession', back_populates='book', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Book {self.title}>'


class ReadingSession(db.Model):
    __tablename__ = 'reading_sessions'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    pages_read = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer)  # Продолжительность в минутах

    book = relationship('Book', back_populates='reading_sessions')

    def __repr__(self):
        return f'<ReadingSession {self.id} for Book {self.book_id}>'


class ReadingGoal(db.Model):
    __tablename__ = 'reading_goals'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    goal_type = db.Column(db.String(20), nullable=False)  # 'books' или 'pages'
    target = db.Column(db.Integer, nullable=False)
    current_progress = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<ReadingGoal {self.goal_type} {self.year}>'