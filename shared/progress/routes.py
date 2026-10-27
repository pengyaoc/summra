"""Continuous-reader progress and Library API routes.

`user_db` (shared.auth.user_models.UserDatabase) and `content_db` are set by
the app. `content_db` is duck-typed; the surface used here is:

    get_book(book_id)
    resolve_reader_marker(book_id, marker)
    get_reader_manifest(book_id)
    library_books(book_ids)      # {book_id: {id, slug, title, author, cover_image_url}}
    chapter_titles(chapter_ids)  # {chapter_id: {id, chapter_number, chapter_title}}
    library_word_totals(book_ids)  # optional batched {book_id: {mode: word_count}}
"""

import logging
import uuid

from flask import Blueprint, current_app, g, jsonify, request

from shared.auth.pchauth.flask_adapter import login_required


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
    config = current_app.extensions.get('reader_config')
    completion_allowed = (config is None or config.features.automatic_completion) and bool(
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


@progress_bp.route('/progress/v2/books/<int:book_id>/status', methods=['POST'])
@login_required
def set_book_status(book_id):
    """Explicit book-level read/unread action; preserve the reader's place."""
    payload = request.get_json(silent=True)
    if not _validate_book(book_id):
        return jsonify({'error': 'Unknown book'}), 404
    if not isinstance(payload, dict) or payload.get('status') not in ('read', 'reading'):
        return jsonify({'error': 'Status must be read or reading'}), 400
    state = user_db.get_book_projection(g.user_id, book_id)
    mode_state = next((m for m in state['modes'] if m['mode'] == (state['book'] or {}).get('last_mode')), None)
    mode = mode_state['mode'] if mode_state else None
    marker = content_db.resolve_reader_marker(book_id, {**mode_state['current_marker'], 'mode': mode}) if mode_state and mode_state.get('current_marker') else None
    if not marker:
        manifest = content_db.get_reader_manifest(book_id)
        config = current_app.extensions.get('reader_config')
        preferred = config.default_modes if config else ('summary', 'plain', 'original')
        available = [m for m in manifest['modes'] if m['first_segment_id']]
        selected = next((m for key in preferred for m in available if m['mode'] == key), None)
        if not selected:
            return jsonify({'error': 'Book has no readable content'}), 400
        mode = selected['mode']
        segment = content_db.get_reader_segment(book_id, selected['first_segment_id'], mode)
        marker = content_db.resolve_reader_marker(book_id, {'mode': mode, 'paragraph_id': segment['units'][0]['id']})
        mode_state = next((m for m in state['modes'] if m['mode'] == mode), None)
    identity = uuid.uuid4().hex
    mutation = {'book_id': book_id, 'mode': mode, 'mutation_id': identity,
                'device_id': 'book-status-' + identity, 'device_sequence': 1,
                'base_revision': mode_state['revision'] if mode_state else 0,
                'event_cause': 'manual_finish' if payload['status'] == 'read' else 'manual_unfinish'}
    result = user_db.apply_mutation(g.user_id, mutation, marker, None)
    return jsonify({'success': True, **result}), 409 if result['result'] == 'conflict' else 200


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
    return jsonify({'success': True, **library_cards(g.user_id)})


def library_cards(user_id, book_id=None):
    """A reader's Library cards, {'continue_reading': [...], 'finished': [...]}.
    Shared by /api/library and the home page, which renders Continue reading
    into the first HTML so it doesn't pop in after the page loads. A book_id
    scopes a book page's lookup instead of processing the reader's whole shelf.
    """
    states = []
    if user_db and user_id is not None:
        states = (user_db.get_library_projection(user_id, book_id=book_id) if book_id is not None
                  else user_db.get_library_projection(user_id))
    if not states:
        return {'continue_reading': [], 'finished': []}

    ids = [state['book_id'] for state in states]
    books = content_db.library_books(ids)
    chapter_ids = {
        state['last_mode_state']['current_marker']['chapter_id']
        for state in states
        if state.get('last_mode_state') and state['last_mode_state'].get('current_marker')
    }
    chapters = content_db.chapter_titles(list(chapter_ids)) if chapter_ids else {}

    cards = {'continue_reading': [], 'finished': []}
    progress_ids = [s['book_id'] for s in states if s['book_id'] in books and s['status'] != 'finished'
                    and s.get('last_mode_state') and s['last_mode_state'].get('furthest_marker')]
    totals_hook = getattr(content_db, 'library_word_totals', None)
    totals = totals_hook(progress_ids) if totals_hook and progress_ids else {}
    for state in states:
        book = books.get(state['book_id'])
        if not book:
            continue
        mode_state = state.get('last_mode_state')
        marker = mode_state.get('furthest_marker') if mode_state else None
        percentage = 0
        if marker and mode_state and state['status'] != 'finished':
            if totals_hook:
                word_count = totals.get(state['book_id'], {}).get(state['last_mode'], 0)
            else:
                manifest = content_db.get_reader_manifest(state['book_id'])
                mode = next((item for item in manifest['modes'] if item['mode'] == state['last_mode']), None)
                word_count = mode['total_word_count'] if mode else 0
            if word_count:
                percentage = min(99, round(marker['word_position'] * 100 / word_count))
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
    return cards


@progress_bp.route('/hints/<hint_key>/seen', methods=['POST'])
@login_required
def mark_hint_seen(hint_key):
    """Remember that this account has seen a one-time hint (any device)."""
    if hint_key not in user_db.valid_hints:
        return jsonify({'error': 'Unknown hint'}), 400
    user_db.mark_hint_seen(g.user_id, hint_key)
    return jsonify({'success': True})


# Retained only as a harmless auth-route probe used by existing integration
# coverage. Reader code no longer calls this v1 endpoint.
@progress_bp.route('/progress/all', methods=['GET'])
@login_required
def retired_progress_all():
    return jsonify({'success': True, 'progress': []})
