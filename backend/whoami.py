"""The frontend's sign-in-state boot probe. There is no /api/auth/login or
/api/auth/register any more — Apache owns login entirely in
trusted_header mode (see pchauth's spec) — but the frontend still needs
one cheap way to ask "am I signed in," which is all this does.
"""
from flask import Blueprint, g, jsonify

whoami_bp = Blueprint('whoami', __name__, url_prefix='/api/auth')

# Set by app_base.py, same pattern as progress_routes.user_db.
user_db = None


@whoami_bp.route('/check', methods=['GET'])
def check():
    if g.user_id is None:
        return jsonify({'authenticated': False}), 200
    user = user_db.get_user_by_id(g.user_id)
    if user is None:
        return jsonify({'authenticated': False}), 200
    return jsonify({'authenticated': True, 'user': user}), 200
