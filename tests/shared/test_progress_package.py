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
