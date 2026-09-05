"""Shared auth helpers for auth_routes.py and progress_routes.py.

Extracted because both defined an identical `login_required` decorator
(2026-09 refactor — see WORK_LOG.md).
"""
from functools import wraps

from flask import jsonify, session


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function
