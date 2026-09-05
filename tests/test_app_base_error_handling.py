"""Regressions for error-handling bugs found in the 2026-09 refactor audit.

1. get_author()/get_author_books() reference `author_name` inside their
   `except` blocks, but it is only assigned inside the `try`. If
   slug_to_author_name() (which hits the DB) raises before that assignment
   completes, the except handler itself raises UnboundLocalError instead of
   returning the intended JSON 500 — turning a clean error response into an
   unhandled crash.

2. The global 404 handler returns JSON for every unmatched URL, including
   ordinary page navigation (e.g. a typo'd /books/<slug> URL). Page routes
   should fall through to the SPA shell so client-side routing / friendly
   404 UI can take over; only /api/* misses should get a JSON 404.
"""
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from backend import app_base
    app_base.app.testing = True
    return app_base.app.test_client()


def test_get_author_returns_json_500_when_lookup_raises(client):
    """Reproduces the bug: slug_to_author_name() raising must not crash the
    except handler with UnboundLocalError. The response must be the intended
    clean JSON 500, not an unhandled exception."""
    # The authors.py blueprint reads backend.routes.common.db (injected by
    # app_base.py at import time), not app_base.db directly — see
    # backend/routes/common.py.
    from backend.routes import common

    with patch.object(common.db, 'get_all_authors', side_effect=RuntimeError("db exploded")):
        resp = client.get('/api/authors/some-author')

    assert resp.status_code == 500
    data = resp.get_json()
    assert data is not None, "handler crashed instead of returning JSON"
    assert data['success'] is False


def test_get_author_books_returns_json_500_when_lookup_raises(client):
    from backend.routes import common

    with patch.object(common.db, 'get_all_authors', side_effect=RuntimeError("db exploded")):
        resp = client.get('/api/authors/some-author/books')

    assert resp.status_code == 500
    data = resp.get_json()
    assert data is not None, "handler crashed instead of returning JSON"
    assert data['success'] is False


def test_unmatched_page_url_renders_spa_shell_not_json(client):
    """A typo'd page URL (no /api/ prefix) must fall through to the SPA
    shell (index.html) so client-side routing can render a friendly 404,
    not a bare JSON error body."""
    resp = client.get('/this-page-does-not-exist')
    assert resp.status_code == 404
    assert resp.content_type.startswith('text/html'), (
        f"expected the SPA shell (text/html), got {resp.content_type!r} — "
        "the global 404 handler is returning JSON for a page route"
    )


def test_unmatched_api_url_still_returns_json_404(client):
    """/api/* misses must keep returning JSON — only page routes change."""
    resp = client.get('/api/this-endpoint-does-not-exist')
    assert resp.status_code == 404
    data = resp.get_json()
    assert data is not None
    assert data['success'] is False
