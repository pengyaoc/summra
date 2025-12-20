"""Authentication and user management routes.

This module provides endpoints for user registration, login, logout,
and reading progress tracking.
"""

from flask import Blueprint, jsonify, request, session
from functools import wraps
from typing import Optional
import logging

# Will be set by app_base.py
user_db = None

logger = logging.getLogger(__name__)

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_current_user_id() -> Optional[int]:
    """Get current user ID from session.

    Returns:
        User ID if logged in, None otherwise
    """
    return session.get('user_id')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account.

    Request JSON:
        {
            "username": "string",
            "password": "string"
        }

    Returns:
        201: User created successfully
        400: Invalid request or username already exists
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    # Validate input
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Create user
    user_id = user_db.create_user(username, password)

    if user_id is None:
        return jsonify({'error': 'Username already exists'}), 400

    # Log user in automatically
    session['user_id'] = user_id
    session['username'] = username

    logger.info(f"User registered and logged in: {username} (ID: {user_id})")

    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'username': username
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and create session.

    Request JSON:
        {
            "username": "string",
            "password": "string"
        }

    Returns:
        200: Login successful
        401: Invalid credentials
        400: Invalid request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Authenticate user
    user = user_db.authenticate_user(username, password)

    if user is None:
        return jsonify({'error': 'Invalid username or password'}), 401

    # Create session
    session['user_id'] = user['id']
    session['username'] = user['username']

    logger.info(f"User logged in: {username} (ID: {user['id']})")

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'last_login': user['last_login']
        }
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Log out current user and clear session.

    Returns:
        200: Logout successful
    """
    username = session.get('username', 'unknown')
    session.clear()

    logger.info(f"User logged out: {username}")

    return jsonify({'success': True}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current logged-in user information.

    Returns:
        200: User information
        401: Not authenticated
    """
    user_id = session.get('user_id')
    user = user_db.get_user_by_id(user_id)

    if user is None:
        session.clear()
        return jsonify({'error': 'User not found'}), 401

    return jsonify({
        'success': True,
        'user': user
    }), 200


@auth_bp.route('/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated.

    Returns:
        200: Authentication status
    """
    user_id = session.get('user_id')

    if user_id is None:
        return jsonify({
            'authenticated': False
        }), 200

    user = user_db.get_user_by_id(user_id)

    if user is None:
        session.clear()
        return jsonify({
            'authenticated': False
        }), 200

    return jsonify({
        'authenticated': True,
        'user': {
            'id': user['id'],
            'username': user['username']
        }
    }), 200
