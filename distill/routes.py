"""Distill's own routes. The reader API, progress and sign-in come from the
shared platform; this blueprint holds the pages (Task 8) and the image route."""
from flask import Blueprint, abort, current_app, make_response, request

from shared.auth.pchauth.flask_adapter import login_required

bp = Blueprint('distill', __name__)


@bp.route('/books/<slug>/images/<name>')
@login_required
def book_image(slug, name):
    db = current_app.config['CONTENT_DB']
    book = db.get_book_by_slug(slug)
    image = db.get_image(book['id'], name) if book else None
    if not image:
        abort(404)
    mime, data = image
    response = make_response(data)
    response.mimetype = mime
    response.headers['Cache-Control'] = 'private, max-age=3600'
    response.add_etag()
    return response.make_conditional(request)
