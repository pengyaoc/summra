"""Server-side-rendered page routes (SEO): home, discover, book
detail/summary/chapter, category detail/list, all-books.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
from flask import Blueprint, render_template

from backend.routes import common

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html',
                         meta_title='Summra — Read the Classics in Plain English')


@bp.route('/discover')
def discover():
    """Serve the discover page with curated book collections"""
    return render_template('index.html',
                         meta_title='Discover Classic Books by Difficulty Level | Summra')


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
        'book': {
            'id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'slug': slug
        },
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
        initial_data=initial_data
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
        'book': {
            'id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'slug': slug
        }
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
            'book': {'id': book['id'], 'title': book['title'], 'author': book['author'], 'slug': slug},
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
        'book': {
            'id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'slug': slug
        },
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
