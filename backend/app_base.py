"""
Base Flask application with common routes and logic.
This module is imported by both app.py (development) and app_prod.py (production).
"""
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
from pathlib import Path
import os
import sys
import logging

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Handle both direct execution and module execution
try:
    from . import config
    from . import models
except ImportError:
    import config
    import models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Initialize database
db = models.Database()


# Helper Functions

def build_breadcrumbs(page_type, **kwargs):
    """
    Build breadcrumb data for SEO and navigation.

    Returns list of breadcrumb items with:
    - name: Display text
    - url: Relative URL
    - position: Position in breadcrumb trail (starts at 1)
    """
    breadcrumbs = [
        {'name': 'Home', 'url': '/', 'position': 1}
    ]

    if page_type == 'categories':
        breadcrumbs.append({'name': 'Categories', 'url': '/categories', 'position': 2})

    elif page_type == 'category':
        category = kwargs.get('category')
        breadcrumbs.append({'name': 'Categories', 'url': '/categories', 'position': 2})
        if category:
            breadcrumbs.append({
                'name': category['name'],
                'url': f"/categories/{category['id']}",
                'position': 3
            })

    elif page_type == 'all_books':
        breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})

    elif page_type == 'book':
        book = kwargs.get('book')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })

    elif page_type == 'book_summary':
        book = kwargs.get('book')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })
            breadcrumbs.append({
                'name': 'Summary',
                'url': f"/books/{book['slug']}/summary",
                'position': 4
            })

    elif page_type == 'chapter':
        book = kwargs.get('book')
        chapter = kwargs.get('chapter')
        if book:
            breadcrumbs.append({'name': 'All Books', 'url': '/all-books', 'position': 2})
            breadcrumbs.append({
                'name': book['title'],
                'url': f"/books/{book['slug']}",
                'position': 3
            })
            if chapter:
                # Use chapter title if available, otherwise fall back to chapter number
                chapter_title = chapter.get('chapter_title')
                chapter_name = (
                    f"{chapter['chapter_number']}. {chapter_title}"
                    if chapter_title
                    else f"Chapter {chapter['chapter_number']}"
                )
                breadcrumbs.append({
                    'name': chapter_name,
                    'url': f"/books/{book['slug']}/chapters/{chapter['chapter_number']}",
                    'position': 4
                })

    return breadcrumbs


def breadcrumbs_to_schema(breadcrumbs):
    """Convert breadcrumbs list to Schema.org BreadcrumbList JSON-LD"""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": crumb['position'],
                "name": crumb['name'],
                "item": f"https://summra.com{crumb['url']}" if crumb['position'] < len(breadcrumbs) else None
            }
            for crumb in breadcrumbs
        ]
    }


# HTTP Caching Headers
@app.after_request
def add_cache_headers(response):
    """Add appropriate cache control headers to responses"""
    # Static assets (images, CSS, JS) - cache for 1 year
    if request.path.startswith('/static/'):
        # Immutable static assets
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True
        response.cache_control.immutable = True
    # API responses - cache for 1 hour
    elif request.path.startswith('/api/'):
        response.cache_control.max_age = 3600  # 1 hour
        response.cache_control.public = True
        # Add ETag for conditional requests (only for successful responses)
        if response.status_code == 200:
            response.add_etag()
            # Check if client sent If-None-Match header
            response.make_conditional(request)
    # HTML pages - no cache (always fresh)
    elif request.path == '/' or request.path.endswith('.html'):
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True

    return response


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html',
                         meta_title='Free Classic Book Summaries, Chapter Summaries & Full Text | Summra')


@app.route('/robots.txt')
def robots():
    """Serve robots.txt for SEO"""
    return send_from_directory(app.static_folder, 'robots.txt')


@app.route('/sitemap.xml')
def sitemap():
    """Generate dynamic XML sitemap for SEO"""
    from datetime import datetime

    pages = []

    # Home page
    pages.append({
        'loc': 'https://summra.com/',
        'lastmod': datetime.now().strftime('%Y-%m-%d'),
        'changefreq': 'daily',
        'priority': '1.0'
    })

    # All books pages
    books = db.get_all_books()
    for book in books:
        slug = book.get('slug')
        if not slug:
            continue

        # Book detail page
        pages.append({
            'loc': f'https://summra.com/books/{slug}',
            'lastmod': book.get('updated_at', datetime.now().strftime('%Y-%m-%d')),
            'changefreq': 'weekly',
            'priority': '0.8'
        })

    # Category pages
    categories = db.get_all_categories()
    for category in categories:
        pages.append({
            'loc': f'https://summra.com/categories/{category["id"]}',
            'changefreq': 'weekly',
            'priority': '0.7'
        })

    # All books and categories listing pages
    pages.append({
        'loc': 'https://summra.com/books',
        'changefreq': 'daily',
        'priority': '0.9'
    })

    pages.append({
        'loc': 'https://summra.com/categories',
        'changefreq': 'weekly',
        'priority': '0.8'
    })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = app.make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response


@app.route('/books/<slug>')
def book_detail(slug):
    """Server-side rendering for book detail pages (SEO)"""
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
    canonical_url = f"https://summra.com/books/{slug}"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"https://summra.com/static/{cover_url}"
    og_image = cover_url if cover_url else 'https://summra.com/static/images/og-image.png'

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
    breadcrumbs = build_breadcrumbs('book', book=book)
    breadcrumb_schema = breadcrumbs_to_schema(breadcrumbs)

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


@app.route('/books/<slug>/summary')
def book_summary_detail(slug):
    """Server-side rendering for book full summary pages (SEO)"""
    book = db.get_book_by_slug(slug)

    if not book:
        return render_template('index.html'), 404

    # Get medium summary for meta description
    medium_summary = db.get_summary(book['id'], 'medium')
    summary_text = medium_summary['content'][:200] if medium_summary else ''

    # Prepare meta tags
    meta_title = f"{book['title']} - Full Summary | Summra"
    meta_description = f"Read the complete AI-generated summary of {book['title']} by {book['author']}. {summary_text}..."
    canonical_url = f"https://summra.com/books/{slug}/summary"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"https://summra.com/static/{cover_url}"
    og_image = cover_url if cover_url else 'https://summra.com/static/images/og-image.png'

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


@app.route('/books/<slug>/chapters/<int:chapter_number>')
def book_chapter_detail(slug, chapter_number):
    """Server-side rendering for chapter pages (SEO)"""
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
    canonical_url = f"https://summra.com/books/{slug}/chapters/{chapter_number}"

    # Get cover image URL
    cover_url = book.get('cover_image_url', '')
    if cover_url and not cover_url.startswith('http'):
        cover_url = f"https://summra.com/static/{cover_url}"
    og_image = cover_url if cover_url else 'https://summra.com/static/images/og-image.png'

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


@app.route('/categories/<int:category_id>')
def category_detail(category_id):
    """Server-side rendering for category pages (SEO)"""
    category = db.get_category(category_id)

    if not category:
        return render_template('index.html'), 404

    books = db.get_books_by_category(category_id)
    book_count = len(books)

    # Prepare meta tags
    meta_title = f"{category['name']} - Classic Books | Summra"
    meta_description = f"Explore {book_count} classic {category['name']} books with AI-generated summaries. Browse timeless literature with concise and comprehensive analyses."
    canonical_url = f"https://summra.com/categories/{category_id}"

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


@app.route('/categories')
def categories_list():
    """Server-side rendering for all categories page (SEO)"""
    categories = db.get_all_categories()

    # Prepare meta tags
    meta_title = "Browse Categories - Classic Book Summaries | Summra"
    meta_description = f"Browse {len(categories)} categories of classic literature. Discover timeless books organized by genre, theme, and literary movement with AI-generated summaries."
    canonical_url = "https://summra.com/categories"

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


@app.route('/books')
def all_books():
    """Server-side rendering for all books page (SEO)"""
    books = db.get_all_books()
    book_count = len(books)

    # Prepare meta tags
    meta_title = f"Browse {book_count} Classic Books - Free Summaries | Summra"
    meta_description = f"Browse our complete collection of {book_count} classic books with free summaries. From Shakespeare to Tolstoy, explore timeless literature with concise and comprehensive analyses."
    canonical_url = "https://summra.com/books"

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


@app.route('/api/books', methods=['GET'])
def get_books():
    """Get all books"""
    try:
        books = db.get_all_books()

        # Convert cover image paths to URLs for frontend
        for book in books:
            if book.get('cover_image_url') and not book['cover_image_url'].startswith('http'):
                # It's a local path, prepend /static/
                book['cover_image_url'] = f"/static/{book['cover_image_url']}"

        return jsonify({
            'success': True,
            'books': books
        })
    except Exception as e:
        logger.error(f"Error fetching books: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    """Get book details"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # Don't return full text in API response (too large)
        book_data = {k: v for k, v in book.items() if k != 'full_text'}

        # Convert cover image path to URL for frontend
        if book_data.get('cover_image_url') and not book_data['cover_image_url'].startswith('http'):
            # It's a local path, prepend /static/
            book_data['cover_image_url'] = f"/static/{book_data['cover_image_url']}"

        return jsonify({
            'success': True,
            'book': book_data
        })
    except Exception as e:
        logger.error(f"Error fetching book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/summary/<summary_type>', methods=['GET'])
def get_summary(book_id, summary_type):
    """Get summary for a book"""
    try:
        # Validate summary type
        if summary_type not in ['concise', 'medium', 'comprehensive', 'full']:
            return jsonify({
                'success': False,
                'error': 'Invalid summary type. Must be: concise, medium, comprehensive, or full'
            }), 400

        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # For full-length view, use comprehensive summary with chapter text
        if summary_type == 'full':
            summary = db.get_summary(book_id, 'comprehensive')
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            if not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Full-length view requires comprehensive summary. Please generate summaries first.'
                }), 404

            # Check if chapters have text (for backwards compatibility)
            if chapters and not chapters[0].get('chapter_text'):
                return jsonify({
                    'success': False,
                    'error': 'Chapter text not available. Please regenerate summaries to include full text.'
                }), 404

            # Prepare book data with cover image path conversion
            book_data = {
                'id': book['id'],
                'title': book['title'],
                'author': book['author']
            }

            # Add cover image if available
            if book.get('cover_image_url'):
                cover_url = book['cover_image_url']
                if not cover_url.startswith('http'):
                    # It's a local path, prepend /static/
                    cover_url = f"/static/{cover_url}"
                book_data['cover_image_url'] = cover_url

            # Check if audio exists for the summary
            has_audio = False
            if summary and summary.get('id'):
                has_audio = db.has_audio_for_summary(summary['id'])

            # Add has_audio flag to each chapter
            for chapter in chapters:
                if chapter.get('id'):
                    chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
                else:
                    chapter['has_audio'] = False

            response_data = {
                'success': True,
                'book': book_data,
                'summary': summary,
                'summary_type': 'full',
                'has_audio': has_audio,
                'chapters': chapters
            }

            return jsonify(response_data)

        # For other summary types
        summary = db.get_summary(book_id, summary_type)

        # For comprehensive summary, also get chapters
        chapters = None
        if summary_type == 'comprehensive':
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            # This handles the case where chapters are still being generated
            if not summary and not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Summary not found. Please generate summaries first.'
                }), 404

        # For other summary types (concise, medium), require the summary
        if not summary and summary_type != 'comprehensive':
            return jsonify({
                'success': False,
                'error': 'Summary not found. Please generate summaries first.'
            }), 404

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        # Check if audio exists for this summary
        has_audio = False
        if summary and summary.get('id'):
            has_audio = db.has_audio_for_summary(summary['id'])

        response_data = {
            'success': True,
            'book': book_data,
            'summary': summary,
            'summary_type': summary_type,
            'has_audio': has_audio
        }

        if chapters:
            # Add has_audio flag to each chapter
            for chapter in chapters:
                if chapter.get('id'):
                    chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
                else:
                    chapter['has_audio'] = False
            response_data['chapters'] = chapters

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error fetching summary for book {book_id}, type {summary_type}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/chapters', methods=['GET'])
def get_chapters(book_id):
    """Get chapter metadata only (optimized for chapter list display)"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # Get hierarchical book structure with metadata only (no full text/summaries)
        book_structure = db.get_book_structure_metadata(book_id)

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        return jsonify({
            'success': True,
            'book': book_data,
            'has_sections': book_structure['has_sections'],
            'sections': book_structure['sections']
        })

    except Exception as e:
        logger.error(f"Error fetching chapters for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/chapters/<int:chapter_number>', methods=['GET'])
def get_chapter_detail(book_id, chapter_number):
    """Get full details for a specific chapter (summary and full text)"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        chapter = db.get_chapter(book_id, chapter_number)
        if not chapter:
            return jsonify({
                'success': False,
                'error': 'Chapter not found'
            }), 404

        # Check if audio exists for this chapter
        if chapter.get('id'):
            chapter['has_audio'] = db.has_audio_for_chapter(chapter['id'])
        else:
            chapter['has_audio'] = False

        return jsonify({
            'success': True,
            'chapter': chapter
        })

    except Exception as e:
        logger.error(f"Error fetching chapter {chapter_number} for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/summary-configs', methods=['GET'])
def get_summary_configs():
    """Get available summary configurations"""
    return jsonify({
        'success': True,
        'configs': config.SUMMARY_CONFIGS
    })


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    try:
        categories = db.get_all_categories()
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """Get a specific category"""
    try:
        category = db.get_category(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        return jsonify({
            'success': True,
            'category': category
        })
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories/<int:category_id>/books', methods=['GET'])
def get_books_by_category(category_id):
    """Get all books for a specific category"""
    try:
        category = db.get_category(category_id)
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category not found'
            }), 404

        books = db.get_books_by_category(category_id)

        # Convert cover image paths to URLs for frontend
        for book in books:
            if book.get('cover_image_url') and not book['cover_image_url'].startswith('http'):
                book['cover_image_url'] = f"/static/{book['cover_image_url']}"

        return jsonify({
            'success': True,
            'category': category,
            'books': books
        })
    except Exception as e:
        logger.error(f"Error fetching books for category {category_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/categories', methods=['GET'])
def get_book_categories(book_id):
    """Get all categories for a specific book"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        categories = db.get_book_categories(book_id)

        return jsonify({
            'success': True,
            'book_id': book_id,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error fetching categories for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/related', methods=['GET'])
def get_related_books(book_id):
    """Get related books for a specific book (by author, category, and country)"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        related = db.get_related_books(book_id)

        return jsonify({
            'success': True,
            'book_id': book_id,
            'related': related
        })
    except Exception as e:
        logger.error(f"Error fetching related books for book {book_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/covers/<path:filename>')
def serve_cover(filename):
    """Serve cover images"""
    covers_dir = os.path.join(app.static_folder, 'covers')
    return send_from_directory(covers_dir, filename)


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


def ensure_directories():
    """Ensure data directories exist"""
    config.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    config.SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    config.TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.COVERS_DIR.mkdir(parents=True, exist_ok=True)
