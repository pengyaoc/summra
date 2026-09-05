"""API route for the discover page's curated carousels.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import logging

from flask import Blueprint, jsonify

from backend.routes import common

logger = logging.getLogger(__name__)

bp = Blueprint('discover', __name__)


@bp.route('/api/discover/carousels', methods=['GET'])
def get_discover_carousels():
    """Get curated book collections for the discover page"""
    db = common.db
    try:
        all_books = db.get_all_books()

        # Carousel 1: Easy to Read (A2-B1 level)
        easy_to_read = []
        for book in all_books:
            cefr_level = book.get('cefr_level')
            if cefr_level and book.get('slug') and any(level in cefr_level for level in ['A2', 'B1']):
                easy_to_read.append(book)

        # Carousel 2: Books with Full Audio Summaries
        # Only include books that have medium summaries (the "Full Summary") AND have audio files
        books_with_audio = []
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.book_id
            FROM summaries s
            INNER JOIN audio_files af ON s.id = af.summary_id
            WHERE s.summary_type = 'medium'
        ''')
        audio_book_ids = {row['book_id'] for row in cursor.fetchall()}
        conn.close()

        for book in all_books:
            if book.get('id') in audio_book_ids and book.get('slug'):
                books_with_audio.append(book)

        # Carousel 3: Books You Can Read in a Day (under 50,000 words)
        quick_reads = []
        for book in all_books:
            word_count = book.get('word_count')
            if word_count and word_count < 50000 and book.get('slug'):
                quick_reads.append(book)

        # Carousel 4: Adventure Category (category_id = 34)
        adventure_books = []
        for book in all_books:
            if book.get('slug') and book.get('categories'):
                if any(cat.get('id') == 34 for cat in book['categories']):
                    adventure_books.append(book)

        # Carousel 4: Children's Literature (category_id = 51)
        childrens_books = []
        for book in all_books:
            if book.get('slug') and book.get('categories'):
                if any(cat.get('id') == 51 for cat in book['categories']):
                    childrens_books.append(book)

        # Carousel 5: Romance (category_id = 46)
        romance_books = []
        for book in all_books:
            if book.get('slug') and book.get('categories'):
                if any(cat.get('id') == 46 for cat in book['categories']):
                    romance_books.append(book)

        # Carousel 6: Books by Charles Dickens
        dickens_books = []
        for book in all_books:
            if book.get('slug') and book.get('author') == 'Charles Dickens':
                dickens_books.append(book)

        # Build carousel data
        carousels = []

        if easy_to_read:
            carousels.append({
                'id': 'easy-to-read',
                'title': 'Easy to Read',
                'description': 'Perfect for beginners and intermediate learners (A2-B1 level)',
                'books': easy_to_read
            })

        if books_with_audio:
            carousels.append({
                'id': 'with-audio',
                'title': 'Books with Full Audio Summaries',
                'description': 'Listen to comprehensive summaries of these classics',
                'books': books_with_audio
            })

        if quick_reads:
            carousels.append({
                'id': 'quick-reads',
                'title': 'Books You Can Read in a Day',
                'description': 'Shorter classics under 50,000 words - perfect for a quick read',
                'books': quick_reads
            })

        if adventure_books:
            carousels.append({
                'id': 'adventure',
                'title': 'Adventure',
                'description': 'Thrilling tales of exploration and excitement',
                'books': adventure_books
            })

        if childrens_books:
            carousels.append({
                'id': 'childrens',
                'title': "Children's Literature",
                'description': 'Timeless stories written for young readers',
                'books': childrens_books
            })

        if romance_books:
            carousels.append({
                'id': 'romance',
                'title': 'Romance',
                'description': 'Classic love stories and romantic literature',
                'books': romance_books
            })

        if dickens_books:
            carousels.append({
                'id': 'charles-dickens',
                'title': 'Books by Charles Dickens',
                'description': 'Works by the master of Victorian literature',
                'books': dickens_books
            })

        return jsonify({
            'success': True,
            'carousels': carousels
        })
    except Exception as e:
        logger.error(f"Error fetching discover carousels: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
