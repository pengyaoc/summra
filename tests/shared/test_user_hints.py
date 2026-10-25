"""One-time UI hints (e.g. the reader's swipe hint) are remembered per
account, so a signed-in reader sees each hint once across all devices."""
import importlib
import sys

from shared.auth.user_models import UserDatabase


def test_new_user_has_seen_no_hints(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email('a@example.com')
    assert db.get_seen_hints(user_id) == []


def test_marking_a_hint_seen_is_remembered_and_idempotent(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    user_id = db.upsert_user_by_email('a@example.com')
    db.mark_hint_seen(user_id, 'reader_swipe_mobile')
    db.mark_hint_seen(user_id, 'reader_swipe_mobile')
    assert db.get_seen_hints(user_id) == ['reader_swipe_mobile']


def test_hints_are_per_user(test_db_path):
    db = UserDatabase(db_path=test_db_path)
    a = db.upsert_user_by_email('a@example.com')
    b = db.upsert_user_by_email('b@example.com')
    db.mark_hint_seen(a, 'reader_nav_desktop')
    assert db.get_seen_hints(b) == []


def _client(monkeypatch, tmp_path):
    for mod in ['app_base', 'config', 'progress_routes', 'models', 'user_models', 'whoami']:
        sys.modules.pop(mod, None)
        sys.modules.pop(f'backend.{mod}', None)
    from backend import config as _config
    monkeypatch.setattr(_config, 'FEATURE_AUTH', True, raising=False)
    monkeypatch.setattr(_config, 'USER_DATABASE_PATH', tmp_path / 'users.db', raising=False)
    monkeypatch.setenv('SUMMRA_AUTH_MODE', 'optional')
    monkeypatch.setenv('SUMMRA_ALLOWED_EMAILS', 'me@example.com')
    sys.modules['backend.config'] = _config
    return importlib.import_module('backend.app_base').app.test_client()


ME = {'X-Remote-Email': 'me@example.com'}


def test_check_lists_seen_hints_after_marking(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get('/api/auth/check', headers=ME).json['hints_seen'] == []

    response = client.post('/api/hints/reader_swipe_mobile/seen', headers=ME)
    assert response.status_code == 200
    assert client.get('/api/auth/check', headers=ME).json['hints_seen'] == ['reader_swipe_mobile']


def test_unknown_hint_key_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post('/api/hints/not_a_hint/seen', headers=ME).status_code == 400
    assert client.get('/api/auth/check', headers=ME).json['hints_seen'] == []


def test_signed_out_cannot_mark_hints(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.post('/api/hints/reader_swipe_mobile/seen').status_code == 401
    assert client.get('/api/auth/check').json == {'authenticated': False}
