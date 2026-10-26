"""Distill's own routes: the pages (library, book, reader) and the private
image route. The reader API, progress and sign-in come from the shared platform."""
from flask import Blueprint, abort, current_app, g, make_response, render_template, request

from shared.auth.pchauth.flask_adapter import login_required
from shared.progress.routes import library_cards

bp = Blueprint('distill', __name__)


def progress_label(card, chapter_count) -> str:
    """Where a reader is in a book: 'Overview', 'Chapter 3 of 12', or '' with no place saved.
    The count excludes the Overview (chapter_number 0)."""
    chapter = (card or {}).get('current_chapter')
    if not chapter:
        return ''
    if chapter['chapter_number'] == 0:
        return 'Overview'
    return f"Chapter {chapter['chapter_number']} of {chapter_count}"


def _db():
    return current_app.config['CONTENT_DB']


def _not_found_page():
    return render_template('not_found.html'), 404


def _card_for(book_id):
    """The signed-in reader's library card for one book, if they have started it."""
    cards = library_cards(g.user_id)
    return next((c for c in cards['continue_reading'] + cards['finished'] if c['id'] == book_id), None)


def newest_first(db):
    return sorted(db.list_books(), key=lambda b: (b['imported_at'] or '', b['id']), reverse=True)


def reading_cards(db, user_id, books):
    """The reader's books in progress, as library cards whose location line is `progress_label`."""
    by_id = {b['id']: b for b in books}
    reading = []
    for card in library_cards(user_id)['continue_reading']:
        book = by_id.get(card['id'])
        if not book:
            continue
        label = progress_label(card, db.count_chapters(book['id']))
        # The shared card macro prints current_chapter.chapter_title as its location line.
        reading.append({**card, 'cover_image': book['cover_image'],
                        'current_chapter': {'chapter_title': label} if label else None})
    return reading


# Editorial categories for the original imported collection, whose format predates
# category metadata. New imports can supply their own `categories` list.
_LEGACY_CATEGORIES = {
    'Personal growth': 'atomic-habits getting-things-done hbr-10-must-reads-managing-yourself the-one-thing poor-richards-almanack',
    'Business & leadership': 'the-goal blue-ocean-strategy built-to-last business-adventures first-break-all-the-rules good-to-great measure-what-matters power-pfeffer the-managers-path winning-jack-welch',
    'Money & investing': 'buy-this-not-that howard-marks-memos-complete-collection poor-charlies-almanack the-intelligent-investor',
    'History & biography': 'guns-germs-and-steel quanqiutongshi-zhangjie-zongjie better-angels-of-our-nature born-in-blackness energy-and-civilization surely-youre-joking-mr-feynman team-of-rivals the-box the-glory-and-the-dream titan-rockefeller',
    'Science & technology': 'a-thousand-brains abundance brave-new-words cell-song growth-smil how-the-world-really-works-smil invention-and-innovation life-3-0 numbers-dont-lie phantoms-in-the-brain superintelligence the-tell-tale-brain the-vital-question',
    'Society & economics': 'abundance-klein-thompson power-to-compete wealth-of-nations why-nations-fail why-were-polarized',
    'Psychology & philosophy': 'antifragile mans-search-for-meaning thinking-fast-and-slow',
    'Nature & climate': 'how-to-avoid-a-climate-disaster how-to-feed-the-world silent-spring the-sixth-extinction',
}


def book_categories(book):
    return book.get('categories') or [category for category, slugs in _LEGACY_CATEGORIES.items()
                                      if book['slug'] in slugs.split()] or ['Uncategorized']


@bp.route('/')
@login_required
def library():
    db = _db()
    books = newest_first(db)
    categories = sorted({category for book in books for category in book_categories(book)})
    query = request.args.get('q', '').strip()
    language = request.args.get('lang', '')
    language = language if language in ('zh', 'en') else ''
    category = request.args.get('category', '')
    filtered = [book for book in books
                if (not language or book['lang'] == language)
                and (not category or category in book_categories(book))]
    shown = [book for book in filtered
             if not query or query.casefold() in f"{book['title']} {book.get('author') or ''}".casefold()]
    # Only searchable metadata is embedded, never chapter content. Keep the whole
    # selected shelf available when editing a previously submitted search.
    search_catalog = [{key: book.get(key) or '' for key in ('title', 'author', 'slug')}
                      for book in filtered]
    return render_template('library.html', reading=reading_cards(db, g.user_id, books), books=shown,
                           total_books=len(books), categories=categories, query=query,
                           language=language, category=category, book_categories=book_categories, search_catalog=search_catalog)


@bp.route('/books/<slug>')
@login_required
def book_page(slug):
    book = _db().get_book_by_slug(slug)
    if not book:
        return _not_found_page()
    outline = _db().get_chapter_outline(book['id'])
    card = _card_for(book['id'])
    toc = []  # [(part_title, [chapter, ...])] in reading order
    for chapter in outline:
        if not toc or toc[-1][0] != chapter['part_title']:
            toc.append((chapter['part_title'], []))
        toc[-1][1].append(chapter)
    return render_template(
        'book.html', book=book, toc=toc, card=card,
        label=progress_label(card, _db().count_chapters(book['id'])),
        percent=card['furthest_percentage'] if card else 0)


@bp.route('/books/<slug>/read')
@login_required
def reader(slug):
    book = _db().get_book_by_slug(slug)
    return render_template('reader.html', book=book) if book else _not_found_page()


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
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.add_etag()
    return response.make_conditional(request)
