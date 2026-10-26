"""shared.kindle: config-driven Kindle pages, progress and assets, tested on
a bare Flask app with a fake host (no Plainly)."""
import re
from pathlib import Path

import pytest
from flask import Blueprint, Flask, render_template_string

from shared import web
from shared.auth import user_models
from shared.kindle import pages, progress
from shared.reader.config import KindleOptions, ReaderConfig, ReaderFeatures, ReaderMode

ROOT = Path(__file__).resolve().parents[2]
KINDLE_UA = ('Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ '
             '(KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+')
DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130.0.0.0 Safari/537.36'


def make_config(kindle=True, text_modes=(('plain', 'Plain'), ('original', 'Original'))):
    return ReaderConfig(
        app_name='Host', cache_db_name='host', cache_visibility='private',
        modes=(ReaderMode('original', 'Original'), ReaderMode('plain', 'Plain')),
        default_modes=('original',), features=ReaderFeatures(kindle=kindle),
        kindle=KindleOptions(text_modes, text_modes[0][0]) if kindle else None,
    )


def make_app(config):
    """Two web routes in blueprint 'pages'; Kindle serves only pages.index."""
    app = Flask(__name__)
    web.install_shared_ui(app)
    bp = Blueprint('pages', __name__)

    @bp.route('/')
    def index():
        return 'WEB'

    @bp.route('/other')
    def other():
        return 'WEB OTHER'

    @bp.route('/books/<slug>')
    def book(slug):
        return 'WEB BOOK'

    app.register_blueprint(bp)
    kbp = Blueprint('kindle', __name__)
    pages.register_kindle_pages(
        kbp, {'pages.index': lambda: 'KINDLE', 'pages.book': lambda slug: f'KINDLE {slug}'}, config)
    app.register_blueprint(kbp)
    return app


def get(app, path, ua=KINDLE_UA, **kw):
    return app.test_client().get(path, headers={'User-Agent': ua}, **kw)


def test_register_kindle_pages_noop_when_feature_off():
    app = make_app(make_config(kindle=False))
    resp = get(app, '/')
    assert resp.get_data(as_text=True) == 'WEB'
    assert 'Vary' not in resp.headers


def test_dispatches_only_in_kindle_mode():
    app = make_app(make_config())
    assert get(app, '/').get_data(as_text=True) == 'KINDLE'
    assert get(app, '/books/moby').get_data(as_text=True) == 'KINDLE moby'
    assert get(app, '/', ua=DESKTOP_UA).get_data(as_text=True) == 'WEB'
    assert get(app, '/other').get_data(as_text=True) == 'WEB OTHER'
    assert get(app, '/?kindle=0').get_data(as_text=True) == 'WEB'
    assert get(app, '/?kindle=1', ua=DESKTOP_UA).get_data(as_text=True) == 'KINDLE'
    assert app.test_client().post('/', headers={'User-Agent': KINDLE_UA}).status_code == 405


def test_kindle_query_sets_cookie_on_app_path():
    app = make_app(make_config())
    resp = get(app, '/?kindle=1', ua=DESKTOP_UA, base_url='http://localhost/')
    cookie = resp.headers['Set-Cookie']
    assert cookie.startswith('kindle=1') and 'Path=/' in cookie
    with app.test_request_context('/x', base_url='http://localhost/host/'):
        assert pages.cookie_path() == '/host/'


def test_vary_headers_on_kindle_endpoints():
    app = make_app(make_config())
    vary = get(app, '/', ua=DESKTOP_UA).headers['Vary']
    assert 'User-Agent' in vary and 'Cookie' in vary
    assert 'Vary' not in get(app, '/other').headers


def test_helpers_paginate_and_url():
    app = Flask(__name__)
    assert pages.paginate(list(range(10)), 4, 2) == ([4, 5, 6, 7], 2, 3)
    assert pages.paginate(list(range(10)), 4, 9) == ([8, 9], 3, 3)
    assert pages.paginate([], 4, 1) == ([], 1, 1)
    with app.test_request_context('/x?page=abc', base_url='http://localhost/host/'):
        assert pages.page_number() == 1
        assert pages.url('/books', q='a b', page=None, x='') == '/host/books?q=a+b'
    with app.test_request_context('/x?page=0'):
        assert pages.page_number() == 1
    with app.test_request_context('/x', headers={'Cookie': 'kfs=5'}):
        assert pages.font_size() == 5
    with app.test_request_context('/x', headers={'Cookie': 'kfs=9'}):
        assert pages.font_size() == 3


def render_reader(config, text_urls, text='plain'):
    app = Flask(__name__)
    web.install_shared_ui(app)
    app.jinja_env.globals['asset_v'] = lambda f: ''
    app.jinja_env.globals['base_path'] = ''
    template = ("{% extends 'shared/kindle/reader_base.html' %}"
                "{% block flow_class %} verse{% endblock %}"
                "{% block flow_body %}<p data-i=\"0\">Hi</p>{% endblock %}")
    book = {'id': 1, 'slug': 's', 'title': 'T'}
    chapter = {'chapter_number': 1, 'chapter_title': 'One'}
    with app.test_request_context('/'):
        return render_template_string(
            template, reader_config=config, app_name=config.app_name, book=book, chapter=chapter,
            text=text, text_urls=text_urls, font_size=3, start=0, chars_before=0, chapter_chars=1,
            total_chars=1, cookie_path='/', sync_url=None, prev_url=None, next_url=None,
            next_title=None, auth_enabled=False, signed_in=False, signin_url='')


def test_text_row_hidden_for_single_text_mode():
    one = make_config(text_modes=(('original', 'Original'),))
    html = render_reader(one, {'original': '/o'}, text='original')
    assert 'row-label">Text' not in html
    two = render_reader(make_config(), {'plain': '/p', 'original': '/o'})
    assert 'row-label">Text' in two
    assert re.search(r'class="btn keep on" href="/p">Plain</a>', two)
    assert re.search(r'class="btn keep" href="/o">Original</a>', two)
    assert '<title>One — T</title>' in two and 'flow verse' in two and 'data-i="0"' in two


def test_text_row_omits_modes_without_a_url():
    html = render_reader(make_config(), {'original': '/o'}, text='original')
    assert '>Plain</a>' not in html and 'href="/o"' in html


def test_account_context_and_render(tmp_path):
    users = user_models.UserDatabase(tmp_path / 'u.db')
    uid = users.upsert_user_by_email('a@example.com')
    app = Flask(__name__)
    with app.test_request_context('/x', base_url='http://localhost/host/'):
        ctx = pages.account_context(users, uid)
        assert ctx['auth_enabled'] and ctx['signed_in'] and ctx['account_email'] == 'a@example.com'
        out = pages.account_context(users, None)
        assert out['signed_in'] is False and out['signin_url'] == '/host/login?logout=%2Fhost%2Flogin'
        assert pages.account_context(None, 5)['signed_in'] is False
        assert pages.account_context(None, None)['auth_enabled'] is False


def test_shared_glue_account_user_id_render_page_and_not_found(monkeypatch):
    from flask import g
    from shared.progress import routes as progress_routes
    assert (pages.LIBRARY_PAGE_SIZE, pages.READING_ON_HOME, pages.CONTENTS_PAGE_SIZE) == (7, 3, 8)
    app = Flask(__name__)
    web.install_shared_ui(app)
    app.jinja_env.globals['asset_v'] = lambda f: ''
    with app.test_request_context('/'):
        g.user_id = 5
        monkeypatch.setattr(progress_routes, 'user_db', None)
        assert pages.account_user_id() is None   # auth off: nobody is signed in
        monkeypatch.setattr(progress_routes, 'user_db', type(
            'Users', (), {'get_user_by_id': staticmethod(lambda uid: {'email': 'a@example.com'})})())
        assert pages.account_user_id() == 5
        body, status_code, headers = pages.not_found_page()
        assert status_code == 404 and headers['Cache-Control'] == 'private, no-cache'
        # An explicit id (an app's own auth boundary) overrides the default.
        assert pages.account_user_id() == 5
        body, status_code, _ = pages.not_found_page(user_id=None)
        assert status_code == 404


class FakeContent:
    def __init__(self, terminal='1.3'):
        self.terminal = terminal

    def resolve_reader_marker(self, book_id, marker):
        if marker['paragraph_id'] == 'bad':
            return None
        chapter, ordinal = map(int, marker['paragraph_id'].split('.'))
        return {'book_id': book_id, 'mode': marker['mode'], 'content_version': 'v1', 'chapter_id': chapter,
                'paragraph_id': marker['paragraph_id'], 'offset': 0.0, 'quote': '',
                'ordinal': ordinal, 'word_position': ordinal * 10}

    def get_reader_manifest(self, book_id):
        return {'modes': [{'mode': 'plain', 'terminal_paragraph_id': self.terminal}]}

    def recover_reader_marker(self, book_id, marker):
        return marker


@pytest.fixture
def users(tmp_path):
    return user_models.UserDatabase(tmp_path / 'u.db')


def status(users, uid):
    return users.get_book_projection(uid, 1)['book']['status']


def record(users, uid, paragraph, **kw):
    args = dict(mode='plain', quote=None, forward=True, seconds=5, finished=False)
    args.update(kw)
    return progress.record_page(users, FakeContent(), uid, 1, paragraph_id=paragraph, **args)


def test_record_page_completion_only_on_terminal_forward(users):
    uid = users.upsert_user_by_email('a@example.com')
    payload, code = record(users, uid, '1.0', quote='Call me', seconds=999)
    assert (code, payload['result']) == (200, 'accepted') and payload['success'] is True
    state = users.get_book_projection(uid, 1)['modes'][0]
    assert state['current_marker']['quote'] == 'Call me'
    # finished but not the terminal paragraph, then terminal but not forward: not finished
    assert record(users, uid, '1.1', finished=True)[1] == 200
    assert status(users, uid) != 'finished'
    assert record(users, uid, '1.3', finished=True, forward=False)[1] == 200
    assert status(users, uid) != 'finished'
    assert record(users, uid, '1.3', finished=True, forward=True)[1] == 200
    assert status(users, uid) == 'finished'


def test_record_page_rejects_unknown_paragraph(users):
    uid = users.upsert_user_by_email('a@example.com')
    assert record(users, uid, 'bad') == ({'error': 'Unknown paragraph'}, 400)


def test_saved_marker_ignores_unlisted_modes(users):
    uid = users.upsert_user_by_email('a@example.com')
    record(users, uid, '7.2')
    content = FakeContent()
    assert pages_saved(users, content, uid, ('plain', 'original')) == (7, 2, 'plain')
    assert pages_saved(users, content, uid, ('original',)) is None
    assert pages_saved(users, content, uid + 1, ('plain',)) is None


@pytest.mark.parametrize('field', ['book_id', 'ch', 'p'])
def test_save_progress_rejects_bool_ints(users, field):
    uid = users.upsert_user_by_email('a@example.com')
    body = {'book_id': 1, 'ch': 1, 'p': 1, 'text': 'plain'}
    body[field] = True
    with Flask(__name__).test_request_context('/', method='POST', json=body):
        response, code = progress.save_progress(
            make_config(), users, FakeContent(), uid, lambda *args: ('1.1', None))
    assert code == 400 and response.get_json() == {'error': 'Invalid position'}


def pages_saved(users, content, uid, modes):
    return pages.saved_marker(users, content, uid, 1, modes)


def test_kindle_js_collects_data_i_units():
    src = (ROOT / 'shared/static/js/kindle.js').read_text()
    assert "getElementsByTagName('*')" in src and "getAttribute('data-i')" in src
    assert "var paragraphs = flow.getElementsByTagName('p')" not in src
    assert "getElementsByTagName('p')[0]" in src   # lineHeight still reads the first <p>


def test_kindle_script_is_es5():
    """The older Kindle browser is WebKit 531 (Safari 4): no let/const,
    arrow functions, classes, template literals or classList."""
    src = (ROOT / 'shared/static/js/kindle.js').read_text()
    for pattern in (r'\blet\s', r'\bconst\s', r'=>', r'\bclass\s', '`', r'classList'):
        assert not re.search(pattern, src), pattern
