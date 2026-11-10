"""
Production Flask application with pre-generated TTS only.
Imports common routes from app_base and adds production-specific features.
"""
from flask import jsonify
import os

# Absolute imports work for both `python plainly/app.py` (dev) and gunicorn's
# `plainly.app_prod:app` (prod): `plainly` is installed as an editable
# package (see pyproject.toml), so it resolves from anywhere.
from plainly import config
from plainly.app_base import app, logger, ensure_directories

# Ensure production mode (IS_DEVELOPMENT = False is already set in app_base)
app.config['IS_DEVELOPMENT'] = False


@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring"""
    return jsonify({'status': 'healthy'}), 200


# ===== ADMIN ENDPOINTS (Disabled in Production) =====

@app.route('/api/admin/chapters/<int:book_id>/<int:chapter_number>', methods=['PUT'])
def update_chapter_admin(book_id, chapter_number):
    """Admin endpoint - disabled in production"""
    return jsonify({
        'success': False,
        'error': 'Admin endpoints are not available in production'
    }), 403


if __name__ == '__main__':
    # Ensure data directories exist
    ensure_directories()

    # This is only for development/testing
    # In production, use: gunicorn -c deploy/gunicorn_config.py plainly.app_prod:app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
