"""
Base Flask application: app factory, middleware, session config, and
blueprint registration. This module is imported by both app.py
(development) and app_prod.py (production).

Route handlers live in plainly/routes/*.py (split out 2026-09 — see
plainly/routes/common.py for why db/config are injected as module
attributes rather than imported back from here).
"""
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import os
import logging

# Absolute imports work for both `python plainly/app.py` (dev) and gunicorn's
# `plainly.app_prod:app` (prod): `plainly` is installed as an editable
# package (see pyproject.toml), so it resolves from anywhere.
from plainly import config
from plainly import models
from plainly.routes import common, pages, books, taxonomy, authors, blog, system, kindle

from shared.auth import user_models, whoami
from shared.web import install_web_basics
from shared.progress import routes as progress_routes
from shared.auth.pchauth.config import AuthConfig
from shared.auth.pchauth.config import load_config as load_pchauth_config
from shared.auth.pchauth.flask_adapter import init_pchauth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__,
            static_folder='frontend/static',
            template_folder='frontend/templates')

# No SECRET_KEY / session cookie config needed: trusted_header mode reads
# an already-verified identity from a header on every request, it doesn't
# mint or read a cookie of its own. (self_oidc, if ever built, would need
# this back — see pchauth's spec.)
CORS(app, supports_credentials=True)

# Initialize databases
db = models.Database()
user_db = user_models.UserDatabase(config.USER_DATABASE_PATH, valid_hints=config.READER_HINTS)

# Set user_db in progress routes
progress_routes.user_db = user_db
progress_routes.content_db = db

# Inject db/config into the routes.common module so plainly/routes/*.py can
# reach them without importing this module back (see plainly/routes/common.py).
common.db = db
common.config = config

# Register blueprints — gated behind FEATURE_AUTH/FEATURE_BLOG so the routes
# return clean 404s (not 403s) when a subsystem is dark.
if config.FEATURE_AUTH:
    # SUMMRA_AUTH_MODE unset (local dev/test default) means 'off', not
    # pchauth's own library default of 'required' — there's no Apache
    # gateway to supply X-Remote-Email outside the cohosted deployment, so
    # 'off' reproduces the old no-login behavior exactly and needs no
    # SUMMRA_ALLOWED_EMAILS configured. The cohosted deploy's service.env
    # sets SUMMRA_AUTH_MODE=optional and a real SUMMRA_ALLOWED_EMAILS
    # explicitly, at which point load_pchauth_config is what runs.
    if os.environ.get('SUMMRA_AUTH_MODE'):
        pchauth_config = load_pchauth_config(os.environ, prefix='SUMMRA')
    else:
        pchauth_config = AuthConfig(mode='off')
    init_pchauth(
        app,
        pchauth_config,
        upsert_user=lambda identity: user_db.upsert_user_by_email(identity.email),
    )
    whoami.user_db = user_db
    app.register_blueprint(progress_routes.progress_bp)
    app.register_blueprint(whoami.whoami_bp)

app.register_blueprint(system.bp)
app.register_blueprint(pages.bp)
app.register_blueprint(kindle.bp)
app.register_blueprint(books.bp)
app.register_blueprint(taxonomy.bp)
app.register_blueprint(authors.bp)
if config.FEATURE_BLOG:
    app.register_blueprint(blog.bp)

# Set environment flag (will be overridden by app.py or app_prod.py)
app.config['IS_DEVELOPMENT'] = False

# Add context processor to make environment available in templates
@app.context_processor
def inject_environment():
    """Make environment flag and feature flags available to all templates."""
    return {
        'is_development': app.config.get('IS_DEVELOPMENT', False),
        'feature_auth': config.FEATURE_AUTH,
        'feature_blog': config.FEATURE_BLOG,
        'base_path': request.script_root,
        'site_origin': common.site_origin(),
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
    # Authentication and reading-state responses are personal. They must not
    # enter the browser's shared HTTP cache: a stale Library projection hides
    # recently read books, and a shared cache is inappropriate for identity.
    elif (
        request.path == '/api/auth/check'
        or request.path == '/api/library'
        or request.path.startswith('/api/progress/')
    ):
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.private = True
    # Public API responses - cache for 1 hour
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
        response.cache_control.private = True  # home carries the reader's Continue reading

    return response


# Registered after add_cache_headers so gzip runs before it (Flask runs
# after_request hooks in reverse): the ETag is then computed over the gzipped
# bytes, and mtime=0 keeps those bytes — and so the ETag — stable. Also wraps
# the app with PrefixMiddleware and sets the asset_v Jinja global.
install_web_basics(app, 'SUMMRA_STATIC_DIR_OVERRIDE')


# Error handlers
@app.errorhandler(404)
def not_found(error):
    # /api/* misses stay JSON for API clients; every other unmatched URL
    # (a mistyped page route) falls through to the SPA shell so client-side
    # routing / friendly 404 UI can take over.
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Not found'
        }), 404
    return render_template('index.html'), 404


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
