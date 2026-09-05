"""Regression: SECRET_KEY must not silently regenerate per process.

app_base.py fell back to `secrets.token_hex(32)` when SECRET_KEY was unset.
Under gunicorn each worker process imports app_base independently, so each
worker got a *different* random key — session cookies signed by one worker
fail to validate on another, breaking auth. This is latent today only
because FEATURE_AUTH=False; it must fail fast (not silently work-and-break)
once auth is turned on.
"""
import importlib
import sys

import pytest


def _reload_app_base(monkeypatch, feature_auth: bool, secret_key=None, delete_env=False):
    for mod in ['app_base', 'config', 'auth_routes', 'progress_routes', 'models', 'user_models']:
        sys.modules.pop(mod, None)
        sys.modules.pop(f'backend.{mod}', None)

    from backend import config as _config
    monkeypatch.setattr(_config, 'FEATURE_AUTH', feature_auth, raising=False)

    if delete_env:
        monkeypatch.delenv('SECRET_KEY', raising=False)
    elif secret_key is not None:
        monkeypatch.setenv('SECRET_KEY', secret_key)

    sys.modules['backend.config'] = _config
    # `from backend import app_base` would silently return backend's stale
    # cached `app_base` attribute (never cleared by the sys.modules.pop
    # above) instead of re-executing the module — import_module correctly
    # detects it's missing from sys.modules and re-imports for real.
    app_base = importlib.import_module('backend.app_base')
    return app_base


def test_missing_secret_key_fails_fast_when_auth_enabled(monkeypatch):
    """FEATURE_AUTH=True with no SECRET_KEY env var must raise at import time,
    not silently generate a per-process random key."""
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _reload_app_base(monkeypatch, feature_auth=True, delete_env=True)


def test_missing_secret_key_is_fine_when_auth_disabled(monkeypatch):
    """FEATURE_AUTH=False (today's default) must keep working without
    SECRET_KEY set — sessions aren't exercised, so a random per-process key
    is harmless."""
    app_base = _reload_app_base(monkeypatch, feature_auth=False, delete_env=True)
    assert app_base.app.config['SECRET_KEY'] is not None


def test_explicit_secret_key_is_used_when_auth_enabled(monkeypatch):
    app_base = _reload_app_base(monkeypatch, feature_auth=True, secret_key='a-real-secret')
    assert app_base.app.config['SECRET_KEY'] == 'a-real-secret'
