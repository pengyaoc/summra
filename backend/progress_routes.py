"""Reading progress tracking routes.

This module provides endpoints for saving and retrieving reading progress,
including chapter completion tracking.
"""

from flask import Blueprint, jsonify, request, session
import logging

try:
    from .auth_utils import login_required
except ImportError:
    from backend.auth_utils import login_required

# Will be set by app_base.py
user_db = None

logger = logging.getLogger(__name__)

# Create blueprint
progress_bp = Blueprint('progress', __name__, url_prefix='/api/progress')


@progress_bp.route('/save', methods=['POST'])
@login_required
def save_progress():
    """Save reading progress for current user.

    Request JSON:
        {
            "book_id": int,
            "chapter_number": int,
            "page_number": int (optional),
            "scroll_position": int (optional)
        }

    Returns:
        200: Progress saved successfully
        400: Invalid request
        401: Not authenticated
    """
    user_id = session.get('user_id')
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    book_id = data.get('book_id')
    chapter_number = data.get('chapter_number')
    page_number = data.get('page_number', 0)
    scroll_position = data.get('scroll_position', 0)

    if book_id is None or chapter_number is None:
        return jsonify({'error': 'book_id and chapter_number are required'}), 400

    # Save progress
    user_db.save_reading_progress(
        user_id=user_id,
        book_id=book_id,
        chapter_number=chapter_number,
        page_number=page_number,
        scroll_position=scroll_position
    )

    logger.info(
        f"Progress saved for user {user_id}: book {book_id}, "
        f"chapter {chapter_number}, page {page_number}"
    )

    return jsonify({'success': True}), 200


@progress_bp.route('/get/<int:book_id>', methods=['GET'])
@login_required
def get_progress(book_id):
    """Get reading progress for a specific book.

    Args:
        book_id: Book ID

    Returns:
        200: Progress data
        404: No progress found
        401: Not authenticated
    """
    user_id = session.get('user_id')

    progress = user_db.get_reading_progress(user_id, book_id)

    if progress is None:
        return jsonify({
            'success': True,
            'progress': None
        }), 200

    return jsonify({
        'success': True,
        'progress': progress
    }), 200


@progress_bp.route('/all', methods=['GET'])
@login_required
def get_all_progress():
    """Get all reading progress for current user.

    Returns:
        200: List of progress data
        401: Not authenticated
    """
    user_id = session.get('user_id')

    progress_list = user_db.get_all_reading_progress(user_id)

    return jsonify({
        'success': True,
        'progress': progress_list
    }), 200


@progress_bp.route('/chapter/complete', methods=['POST'])
@login_required
def mark_chapter_complete():
    """Mark a chapter as complete or incomplete.

    Request JSON:
        {
            "book_id": int,
            "chapter_number": int,
            "completed": bool (optional, default: true)
        }

    Returns:
        200: Chapter status updated
        400: Invalid request
        401: Not authenticated
    """
    user_id = session.get('user_id')
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    book_id = data.get('book_id')
    chapter_number = data.get('chapter_number')
    completed = data.get('completed', True)

    if book_id is None or chapter_number is None:
        return jsonify({'error': 'book_id and chapter_number are required'}), 400

    # Mark chapter
    user_db.mark_chapter_complete(
        user_id=user_id,
        book_id=book_id,
        chapter_number=chapter_number,
        completed=completed
    )

    logger.info(
        f"Chapter {'completed' if completed else 'uncompleted'} for user {user_id}: "
        f"book {book_id}, chapter {chapter_number}"
    )

    return jsonify({'success': True}), 200


@progress_bp.route('/chapters/<int:book_id>', methods=['GET'])
@login_required
def get_completed_chapters(book_id):
    """Get list of completed chapters for a book.

    Args:
        book_id: Book ID

    Returns:
        200: List of completed chapter numbers
        401: Not authenticated
    """
    user_id = session.get('user_id')

    completed = user_db.get_completed_chapters(user_id, book_id)

    return jsonify({
        'success': True,
        'completed_chapters': completed
    }), 200


@progress_bp.route('/sync', methods=['POST'])
@login_required
def sync_progress():
    """Sync offline progress with server.

    This endpoint allows syncing multiple progress entries at once,
    useful for offline mode where progress is stored locally and
    synced when connection is restored.

    Request JSON:
        {
            "progress": [
                {
                    "book_id": int,
                    "chapter_number": int,
                    "page_number": int,
                    "scroll_position": int,
                    "timestamp": str (ISO format)
                },
                ...
            ],
            "completed_chapters": [
                {
                    "book_id": int,
                    "chapter_number": int,
                    "completed": bool,
                    "timestamp": str (ISO format)
                },
                ...
            ]
        }

    Returns:
        200: Progress synced successfully
        400: Invalid request
        401: Not authenticated
    """
    user_id = session.get('user_id')
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    # Sync reading progress
    progress_list = data.get('progress', [])
    for progress in progress_list:
        book_id = progress.get('book_id')
        chapter_number = progress.get('chapter_number')
        page_number = progress.get('page_number', 0)
        scroll_position = progress.get('scroll_position', 0)

        if book_id is not None and chapter_number is not None:
            user_db.save_reading_progress(
                user_id=user_id,
                book_id=book_id,
                chapter_number=chapter_number,
                page_number=page_number,
                scroll_position=scroll_position
            )

    # Sync chapter completion
    completed_list = data.get('completed_chapters', [])
    for completion in completed_list:
        book_id = completion.get('book_id')
        chapter_number = completion.get('chapter_number')
        completed = completion.get('completed', True)

        if book_id is not None and chapter_number is not None:
            user_db.mark_chapter_complete(
                user_id=user_id,
                book_id=book_id,
                chapter_number=chapter_number,
                completed=completed
            )

    synced_count = len(progress_list) + len(completed_list)
    logger.info(f"Synced {synced_count} progress entries for user {user_id}")

    return jsonify({
        'success': True,
        'synced': {
            'progress': len(progress_list),
            'completed_chapters': len(completed_list)
        }
    }), 200
