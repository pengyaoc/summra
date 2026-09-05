"""API routes for categories and related-books.

Moved out of app_base.py as part of the blueprint split (2026-09 refactor).
"""
import logging

from flask import Blueprint, jsonify

from backend.routes import common

logger = logging.getLogger(__name__)

bp = Blueprint('taxonomy', __name__)


@bp.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    db = common.db
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


@bp.route('/api/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """Get a specific category"""
    db = common.db
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


@bp.route('/api/categories/<int:category_id>/books', methods=['GET'])
def get_books_by_category(category_id):
    """Get all books for a specific category"""
    db = common.db
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


@bp.route('/api/books/<int:book_id>/categories', methods=['GET'])
def get_book_categories(book_id):
    """Get all categories for a specific book"""
    db = common.db
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


@bp.route('/api/books/<int:book_id>/related', methods=['GET'])
def get_related_books(book_id):
    """Get related books for a specific book (by author, category, and country)"""
    db = common.db
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
