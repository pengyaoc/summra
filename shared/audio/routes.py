"""The audio API, shared by every content app. Same URLs in each; the app supplies access rules."""
from flask import Blueprint, abort, jsonify, request, send_file, url_for

from shared.audio.store import DEFAULT_MODE


def audio_blueprint(get_db, access_check, audio_mode=lambda: DEFAULT_MODE):
    """`access_check` decorates each route; `audio_mode()` is the mode when ?mode= is absent."""
    bp = Blueprint('shared_audio', __name__)

    def recordings(slug):
        book = get_db().get_book_by_slug(slug)
        if not book:
            abort(404)
        mode = request.args.get('mode') or audio_mode()
        return book, mode, get_db().book_audio(book['id'], mode)

    @bp.route('/books/<slug>/audio/<int:chapter_id>.m4a')
    @access_check
    def chapter_audio(slug, chapter_id):
        _, _, chapters = recordings(slug)
        item = next((c for c in chapters if c['chapter_id'] == chapter_id), None)
        if not item:
            abort(404)
        key = item['deploy_key'] or item['storage_key']  # Opus; an older chapter's AAC until converted
        response = send_file(get_db().media.path(key), mimetype='audio/mp4', conditional=True, etag=key, max_age=0)
        # The URL survives a re-render; the ETag (the storage key) is what changes.
        response.headers['Cache-Control'] = 'private, no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @bp.route('/api/books/<slug>/audio')
    @access_check
    def book_audio_api(slug):
        book, mode, chapters = recordings(slug)
        query = {} if mode == audio_mode() else {'mode': mode}
        return jsonify({'book_id': book['id'], 'chapters': [{
            'chapter_id': c['chapter_id'], 'ordinal': c['ordinal'], 'title': c['title'],
            'url': url_for('shared_audio.chapter_audio', slug=slug, chapter_id=c['chapter_id'], **query),
            'duration_ms': c['duration_ms'], 'timings': c['timings'],
        } for c in chapters]})

    return bp
