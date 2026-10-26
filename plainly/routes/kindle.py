"""Kindle e-ink mode: when a Kindle's browser asks for the library, a book
page or the reader, serve a lean server-rendered page instead of the SPA.

E-ink screens ghost on scrolling and animation, and the older Kindle browser
(WebKit 531) can't run app.js, so these pages work without JavaScript and
use only an ES5 script (shared/static/js/kindle.js) to turn the reader into tap-to-
turn pages. `?kindle=0` / `?kindle=1` switch the mode by cookie.

The paging, cookies, account line and progress recording are shared
(shared.kindle); this module supplies Plainly's pages and its text versions.

Signed-in readers share reading progress with the web reader: the reader
posts its page to /api/kindle/progress, which records it as a web-reader
progress mutation, and opening a book resumes from that account state.
"""
import re

from flask import Blueprint, g, request
from markupsafe import Markup, escape

from plainly import models
from plainly.reader_config import PLAINLY_READER
from plainly.routes import common
from plainly.routes.pages import _cover_base
from shared.kindle import pages as kindle_pages
from shared.kindle.pages import (
    cookie_path, font_size, page_number, paginate, register_kindle_pages, url,
)
from shared.kindle.progress import save_progress as shared_save_progress
from shared.progress import routes as progress_routes

bp = Blueprint('kindle', __name__)

LIBRARY_PAGE_SIZE = 7
READING_ON_HOME = 3
CONTENTS_PAGE_SIZE = 8
KINDLE = PLAINLY_READER.kindle
TEXT_MODES = tuple(mode for mode, _ in KINDLE.text_modes)


def _signed_in_user_id():
    """Set per request by pchauth (Apache's trusted header in prod)."""
    return g.get('user_id')


def _account_user_id():
    """The signed-in reader whose progress syncs, or None (signed out, or
    auth turned off by FEATURE_AUTH)."""
    if progress_routes.user_db is None:
        return None
    return _signed_in_user_id()


def _render(template, **context):
    return kindle_pages.render(f'kindle/{template}', progress_routes.user_db, _account_user_id(), **context)


def not_found():
    resp, _, headers = kindle_pages.render(
        'shared/kindle/not_found.html', progress_routes.user_db, _account_user_id())
    return resp, 404, headers


def _saved_position(book_id):
    """(chapter_number, paragraph index, text or None) to resume at: the
    account's position (shared with the web reader) when signed in, else
    this device's cookie."""
    user_id = _account_user_id()
    if user_id is not None:
        return _account_position(user_id, book_id)
    m = re.fullmatch(r'(\d+)\.(\d+)', request.cookies.get(f'kpos_{book_id}', ''))
    return (int(m.group(1)), int(m.group(2)), None) if m else None


def _account_position(user_id, book_id):
    """The account's current position in its last-used reading mode.
    Side by Side shares paragraph ids with both texts and opens as Plain
    English; a Summary position isn't a place in the text."""
    saved = kindle_pages.saved_marker(
        progress_routes.user_db, common.db, user_id, book_id, ('plain', 'original', 'side_by_side'))
    if not saved:
        return None
    chapter_id, ordinal, mode = saved
    number = next((c['chapter_number'] for c in common.db.get_chapter_outline(book_id)
                   if c['id'] == chapter_id), None)
    if number is None:
        return None
    return number, ordinal, 'original' if mode == 'original' else 'plain'


def library_page():
    """Books, filtered by ?show= (plain / all / reading) and ?q=. Signed in,
    home starts with Reading now: the account's books in progress (the web
    Library's Continue reading), with chapter and progress."""
    user_id = _account_user_id()
    reading = progress_routes.library_cards(user_id)['continue_reading'] if user_id is not None else []
    show = request.args.get('show')
    if show not in ('all', 'reading') or (show == 'reading' and user_id is None):
        show = 'plain'
    query = request.args.get('q', '').strip()
    if show == 'reading':
        books = reading
    else:
        books = [b for b in common.db.get_all_books() if b.get('slug')]
        if show == 'plain':
            books = [b for b in books if b.get('has_plain_english')]
        if query:
            needle = query.lower()
            books = [b for b in books if needle in b['title'].lower() or needle in (b['author'] or '').lower()]
    shown, page, pages = paginate(books, LIBRARY_PAGE_SIZE, page_number())
    continue_book = None
    if user_id is None:
        last = request.cookies.get('klast')
        continue_book = common.db.get_book_by_slug(last) if last else None

    def page_url(n):
        return url('/', show=show if show != 'plain' else None, q=query, page=n)

    return _render(
        'library.html',
        books=shown, show=show, query=query, page=page, pages=pages,
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
        continue_book=continue_book,
        reading=shown if show == 'reading' else (reading[:READING_ON_HOME] if page == 1 and not query else []),
        reading_count=len(reading),
    )


def book_page(slug):
    db = common.db
    book = db.get_book_by_slug(slug)
    if not book:
        return not_found()
    outline = db.get_chapter_outline(book['id'])
    shown, page, pages = paginate(outline, CONTENTS_PAGE_SIZE, page_number())
    saved = _saved_position(book['id'])
    first = outline[0]['chapter_number'] if outline else None
    cover = _cover_base(book.get('cover_image_url'))

    def page_url(n):
        return url(f'/books/{slug}', page=n)

    return _render(
        'book.html',
        book=book, chapters=shown, page=page, pages=pages,
        first_chapter=first,
        has_plain=book.get('has_plain_english'),
        saved=saved,
        cover_url=url(f'/static/{cover}.jpg') if cover else None,
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
    )


@bp.app_template_filter('kindle_inline')
def kindle_inline(text):
    """Escape a paragraph and turn *x* / _x_ into italics, as the web
    reader does without marked (shared/static/js/blocks.js formatInline)."""
    html = str(escape(text))
    html = re.sub(r'\*([^\s*](?:[^*\n]*?[^\s*])?)\*', r'<em>\1</em>', html)
    html = re.sub(r'\b_([^_\n]+?)_\b', r'<em>\1</em>', html)
    return Markup(html)


def _same_text(a, b):
    def norm(s):
        return re.sub(r'[\W_]+', ' ', (s or '').lower()).strip()
    return bool(norm(a)) and norm(a) == norm(b)


def chapter_paragraphs(chapter, text, verse):
    """(index, paragraph) pairs. Indexes match between Plain English and the
    original, so the reader can switch versions on the same paragraph. A
    leading paragraph that just repeats the chapter title is left out: the
    page shows the title as its heading."""
    if text == 'plain':
        paragraphs = models.Database._reader_split_paragraphs(chapter.get('modern_english_text'))
    else:
        paragraphs = models.Database._reader_split_paragraphs(chapter.get('chapter_text'), verse=verse)
    pairs = list(enumerate(paragraphs))
    if pairs and _same_text(pairs[0][1], chapter.get('chapter_title')):
        pairs = pairs[1:]
    return pairs


def reader_page(slug, chapter_number=None):
    db = common.db
    book = db.get_book_by_slug(slug)
    if not book:
        return not_found()
    outline = db.get_chapter_outline(book['id'])
    numbers = [c['chapter_number'] for c in outline]
    if not numbers:
        return not_found()

    start = 0
    saved = _saved_position(book['id'])
    if chapter_number is None and 'ch' in request.args:
        if not request.args['ch'].isdigit():
            return not_found()
        chapter_number = int(request.args['ch'])
    if chapter_number is None:
        if saved and saved[0] in numbers:
            chapter_number = saved[0]
        else:
            chapter_number = numbers[0]
    if chapter_number not in numbers:
        return not_found()
    if saved and saved[0] == chapter_number:
        start = saved[1]

    chapter = db.get_chapter(book['id'], chapter_number)
    saved_text = saved[2] if saved and saved[0] == chapter_number else None
    wanted = request.args.get('text') or saved_text or request.cookies.get('ktext') or KINDLE.default_text
    has_plain = bool((chapter.get('modern_english_text') or '').strip())
    text = 'plain' if wanted == 'plain' and has_plain else 'original'
    verse = bool(book.get('is_poetry')) and text == 'original'

    def chars(c):
        return c['plain_chars'] if text == 'plain' and c['plain_chars'] else c['text_chars']

    position = numbers.index(chapter_number)
    prev_number = numbers[position - 1] if position > 0 else None
    next_number = numbers[position + 1] if position + 1 < len(numbers) else None

    def chapter_url(n, version=text):
        return url(f'/books/{slug}/read', ch=n, text=version) if n is not None else None

    return _render(
        'reader.html',
        book=book, chapter=chapter, text=text, verse=verse,
        paragraphs=chapter_paragraphs(chapter, text, verse),
        plain_missing=wanted == 'plain' and not has_plain,
        has_plain=has_plain,
        start=start,
        font_size=font_size(),
        chars_before=sum(chars(c) for c in outline[:position]),
        chapter_chars=chars(outline[position]),
        total_chars=sum(chars(c) for c in outline) or 1,
        prev_url=chapter_url(prev_number),
        next_url=chapter_url(next_number),
        next_title=outline[position + 1]['chapter_title'] if next_number is not None else None,
        text_urls={mode: chapter_url(chapter_number, mode)
                   for mode in TEXT_MODES if mode != 'plain' or has_plain},
        cookie_path=cookie_path(),
        sync_url=url('/api/kindle/progress') if _account_user_id() is not None else None,
    )


def _position(db, book_id, number, index, text):
    """Plainly's side of the shared progress handler: (unit id, quote) of
    paragraph `index` of chapter `number` in `text`, or None if unknown."""
    book = db.get_book(book_id)
    chapter = db.get_chapter(book_id, number) if book else None
    if not chapter:
        return None
    verse = bool(book.get('is_poetry')) and text == 'original'
    source = chapter.get('modern_english_text' if text == 'plain' else 'chapter_text')
    paragraphs = models.Database._reader_split_paragraphs(source, verse=verse)
    quote = re.sub(r'\s+', ' ', paragraphs[index]).strip()[:180] if index < len(paragraphs) else None
    return models.Database._reader_unit_id(chapter['id'], index), quote


@bp.route('/api/kindle/progress', methods=['POST'])
def save_progress():
    """Record the Kindle reader's page as a web-reader progress mutation
    (shared.kindle.progress.save_progress; ch is the chapter number)."""
    return shared_save_progress(PLAINLY_READER, progress_routes.user_db, common.db,
                                _signed_in_user_id(), _position)


register_kindle_pages(bp, {
    **dict.fromkeys(('pages.index', 'pages.discover', 'pages.library', 'pages.all_books'),
                    lambda: library_page()),
    'pages.book_detail': lambda slug: book_page(slug),
    **dict.fromkeys(('pages.book_reader', 'pages.book_chapter_detail'),
                    lambda slug, chapter_number=None: reader_page(slug, chapter_number)),
}, PLAINLY_READER)
