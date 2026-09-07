"""Continuous-reader progress and Library API routes."""

import logging

from flask import Blueprint, g, jsonify, request

try:
    from .pchauth.flask_adapter import login_required
except ImportError:
    from backend.pchauth.flask_adapter import login_required


user_db = None
content_db = None
logger = logging.getLogger(__name__)
progress_bp = Blueprint('progress', __name__, url_prefix='/api')


def _marker_for(payload, key):
    marker = payload.get(key)
    return marker if isinstance(marker, dict) else None


def _validate_book(book_id):
    return isinstance(book_id, int) and content_db and content_db.get_book(book_id)


@progress_bp.route('/progress/v2/mutations', methods=['POST'])
@login_required
def apply_progress_mutation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'JSON mutation required'}), 400
    book_id = payload.get('book_id')
    if not _validate_book(book_id):
        return jsonify({'error': 'Unknown book'}), 400

    current_marker = content_db.resolve_reader_marker(book_id, _marker_for(payload, 'current_marker'))
    if not current_marker:
        return jsonify({'error': 'Invalid current marker'}), 400
    if current_marker['mode'] != payload.get('mode'):
        return jsonify({'error': 'Marker mode does not match mutation mode'}), 400

    furthest_input = _marker_for(payload, 'qualified_furthest_marker')
    furthest_marker = content_db.resolve_reader_marker(book_id, furthest_input) if furthest_input else None
    if furthest_input and not furthest_marker:
        return jsonify({'error': 'Invalid furthest marker'}), 400
    if furthest_marker and furthest_marker['mode'] != payload.get('mode'):
        return jsonify({'error': 'Furthest marker mode does not match mutation mode'}), 400

    manifest = content_db.get_reader_manifest(book_id)
    mode_manifest = next((item for item in manifest['modes'] if item['mode'] == payload.get('mode')), None)
    completion_allowed = bool(
        payload.get('event_cause') == 'completion'
        and payload.get('terminal_dwell_ms', 0) >= 2000
        and payload.get('sequential_terminal_entry') is True
        and mode_manifest
        and mode_manifest['terminal_paragraph_id'] == current_marker['paragraph_id']
    )
    try:
        result = user_db.apply_mutation(
            g.user_id, payload, current_marker, furthest_marker, completion_allowed=completion_allowed,
        )
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    status = 409 if result['result'] == 'conflict' else 200
    return jsonify({'success': True, **result}), status


@progress_bp.route('/progress/v2/books/<int:book_id>', methods=['GET'])
@login_required
def get_progress_v2(book_id):
    if not _validate_book(book_id):
        return jsonify({'error': 'Unknown book'}), 404
    return jsonify({'success': True, 'projection': user_db.get_book_projection(g.user_id, book_id)})


@progress_bp.route('/library', methods=['GET'])
@login_required
def get_library():
    """Return denormalized cards without per-book client requests."""
    states = user_db.get_library_projection(g.user_id)
    if not states:
        return jsonify({'success': True, 'continue_reading': [], 'finished': []})

    ids = [state['book_id'] for state in states]
    placeholders = ', '.join('?' for _ in ids)
    conn = content_db.get_connection()
    try:
        books = {
            row['id']: dict(row)
            for row in conn.execute(
                f'''SELECT id, slug, title, author, cover_image_url FROM books WHERE id IN ({placeholders})''', ids
            ).fetchall()
        }
        chapter_ids = {
            state['last_mode_state']['current_marker']['chapter_id']
            for state in states
            if state.get('last_mode_state') and state['last_mode_state'].get('current_marker')
        }
        chapters = {}
        if chapter_ids:
            chapter_placeholders = ', '.join('?' for _ in chapter_ids)
            chapters = {
                row['id']: dict(row)
                for row in conn.execute(
                    f'''SELECT id, chapter_number, chapter_title FROM chapters WHERE id IN ({chapter_placeholders})''',
                    list(chapter_ids),
                ).fetchall()
            }
    finally:
        conn.close()

    cards = {'continue_reading': [], 'finished': []}
    for state in states:
        book = books.get(state['book_id'])
        if not book:
            continue
        mode_state = state.get('last_mode_state')
        marker = mode_state.get('furthest_marker') if mode_state else None
        percentage = 0
        if marker and mode_state:
            manifest = content_db.get_reader_manifest(state['book_id'])
            mode = next((item for item in manifest['modes'] if item['mode'] == state['last_mode']), None)
            if mode and mode['total_word_count']:
                percentage = min(99, round(marker['word_position'] * 100 / mode['total_word_count']))
        if state['status'] == 'finished':
            percentage = 100
        current = mode_state.get('current_marker') if mode_state else None
        chapter = chapters.get(current['chapter_id']) if current else None
        card = {
            **book,
            'status': state['status'],
            'last_mode': state['last_mode'],
            'furthest_percentage': percentage,
            'current_chapter': chapter,
            'last_meaningful_read_at': state['last_meaningful_read_at'],
            'finished_at': state['finished_at'],
        }
        cards['finished' if state['status'] == 'finished' else 'continue_reading'].append(card)
    return jsonify({'success': True, **cards})


# Retained only as a harmless auth-route probe used by existing integration
# coverage. Reader code no longer calls this v1 endpoint.
@progress_bp.route('/progress/all', methods=['GET'])
@login_required
def retired_progress_all():
    return jsonify({'success': True, 'progress': []})
