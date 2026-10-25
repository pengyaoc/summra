"""Characterization tests: the reader shell and the Kindle pages render the
same markup before and after the reader files move into shared/.

Golden files live in tests/plainly/golden/. Regenerate on purpose with
UPDATE_GOLDEN=1 (only when Plainly's markup is meant to change).
"""
import os
import re
from pathlib import Path

from .test_kindle_mode import client, kget, body, DESKTOP  # noqa: F401

GOLDEN = Path(__file__).parent / 'golden'


def _squash(html):
    # Asset cache-busting hashes change with file content, not structure.
    return re.sub(r'\s+', ' ', re.sub(r'\?v=\d+', '?v=N', html)).strip()


def _shell(html):
    start = html.index('id="continuous-reader-section"')
    end = html.index('<!-- Category Detail Section -->')
    return _squash(html[start:end])


def _kindle_body(html):
    start = html.index('<body')
    end = html.index('</body>') + len('</body>')
    return _squash(html[start:end])


def _check(name, actual):
    path = GOLDEN / name
    if os.environ.get('UPDATE_GOLDEN'):
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(actual + '\n')
    assert actual == path.read_text().strip(), f'{name} drifted'


def test_reader_shell_markup_unchanged(client):
    html = body(client.get('/books/moby-dick/read', headers={'User-Agent': DESKTOP}))
    _check('reader_shell.html', _shell(html))


def test_kindle_pages_markup_unchanged(client):
    _check('kindle_library.html', _kindle_body(body(kget(client, '/'))))
    _check('kindle_book.html', _kindle_body(body(kget(client, '/books/moby-dick'))))
    _check('kindle_reader.html', _kindle_body(body(kget(client, '/books/moby-dick/read?ch=1'))))
