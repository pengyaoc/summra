import copy
import json

import pytest
from PIL import Image

from distill.models import DistillDatabase
from shared.auth import whoami
from shared.auth.pchauth.config import AuthConfig
from shared.auth.user_models import UserDatabase
from shared.progress import routes as progress_routes

SAMPLE_BOOK = {
    'format': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer',
    'lang': 'en', 'cover': 'images/cover.jpg',
    'overview': [{'type': 'p', 'text': 'Hello **world**.'}],
    'parts': [
        {'title': 'Part One', 'chapters': [
            {'title': '1. First', 'blocks': [
                {'type': 'p', 'text': 'one two three'},
                {'type': 'ul', 'items': ['a', 'b']},
                {'type': 'table', 'header': ['h1', 'h2'], 'rows': [['x', 'y']]},
                {'type': 'p', 'text': 'The fourth block has a distinctive phrase.'},
                {'type': 'image', 'src': 'images/cover.jpg', 'caption': None},
            ]},
            {'title': '2. Second', 'blocks': [{'type': 'p', 'text': 'Second chapter.'}]},
        ]},
        {'title': None, 'chapters': [
            {'title': '3. Third', 'blocks': [{'type': 'p', 'text': 'Last block.'}]},
        ]},
    ],
    'sources': [{'type': 'p', 'text': 'src'}],
}


@pytest.fixture
def sample_book():
    return copy.deepcopy(SAMPLE_BOOK)


@pytest.fixture
def write_book(tmp_path):
    """write_book(book_dict) -> folder holding book.json and images/cover.jpg."""
    def _write(book):
        (tmp_path / 'images').mkdir(exist_ok=True)
        Image.new('RGB', (4, 4), 'red').save(tmp_path / 'images' / 'cover.jpg', 'JPEG')
        (tmp_path / 'book.json').write_text(json.dumps(book, ensure_ascii=False))
        return tmp_path
    return _write


ALLOWED = 'me@example.com'
HEADERS = {'X-Remote-Email': ALLOWED}


def pin_platform_globals(monkeypatch):
    # The reader platform keeps its db handles in module globals (last install
    # wins). Pin them to their current values first so monkeypatch restores
    # them and Plainly tests in the same process are unaffected.
    for module, name in ((progress_routes, 'user_db'), (progress_routes, 'content_db'), (whoami, 'user_db')):
        monkeypatch.setattr(module, name, getattr(module, name))


@pytest.fixture
def app_env(tmp_path, monkeypatch, sample_book, write_book):
    pin_platform_globals(monkeypatch)

    from distill.app_base import create_app
    content_db = DistillDatabase(tmp_path / 'distill.db')
    book_id = content_db.import_book(write_book(sample_book))
    user_db = UserDatabase(tmp_path / 'user.db', valid_hints=frozenset({'reader_nav_desktop'}))
    app = create_app(content_db, user_db, AuthConfig(mode='required', allowed_emails=frozenset({ALLOWED})))
    return app.test_client(), content_db, user_db, book_id


@pytest.fixture
def client(app_env):
    return app_env[0]
