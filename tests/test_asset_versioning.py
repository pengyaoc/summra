"""Tests for the static-asset cache-busting helper.

Bug this guards against:
Browsers cache CSS aggressively. When a deploy ships a layout change that
depends on new CSS rules (e.g. the pagination redesign that added
padding-top:51px on .chapter-detail-section to reserve space for the always-on
sticky header), returning users can serve NEW HTML + NEW JS over OLD cached
CSS, producing visual breakage (sticky header overlapping body text, dead nav
buttons because click coordinates landed where the old layout placed them).

The fix: asset_v('css/foo.css') returns '?v=<content-hash>' so the CSS URL
changes whenever style.css's content changes. Different URL → cache miss →
fresh fetch. (Originally this was '?v=<mtime>' — switched to a content hash
since mtime is preserved or reset inconsistently by different deploy paths,
so it can miss a real content change or churn on a no-op one.)

This app previously also ran a service worker with its own CSS caching
strategy (removed 2026-09-07 along with the rest of offline support); that
half of the original fix no longer applies.

These tests cover the URL versioning piece.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture
def client():
    """Flask test client. Imported lazily so the app boots inside the test."""
    from backend import app_base
    return app_base.app.test_client()


@pytest.fixture
def app_ctx():
    """Request context — index.html calls url_for() and asset_v()."""
    from backend import app_base
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
    assert a == b, 'asset_v must be deterministic for unchanged file content'


def test_asset_v_changes_when_file_content_changes(app_ctx, tmp_path, monkeypatch):
    """Editing a file's content produces a new version string, even with the
    mtime bumped to the exact same value both times.

    This is the actual property that makes deploys cache-bust correctly —
    and specifically why this is a content hash rather than the mtime
    itself: a deploy step (git checkout, rsync, a plain file copy) can
    easily preserve or reset mtimes without regard to whether content
    actually changed, which would either miss a real change or churn URLs
    for a no-op one under the old mtime-based scheme.
    """
    asset_v = app_ctx.jinja_env.globals['asset_v']

    fake = tmp_path / 'fake.css'
    monkeypatch.setenv('SUMMRA_STATIC_DIR_OVERRIDE', str(tmp_path))

    fake.write_text('body{}')
    os.utime(fake, (1700000000, 1700000000))
    v1 = asset_v('fake.css')
    assert v1.startswith('?v='), f'unexpected version string: {v1!r}'
    assert v1[3:].isdigit(), f'expected digits after ?v=, got {v1!r}'

    # Same mtime, different content — must still produce a different version.
    fake.write_text('body{color:red}')
    os.utime(fake, (1700000000, 1700000000))
    v2 = asset_v('fake.css')
    assert v2 != v1, 'same mtime but different content must still cache-bust'

    # Bumping mtime with unchanged content must NOT force a re-read/re-hash
    # cache miss to produce a different value — content is what matters.
    os.utime(fake, (1700000100, 1700000100))
    v3 = asset_v('fake.css')
    assert v3 == v2, 'unchanged content must keep the same version even if mtime moves'


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
