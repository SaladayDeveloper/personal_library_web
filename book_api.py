import requests
import isbnlib


def get_book_by_isbn(isbn):
    """Получает информацию о книге по ISBN"""
    try:
        # Очищаем ISBN
        clean_isbn = isbnlib.to_isbn13(isbn) if isbnlib.is_isbn10(isbn) else isbn

        # Пробуем разные источники
        book_info = isbnlib.meta(clean_isbn)

        if book_info:
            # Пытаемся получить обложку
            cover_url = f"https://covers.openlibrary.org/b/isbn/{clean_isbn}-L.jpg"

            return {
                'title': book_info.get('Title', ''),
                'author': book_info.get('Authors', [''])[0],
                'isbn': clean_isbn,
                'publisher': book_info.get('Publisher', ''),
                'publication_year': book_info.get('Year', ''),
                'language': book_info.get('Language', 'ru'),
                'cover_image_url': cover_url
            }

        # Альтернативный источник - Open Library
        ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
        response = requests.get(ol_url)

        if response.status_code == 200:
            data = response.json()
            book_key = f"ISBN:{clean_isbn}"

            if book_key in data:
                book_data = data[book_key]

                return {
                    'title': book_data.get('title', ''),
                    'author': book_data.get('authors', [{}])[0].get('name', '') if book_data.get('authors') else '',
                    'isbn': clean_isbn,
                    'publisher': book_data.get('publishers', [{}])[0].get('name', '') if book_data.get(
                        'publishers') else '',
                    'publication_year': book_data.get('publish_date', ''),
                    'cover_image_url': book_data.get('cover', {}).get('large', ''),
                    'page_count': book_data.get('number_of_pages')
                }

        return None

    except Exception as e:
        print(f"Error fetching book data: {e}")
        return None