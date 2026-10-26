"""Record a Kindle reader's page as a web-reader progress mutation.

The Kindle script posts only a position; the server fills in what the web
client tracks itself (marker, revision, device), so the ES5 script stays
small. The Kindle is the device being read, so it always writes on top of the
latest revision.
"""
import time
import uuid

from flask import jsonify, request


def record_page(user_db, content_db, user_id, book_id, mode, paragraph_id, quote, forward, seconds, finished):
    """Apply one page turn. `paragraph_id` is the reader-index unit id,
    `quote` the unit's text (or None), `forward` whether the reader arrived
    by turning forward, `seconds` the time on the previous page, `finished`
    whether this is the book's last page. Returns (JSON payload, status)."""
    marker = content_db.resolve_reader_marker(book_id, {
        'mode': mode, 'paragraph_id': paragraph_id, 'offset': 0,
    })
    if not marker:
        return {'error': 'Unknown paragraph'}, 400
    if quote is not None:
        marker['quote'] = quote

    finished = finished and forward
    terminal = next((m['terminal_paragraph_id'] for m in content_db.get_reader_manifest(book_id)['modes']
                     if m['mode'] == mode), None)
    state = next((m for m in user_db.get_book_projection(user_id, book_id)['modes']
                  if m['mode'] == mode), None)
    try:
        seconds = max(0, min(60, int(seconds or 0)))
    except (TypeError, ValueError):
        seconds = 0
    payload = {
        'mutation_id': f'kindle_{uuid.uuid4().hex}', 'device_id': 'kindle',
        'device_sequence': time.time_ns() // 1000, 'book_id': book_id, 'mode': mode,
        'event_cause': 'completion' if finished else 'page_turn',
        'active_seconds_delta': seconds, 'sequential_boundaries_delta': 1 if forward else 0,
        'base_revision': state['revision'] if state else 0,
    }
    result = user_db.apply_mutation(
        user_id, payload, marker, marker if forward else None,
        completion_allowed=finished and terminal == marker['paragraph_id'],
    )
    return {'success': True, 'result': result['result']}, 409 if result['result'] == 'conflict' else 200


def save_progress(config, user_db, content_db, user_id, position):
    """The body of POST /api/kindle/progress, for any app. JSON: book_id,
    ch (the app's chapter key), p (unit index), text (a configured Kindle
    text mode), forward (arrived by turning forward), seconds (time on the
    previous page), finished (on the book's last page).

    `position(content_db, book_id, ch, p, text)` is the app's hook: it returns
    (reader-index unit id, quote or None), or None for an unknown book or
    chapter. Returns (response, status) for the route to hand back."""
    if not config.features.kindle or user_db is None:
        return jsonify({'error': 'Not found'}), 404
    if user_id is None:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json(silent=True) or {}
    book_id, number, index, text = data.get('book_id'), data.get('ch'), data.get('p'), data.get('text')
    if not (isinstance(book_id, int) and isinstance(number, int) and isinstance(index, int)
            and index >= 0 and text in [mode for mode, _ in config.kindle.text_modes]):
        return jsonify({'error': 'Invalid position'}), 400
    found = position(content_db, book_id, number, index, text)
    if not found:
        return jsonify({'error': 'Unknown chapter'}), 400
    unit_id, quote = found
    payload, status = record_page(
        user_db, content_db, user_id, book_id, text, unit_id, quote,
        data.get('forward') is True, data.get('seconds'), data.get('finished') is True)
    return jsonify(payload), status
