"""The page ships the reader config the client reads: parse the JSON out of
Plainly's index.html and compare it to PLAINLY_READER.to_client()."""
import json
import re

from plainly.reader_config import PLAINLY_READER

from .test_kindle_mode import client, body, DESKTOP  # noqa: F401


def test_index_renders_plainly_reader_config(client):  # noqa: F811
    html = body(client.get('/', headers={'User-Agent': DESKTOP}))
    match = re.search(r'<script>window\.READER_CONFIG = (.*?);</script>', html, re.S)
    assert match, 'READER_CONFIG script missing from index.html'
    assert json.loads(match.group(1)) == PLAINLY_READER.to_client()
    assert html.index('window.READER_CONFIG') < html.index('</head>')


def test_auth_js_loads_after_reader_state(client):  # noqa: F811
    """reader_state.js sets a default window.authModule; Plainly's auth.js
    must load after it so Plainly's full module is the one in force."""
    html = body(client.get('/', headers={'User-Agent': DESKTOP}))
    order = [html.index(name) for name in ('shared/js/base_path.js', 'js/route_utils.js',
                                           'shared/js/reader_state.js', '/js/auth.js', '/js/app.')]
    assert order == sorted(order)
