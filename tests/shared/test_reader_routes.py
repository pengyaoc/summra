import pytest
from flask import Flask, g

from shared.auth import whoami
from shared.progress import routes as progress_routes
from shared.reader.config import ReaderConfig, ReaderFeatures, ReaderMode
from shared.reader.platform import install_reader_platform


class FakeDB:
    def __init__(self, tag='a'):
        self.tag = tag

    def get_reader_manifest(self, book_id):
        if book_id == 99:
            raise ValueError('no such book')
        return {'etag': f'm-{self.tag}', 'book_id': book_id}

    def get_reader_segment(self, book_id, segment_id, mode):
        if segment_id == 'missing':
            return None
        return {'etag': 's1', 'text': self.tag}

    def map_reader_marker(self, book_id, marker, target_mode):
        return None

    def recover_reader_marker(self, book_id, marker):
        return {'paragraph_id': '1.0'}


def config(visibility='public', progress=False):
    return ReaderConfig(
        app_name='T', cache_db_name='t', cache_visibility=visibility,
        modes=(ReaderMode('original', 'Original'),), default_modes=('original',),
        features=ReaderFeatures(progress=progress, kindle=False))


@pytest.fixture(autouse=True)
def restore_globals(monkeypatch):
    for module, attr in ((progress_routes, 'user_db'), (progress_routes, 'content_db'), (whoami, 'user_db')):
        monkeypatch.setattr(module, attr, getattr(module, attr))


def client_for(cfg, get_db, user_db=None):
    app = Flask(__name__)
    install_reader_platform(app, cfg, get_db, user_db)
    return app.test_client()


def test_manifest_public_by_default_config():
    c = client_for(config(), lambda: FakeDB())
    r = c.get('/api/reader/books/1/manifest')
    assert r.status_code == 200
    assert r.headers['Cache-Control'] == 'public, max-age=300, must-revalidate'
    assert c.get('/api/reader/books/99/manifest').status_code == 404


def test_private_visibility_marks_manifest_and_segment_private():
    c = client_for(config('private'), lambda: FakeDB())
    assert c.get('/api/reader/books/1/manifest').headers['Cache-Control'] == 'private, max-age=300, must-revalidate'
    seg = c.get('/api/reader/books/1/segments/s?mode=original')
    assert seg.headers['Cache-Control'] == 'private, max-age=31536000, immutable'


def test_segment_404_json_on_unknown():
    r = client_for(config(), lambda: FakeDB()).get('/api/reader/books/1/segments/missing?mode=original')
    assert r.status_code == 404 and r.get_json()['success'] is False


def test_map_requires_marker_400():
    c = client_for(config(), lambda: FakeDB())
    assert c.post('/api/reader/books/1/map', json={}).status_code == 400
    assert c.post('/api/reader/books/1/recover', json={'marker': 'x'}).status_code == 400
    assert c.post('/api/reader/books/1/map', json={'marker': {}, 'target_mode': 'plain'}).status_code == 404


def test_db_resolved_per_request():
    current = {'db': FakeDB('one')}
    c = client_for(config(), lambda: current['db'])
    assert c.get('/api/reader/books/1/segments/s?mode=original').get_json()['segment']['text'] == 'one'
    current['db'] = FakeDB('two')
    assert c.get('/api/reader/books/1/segments/s?mode=original').get_json()['segment']['text'] == 'two'


def test_progress_feature_off_leaves_progress_and_auth_check_404():
    c = client_for(config(progress=False), lambda: FakeDB(), user_db=object())
    assert c.get('/api/progress/v2/books/1').status_code == 404
    assert c.get('/api/library').status_code == 404
    assert c.get('/api/auth/check').status_code == 404


def test_progress_feature_on_registers_progress_and_whoami_routes():
    app = Flask(__name__)
    app.before_request(lambda: setattr(g, 'user_id', None))  # what pchauth does for an anonymous caller
    install_reader_platform(app, config(progress=True), lambda: FakeDB(), object())
    c = app.test_client()
    library = c.get('/api/library')
    assert library.status_code == 401
    assert library.get_json() == {'error': 'Authentication required'}
    check = c.get('/api/auth/check')
    assert check.status_code == 200
    assert check.get_json() == {'authenticated': False}


def test_no_user_db_leaves_progress_globals_untouched():
    sentinel_user, sentinel_db = object(), object()
    progress_routes.user_db, progress_routes.content_db = sentinel_user, sentinel_db
    whoami.user_db = sentinel_user
    client_for(config(progress=False), lambda: FakeDB(), user_db=None)
    assert progress_routes.user_db is sentinel_user
    assert progress_routes.content_db is sentinel_db
    assert whoami.user_db is sentinel_user


def test_platform_sets_progress_globals_even_when_feature_off():
    db, user = FakeDB(), object()
    client_for(config(progress=False), lambda: db, user_db=user)
    assert progress_routes.user_db is user
    assert progress_routes.content_db is db
    assert whoami.user_db is user
