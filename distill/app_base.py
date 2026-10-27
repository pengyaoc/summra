"""Distill app factory: shared reader platform, allow-listed sign-in, private caching."""
import logging
import os

from flask import Flask, request

from distill import config
from distill.kindle_routes import bp as kindle_bp
from distill.models import DistillDatabase
from distill.reader_config import DISTILL_READER
from distill.routes import bp
from shared.auth.pchauth.config import AuthConfig
from shared.auth.pchauth.config import load_config as load_pchauth_config
from shared.auth.pchauth.flask_adapter import init_pchauth
from shared.auth.user_models import UserDatabase
from shared.reader.blocks import block_element
from shared.reader.platform import install_reader_platform
from shared.web import install_shared_ui, install_web_basics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def create_app(content_db=None, user_db=None, auth_config=None) -> Flask:
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['CONTENT_DB'] = content_db or DistillDatabase(config.DATABASE_PATH)
    user_db = user_db or UserDatabase(config.USER_DATABASE_PATH, valid_hints=DISTILL_READER.hint_keys)
    app.config['IS_DEVELOPMENT'] = False

    # Unset DISTILL_AUTH_MODE means 'off' (local dev), not pchauth's library default of 'required'.
    if auth_config is None:
        auth_config = (load_pchauth_config(os.environ, prefix='DISTILL')
                       if os.environ.get('DISTILL_AUTH_MODE') else AuthConfig(mode='off'))
    if auth_config.mode == 'optional':
        raise ValueError("Distill is all-private: auth mode 'optional' is not allowed (use 'off' for dev, 'required' for prod)")
    # Must stay before any blueprint: the Kindle dispatch (a before_app_request) skips
    # @login_required, so Flask running this auth hook first is what keeps Kindle pages private.
    init_pchauth(app, auth_config, upsert_user=lambda identity: user_db.upsert_user_by_email(identity.email),
                 public_endpoints=frozenset({'distill.manifest', 'distill.favicon', 'distill.app_icon'}))

    install_reader_platform(app, DISTILL_READER, lambda: app.config['CONTENT_DB'], user_db)
    app.register_blueprint(bp)
    app.register_blueprint(kindle_bp)
    app.jinja_env.globals['block_element'] = block_element

    @app.context_processor
    def inject_environment():
        return {'base_path': request.script_root, 'is_development': app.config['IS_DEVELOPMENT']}

    @app.after_request
    def default_private_cache(response):
        # Everything here is one reader's private content: never let a response
        # fall through without a Cache-Control (static assets excepted).
        if request.endpoint == 'static' and response.status_code in (200, 304):
            filename = (request.view_args or {}).get('filename', '')
            version = request.args.get('v')
            expected = app.jinja_env.globals['asset_v'](filename)
            # Only content-hashed URLs can be immutable. ES module imports use
            # bare URLs and must still revalidate to pick up deployments.
            response.headers['Cache-Control'] = (
                'private, max-age=31536000, immutable' if version and expected == f'?v={version}'
                else 'private, no-cache')
        elif 'Cache-Control' not in response.headers:
            response.headers['Cache-Control'] = 'private, no-cache'
        return response

    install_web_basics(app, 'DISTILL_STATIC_DIR_OVERRIDE')
    install_shared_ui(app)
    return app
