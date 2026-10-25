"""Record a Kindle reader's page as a web-reader progress mutation.

The Kindle script posts only a position; the server fills in what the web
client tracks itself (marker, revision, device), so the ES5 script stays
small. The Kindle is the device being read, so it always writes on top of the
latest revision.
"""
import time
import uuid


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
