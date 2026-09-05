"""Tests for backend/app_prod.py — the production entrypoint's own routes
(everything else is covered by tests/test_api_routes_characterization.py
against the shared app_base routes).

Previously this file was a print-based smoke script collected by pytest as
3 tests with zero assert statements — each "test" returned True/False and
printed instead of failing, so it passed unconditionally regardless of
whether anything actually worked, and it hit the real, 200+MB production
database directly. Rewritten to assert real behavior.

`app_prod` is imported at module level (not inside a fixture) deliberately:
its routes register onto the shared `app_base.app` singleton lazily, on
first import, and Flask refuses to register new routes on an app that has
already served a request (`_got_first_request`). Importing here, at
collection time — before any test in any file has made a request — avoids
a real ordering fragility in the app.py/app_prod.py/app_base.py shared-
singleton design (see the backend audit's app.py-vs-app_prod.py section).
"""
import pytest

from backend import app_prod, models, config  # noqa: F401


def test_app_prod_imports_cleanly():
    from backend import app_prod, models, config  # noqa: F401


@pytest.fixture
def client():
    # app_prod's own routes (/health, /api/tts/*, /api/admin/*) don't touch
    # the database at all, so no seeded db / monkeypatch is needed here.
    app_prod.app.testing = True
    return app_prod.app.test_client()


def test_health_check(client):
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.get_json() == {'status': 'healthy'}


def test_tts_generate_without_cached_audio_returns_404(client):
    """Production never generates TTS live — without a pre-generated file
    cached under this id, the endpoint must say so, not attempt generation."""
    resp = client.post('/api/tts/generate', json={'id': 'no-such-audio-id'})
    assert resp.status_code == 404
    data = resp.get_json()
    assert data['success'] is False


def test_tts_generate_missing_id_returns_400(client):
    resp = client.post('/api/tts/generate', json={})
    assert resp.status_code == 400


def test_tts_stop_is_a_noop(client):
    """No generation happens in prod, so /api/tts/stop must always succeed
    without doing anything — verifies it doesn't error even with no active
    generation to stop."""
    resp = client.post('/api/tts/stop')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_admin_chapter_update_disabled_in_production(client):
    resp = client.put('/api/admin/chapters/1/1', json={})
    assert resp.status_code == 403
    assert resp.get_json()['success'] is False


def test_expected_routes_are_registered():
    """The routes app_prod.py itself defines, plus a couple of shared
    app_base routes it inherits, must all be present on the app object."""
    routes = {str(rule) for rule in app_prod.app.url_map.iter_rules()}
    for expected in ['/health', '/api/tts/generate', '/api/tts/stop', '/api/books']:
        assert any(expected in r for r in routes), f"missing route: {expected}"
