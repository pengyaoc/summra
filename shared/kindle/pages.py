"""Kindle e-ink mode, shared: when a Kindle's browser asks for a page that
has a Kindle version, serve the app's lean server-rendered page instead of
the web reader. `?kindle=0` / `?kindle=1` switch the mode by cookie.

An app supplies one handler per web endpoint (`register_kindle_pages`) and
the page templates; paging, cookies, pagination and the account line live here.
"""
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote, urlencode

from flask import Blueprint, after_this_request, current_app, g, render_template, request

from shared.kindle import is_kindle_user_agent
from shared.reader.config import ReaderConfig
from shared.reader.index import ReaderIndexMixin

FONT_SIZES = range(1, 6)
DEFAULT_FONT_SIZE = 3
COOKIE_AGE = 365 * 24 * 3600


def kindle_mode() -> bool:
    """?kindle= wins, then the remembered choice, then the user agent."""
    choice = request.args.get('kindle') or request.cookies.get('kindle')
    if choice in ('0', '1'):
        return choice == '1'
    return is_kindle_user_agent(request.headers.get('User-Agent'))


def cookie_path() -> str:
    return (request.script_root or '') + '/'


def register_kindle_pages(bp: Blueprint, handlers: Dict[str, Callable[..., Any]], config: ReaderConfig) -> None:
    """Serve `handlers[endpoint](**view_args)` to Kindle browsers on those
    web endpoints. Does nothing when the app's reader has no Kindle feature."""
    if not config.features.kindle:
        return

    @bp.before_app_request
    def serve_kindle_page():
        if request.method != 'GET' or request.endpoint not in handlers:
            return None
        choice = request.args.get('kindle')
        if choice in ('0', '1'):
            @after_this_request
            def remember(response):
                response.set_cookie('kindle', choice, max_age=COOKIE_AGE, path=cookie_path())
                return response
        if not kindle_mode():
            return None
        return handlers[request.endpoint](**(request.view_args or {}))

    @bp.after_app_request
    def vary_on_device(response):
        """These URLs serve different HTML per device, so caches must not mix them."""
        if request.endpoint in handlers:
            response.vary.add('User-Agent')
            response.vary.add('Cookie')
        return response


def account_context(user_db, user_id) -> dict:
    """What the account line and masthead show. `user_db` is None when the
    app has no sign-in; `user_id` is the signed-in reader or None."""
    if user_db is None:
        user_id = None
    user = user_db.get_user_by_id(user_id) if user_id is not None else None
    login = f'{request.script_root}/login'
    return {
        'auth_enabled': user_db is not None,
        'account_email': user['email'] if user else None,
        'signed_in': user_id is not None,
        # Same round trip as the web reader's signinUrl(): logout first, so a
        # stale wrong-account session can't stick.
        'signin_url': f"{login}?logout={quote(login, safe='')}",
    }


def url(path: str, **params) -> str:
    params = {k: v for k, v in params.items() if v not in (None, '')}
    query = f'?{urlencode(params)}' if params else ''
    return f'{request.script_root}{path}{query}'


def page_number() -> int:
    try:
        return max(1, int(request.args.get('page', 1)))
    except ValueError:
        return 1


def paginate(items, size, page):
    pages = max(1, -(-len(items) // size))
    page = min(page, pages)
    return items[(page - 1) * size:page * size], page, pages


def font_size() -> int:
    config = current_app.extensions.get('reader_config')
    options = config.kindle if config else None
    default = options.font_size_default if options else DEFAULT_FONT_SIZE
    maximum = options.font_size_max if options else max(FONT_SIZES)
    try:
        size = int(request.cookies.get('kfs', default))
    except ValueError:
        return default
    return size if 1 <= size <= maximum else default


def font_family() -> str:
    config = current_app.extensions.get('reader_config')
    options = config.kindle if config else None
    if not options or not options.font_choices:
        return 'system'
    choice = request.cookies.get('kff', options.font_default)
    return choice if choice in dict(options.font_choices) else options.font_default


def render(template, user_db, user_id, **context):
    resp = render_template(template, **account_context(user_db, user_id), **context)
    return resp, 200, {'Cache-Control': 'private, no-cache'}


LIBRARY_PAGE_SIZE = 7
READING_ON_HOME = 3
CONTENTS_PAGE_SIZE = 8
_ACCOUNT = object()


def _progress_routes():
    # Imported at call time so the app's current shared.progress.routes is always
    # the one read (tests purge and re-import that module).
    from shared.progress import routes
    return routes


def account_user_id():
    """The signed-in reader whose progress syncs, or None (signed out, or the
    app has no sign-in). Set per request by pchauth."""
    return g.get('user_id') if _progress_routes().user_db is not None else None


def render_page(template, user_id=_ACCOUNT, **context):
    """Render the app's `kindle/<template>` with the account line. `user_id`
    defaults to the signed-in reader; an app with its own auth boundary passes it."""
    if user_id is _ACCOUNT:
        user_id = account_user_id()
    return render(f'kindle/{template}', _progress_routes().user_db, user_id, **context)


def not_found_page(user_id=_ACCOUNT):
    """The shared 404 page as a (body, 404, headers) response."""
    if user_id is _ACCOUNT:
        user_id = account_user_id()
    resp, _, headers = render('shared/kindle/not_found.html', _progress_routes().user_db, user_id)
    return resp, 404, headers


def saved_marker(user_db, content_db, user_id, book_id, modes) -> Optional[tuple]:
    """(chapter_id, ordinal, mode) of the account's current position in its
    last-used reading mode, or None when that mode is not in `modes` (e.g. a
    summary position isn't a place in the text) or the marker is gone. The
    marker goes through `recover_reader_marker` to survive content changes."""
    projection = user_db.get_book_projection(user_id, book_id)
    mode = (projection.get('book') or {}).get('last_mode')
    state = next((m for m in projection['modes'] if m['mode'] == mode), None)
    marker = state and state.get('current_marker')
    if mode not in modes or not marker:
        return None
    marker = content_db.recover_reader_marker(book_id, {**marker, 'mode': mode})
    coords = marker and ReaderIndexMixin._reader_parse_unit_id(marker['paragraph_id'])
    if not coords:
        return None
    return coords[0], coords[1], mode
