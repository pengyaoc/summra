"""
Base Flask application: app factory, middleware, session config, and
blueprint registration. This module is imported by both app.py
(development) and app_prod.py (production).

Route handlers live in backend/routes/*.py (split out 2026-09 — see
backend/routes/common.py for why db/config are injected as module
attributes rather than imported back from here).
"""
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pathlib import Path
from datetime import timedelta
import os
import logging
import zlib
import secrets

# Handle both direct execution (`python backend/app.py`, dev) and package
# import (gunicorn's `backend.app_prod:app`, prod) — `backend` is installed
# as an editable package (see pyproject.toml), so the fallback resolves from
# anywhere without a sys.path hack.
try:
    from . import config
    from . import models
    from . import user_models
    from . import auth_routes
    from . import progress_routes
    from .routes import common, pages, books, taxonomy, discover, authors, blog, system
except ImportError:
    from backend import config
    from backend import models
    from backend import user_models
    from backend import auth_routes
    from backend import progress_routes
    from backend.routes import common, pages, books, taxonomy, discover, authors, blog, system

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PrefixMiddleware:
    """WSGI middleware letting this app be reverse-proxied under a URL prefix
    (e.g. Apache's `ProxyPass /summrabook/ http://127.0.0.1:5001/`, which strips
    the prefix before forwarding to the backend). Reads X-Forwarded-Prefix (set
    by the proxy) and applies it as SCRIPT_NAME, so url_for() and
    request.script_root automatically produce correctly-prefixed URLs
    everywhere. No effect when the header is absent (root deployment, local dev).
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(prefix):
                environ['PATH_INFO'] = path_info[len(prefix):] or '/'
        return self.wsgi_app(environ, start_response)


# Create Flask app
app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
app.wsgi_app = PrefixMiddleware(app.wsgi_app)

# Configure session
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if config.FEATURE_AUTH:
        # A per-process random key would silently break sessions across
        # gunicorn workers (each generates a different key, so cookies signed
        # by one worker fail to validate on another) — fail fast instead.
        raise RuntimeError(
            "SECRET_KEY environment variable must be set when FEATURE_AUTH "
            "is enabled — see deploy/service.env.example."
        )
    # FEATURE_AUTH is off, so sessions aren't exercised; a random per-process
    # key is harmless here and keeps dev/test running without extra setup.
    _secret_key = secrets.token_hex(32)
app.config['SECRET_KEY'] = _secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '1') == '1'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

CORS(app, supports_credentials=True)

# Initialize databases
db = models.Database()
user_db = user_models.UserDatabase(config.USER_DATABASE_PATH)

# Set user_db in auth and progress routes
auth_routes.user_db = user_db
progress_routes.user_db = user_db

# Inject db/config into the routes.common module so backend/routes/*.py can
# reach them without importing this module back (see backend/routes/common.py).
common.db = db
common.config = config

# Register blueprints — gated behind FEATURE_AUTH/FEATURE_BLOG so the routes
# return clean 404s (not 403s) when a subsystem is dark.
if config.FEATURE_AUTH:
    app.register_blueprint(auth_routes.auth_bp)
    app.register_blueprint(progress_routes.progress_bp)

app.register_blueprint(system.bp)
app.register_blueprint(pages.bp)
app.register_blueprint(books.bp)
app.register_blueprint(taxonomy.bp)
app.register_blueprint(discover.bp)
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


# Cache-busting helper for static assets.
#
# The service worker (frontend/static/service-worker.js) caches CSS with the
# CacheFirst strategy and a 30-day max-age. If a deploy ships a CSS that's
# incompatible with the existing HTML/JS, returning users will serve the new
# HTML over old cached CSS until either the cache expires or the user clears
# site data. asset_v('css/foo.css') returns '?v=<content-hash>' so the URL
# changes whenever the file's *content* changes, forcing a cache miss on the
# new URL.
#
# Content hash, not mtime: mtime is preserved or reset inconsistently by
# different deploy paths (git checkout, rsync, a straight file copy), so it
# can fail to change even when content did, or change with no content
# change at all — either way defeating the point of a cache-busting query
# string. A hash of the actual bytes is correct regardless of how the file
# got onto disk. No mtime-keyed cache here on purpose: an earlier version
# cached the hash keyed by mtime and only recomputed on a mtime change —
# which reintroduced the exact bug this function exists to avoid (same
# mtime, different content, due to a deploy tool that doesn't bump it, would
# silently serve a stale cached hash). Every static asset here is small
# (KB-scale CSS/JS), so hashing on every call is cheap enough not to need
# caching at all.
def _resolve_static_path(filename: str):
    """Return the on-disk path of a static asset, honoring a test override."""
    override = os.environ.get('SUMMRA_STATIC_DIR_OVERRIDE')
    if override:
        return Path(override) / filename
    static_folder = app.static_folder
    if not static_folder:
        return None
    return Path(static_folder) / filename


def asset_v(filename: str) -> str:
    """Return '?v=<content-hash>' for an existing static asset, or '' if missing.

    Composed in templates as:
        href="{{ url_for('static', filename='css/style.css') }}{{ asset_v('css/style.css') }}"
    """
    path = _resolve_static_path(filename)
    if not path or not path.exists():
        return ''
    try:
        content = path.read_bytes()
    except OSError:
        return ''
    return f'?v={zlib.crc32(content)}'


app.jinja_env.globals['asset_v'] = asset_v


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
