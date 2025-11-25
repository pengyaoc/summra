# Production version of app.py (TTS disabled)
import os
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
from backend.models import init_db, Book, Summary, Chapter
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
init_db()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/books')
def get_books():
    """Get all books"""
    try:
        books = Book.get_all()
        return jsonify([{
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'word_count': book.word_count,
            'cover_image_url': book.cover_image_url,
            'gutenberg_id': book.gutenberg_id
        } for book in books])
    except Exception as e:
        logger.error(f"Error fetching books: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books/<int:book_id>')
def get_book(book_id):
    """Get a specific book"""
    try:
        book = Book.get_by_id(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404

        return jsonify({
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'word_count': book.word_count,
            'cover_image_url': book.cover_image_url,
            'gutenberg_id': book.gutenberg_id
        })
    except Exception as e:
        logger.error(f"Error fetching book {book_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books/<int:book_id>/summary/<summary_type>')
def get_summary(book_id, summary_type):
    """Get a summary for a book"""
    try:
        if summary_type not in ['concise', 'medium', 'comprehensive']:
            return jsonify({'error': 'Invalid summary type'}), 400

        summary = Summary.get_by_book_and_type(book_id, summary_type)
        if not summary:
            return jsonify({'error': 'Summary not found'}), 404

        return jsonify({
            'id': summary.id,
            'book_id': summary.book_id,
            'summary_type': summary.summary_type,
            'content': summary.content,
            'word_count': summary.word_count
        })
    except Exception as e:
        logger.error(f"Error fetching summary for book {book_id}, type {summary_type}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books/<int:book_id>/chapters')
def get_chapters(book_id):
    """Get all chapters for a book"""
    try:
        chapters = Chapter.get_by_book(book_id)
        return jsonify([{
            'id': chapter.id,
            'book_id': chapter.book_id,
            'chapter_number': chapter.chapter_number,
            'chapter_title': chapter.chapter_title,
            'summary': chapter.summary,
            'word_count': chapter.word_count
        } for chapter in chapters])
    except Exception as e:
        logger.error(f"Error fetching chapters for book {book_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary-configs')
def get_summary_configs():
    """Get summary configuration information"""
    from backend.config import SUMMARY_CONFIGS
    return jsonify(SUMMARY_CONFIGS)

@app.route('/covers/<path:filename>')
def serve_cover(filename):
    """Serve cover images"""
    import os
    covers_dir = os.path.join(app.static_folder, 'covers')
    return send_from_directory(covers_dir, filename)

@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """TTS disabled in production - return error"""
    return jsonify({
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
