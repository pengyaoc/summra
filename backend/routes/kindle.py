"""Kindle e-ink mode: when a Kindle's browser asks for the library, a book
page or the reader, serve a lean server-rendered page instead of the SPA.

E-ink screens ghost on scrolling and animation, and the older Kindle browser
(WebKit 531) can't run app.js, so these pages work without JavaScript and
use only an ES5 script (static/js/kindle.js) to turn the reader into tap-to-
turn pages. `?kindle=0` / `?kindle=1` switch the mode by cookie.
"""
import re
from urllib.parse import urlencode

from flask import Blueprint, after_this_request, render_template, request
from markupsafe import Markup, escape

from backend import models
from backend.kindle import is_kindle_user_agent
from backend.routes import common
from backend.routes.pages import _cover_base

bp = Blueprint('kindle', __name__)

LIBRARY_PAGE_SIZE = 7
CONTENTS_PAGE_SIZE = 8
FONT_SIZES = range(1, 6)
DEFAULT_FONT_SIZE = 3
COOKIE_AGE = 365 * 24 * 3600

# SPA page endpoints that have a Kindle version.
LIBRARY_ENDPOINTS = {'pages.index', 'pages.discover', 'pages.library', 'pages.all_books'}
BOOK_ENDPOINTS = {'pages.book_detail'}
READER_ENDPOINTS = {'pages.book_reader', 'pages.book_chapter_detail'}
KINDLE_ENDPOINTS = LIBRARY_ENDPOINTS | BOOK_ENDPOINTS | READER_ENDPOINTS


def kindle_mode():
    """?kindle= wins, then the remembered choice, then the user agent."""
    choice = request.args.get('kindle') or request.cookies.get('kindle')
    if choice in ('0', '1'):
        return choice == '1'
    return is_kindle_user_agent(request.headers.get('User-Agent'))


@bp.before_app_request
def serve_kindle_page():
    if request.method != 'GET' or request.endpoint not in KINDLE_ENDPOINTS:
        return None
    choice = request.args.get('kindle')
    if choice in ('0', '1'):
        @after_this_request
        def remember(response):
            response.set_cookie('kindle', choice, max_age=COOKIE_AGE, path=_cookie_path())
            return response
    if not kindle_mode():
        return None
    args = request.view_args or {}
    if request.endpoint in LIBRARY_ENDPOINTS:
        return library_page()
    if request.endpoint in BOOK_ENDPOINTS:
        return book_page(args['slug'])
    return reader_page(args['slug'], args.get('chapter_number'))


@bp.after_app_request
def vary_on_device(response):
    """These URLs serve different HTML per device, so caches must not mix them."""
    if request.endpoint in KINDLE_ENDPOINTS:
        response.vary.add('User-Agent')
        response.vary.add('Cookie')
    return response


def _cookie_path():
    return (request.script_root or '') + '/'


def _url(path, **params):
    params = {k: v for k, v in params.items() if v not in (None, '')}
    query = f'?{urlencode(params)}' if params else ''
    return f'{request.script_root}{path}{query}'


def _page_number():
    try:
        return max(1, int(request.args.get('page', 1)))
    except ValueError:
        return 1


def _paginate(items, size, page):
    pages = max(1, -(-len(items) // size))
    page = min(page, pages)
    return items[(page - 1) * size:page * size], page, pages


def _render(template, **context):
    resp = render_template(f'kindle/{template}', **context)
    return resp, 200, {'Cache-Control': 'private, no-cache'}


def not_found():
    resp, _, headers = _render('not_found.html')
    return resp, 404, headers


def _saved_position(book_id):
    """(chapter_number, paragraph index) from the reader's cookie, or None."""
    m = re.fullmatch(r'(\d+)\.(\d+)', request.cookies.get(f'kpos_{book_id}', ''))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _font_size():
    try:
        size = int(request.cookies.get('kfs', DEFAULT_FONT_SIZE))
    except ValueError:
        return DEFAULT_FONT_SIZE
    return size if size in FONT_SIZES else DEFAULT_FONT_SIZE


def library_page():
    show = 'all' if request.args.get('show') == 'all' else 'plain'
    query = request.args.get('q', '').strip()
    books = [b for b in common.db.get_all_books() if b.get('slug')]
    if show == 'plain':
        books = [b for b in books if b.get('has_plain_english')]
    if query:
        needle = query.lower()
        books = [b for b in books if needle in b['title'].lower() or needle in (b['author'] or '').lower()]
    shown, page, pages = _paginate(books, LIBRARY_PAGE_SIZE, _page_number())
    last = request.cookies.get('klast')
    continue_book = common.db.get_book_by_slug(last) if last else None

    def page_url(n):
        return _url('/', show=show if show == 'all' else None, q=query, page=n)

    return _render(
        'library.html',
        books=shown, show=show, query=query, page=page, pages=pages,
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
        continue_book=continue_book,
    )


def book_page(slug):
    db = common.db
    book = db.get_book_by_slug(slug)
    if not book:
        return not_found()
    outline = db.get_chapter_outline(book['id'])
    shown, page, pages = _paginate(outline, CONTENTS_PAGE_SIZE, _page_number())
    saved = _saved_position(book['id'])
    first = outline[0]['chapter_number'] if outline else None
    cover = _cover_base(book.get('cover_image_url'))

    def page_url(n):
        return _url(f'/books/{slug}', page=n)

    return _render(
        'book.html',
        book=book, chapters=shown, page=page, pages=pages,
        first_chapter=first,
        has_plain=book.get('has_plain_english'),
        saved=saved,
        cover_url=_url(f'/static/{cover}.jpg') if cover else None,
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
    )


@bp.app_template_filter('kindle_inline')
def kindle_inline(text):
    """Escape a paragraph and turn *x* / _x_ into italics, as the web
    reader does without marked (reader.js formatContinuousReaderText)."""
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
    wanted = request.args.get('text') or request.cookies.get('ktext') or 'plain'
    has_plain = bool((chapter.get('modern_english_text') or '').strip())
    text = 'plain' if wanted == 'plain' and has_plain else 'original'
    verse = bool(book.get('is_poetry')) and text == 'original'

    def chars(c):
        return c['plain_chars'] if text == 'plain' and c['plain_chars'] else c['text_chars']

    position = numbers.index(chapter_number)
    prev_number = numbers[position - 1] if position > 0 else None
    next_number = numbers[position + 1] if position + 1 < len(numbers) else None

    def chapter_url(n, version=text):
        return _url(f'/books/{slug}/read', ch=n, text=version) if n is not None else None

    return _render(
        'reader.html',
        book=book, chapter=chapter, text=text, verse=verse,
        paragraphs=chapter_paragraphs(chapter, text, verse),
        plain_missing=wanted == 'plain' and not has_plain,
        has_plain=has_plain,
        start=start,
        font_size=_font_size(),
        chars_before=sum(chars(c) for c in outline[:position]),
        chapter_chars=chars(outline[position]),
        total_chars=sum(chars(c) for c in outline) or 1,
        prev_url=chapter_url(prev_number),
        next_url=chapter_url(next_number),
        next_title=outline[position + 1]['chapter_title'] if next_number is not None else None,
        plain_url=chapter_url(chapter_number, 'plain'),
        original_url=chapter_url(chapter_number, 'original'),
        cookie_path=_cookie_path(),
    )
