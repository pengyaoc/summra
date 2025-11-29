"""
Base Flask application with common routes and logic.
This module is imported by both app.py (development) and app_prod.py (production).
"""
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
from pathlib import Path
import os
import sys
import logging

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Handle both direct execution and module execution
try:
    from . import config
    from . import models
except ImportError:
    import config
    import models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Initialize database
db = models.Database()


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/books', methods=['GET'])
def get_books():
    """Get all books"""
    try:
        books = db.get_all_books()

        # Convert cover image paths to URLs for frontend
        for book in books:
            if book.get('cover_image_url') and not book['cover_image_url'].startswith('http'):
                # It's a local path, prepend /static/
                book['cover_image_url'] = f"/static/{book['cover_image_url']}"

        return jsonify({
            'success': True,
            'books': books
        })
    except Exception as e:
        logger.error(f"Error fetching books: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    """Get book details"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # Don't return full text in API response (too large)
        book_data = {k: v for k, v in book.items() if k != 'full_text'}

        # Convert cover image path to URL for frontend
        if book_data.get('cover_image_url') and not book_data['cover_image_url'].startswith('http'):
            # It's a local path, prepend /static/
            book_data['cover_image_url'] = f"/static/{book_data['cover_image_url']}"

        return jsonify({
            'success': True,
            'book': book_data
        })
    except Exception as e:
        logger.error(f"Error fetching book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/summary/<summary_type>', methods=['GET'])
def get_summary(book_id, summary_type):
    """Get summary for a book"""
    try:
        # Validate summary type
        if summary_type not in ['concise', 'medium', 'comprehensive', 'full']:
            return jsonify({
                'success': False,
                'error': 'Invalid summary type. Must be: concise, medium, comprehensive, or full'
            }), 400

        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # For full-length view, use comprehensive summary with chapter text
        if summary_type == 'full':
            summary = db.get_summary(book_id, 'comprehensive')
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            if not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Full-length view requires comprehensive summary. Please generate summaries first.'
                }), 404

            # Check if chapters have text (for backwards compatibility)
            if chapters and not chapters[0].get('chapter_text'):
                return jsonify({
                    'success': False,
                    'error': 'Chapter text not available. Please regenerate summaries to include full text.'
                }), 404

            # Prepare book data with cover image path conversion
            book_data = {
                'id': book['id'],
                'title': book['title'],
                'author': book['author']
            }

            # Add cover image if available
            if book.get('cover_image_url'):
                cover_url = book['cover_image_url']
                if not cover_url.startswith('http'):
                    # It's a local path, prepend /static/
                    cover_url = f"/static/{cover_url}"
                book_data['cover_image_url'] = cover_url

            # Check if audio exists for the summary
            has_audio = False
            if summary and summary.get('id'):
                has_audio = db.has_audio_for_summary(summary['id'])

            # Add has_audio flag to each chapter
            for chapter in chapters:
                if chapter.get('id'):
                    chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
                else:
                    chapter['has_audio'] = False

            response_data = {
                'success': True,
                'book': book_data,
                'summary': summary,
                'summary_type': 'full',
                'has_audio': has_audio,
                'chapters': chapters
            }

            return jsonify(response_data)

        # For other summary types
        summary = db.get_summary(book_id, summary_type)

        # For comprehensive summary, also get chapters
        chapters = None
        if summary_type == 'comprehensive':
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            # This handles the case where chapters are still being generated
            if not summary and not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Summary not found. Please generate summaries first.'
                }), 404

        # For other summary types (concise, medium), require the summary
        if not summary and summary_type != 'comprehensive':
            return jsonify({
                'success': False,
                'error': 'Summary not found. Please generate summaries first.'
            }), 404

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        # Check if audio exists for this summary
        has_audio = False
        if summary and summary.get('id'):
            has_audio = db.has_audio_for_summary(summary['id'])

        response_data = {
            'success': True,
            'book': book_data,
            'summary': summary,
            'summary_type': summary_type,
            'has_audio': has_audio
        }

        if chapters:
            # Add has_audio flag to each chapter
            for chapter in chapters:
                if chapter.get('id'):
                    chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
                else:
                    chapter['has_audio'] = False
            response_data['chapters'] = chapters

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error fetching summary for book {book_id}, type {summary_type}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/chapters', methods=['GET'])
def get_chapters(book_id):
    """Get chapter metadata only (optimized for chapter list display)"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # Get hierarchical book structure with metadata only (no full text/summaries)
        book_structure = db.get_book_structure_metadata(book_id)

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        return jsonify({
            'success': True,
            'book': book_data,
            'has_sections': book_structure['has_sections'],
            'sections': book_structure['sections']
        })

    except Exception as e:
        logger.error(f"Error fetching chapters for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/chapters/<int:chapter_number>', methods=['GET'])
def get_chapter_detail(book_id, chapter_number):
    """Get full details for a specific chapter (summary and full text)"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        chapter = db.get_chapter(book_id, chapter_number)
        if not chapter:
            return jsonify({
                'success': False,
                'error': 'Chapter not found'
            }), 404

        # Check if audio exists for this chapter
        if chapter.get('id'):
            chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
        else:
            chapter['has_audio'] = False

        return jsonify({
            'success': True,
            'chapter': chapter
        })

    except Exception as e:
        logger.error(f"Error fetching chapter {chapter_number} for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/summary-configs', methods=['GET'])
def get_summary_configs():
    """Get available summary configurations"""
    return jsonify({
        'success': True,
        'configs': config.SUMMARY_CONFIGS
    })


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    try:
        categories = db.get_all_categories()
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """Get a specific category"""
    try:
        category = db.get_category(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        return jsonify({
            'success': True,
            'category': category
        })
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories/<int:category_id>/books', methods=['GET'])
def get_books_by_category(category_id):
    """Get all books for a specific category"""
    try:
        category = db.get_category(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        books = db.get_books_by_category(category_id)

        # Convert cover image paths to URLs for frontend
        for book in books:
            if book.get('cover_image_url') and not book['cover_image_url'].startswith('http'):
                book['cover_image_url'] = f"/static/{book['cover_image_url']}"

        return jsonify({
            'success': True,
            'category': category,
            'books': books
        })
    except Exception as e:
        logger.error(f"Error fetching books for category {category_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/categories', methods=['GET'])
def get_book_categories(book_id):
    """Get all categories for a specific book"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        categories = db.get_book_categories(book_id)

        return jsonify({
            'success': True,
            'book_id': book_id,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error fetching categories for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/covers/<path:filename>')
def serve_cover(filename):
    """Serve cover images"""
    covers_dir = os.path.join(app.static_folder, 'covers')
    return send_from_directory(covers_dir, filename)


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


def ensure_directories():
    """Ensure data directories exist"""
    config.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    config.SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    config.TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.COVERS_DIR.mkdir(parents=True, exist_ok=True)
