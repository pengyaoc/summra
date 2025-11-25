# Production version of app.py (TTS disabled)
import os
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
import sys

# Add backend directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import config
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
CORS(app)

# Initialize database
db = models.Database()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/books')
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

@app.route('/api/books/<int:book_id>')
def get_book(book_id):
    """Get a specific book"""
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

@app.route('/api/books/<int:book_id>/summary/<summary_type>')
def get_summary(book_id, summary_type):
    """Get a summary for a book"""
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

        summary = db.get_summary(book_id, summary_type)
        if not summary:
            return jsonify({
                'success': False,
                'error': f'No {summary_type} summary found for this book'
            }), 404

        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        logger.error(f"Error fetching summary for book {book_id}, type {summary_type}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/books/<int:book_id>/chapters')
def get_chapters(book_id):
    """Get all chapters for a book"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        chapters = db.get_chapters(book_id)

        return jsonify({
            'success': True,
            'chapters': chapters
        })
    except Exception as e:
        logger.error(f"Error fetching chapters for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/summary-configs')
def get_summary_configs():
    """Get summary configuration information"""
    return jsonify({
        'success': True,
        'configs': config.SUMMARY_CONFIGS
    })

@app.route('/covers/<path:filename>')
def serve_cover(filename):
    """Serve cover images"""
    covers_dir = os.path.join(app.static_folder, 'covers')
    return send_from_directory(covers_dir, filename)

@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """TTS disabled in production - return error"""
    return jsonify({
        'success': False,
        'error': 'TTS generation is disabled in production. Audio files are pre-generated.',
        'message': 'Please contact administrator if audio is missing.'
    }), 501

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # This is only for development
    # In production, use: gunicorn -c gunicorn_config.py backend.app_prod:app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
