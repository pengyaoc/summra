"""Tests for FEATURE_AUTH and FEATURE_BLOG feature flags.

These tests verify that:
- When the flag is False, gated routes return 404 (not 403) and are not registered.
- When the flag is True, the routes register and respond normally.
- The sitemap excludes /blog URLs when FEATURE_BLOG is False.

Each test reloads the relevant backend modules so the flag value at import time
takes effect — Flask blueprint registration happens at module import.
"""

import importlib
import sys
import pytest


def _reload_app_base(monkeypatch, feature_auth: bool, feature_blog: bool):
    """Reload backend modules with the requested flag values.

    Returns the Flask test client for the reloaded app.
    """
    # Drop cached modules so module-level blueprint registration re-runs
    for mod in [
        'app_base', 'config', 'auth_routes', 'progress_routes',
        'models', 'user_models',
    ]:
        sys.modules.pop(mod, None)
        sys.modules.pop(f'backend.{mod}', None)

    import config as _config
    monkeypatch.setattr(_config, 'FEATURE_AUTH', feature_auth, raising=False)
    monkeypatch.setattr(_config, 'FEATURE_BLOG', feature_blog, raising=False)
    # Ensure the freshly-imported app_base sees the patched values
    sys.modules['config'] = _config

    import app_base
    importlib.reload(app_base)
    return app_base.app.test_client()


def test_auth_routes_return_404_when_flag_off(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=False)
    assert client.get('/api/auth/check').status_code == 404
    assert client.get('/api/auth/login').status_code == 404
    assert client.get('/api/auth/register').status_code == 404


def test_progress_routes_return_404_when_flag_off(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=False)
    assert client.get('/api/progress/all').status_code == 404
    assert client.get('/api/progress/save').status_code == 404


def test_auth_routes_registered_when_flag_on(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=True, feature_blog=False)
    # /api/auth/check exists when registered; it should NOT return 404.
    # (It may return 200 with a JSON payload or 401, but never 404.)
    resp = client.get('/api/auth/check')
    assert resp.status_code != 404, f'auth blueprint should register, got {resp.status_code}'


def test_blog_routes_return_404_when_flag_off(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=False)
    assert client.get('/blog').status_code == 404
    assert client.get('/blog/some-slug').status_code == 404
    assert client.get('/api/blog').status_code == 404
    assert client.get('/api/blog/some-slug').status_code == 404


def test_blog_routes_registered_when_flag_on(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=True)
    # /blog should return 200 (renders blog index); /api/blog returns 200 JSON.
    assert client.get('/blog').status_code == 200
    assert client.get('/api/blog').status_code == 200


def test_sitemap_excludes_blog_when_flag_off(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=False)
    resp = client.get('/sitemap.xml')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '/blog' not in body, 'sitemap must not contain blog URLs when FEATURE_BLOG=False'


def test_templates_receive_feature_flags(monkeypatch):
    """The home page render call must expose feature_auth / feature_blog
    to templates so frontend Jinja conditionals can read them.
    Verified via the context processor wiring."""
    client = _reload_app_base(monkeypatch, feature_auth=False, feature_blog=False)
    import app_base
    # Trigger a request context so context processors run.
    with app_base.app.test_request_context('/'):
        ctx = {}
        for processor in app_base.app.template_context_processors[None]:
            ctx.update(processor())
        assert 'feature_auth' in ctx, 'context processor must inject feature_auth'
        assert 'feature_blog' in ctx, 'context processor must inject feature_blog'
        assert ctx['feature_auth'] is False
        assert ctx['feature_blog'] is False


def test_tts_handler_module_is_removed():
    """The local Coqui/VITS TTS handler must be deleted."""
    sys.modules.pop('tts_handler', None)
    sys.modules.pop('backend.tts_handler', None)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('tts_handler')
