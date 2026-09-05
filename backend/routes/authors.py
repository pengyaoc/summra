"""Author routes: books-by-author API, cover serving, author SSR page,
author detail/books API.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import logging
import os
import json

from flask import Blueprint, current_app, jsonify, render_template, request, send_from_directory

from backend.routes import common

logger = logging.getLogger(__name__)

bp = Blueprint('authors', __name__)


@bp.route('/api/books/by-author/<path:author_name>', methods=['GET'])
def get_books_by_author(author_name):
    """Get all books by a specific author"""
    db = common.db
    try:
        # Decode URL-encoded author name
        from urllib.parse import unquote
        author_name = unquote(author_name)

        # Get exclude_book_id from query params if provided
        exclude_book_id = request.args.get('exclude', type=int)

        # Query database directly for books by author
        author_books_raw = db.get_books_by_author_name(author_name, exclude_book_id=exclude_book_id, limit=20)

        # Format response with cover image URLs
        author_books = []
        for book in author_books_raw:
            book_data = {
                'id': book['id'],
                'title': book['title'],
                'author': book['author']
            }

            # Check if cover image exists
            if book.get('cover_image_url'):
                book_data['cover_image_url'] = book['cover_image_url']
            else:
                # Check for static cover file
                cover_path = os.path.join(current_app.static_folder, 'covers', f"{book['id']}.webp")
                if os.path.exists(cover_path):
                    book_data['cover_image_url'] = f"/static/covers/{book['id']}.webp"

            author_books.append(book_data)

        return jsonify({
            'success': True,
            'author': author_name,
            'books': author_books,
            'count': len(author_books)
        })
    except Exception as e:
        logger.error(f"Error fetching books by author {author_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/covers/<path:filename>')
def serve_cover(filename):
    """Serve cover images"""
    covers_dir = os.path.join(current_app.static_folder, 'covers')
    return send_from_directory(covers_dir, filename)


@bp.route('/authors/<path:author_slug>')
def author_page(author_slug):
    """Server-side rendering for author pages (SEO)"""
    db = common.db
    site_origin = common.site_origin

    # Convert slug back to author name
    author_name = common.slug_to_author_name(author_slug)

    if not author_name:
        # Author not found
        return render_template('index.html'), 404

    author = db.get_author_by_name(author_name)

    if not author:
        # Return 404 but still render the SPA shell
        return render_template('index.html'), 404

    # Get books by this author
    books = db.get_books_by_author_id(author['id'], limit=100) if author.get('id') else []

    # Prepare meta tags
    meta_title = f"{author_name} - Author Profile | Summra"
    meta_description = f"Explore books and summaries by {author_name}."
    if author.get('short_bio'):
        meta_description = author['short_bio'][:160]

    canonical_url = f"{site_origin()}/authors/{author_slug}"

    # Schema.org structured data for Person (Author)
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": author_name,
        "jobTitle": "Author"
    }

    if author.get('country'):
        structured_data["nationality"] = author['country']

    if author.get('short_bio'):
        structured_data["description"] = author['short_bio']

    # Build breadcrumbs
    breadcrumbs = common.build_breadcrumbs('author', author=author)
    breadcrumb_schema = common.breadcrumbs_to_schema(breadcrumbs)

    # Combine structured data
    combined_structured_data = [structured_data, breadcrumb_schema]

    # Pass initial data
    initial_data = {
        'type': 'author',
        'author': {
            'name': author_name
        },
        'breadcrumbs': breadcrumbs
    }

    return render_template(
        'index.html',
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=f"{author_name}, author, books, summaries",
        canonical_url=canonical_url,
        og_type='profile',
        structured_data=combined_structured_data,
        initial_data=initial_data
    )


@bp.route('/api/authors/<path:author_slug>', methods=['GET'])
def get_author(author_slug):
    """Get author details by slug"""
    db = common.db
    author_name = None
    try:
        # Convert slug back to author name
        author_name = common.slug_to_author_name(author_slug)

        if not author_name:
            return jsonify({
                'success': False,
                'error': 'Author not found'
            }), 404

        author = db.get_author_by_name(author_name)
        if not author:
            return jsonify({
                'success': False,
                'error': 'Author not found'
            }), 404

        # Parse other_books field (comma-separated string)
        other_books = []
        if author.get('other_books'):
            try:
                # Try to parse as JSON array first
                other_books = json.loads(author['other_books'])
            except (json.JSONDecodeError, TypeError):
                # Fallback for old comma-separated format
                other_books = [book.strip() for book in author['other_books'].split(',') if book.strip()]

        author_data = {
            'id': author['id'],
            'name': author['name'],
            'short_bio': author.get('short_bio', ''),
            'long_bio': author.get('long_bio', ''),
            'country': author.get('country', ''),
            'other_books': other_books
        }

        return jsonify({
            'success': True,
            'author': author_data
        })
    except Exception as e:
        logger.error(f"Error fetching author {author_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/authors/<path:author_slug>/books', methods=['GET'])
def get_author_books(author_slug):
    """Get all books by an author"""
    db = common.db
    author_name = None
    try:
        # Convert slug back to author name
        author_name = common.slug_to_author_name(author_slug)

        if not author_name:
            return jsonify({
                'success': False,
                'error': 'Author not found'
            }), 404

        author = db.get_author_by_name(author_name)
        if not author:
            return jsonify({
                'success': False,
                'error': 'Author not found'
            }), 404

        # Get all books by this author
        books = db.get_books_by_author_id(author['id'], limit=100) if author.get('id') else []

        # Format book data
        books_data = []
        for book in books:
            book_info = {
                'id': book['id'],
                'title': book['title'],
                'author': book['author'],
                'slug': book.get('slug', ''),
                'cover_image_url': book.get('cover_image_url', ''),
                'word_count': book.get('word_count', 0)
            }

            # Convert cover image path to URL
            if book_info['cover_image_url'] and not book_info['cover_image_url'].startswith('http'):
                book_info['cover_image_url'] = f"/static/{book_info['cover_image_url']}"

            books_data.append(book_info)

        return jsonify({
            'success': True,
            'books': books_data,
            'count': len(books_data)
        })
    except Exception as e:
        logger.error(f"Error fetching books for author {author_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
