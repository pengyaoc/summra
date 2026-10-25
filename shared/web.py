"""Web basics both apps share: reverse-proxy prefix support, response
gzip and content-hash cache busting for static assets."""
import gzip
import os
import zlib
from pathlib import Path

from flask import Flask, request


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


def gzip_response(response):
    """Gzip HTML/JSON. Prod's Apache front end compresses the static files it
    serves itself but passes gunicorn's responses through uncompressed."""
    if (
        response.status_code != 200
        or response.direct_passthrough
        or response.is_streamed
        or 'Content-Encoding' in response.headers
        or response.mimetype not in ('text/html', 'application/json')
        or 'gzip' not in request.headers.get('Accept-Encoding', '').lower()
    ):
        return response
    data = response.get_data()
    if len(data) < 1024:
        return response
    response.set_data(gzip.compress(data, compresslevel=6, mtime=0))
    response.headers['Content-Encoding'] = 'gzip'
    response.vary.add('Accept-Encoding')
    return response


def make_asset_v(app: Flask, static_dir_override_env: str = 'SUMMRA_STATIC_DIR_OVERRIDE'):
    """Build the `asset_v` template helper for `app`.

    asset_v('css/foo.css') returns '?v=<content-hash>' for an existing static
    asset, or '' if missing. Composed in templates as:
        href="{{ url_for('static', filename='css/style.css') }}{{ asset_v('css/style.css') }}"

    Content hash, not mtime: mtime is preserved or reset inconsistently by
    different deploy paths (git checkout, rsync, a straight file copy), so it
    can fail to change even when content did. No cache on purpose: a hash
    cached by mtime reintroduced exactly that bug. Static assets are KB-scale,
    so hashing on every call is cheap.
    """
    def resolve(filename: str):
        override = os.environ.get(static_dir_override_env)
        if override:
            return Path(override) / filename
        if not app.static_folder:
            return None
        return Path(app.static_folder) / filename

    def asset_v(filename: str) -> str:
        path = resolve(filename)
        if not path or not path.exists():
            return ''
        try:
            content = path.read_bytes()
        except OSError:
            return ''
        return f'?v={zlib.crc32(content)}'

    return asset_v


def install_web_basics(app: Flask, static_dir_override_env: str = 'SUMMRA_STATIC_DIR_OVERRIDE') -> None:
    """Wrap `app` with PrefixMiddleware, register gzip as an after_request
    hook and set the `asset_v` Jinja global.

    Flask runs after_request hooks in reverse registration order, so call this
    after registering cache-header hooks: gzip then runs first and the ETag is
    computed over the gzipped bytes."""
    app.wsgi_app = PrefixMiddleware(app.wsgi_app)
    app.after_request(gzip_response)
    app.jinja_env.globals['asset_v'] = make_asset_v(app, static_dir_override_env)
