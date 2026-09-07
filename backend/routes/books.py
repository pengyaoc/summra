"""API routes for books, chapters, and summaries.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import logging

from flask import Blueprint, jsonify, make_response, request

from backend.routes import common

logger = logging.getLogger(__name__)

bp = Blueprint('books', __name__)


@bp.route('/api/reader/books/<int:book_id>/manifest', methods=['GET'])
def get_reader_manifest(book_id):
    """Metadata-only entry point for the continuous reader."""
    db = common.db
    try:
        manifest = db.get_reader_manifest(book_id)
        response = make_response(jsonify({'success': True, 'manifest': manifest}))
        response.set_etag(manifest['etag'])
        response.headers['Cache-Control'] = 'public, max-age=300, must-revalidate'
        return response.make_conditional(request)
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 404
    except Exception:
        logger.exception('Error building reader manifest for book %s', book_id)
        return jsonify({'success': False, 'error': 'Unable to load reader metadata'}), 500


@bp.route('/api/reader/books/<int:book_id>/segments/<segment_id>', methods=['GET'])
def get_reader_segment(book_id, segment_id):
    """Return one bounded, immutable reader segment for a mode."""
    mode = request.args.get('mode', '')
    db = common.db
    try:
        segment = db.get_reader_segment(book_id, segment_id, mode)
        if not segment:
            return jsonify({'success': False, 'error': 'Segment not found'}), 404
        response = make_response(jsonify({'success': True, 'segment': segment}))
        response.set_etag(segment['etag'])
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response.make_conditional(request)
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 404
    except Exception:
        logger.exception('Error loading reader segment %s for book %s', segment_id, book_id)
        return jsonify({'success': False, 'error': 'Unable to load reader segment'}), 500


@bp.route('/api/reader/books/<int:book_id>/map', methods=['POST'])
def map_reader_marker(book_id):
    """Map a marker across modes without treating it as progress."""
    payload = request.get_json(silent=True) or {}
    marker = payload.get('marker')
    target_mode = payload.get('target_mode')
    if not isinstance(marker, dict):
        return jsonify({'success': False, 'error': 'A marker is required'}), 400
    try:
        mapped = common.db.map_reader_marker(book_id, marker, target_mode)
        if not mapped:
            return jsonify({'success': False, 'error': 'No aligned destination is available'}), 404
        return jsonify({'success': True, 'marker': mapped})
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 404
    except Exception:
        logger.exception('Error mapping reader marker for book %s', book_id)
        return jsonify({'success': False, 'error': 'Unable to map reader marker'}), 500


@bp.route('/api/reader/books/<int:book_id>/recover', methods=['POST'])
def recover_reader_marker(book_id):
    """Resolve a marker from an older content version without writing state."""
    payload = request.get_json(silent=True) or {}
    marker = payload.get('marker')
    if not isinstance(marker, dict):
        return jsonify({'success': False, 'error': 'A marker is required'}), 400
    try:
        recovered = common.db.recover_reader_marker(book_id, marker)
        if not recovered:
            return jsonify({'success': False, 'error': 'Marker could not be recovered'}), 404
        return jsonify({'success': True, 'marker': recovered})
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 404
    except Exception:
        logger.exception('Error recovering reader marker for book %s', book_id)
        return jsonify({'success': False, 'error': 'Unable to recover reader marker'}), 500


@bp.route('/api/books', methods=['GET'])
def get_books():
    """Get all books"""
    db = common.db
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


@bp.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    """Get book details"""
    db = common.db
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


@bp.route('/api/books/<int:book_id>/summary/<summary_type>', methods=['GET'])
def get_summary(book_id, summary_type):
    """Get summary for a book"""
    db = common.db
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


@bp.route('/api/books/<int:book_id>/chapters', methods=['GET'])
def get_chapters(book_id):
    """Get chapter metadata only (optimized for chapter list display)"""
    db = common.db
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
            'sections': book_structure['sections'],
            'has_modern_english': db.book_has_modern_english(book_id)
        })

    except Exception as e:
        logger.error(f"Error fetching chapters for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/books/<int:book_id>/chapters/<int:chapter_number>', methods=['GET'])
def get_chapter_detail(book_id, chapter_number):
    """Get full details for a specific chapter (summary and full text)"""
    db = common.db
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


@bp.route('/api/summary-configs', methods=['GET'])
def get_summary_configs():
    """Get available summary configurations"""
    return jsonify({
        'success': True,
        'configs': common.config.SUMMARY_CONFIGS
    })
