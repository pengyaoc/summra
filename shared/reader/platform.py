"""One call that plugs an app into the shared reader's server side."""
from typing import Any, Callable, Optional

from flask import Flask

from shared.auth import whoami
from shared.progress import routes as progress_routes
from shared.reader.config import ReaderConfig
from shared.reader.routes import make_reader_blueprint


def install_reader_platform(
    app: Flask,
    config: ReaderConfig,
    get_content_db: Callable[[], Any],
    user_db: Optional[Any],
) -> None:
    app.extensions['reader_config'] = config

    @app.context_processor
    def inject_reader_config():
        return {'reader_config': config, 'app_name': config.app_name}

    app.register_blueprint(make_reader_blueprint(get_content_db, config.cache_visibility))

    if user_db is not None:
        progress_routes.user_db = user_db
        progress_routes.content_db = get_content_db()
        whoami.user_db = user_db
    if config.features.progress:
        app.register_blueprint(progress_routes.progress_bp)
        app.register_blueprint(whoami.whoami_bp)
