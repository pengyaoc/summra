"""Server-side-rendered page routes (SEO): home, discover, book
detail/summary/chapter, category detail/list, all-books.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import re
import time

from flask import Blueprint, render_template, request

from backend.routes import common
from backend.study_cues import first_sentence, level_label

bp = Blueprint('pages', __name__)

# "Where Most Readers Start" carousel: Project Gutenberg's most-downloaded
# titles, in rank order. Mirrored in app.js (renderTop10Carousel et al.),
# which renders the same carousel client-side when home is reached via SPA
# navigation instead of a full page load.
TOP_10_GUTENBERG_IDS = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345]


def _cover_base(cover_image_url):
    """Static-relative cover path without extension (e.g. 'covers/30'), for
    the webp/jpg <picture> pair that getImageHtml() in app.js also builds."""
    if not cover_image_url or cover_image_url.startswith('http'):
        return ''
    base = re.sub(r'\.(png|jpe?g|webp)$', '', cover_image_url.lstrip('/'), flags=re.I)
    return base[len('static/'):] if base.startswith('static/') else base


def _initial_book(book, slug):
    """__INITIAL_DATA__.book for every /books/<slug>/... route. The client
    renders from it without waiting for /api/books, so it uses that
    endpoint's field names and cover_image_url shape."""
    cover = book.get('cover_image_url')
    return {
        'id': book['id'],
        'title': book['title'],
        'author': book['author'],
        'slug': slug,
        'cover_image_url': f"/static/{cover}" if cover and not cover.startswith('http') else cover,
    }


def _top_10_books():
    """Ranked top-10 books with cover paths split into webp/jpg variants,
    matching getImageHtml() in app.js."""
    found = {b['gutenberg_id']: b for b in common.db.get_books_by_gutenberg_ids(TOP_10_GUTENBERG_IDS)}
    ranked = []
    for rank, gid in enumerate(TOP_10_GUTENBERG_IDS, start=1):
        book = found.get(gid)
        if not book or not book.get('slug'):
            continue
        ranked.append({**book, 'rank': rank, 'cover_base': _cover_base(book.get('cover_image_url'))})
    return ranked


# Home hero examples: (book slug, chapter number). Each shows the chapter's
# opening sentence next to its plain-English rewrite; picked because the
# first sentences line up one-to-one. Missing books/rewrites are skipped.
HERO_EXAMPLES = [
    ('pride-and-prejudice', 1),
    ('jane-eyre', 1),
    ('frankenstein', 1),
    ('great-expectations', 1),
]


def _opening(text, title):
    """First sentence of the first paragraph that isn't the chapter title."""
    for paragraph in (text or '').split('\n\n'):
        if paragraph.strip() and paragraph.strip().lower() != (title or '').strip().lower():
            return first_sentence(paragraph)
    return None


def _hero_examples():
    db = common.db
    examples = []
    for slug, chapter_number in HERO_EXAMPLES:
        book = db.get_book_by_slug(slug)
        chapter = book and db.get_chapter(book['id'], chapter_number)
        if not chapter:
            continue
        original = _opening(chapter.get('chapter_text'), chapter.get('chapter_title'))
        plain = _opening(chapter.get('modern_english_text'), chapter.get('chapter_title'))
        if original and plain:
            examples.append({'original': original, 'plain': plain, 'title': book['title'],
                             'author': book['author'], 'slug': slug})
    return examples


def _level_counts():
    counts = {level: 0 for level in ('Easy', 'Moderate', 'Challenging')}
    for cefr, n in common.db.count_books_by_cefr().items():
        label = level_label(cefr)
        if label:
            counts[label] += n
    return counts


# The home section is rendered (hidden) on every page so in-app navigation
# can just reveal it, so its content is needed everywhere. It only changes
# when books are ingested, so cache it briefly per database.
_HOME_CONTENT_TTL = 300
_home_content_cache = {}


@bp.app_context_processor
def home_content():
    key = getattr(common.db, 'db_path', None)
    cached = _home_content_cache.get(key)
    if not cached or time.monotonic() - cached[0] > _HOME_CONTENT_TTL:
        cached = (time.monotonic(), {'hero_examples': _hero_examples(), 'level_counts': _level_counts()})
        _home_content_cache[key] = cached
    return cached[1]


@bp.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html',
                         meta_title='Summra — Read the Classics in Plain English',
                         top_10_books=_top_10_books())


DISCOVER_LEVELS = ('easy', 'moderate', 'challenging')
DISCOVER_LENGTHS = ('short', 'medium', 'long')
_LEVEL_RANK = {level: rank for rank, level in enumerate(DISCOVER_LEVELS)}
# Sort keys; app.js applySortToDiscoverGrid() orders the cards the same way.
DISCOVER_SORTS = {
    'title': lambda b: b['title'].lower(),
    'shortest': lambda b: (b['reading_minutes'] is None, b['reading_minutes'] or 0, b['title'].lower()),
    'easiest': lambda b: (_LEVEL_RANK.get((b['level'] or '').lower(), len(DISCOVER_LEVELS)), b['title'].lower()),
}


def _query_choice(name, allowed):
    value = request.args.get(name, '').lower()
    return value if value in allowed else None


@bp.route('/discover')
def discover():
    """One grid of every book, filterable by level and length (?level=,
    ?length=) and sortable (?sort=). Filtering is done by CSS on the grid's
    data-filter-* attributes, so the server only sets them."""
    books = [b for b in common.db.get_all_books() if b.get('slug')]
    for book in books:
        book['cover_base'] = _cover_base(book.get('cover_image_url'))
    level = _query_choice('level', DISCOVER_LEVELS)
    length = _query_choice('length', DISCOVER_LENGTHS)
    sort = _query_choice('sort', DISCOVER_SORTS) or 'title'
    books.sort(key=DISCOVER_SORTS[sort])
    match_count = sum(
        1 for b in books
        if (not level or (b['level'] or '').lower() == level)
        and (not length or (b['length'] or '').lower() == length)
    )
    return render_template(
        'index.html',
        meta_title='Discover Classic Books by Level and Length | Summra',
        initial_data={'type': 'discover'},
        discover={
            'books': books,
            'level': level or 'all',
            'length': length or 'all',
            'sort': sort,
            'count': match_count,
        },
    )


@bp.route('/library')
def library():
    """Authenticated readers populate this shell from the Library API."""
    return render_template(
        'index.html',
        meta_title='Your Library | Summra',
        initial_data={'type': 'library'},
    )


@bp.route('/books/<slug>')
def book_detail(slug):
    """Server-side rendering for book detail pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    book = db.get_book_by_slug(slug)

    if not book:
        # Return 404 but still render the SPA shell
        # The client-side router will handle showing the 404 message
        return render_template('index.html'), 404

    # Get concise summary for meta description
    concise_summary = db.get_summary(book['id'], 'concise')
    summary_text = concise_summary['content'][:200] if concise_summary else ''

    # Prepare meta tags
    meta_title = f"{book['title']} by {book['author']} - Summary | Summra"
    meta_description = f"Read AI-generated summaries of {book['title']} by {book['author']}. {summary_text}..."
    canonical_url = f"{site_origin()}/books/{slug}"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"{site_origin()}/static/{cover_url}"
    og_image = cover_url if cover_url else f'{site_origin()}/static/images/og-image.png'

    # Schema.org structured data for Book
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": book['title'],
        "author": {
            "@type": "Person",
            "name": book['author']
        },
        "description": summary_text,
        "inLanguage": "en"
    }

    if cover_url:
        structured_data["image"] = og_image

    # Build breadcrumbs
    breadcrumbs = common.build_breadcrumbs('book', book=book)
    breadcrumb_schema = common.breadcrumbs_to_schema(breadcrumbs)

    # Combine structured data (Book + BreadcrumbList)
    combined_structured_data = [structured_data, breadcrumb_schema]

    # Pass initial data to speed up client-side rendering
    initial_data = {
        'type': 'book',
        'book': _initial_book(book, slug),
        'breadcrumbs': breadcrumbs
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=f"{book['title']}, {book['author']}, book summary, literature",
        canonical_url=canonical_url,
        og_type='book',
        og_image=og_image,
        structured_data=combined_structured_data,
        initial_data=initial_data,
        author_slug=common.author_name_to_slug(book['author']),
        cover_base=_cover_base(book.get('cover_image_url')),
        book_meta={
            'level': book['level'],
            'reading_time': book['reading_time'],
            'chapter_count': db.count_chapters(book['id']),
            'has_plain_english': db.book_has_modern_english(book['id']),
        },
    )


@bp.route('/books/<slug>/summary')
def book_summary_detail(slug):
    """Server-side rendering for book full summary pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    book = db.get_book_by_slug(slug)

    if not book:
        return render_template('index.html'), 404

    # Get medium summary for meta description
    medium_summary = db.get_summary(book['id'], 'medium')
    summary_text = medium_summary['content'][:200] if medium_summary else ''

    # Prepare meta tags
    meta_title = f"{book['title']} - Full Summary | Summra"
    meta_description = f"Read the complete AI-generated summary of {book['title']} by {book['author']}. {summary_text}..."
    canonical_url = f"{site_origin()}/books/{slug}/summary"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"{site_origin()}/static/{cover_url}"
    og_image = cover_url if cover_url else f'{site_origin()}/static/images/og-image.png'

    # Schema.org structured data for Book
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": book['title'],
        "author": {
            "@type": "Person",
            "name": book['author']
        },
        "description": summary_text,
        "inLanguage": "en"
    }

    if cover_url:
        structured_data["image"] = og_image

    # Pass initial data
    initial_data = {
        'type': 'book-summary',
        'book': _initial_book(book, slug)
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=f"{book['title']}, {book['author']}, book summary, full summary, literature",
        canonical_url=canonical_url,
        og_type='book',
        og_image=og_image,
        structured_data=structured_data,
        initial_data=initial_data
    )


@bp.route('/books/<slug>/read')
def book_reader(slug):
    """Canonical continuous-reader shell. Prose remains API-delivered so
    opening a large book does not put a full chapter into the HTML shell."""
    db = common.db
    book = db.get_book_by_slug(slug)
    if not book:
        return render_template('index.html'), 404
    summary = db.get_summary(book['id'], 'concise')
    description = (summary or {}).get('content', '')[:200]
    return render_template(
        'index.html',
        meta_title=f"Read {book['title']} by {book['author']} | Summra",
        meta_description=description,
        canonical_url=f"{common.site_origin()}/books/{slug}/read",
        initial_data={
            'type': 'reader',
            'book': _initial_book(book, slug),
        },
    )


@bp.route('/books/<slug>/chapters/<int:chapter_number>')
def book_chapter_detail(slug, chapter_number):
    """Server-side rendering for chapter pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    book = db.get_book_by_slug(slug)

    if not book:
        return render_template('index.html'), 404

    # Get chapter data
    chapter = db.get_chapter(book['id'], chapter_number)

    if not chapter:
        return render_template('index.html'), 404

    # Get chapter summary for meta description
    chapter_summary = chapter.get('summary', '')[:200] if chapter.get('summary') else ''
    chapter_title = chapter.get('chapter_title', f'Chapter {chapter_number}')

    # Prepare meta tags
    meta_title = f"{book['title']} - Chapter {chapter_number}: {chapter_title} | Summra"
    meta_description = f"Read Chapter {chapter_number} of {book['title']} by {book['author']}. {chapter_summary}..."
    canonical_url = f"{site_origin()}/books/{slug}/chapters/{chapter_number}"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"{site_origin()}/static/{cover_url}"
    og_image = cover_url if cover_url else f'{site_origin()}/static/images/og-image.png'

    # Schema.org structured data for Book Chapter
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Chapter",
        "name": f"Chapter {chapter_number}: {chapter_title}",
        "isPartOf": {
            "@type": "Book",
            "name": book['title'],
            "author": {
                "@type": "Person",
                "name": book['author']
            }
        },
        "description": chapter_summary,
        "position": chapter_number
    }

    # Pass initial data
    initial_data = {
        'type': 'chapter',
        'book': _initial_book(book, slug),
        'chapter_number': chapter_number
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=f"{book['title']}, {book['author']}, chapter {chapter_number}, {chapter_title}, book chapter, literature",
        canonical_url=canonical_url,
        og_type='article',
        og_image=og_image,
        structured_data=structured_data,
        initial_data=initial_data
    )


@bp.route('/categories/<int:category_id>')
def category_detail(category_id):
    """Server-side rendering for category pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    category = db.get_category(category_id)

    if not category:
        return render_template('index.html'), 404

    books = db.get_books_by_category(category_id)
    book_count = len(books)

    # Prepare meta tags
    meta_title = f"{category['name']} - Classic Books | Summra"
    meta_description = f"Explore {book_count} classic {category['name']} books with AI-generated summaries. Browse timeless literature with concise and comprehensive analyses."
    canonical_url = f"{site_origin()}/categories/{category_id}"

    # Pass initial data
    initial_data = {
        'type': 'category',
        'category': category
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=f"{category['name']}, classic books, literature, book summaries",
        canonical_url=canonical_url,
        og_type='website',
        initial_data=initial_data
    )


@bp.route('/categories')
def categories_list():
    """Server-side rendering for all categories page (SEO)"""
    db = common.db
    site_origin = common.site_origin

    categories = db.get_all_categories()

    # Prepare meta tags
    meta_title = "Browse Categories - Classic Book Summaries | Summra"
    meta_description = f"Browse {len(categories)} categories of classic literature. Discover timeless books organized by genre, theme, and literary movement with AI-generated summaries."
    canonical_url = f"{site_origin()}/categories"

    # Pass initial data
    initial_data = {
        'type': 'all-categories'
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords="book categories, classic literature, literary genres, book summaries",
        canonical_url=canonical_url,
        og_type='website',
        initial_data=initial_data
    )


@bp.route('/books')
def all_books():
    """Server-side rendering for all books page (SEO)"""
    db = common.db
    site_origin = common.site_origin

    books = db.get_all_books()
    book_count = len(books)

    # Prepare meta tags
    meta_title = f"Browse {book_count} Classic Books - Free Summaries | Summra"
    meta_description = f"Browse our complete collection of {book_count} classic books with free summaries. From Shakespeare to Tolstoy, explore timeless literature with concise and comprehensive analyses."
    canonical_url = f"{site_origin()}/books"

    # Pass initial data
    initial_data = {
        'type': 'all-books'
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords="classic books, literature, free summaries, book collection, timeless literature",
        canonical_url=canonical_url,
        og_type='website',
        initial_data=initial_data
    )
