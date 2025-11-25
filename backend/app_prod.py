# Production version of app.py (TTS disabled)
import os
from flask import Flask, jsonify, render_template, send_from_directory, request
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

            response_data = {
                'success': True,
                'book': book_data,
                'summary': summary,
                'summary_type': 'full',
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

        response_data = {
            'success': True,
            'book': book_data,
            'summary': summary,
            'summary_type': summary_type
        }

        if chapters:
            response_data['chapters'] = chapters

        return jsonify(response_data)

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
    """Check for pre-generated TTS audio (generation disabled in production)"""
    try:
        data = request.json
        audio_id = data.get('id')  # Unique identifier for caching

        if not audio_id:
            return jsonify({
                'success': False,
                'error': 'No audio ID provided'
            }), 400

        # Check for cached audio with prioritization: Gemini > VITS > Legacy complete
        # Priority 1: Check for Gemini TTS (pre-generated offline)
        gemini_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.wav"
        if gemini_audio_path.exists():
            logger.info(f"Using Gemini TTS audio: {gemini_audio_path}")
            relative_path = str(gemini_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
            return jsonify({
                'success': True,
                'audio_url': f'/static/{relative_path}',
                'streaming': False,
                'cached': True,
                'provider': 'gemini'
            })

        # Priority 2: Check for VITS TTS (previously generated)
        vits_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_vits.wav"
        if vits_audio_path.exists():
            logger.info(f"Using VITS TTS audio: {vits_audio_path}")
            relative_path = str(vits_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
            return jsonify({
                'success': True,
                'audio_url': f'/static/{relative_path}',
                'streaming': False,
                'cached': True,
                'provider': 'vits'
            })

        # Priority 3: Check for legacy concatenated audio (backward compatibility)
        cached_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav"
        if cached_audio_path.exists():
            logger.info(f"Using legacy cached audio: {cached_audio_path}")
            relative_path = str(cached_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
            return jsonify({
                'success': True,
                'audio_url': f'/static/{relative_path}',
                'streaming': False,
                'cached': True,
                'provider': 'vits_legacy'
            })

        # No pre-generated audio found
        return jsonify({
            'success': False,
            'error': 'TTS generation is disabled in production. Audio files are pre-generated.',
            'message': 'Please contact administrator if audio is missing.'
        }), 404

    except Exception as e:
        logger.error(f"Error checking for pre-generated audio: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # This is only for development
    # In production, use: gunicorn -c gunicorn_config.py backend.app_prod:app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
