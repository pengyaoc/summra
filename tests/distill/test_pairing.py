"""Real HTTP pairing flow and its authorization boundaries."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import re

import pytest
from PIL import Image

from distill.device_pairing import DEVICE_COOKIE, PAIR_COOKIE, PAIR_TTL, SESSION_TTL, digest
from shared.auth.pchauth.config import AuthConfig
from .conftest import ALLOWED, HEADERS

KINDLE = 'Mozilla/5.0 (Linux; U; en-US) AppleWebKit/531.2+ Kindle/3.0+'
KH = {'User-Agent': KINDLE, 'Accept': 'text/html', 'X-Forwarded-Prefix': '/distill'}
PHONE = {**HEADERS, 'User-Agent': 'Mozilla/5.0 (iPhone)', 'X-Forwarded-Prefix': '/distill'}


def get(client, path, headers=KH):
    return client.get(headers.get('X-Forwarded-Prefix', '') + path, headers=headers, base_url='https://localhost')


def csrf(response):
    return re.search(rb'name="csrf" value="([^"]+)"', response.data)[1].decode()


def pending(client):
    response = get(client, '/pair')
    assert response.status_code == 200
    code = re.search(rb'class="code">([A-Z2-9-]+)', response.data)[1].decode().replace('-', '')
    return code


def approve(phone, code):
    response = get(phone, '/pair/approve?code=' + code, PHONE)
    assert response.status_code == 200
    return phone.post('/distill/pair/approve', data={'code': code, 'csrf': csrf(response)},
                      headers=PHONE, base_url='https://localhost')


def pair(client):
    code = pending(client)
    phone = client.application.test_client()
    assert approve(phone, code).status_code == 200
    result = get(client, '/pair')
    assert result.status_code == 302 and result.location == '/distill/'
    return phone


@pytest.mark.parametrize('prefix', ['', '/distill', '/apps/distill'])
def test_pairing_private_library_and_prefixes(client, prefix):
    headers = {**KH, 'X-Forwarded-Prefix': prefix}
    response = get(client, '/', headers)
    assert response.status_code == 302 and response.location == prefix + '/pair'
    response = get(client, '/pair', headers)
    assert response.status_code == 200
    assert (prefix + '/pair/qr.png').encode() in response.data
    cookie = next(c for c in response.headers.getlist('Set-Cookie') if c.startswith(PAIR_COOKIE + '='))
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    assert 'Path=' + prefix + '/' in cookie
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'frame-ancestors' in response.headers['Content-Security-Policy']


def test_full_flow_qr_and_revocation(client):
    code = pending(client)
    assert get(client, '/').status_code == 302
    image = get(client, '/pair/qr.png')
    assert image.mimetype == 'image/png' and Image.open(BytesIO(image.data)).width > 200
    phone = client.application.test_client()
    assert approve(phone, code).status_code == 200
    assert get(client, '/pair').status_code == 302
    assert b'My Book' in get(client, '/').data
    assert get(client, '/pair/approve?code=' + code).status_code == 401
    assert get(client, '/pair/devices').status_code == 401
    # A paired Kindle token does not authenticate a desktop or phone.
    assert get(client, '/', {'User-Agent': 'iPhone', 'X-Forwarded-Prefix': '/distill'}).status_code == 401
    response = get(phone, '/pair/devices', PHONE)
    session_id = re.search(rb'name="device" value="([^"]+)"', response.data)[1].decode()
    assert phone.post('/distill/pair/devices', data={'device': session_id, 'csrf': csrf(response)},
                      headers=PHONE, base_url='https://localhost').status_code == 302
    assert get(client, '/').status_code == 302


@pytest.mark.parametrize('ua', ['Mozilla/5.0 (iPhone)', 'Chrome/149', 'Kindle Fire',
                                  'Kindle/3.0 Silk/3', 'Kindle/3.0 Android 7', 'KFAUWI Kindle/3.0'])
def test_non_kindle_does_not_trigger_pairing(client, ua):
    h = {**KH, 'User-Agent': ua}
    assert get(client, '/?kindle=1', h).status_code == 401
    assert get(client, '/pair', h).location == '/distill/login'
    assert get(client, '/pair/qr.png', h).status_code == 404
    assert b'Distill Kindle sign-in' not in get(client, '/launch', h).data


def test_approval_needs_real_allowed_identity_and_post(client):
    code = pending(client)
    phone = client.application.test_client()
    assert get(phone, '/pair/approve?code=' + code, KH).status_code == 401
    assert get(phone, '/pair/approve?code=' + code, {**PHONE, 'X-Remote-Email': 'other@example.com'}).status_code == 403
    assert get(phone, '/pair/approve?code=' + code, PHONE).status_code == 200
    assert client.application.extensions['distill_pairing'].by_code(code)['email'] is None
    assert phone.post('/distill/pair/approve', data={'code': code}, headers=PHONE, base_url='https://localhost').status_code == 403
    response = get(phone, '/pair/approve?code=' + code, PHONE)
    token = csrf(response)
    assert phone.post('/distill/pair/approve', data={'code': code, 'csrf': token},
                      headers={**PHONE, 'Origin': 'https://evil.example'}, base_url='https://localhost').status_code == 403
    result = phone.post('/distill/pair/approve', data={'code': code, 'csrf': token}, headers=PHONE, base_url='https://localhost')
    assert result.status_code == 200
    assert phone.post('/distill/pair/approve', data={'code': code, 'csrf': token}, headers=PHONE, base_url='https://localhost').status_code == 403


def test_code_is_not_a_redemption_credential(client):
    code = pending(client)
    phone = client.application.test_client()
    assert approve(phone, code).status_code == 200
    attacker = client.application.test_client()
    attacker.set_cookie(PAIR_COOKIE, code, path='/distill/')
    assert get(attacker, '/pair?code=' + code).status_code == 200
    assert get(attacker, '/').status_code == 302
    # Expired browser secrets cannot redeem an approved code.
    store = client.application.extensions['distill_pairing']
    now = store.clock()
    store.clock = lambda: now + PAIR_TTL + 1
    assert get(client, '/pair').status_code == 200
    assert get(client, '/').status_code == 302


def test_one_time_redemption_and_hashed_secrets(client):
    code = pending(client)
    phone = client.application.test_client()
    assert approve(phone, code).status_code == 200
    secret = client.get_cookie(PAIR_COOKIE, path='/distill/').value
    store = client.application.extensions['distill_pairing']
    config = AuthConfig(mode='required', allowed_emails=frozenset({ALLOWED}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.redeem(secret, config), range(2)))
    tokens = [token for token in results if token]
    assert len(tokens) == 1
    with store.connection() as db:
        assert db.execute('SELECT secret_hash FROM pairing_requests WHERE code=?', (code,)).fetchone()[0] == digest(secret)
        assert db.execute('SELECT token_hash FROM device_sessions').fetchone()[0] == digest(tokens[0])
    assert store.identity(tokens[0]).email == ALLOWED
    now = store.clock()
    store.clock = lambda: now + SESSION_TTL + 1
    assert store.identity(tokens[0]) is None


def test_allowlist_rechecked_and_no_identity_override(client):
    pair(client)
    assert get(client, '/', {**KH, 'X-Remote-Email': 'other@example.com'}).status_code == 403
    client.set_cookie(DEVICE_COOKIE, ALLOWED, path='/distill/')
    assert get(client, '/').status_code == 302


def test_creation_rate_limit(client):
    store = client.application.extensions['distill_pairing']
    for _ in range(40):
        assert store.create()
    assert store.create() is None
    assert get(client, '/pair').status_code == 429


def test_allowlist_removal_invalidates_paired_reader(client, monkeypatch):
    pair(client)
    monkeypatch.setattr('distill.device_pairing.is_allowed', lambda email, config: False)
    assert get(client, '/').status_code == 302


def test_kindles_launch_and_api_fail_closed(client):
    assert get(client, '/launch').location == '/distill/pair'
    assert get(client, '/api/library', {**KH, 'Accept': 'application/json'}).status_code == 401
    client.set_cookie(DEVICE_COOKIE, 'forged', path='/distill/')
    assert get(client, '/api/library', {**KH, 'Accept': 'application/json'}).status_code == 401
