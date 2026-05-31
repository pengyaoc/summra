"""Tests for the static-asset cache-busting helper.

Bug this guards against:
The service worker (frontend/static/service-worker.js) used to cache CSS with
the CacheFirst strategy and a 30-day max-age. When a deploy shipped a layout
change that depended on new CSS rules (e.g. the pagination redesign that added
padding-top:51px on .chapter-detail-section to reserve space for the always-on
sticky header), returning users served NEW HTML + NEW JS over OLD cached CSS,
producing visual breakage (sticky header overlapping body text, dead nav
buttons because click coordinates landed where the old layout placed them).

Clearing browsing history was not enough on iOS Chrome — users had to
explicitly clear site data to evict the SW cache, which also wipes login state
for every site.

Two complementary fixes ship together:
  1. asset_v('css/foo.css') returns '?v=<mtime>' so the CSS URL changes
     whenever style.css changes. Different URL → SW cache miss → fresh fetch.
  2. The SW CSS strategy itself was switched from CacheFirst to
     StaleWhileRevalidate (see service-worker.js), so even without URL
     versioning, the cache self-heals within one navigation cycle.

These tests cover the URL versioning piece.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture
def client():
    """Flask test client. Imported lazily so the app boots inside the test."""
    import app_base
    return app_base.app.test_client()


@pytest.fixture
def app_ctx():
    """Request context — index.html calls url_for() and asset_v()."""
    import app_base
    with app_base.app.test_request_context('/'):
        yield app_base.app


def test_asset_v_for_existing_file_is_query_suffix(app_ctx):
    """asset_v returns '?v=<digits>' for files that exist on disk."""
    asset_v = app_ctx.jinja_env.globals.get('asset_v')
    assert asset_v is not None, 'asset_v jinja global not registered'
    suffix = asset_v('css/style.css')
    assert suffix.startswith('?v='), f'expected ?v= prefix, got {suffix!r}'
    assert suffix[3:].isdigit(), f'expected digits after ?v=, got {suffix!r}'


def test_asset_v_is_stable_between_calls(app_ctx):
    """Repeated calls on an unchanged file return the same version string."""
    asset_v = app_ctx.jinja_env.globals['asset_v']
    a = asset_v('css/style.css')
    b = asset_v('css/style.css')
    assert a == b, 'asset_v must be deterministic for the same file mtime'


def test_asset_v_changes_when_file_mtime_changes(app_ctx, tmp_path, monkeypatch):
    """Bumping a file's mtime produces a new version string.

    This is the property that makes deploys cache-bust correctly: a new
    style.css with a different mtime gets a different URL, so the service
    worker treats it as an entirely new resource.
    """
    asset_v = app_ctx.jinja_env.globals['asset_v']

    fake = tmp_path / 'fake.css'
    fake.write_text('body{}')
    os.utime(fake, (1700000000, 1700000000))

    monkeypatch.setenv('SUMMRA_STATIC_DIR_OVERRIDE', str(tmp_path))

    v1 = asset_v('fake.css')
    assert v1 == '?v=1700000000', f'unexpected version string: {v1!r}'

    os.utime(fake, (1700000100, 1700000100))
    v2 = asset_v('fake.css')
    assert v2 == '?v=1700000100', f'unexpected version string after bump: {v2!r}'
    assert v1 != v2


def test_asset_v_for_missing_file_returns_empty_string(app_ctx):
    """Missing files yield ''. Composed URL collapses to the un-versioned one,
    matching the previous behavior — no template crash if a file moves."""
    asset_v = app_ctx.jinja_env.globals['asset_v']
    assert asset_v('css/does-not-exist.css') == ''


def test_index_html_links_versioned_stylesheet(client):
    """The rendered index.html must include the version query on style.css."""
    resp = client.get('/')
    assert resp.status_code == 200, f'unexpected status: {resp.status_code}'
    body = resp.get_data(as_text=True)
    assert 'css/style.css?v=' in body, (
        'expected style.css to be cache-busted in index.html; got HTML without ?v= suffix. '
        'Check that the template references {{ asset_v("css/style.css") }} '
        'after url_for("static", filename="css/style.css").'
    )
