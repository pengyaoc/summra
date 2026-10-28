"""Tests for pchauth wiring into app_base.py (consolidated login,
2026-09-05). Replaces the old password auth_routes/auth_utils tests —
there is no /api/auth/login or /api/auth/register any more, since Apache
owns login entirely in trusted_header mode; see pchauth's spec.
"""
import importlib
import sys

import pytest

from _reload import purge_app_modules


def _reload_app_base(monkeypatch, feature_auth: bool, auth_mode: str | None = None, allowed_emails: str | None = None):
    purge_app_modules()

    from plainly import config as _config
    monkeypatch.setattr(_config, 'FEATURE_AUTH', feature_auth, raising=False)
    if auth_mode is not None:
        monkeypatch.setenv('SUMMRA_AUTH_MODE', auth_mode)
    else:
        monkeypatch.delenv('SUMMRA_AUTH_MODE', raising=False)
    if allowed_emails is not None:
        monkeypatch.setenv('SUMMRA_ALLOWED_EMAILS', allowed_emails)
    else:
        monkeypatch.delenv('SUMMRA_ALLOWED_EMAILS', raising=False)

    sys.modules['plainly.config'] = _config
    app_base = importlib.import_module('plainly.app_base')
    return app_base.app.test_client()


def test_no_auth_login_route_exists():
    """There is no login endpoint any more — Apache owns login entirely."""
    from plainly import app_base
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


KINDLE_UA = 'Mozilla/5.0 AppleWebKit/531.2+ Kindle/3.0+'


@pytest.fixture
def pairing_client(monkeypatch, tmp_path):
    monkeypatch.setenv('SUMMRA_PAIRING_DB', str(tmp_path / 'plainly_pairing.db'))
    return _reload_app_base(monkeypatch, feature_auth=True, auth_mode='optional',
                            allowed_emails='me@example.com')


@pytest.mark.parametrize('prefix', ['', '/plainly', '/apps/plainly'])
def test_plainly_kindles_pair_with_phone_and_revoke(pairing_client, prefix):
    import re
    client = pairing_client
    kh = {'User-Agent': KINDLE_UA, 'X-Forwarded-Prefix': prefix}
    ph = {'User-Agent': 'iPhone', 'X-Forwarded-Prefix': prefix,
          'X-Remote-Email': 'me@example.com'}
    def get(browser, path, headers=kh):
        return browser.get(prefix + path, headers=headers, base_url='https://localhost')
    def csrf(response):
        return re.search(rb'name="csrf" value="([^"]+)"', response.data)[1].decode()
    # Public reading stays public; only choosing sign-in starts pairing.
    assert get(client, '/').status_code == 200
    assert get(client, '/login').location == prefix + '/pair'
    response = get(client, '/pair')
    assert response.status_code == 200 and b'Plainly Kindle sign-in' in response.data
    assert 'no-store' in response.headers['Cache-Control']
    code = re.search(rb'class="code">([A-Z2-9-]+)', response.data)[1].decode().replace('-', '')
    cookie = client.get_cookie('plainly_pair', path=prefix + '/')
    assert cookie.secure and cookie.http_only and cookie.same_site == 'Lax'
    assert get(client, '/pair/qr.png').mimetype == 'image/png'
    phone = client.application.test_client()
    response = get(phone, '/pair/approve?code=' + code, ph)
    token = csrf(response)
    def approve(headers):
        return phone.post(prefix + '/pair/approve', data={'code': code, 'csrf': token},
                          headers=headers, base_url='https://localhost')
    assert approve({**ph, 'Origin': 'https://evil.example'}).status_code == 403
    assert approve(ph).status_code == 200
    assert approve(ph).status_code == 403  # one-time approval/CSRF
    assert get(client, '/pair').location == prefix + '/'
    assert client.get_cookie('plainly_device', path=prefix + '/')
    assert get(client, '/api/auth/check').json['authenticated'] is True
    # Paired readers cannot approve other readers/manage sessions, nor can a
    # copied Distill cookie or a desktop UA authenticate through this path.
    assert get(client, '/pair/devices').status_code == 401
    assert get(client, '/api/auth/check', {**kh, 'User-Agent': 'Chrome'}).json['authenticated'] is False
    other = client.application.test_client()
    other.set_cookie('distill_device', client.get_cookie('plainly_device', path=prefix + '/').value,
                     path=prefix + '/')
    assert get(other, '/api/auth/check').json['authenticated'] is False
    response = get(phone, '/pair/devices', ph)
    device = re.search(rb'name="device" value="([^"]+)"', response.data)[1].decode()
    assert phone.post(prefix + '/pair/devices', data={'device': device, 'csrf': csrf(response)},
                      headers=ph, base_url='https://localhost').status_code == 302
    assert get(client, '/api/auth/check').json['authenticated'] is False
    assert get(client, '/').status_code == 200


@pytest.mark.parametrize('ua', ['iPhone', 'Chrome/149', 'Kindle Fire', 'Kindle/3.0 Silk/3'])
def test_plainly_pairing_is_kindle_only(pairing_client, ua):
    response = pairing_client.get('/pair', headers={'User-Agent': ua})
    assert response.location == '/login'
    assert pairing_client.get('/pair/qr.png', headers={'User-Agent': ua}).status_code == 404
    assert pairing_client.get('/login', headers={'User-Agent': ua}).status_code == 401
