"""Tests for pchauth wiring into app_base.py (consolidated login,
2026-09-05). Replaces the old password auth_routes/auth_utils tests —
there is no /api/auth/login or /api/auth/register any more, since Apache
owns login entirely in trusted_header mode; see pchauth's spec.
"""
import importlib
import sys

import pytest


def _reload_app_base(monkeypatch, feature_auth: bool, auth_mode: str | None = None, allowed_emails: str | None = None):
    for mod in ['app_base', 'config', 'progress_routes', 'models', 'user_models']:
        sys.modules.pop(mod, None)
        sys.modules.pop(f'backend.{mod}', None)

    from backend import config as _config
    monkeypatch.setattr(_config, 'FEATURE_AUTH', feature_auth, raising=False)
    if auth_mode is not None:
        monkeypatch.setenv('SUMMRA_AUTH_MODE', auth_mode)
    else:
        monkeypatch.delenv('SUMMRA_AUTH_MODE', raising=False)
    if allowed_emails is not None:
        monkeypatch.setenv('SUMMRA_ALLOWED_EMAILS', allowed_emails)
    else:
        monkeypatch.delenv('SUMMRA_ALLOWED_EMAILS', raising=False)

    sys.modules['backend.config'] = _config
    app_base = importlib.import_module('backend.app_base')
    return app_base.app.test_client()


def test_no_auth_login_route_exists():
    """There is no login endpoint any more — Apache owns login entirely."""
    from backend import app_base
    client = app_base.app.test_client()
    assert client.get('/api/auth/login').status_code == 404
    assert client.post('/api/auth/register').status_code == 404


def test_progress_routes_return_404_when_feature_auth_off(monkeypatch):
    client = _reload_app_base(monkeypatch, feature_auth=False)
    assert client.get('/api/progress/all').status_code == 404


def test_off_mode_is_the_default_and_progress_succeeds_without_a_header(monkeypatch):
    """No SUMMRA_AUTH_MODE set (local dev/test default): behaves like the
    old no-login world, not like pchauth's own library default of
    'required' — see app_base.py for why."""
    client = _reload_app_base(monkeypatch, feature_auth=True)
    response = client.get('/api/progress/all')
    assert response.status_code == 200


def test_optional_mode_401s_without_header_and_succeeds_with_it(monkeypatch):
    client = _reload_app_base(
        monkeypatch, feature_auth=True, auth_mode='optional', allowed_emails='me@example.com'
    )
    anon = client.get('/api/progress/all')
    assert anon.status_code == 401

    authed = client.get('/api/progress/all', headers={'X-Remote-Email': 'me@example.com'})
    assert authed.status_code == 200


def test_whoami_check_reflects_signed_out_state(monkeypatch):
    client = _reload_app_base(
        monkeypatch, feature_auth=True, auth_mode='optional', allowed_emails='me@example.com'
    )
    response = client.get('/api/auth/check')
    assert response.status_code == 200
    assert response.json == {'authenticated': False}


def test_whoami_check_reflects_signed_in_state(monkeypatch):
    client = _reload_app_base(
        monkeypatch, feature_auth=True, auth_mode='optional', allowed_emails='me@example.com'
    )
    response = client.get('/api/auth/check', headers={'X-Remote-Email': 'me@example.com'})
    assert response.status_code == 200
    assert response.json['authenticated'] is True
    assert response.json['user']['email'] == 'me@example.com'


def test_authenticated_identity_response_is_never_http_cached(monkeypatch):
    client = _reload_app_base(
        monkeypatch, feature_auth=True, auth_mode='optional', allowed_emails='me@example.com'
    )
    response = client.get('/api/auth/check', headers={'X-Remote-Email': 'me@example.com'})
    assert response.status_code == 200
    assert response.cache_control.no_store
    assert response.cache_control.private
