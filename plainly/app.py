"""
Development Flask application.
Imports common routes from app_base and adds development-specific features.
"""
from flask import jsonify, request

# Absolute imports work for both `python plainly/app.py` (dev) and gunicorn's
# `plainly.app_prod:app` (prod): `plainly` is installed as an editable
# package (see pyproject.toml), so it resolves from anywhere.
from plainly import config
from plainly.app_base import app, logger, ensure_directories

# Set development mode flag
app.config['IS_DEVELOPMENT'] = True


@app.route('/api/admin/chapters/<int:book_id>/<int:chapter_number>', methods=['PUT'])
def update_chapter_admin(book_id, chapter_number):
    """Admin endpoint to update chapter text and modern English text (development only)"""
    # Verify we're in development mode
    if not app.config.get('IS_DEVELOPMENT', False):
        return jsonify({
            'success': False,
            'error': 'Admin endpoints are only available in development mode'
        }), 403

    from plainly.models import Database

    try:
        data = request.json
        chapter_text = data.get('chapter_text')
        modern_english_text = data.get('modern_english_text')

        if chapter_text is None and modern_english_text is None:
            return jsonify({
                'success': False,
                'error': 'At least one field (chapter_text or modern_english_text) must be provided'
            }), 400

        db = Database()

        # Verify chapter exists
        chapter = db.get_chapter(book_id, chapter_number)
        if not chapter:
            return jsonify({
                'success': False,
                'error': f'Chapter {chapter_number} not found for book {book_id}'
            }), 404

        # Update the chapter
        db.update_chapter_both_texts(
            book_id=book_id,
            chapter_number=chapter_number,
            chapter_text=chapter_text,
            modern_english_text=modern_english_text
        )

        logger.info(f"Updated chapter {chapter_number} for book {book_id}")

        return jsonify({
            'success': True,
            'message': f'Chapter {chapter_number} updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating chapter: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Ensure data directories exist
    ensure_directories()

    # Run the app
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )
