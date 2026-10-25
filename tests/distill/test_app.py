import os
import subprocess
import sys
from pathlib import Path

import pytest

from distill.models import DistillDatabase
from shared.auth import whoami
from shared.auth.pchauth.config import AuthConfig
from shared.auth.user_models import UserDatabase
from shared.progress import routes as progress_routes

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = 'me@example.com'
HEADERS = {'X-Remote-Email': ALLOWED}


@pytest.fixture
def app_env(tmp_path, monkeypatch, sample_book, write_book):
    # The reader platform keeps its db handles in module globals (last install
    # wins). Pin them to their current values first so monkeypatch restores
    # them and Plainly tests in the same process are unaffected.
    for module, name in ((progress_routes, 'user_db'), (progress_routes, 'content_db'), (whoami, 'user_db')):
        monkeypatch.setattr(module, name, getattr(module, name))

    from distill.app_base import create_app
    content_db = DistillDatabase(tmp_path / 'distill.db')
    book_id = content_db.import_book(write_book(sample_book))
    user_db = UserDatabase(tmp_path / 'user.db', valid_hints=frozenset({'reader_nav_desktop'}))
    app = create_app(content_db, user_db, AuthConfig(mode='required', allowed_emails=frozenset({ALLOWED})))
    return app.test_client(), content_db, user_db, book_id


@pytest.fixture
def client(app_env):
    return app_env[0]


def test_unknown_email_gets_403_on_pages_images_and_api(client, app_env):
    book_id = app_env[3]
    stranger = {'X-Remote-Email': 'stranger@example.com'}
    for url in ('/', '/books/my-book/images/cover.jpg', f'/api/reader/books/{book_id}/manifest'):
        assert client.get(url, headers=stranger).status_code == 403, url


def test_no_identity_gets_401_in_required_mode(client, app_env):
    for url in ('/', '/books/my-book/images/cover.jpg', f'/api/reader/books/{app_env[3]}/manifest'):
        assert client.get(url).status_code == 401, url


def test_allowed_email_reads_image_private_cache_and_304(client):
    response = client.get('/books/my-book/images/cover.jpg', headers=HEADERS)
    assert response.status_code == 200
    assert response.mimetype == 'image/jpeg' and response.data[:2] == b'\xff\xd8'
    assert response.headers['Cache-Control'] == 'private, max-age=3600'
    etag = response.headers['ETag']

    again = client.get('/books/my-book/images/cover.jpg', headers={**HEADERS, 'If-None-Match': etag})
    assert again.status_code == 304

    assert client.get('/books/my-book/images/nope.jpg', headers=HEADERS).status_code == 404
    assert client.get('/books/no-such-book/images/cover.jpg', headers=HEADERS).status_code == 404


def test_reader_api_responses_are_private(client, app_env):
    book_id = app_env[3]
    manifest = client.get(f'/api/reader/books/{book_id}/manifest', headers=HEADERS)
    assert manifest.status_code == 200
    assert manifest.headers['Cache-Control'].startswith('private')
    segment_id = manifest.get_json()['manifest']['segments'][0]['id']
    segment = client.get(f'/api/reader/books/{book_id}/segments/{segment_id}?mode=summary', headers=HEADERS)
    assert segment.status_code == 200
    assert segment.headers['Cache-Control'].startswith('private')
    assert 'public' not in segment.headers['Cache-Control']
    # Responses that set no Cache-Control of their own get the private default.
    assert client.get('/api/auth/check', headers=HEADERS).headers['Cache-Control'] == 'private, no-cache'


def test_progress_round_trip_into_distill_user_db(client, app_env):
    _, content_db, user_db, book_id = app_env
    chapter = content_db.get_chapters(book_id)[1]
    marker = {'mode': 'summary', 'chapter_id': chapter['id'], 'paragraph_id': f"{chapter['id']}.1", 'offset': 0.5}
    mutation = {
        'mutation_id': 'm1', 'device_id': 'd1', 'device_sequence': 1, 'base_revision': 0,
        'book_id': book_id, 'mode': 'summary', 'event_cause': 'page_turn', 'current_marker': marker,
    }
    response = client.post('/api/progress/v2/mutations', json=mutation, headers=HEADERS)
    assert response.status_code == 200, response.get_json()

    saved = client.get(f'/api/progress/v2/books/{book_id}', headers=HEADERS).get_json()
    assert marker['paragraph_id'] in str(saved)
    import sqlite3
    with sqlite3.connect(user_db.db_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM progress_mutation').fetchone()[0] == 1


def test_page_turn_hint_key_accepted(client):
    assert client.post('/api/hints/reader_nav_desktop/seen', headers=HEADERS).status_code == 200


def _import_app_prod(auth_mode):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DISTILL_')}
    env.update(PYTHONPATH=str(ROOT), DISTILL_DB=':memory:', DISTILL_USER_DB=':memory:')
    if auth_mode:
        env.update(DISTILL_AUTH_MODE=auth_mode, DISTILL_ALLOWED_EMAILS=ALLOWED)
    return subprocess.run([sys.executable, '-c', 'import distill.app_prod'], env=env,
                          capture_output=True, text=True, cwd=ROOT)


@pytest.mark.parametrize('mode', [None, 'off', 'optional'])
def test_app_prod_refuses_without_required_mode(mode):
    result = _import_app_prod(mode)
    assert result.returncode != 0
    assert 'DISTILL_AUTH_MODE' in result.stderr


def test_app_prod_imports_with_required_mode():
    result = _import_app_prod('required')
    assert result.returncode == 0, result.stderr


def test_progress_globals_owned_by_distill_while_app_lives(app_env):
    assert progress_routes.user_db is app_env[2]
    assert whoami.user_db is app_env[2]


def test_progress_globals_restored_for_plainly():
    # Runs after the test above (file order): the fixture's monkeypatch must
    # have handed the globals back, not left Distill's handles installed.
    for installed in (progress_routes.user_db, whoami.user_db):
        assert 'user.db' not in str(getattr(installed, 'db_path', ''))
    assert not hasattr(progress_routes.content_db, 'get_image')
