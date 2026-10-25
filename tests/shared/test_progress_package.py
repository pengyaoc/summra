from flask import Flask
from shared.auth import user_models
from shared.auth.pchauth.config import AuthConfig
from shared.auth.pchauth.flask_adapter import init_pchauth
from shared.progress import routes


class _ContentStub:
    get_book = staticmethod(lambda book_id: None)


def test_progress_blueprint_registers_on_bare_app(tmp_path, monkeypatch):
    users = user_models.UserDatabase(tmp_path / 'u.db')
    monkeypatch.setattr(routes, 'user_db', users)
    monkeypatch.setattr(routes, 'content_db', _ContentStub())

    app = Flask(__name__)
    init_pchauth(app, AuthConfig(mode='off'),
                 upsert_user=lambda identity: users.upsert_user_by_email(identity.email))
    app.register_blueprint(routes.progress_bp)

    resp = app.test_client().post('/api/progress/v2/mutations', json={'book_id': 1})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'Unknown book'}


class _SchemaFreeContent:
    """content_db with no SQL connection at all: library_cards must only use hooks."""

    def get_book(self, book_id):
        return {'id': book_id}

    def library_books(self, book_ids):
        return {i: {'id': i, 'slug': f's{i}', 'title': f'T{i}', 'author': 'A', 'cover_image_url': None}
                for i in book_ids if i != 99}

    def chapter_titles(self, chapter_ids):
        return {i: {'id': i, 'chapter_number': 3, 'chapter_title': 'Three'} for i in chapter_ids}

    def get_reader_manifest(self, book_id):
        return {'modes': [{'mode': 'original', 'total_word_count': 200}]}


class _StubUsers:
    def get_library_projection(self, user_id):
        marker = {'chapter_id': 7, 'word_position': 50}
        base = {'last_mode': 'original', 'last_meaningful_read_at': 't', 'finished_at': None}
        return [
            {**base, 'book_id': 1, 'status': 'reading',
             'last_mode_state': {'current_marker': marker, 'furthest_marker': marker}},
            {**base, 'book_id': 2, 'status': 'finished', 'last_mode_state': None},
            {**base, 'book_id': 99, 'status': 'reading', 'last_mode_state': None},
        ]


def test_library_cards_use_content_hooks_not_sql(monkeypatch):
    monkeypatch.setattr(routes, 'user_db', _StubUsers())
    monkeypatch.setattr(routes, 'content_db', _SchemaFreeContent())

    cards = routes.library_cards(1)

    reading = cards['continue_reading']
    assert [c['id'] for c in reading] == [1]
    assert reading[0]['title'] == 'T1'
    assert reading[0]['furthest_percentage'] == 25
    assert reading[0]['current_chapter'] == {'id': 7, 'chapter_number': 3, 'chapter_title': 'Three'}
    assert [c['id'] for c in cards['finished']] == [2]
    assert cards['finished'][0]['furthest_percentage'] == 100
    assert cards['finished'][0]['current_chapter'] is None
