"""Characterization tests for every /api/* and page route in app_base.py.

These exist as a safety net BEFORE the blueprint split (see the refactor
plan's Phase 3b) — they snapshot each route's status code and top-level
JSON/HTML shape against a seeded temp database, so moving route handlers
into backend/routes/*.py blueprints can be verified to not change behavior.

Every test seeds its own isolated Database (see the `db` fixture) and
monkeypatches it onto the shared `app_base.db` singleton, so tests don't
touch the real data/database.db and don't depend on run order.
"""
import pytest


@pytest.fixture
def db(test_db_path):
    """A freshly seeded temp Database with one author, two categories,
    two books (one fully populated with chapters/summaries/section, one
    minimal), and one blog post — enough surface to exercise every route."""
    from backend import models
    database = models.Database(db_path=test_db_path)

    author_id = database.add_author('Jane Doe', country='UK', bio='A test author')

    cat_fiction = database.add_category('Fiction', description='Fiction books')
    cat_classics = database.add_category('Classics', description='Classic literature')

    book_id = database.add_book(
        title='The Test Novel', author='Jane Doe', filename='test_novel.txt',
        full_text='Full text of the test novel.', author_id=author_id,
    )
    database.update_book_slug(book_id, 'the-test-novel')
    database.add_book_category(book_id, cat_fiction)
    database.add_book_category(book_id, cat_classics)
    database.add_summary(book_id, 'concise', 'A concise summary of the test novel.')
    database.add_summary(book_id, 'medium', 'A medium-length summary of the test novel, with more detail.')
    database.add_summary(book_id, 'comprehensive', 'A comprehensive, chapter-by-chapter summary.')
    database.add_chapter(
        book_id, 1, 'Chapter One', 'Summary of chapter one.',
        chapter_text='The full text of chapter one.',
    )
    database.add_chapter(
        book_id, 2, 'Chapter Two', 'Summary of chapter two.',
        chapter_text='The full text of chapter two.',
    )

    other_book_id = database.add_book(
        title='Another Book', author='Jane Doe', filename='another_book.txt',
        full_text='Full text of another book.', author_id=author_id,
    )
    database.update_book_slug(other_book_id, 'another-book')

    database.add_blog_post(
        'first-post', 'First Post', 'Content of the first post.',
        excerpt='An excerpt.',
    )

    database.ids = {
        'author_id': author_id,
        'book_id': book_id,
        'other_book_id': other_book_id,
        'cat_fiction': cat_fiction,
        'cat_classics': cat_classics,
    }
    return database


@pytest.fixture
def client(db, monkeypatch):
    from backend import app_base
    from backend.routes import common
    # Route handlers live in backend/routes/*.py and read common.db (injected
    # by app_base.py at import time) rather than app_base.db directly — see
    # backend/routes/common.py — so both must be patched for a full swap.
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


# ---------------------------------------------------------------------------
# Page routes (SSR HTML)
# ---------------------------------------------------------------------------

def test_home_page(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert resp.content_type.startswith('text/html')


def test_discover_page(client):
    assert client.get('/discover').status_code == 200


def test_robots_txt(client):
    resp = client.get('/robots.txt')
    assert resp.status_code == 200


def test_manifest_json(client):
    resp = client.get('/manifest.json')
    assert resp.status_code == 200


def test_service_worker_js(client):
    resp = client.get('/service-worker.js')
    assert resp.status_code == 200


def test_offline_page(client):
    assert client.get('/offline').status_code == 200


def test_sitemap_xml(client):
    resp = client.get('/sitemap.xml')
    assert resp.status_code == 200
    assert 'the-test-novel' in resp.get_data(as_text=True)


def test_book_detail_page_found(client):
    assert client.get('/books/the-test-novel').status_code == 200


def test_book_detail_page_not_found(client):
    assert client.get('/books/does-not-exist').status_code == 404


def test_book_summary_page(client):
    assert client.get('/books/the-test-novel/summary').status_code == 200


def test_chapter_detail_page(client):
    assert client.get('/books/the-test-novel/chapters/1').status_code == 200


def test_category_detail_page(client, db):
    resp = client.get(f"/categories/{db.ids['cat_fiction']}")
    assert resp.status_code == 200


def test_all_categories_page(client):
    assert client.get('/categories').status_code == 200


def test_all_books_page(client):
    assert client.get('/books').status_code == 200


def test_author_detail_page(client):
    resp = client.get('/authors/jane-doe')
    assert resp.status_code == 200


def test_author_detail_page_not_found(client):
    assert client.get('/authors/nobody-here').status_code == 404


# ---------------------------------------------------------------------------
# API routes — books / chapters / summaries
# ---------------------------------------------------------------------------

def test_api_books_list(client):
    resp = client.get('/api/books')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert isinstance(data['books'], list)
    assert len(data['books']) == 2


def test_api_book_detail(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert data['book']['title'] == 'The Test Novel'


def test_api_book_detail_not_found(client):
    resp = client.get('/api/books/999999')
    assert resp.status_code == 404
    assert resp.get_json()['success'] is False


def test_api_summary_concise(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/summary/concise")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True


def test_api_summary_invalid_type(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/summary/bogus")
    assert resp.status_code == 400


def test_api_summary_book_not_found(client):
    resp = client.get('/api/books/999999/summary/concise')
    assert resp.status_code == 404


def test_api_chapters_list(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/chapters")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    # Flat (no-sections) shape: one synthetic "Chapters" section wrapping
    # the book's chapters — see models.get_book_structure_metadata.
    assert data['has_sections'] is False
    assert len(data['sections']) == 1
    assert len(data['sections'][0]['chapters']) == 2


def test_api_chapter_detail(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/chapters/1")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert data['chapter']['chapter_number'] == 1


def test_continuous_reader_manifest_segments_mapping_and_recovery_routes(client, db):
    """The public reader protocol stays bounded and validates opaque IDs."""
    db.add_chapter(
        db.ids['book_id'], 1, 'Chapter One', 'Summary of chapter one.',
        chapter_text='The full text of chapter one.', modern_english_text='The plain text of chapter one.',
    )
    manifest_response = client.get(f"/api/reader/books/{db.ids['book_id']}/manifest")
    assert manifest_response.status_code == 200
    assert manifest_response.headers['ETag']
    manifest = manifest_response.get_json()['manifest']
    assert 'chapter_text' not in str(manifest)
    assert [mode['mode'] for mode in manifest['modes']] == ['summary', 'original', 'plain', 'side_by_side']
    side_descriptor = next(item for item in manifest['segments'] if item['mode'] == 'side_by_side')
    segment_response = client.get(
        f"/api/reader/books/{db.ids['book_id']}/segments/{side_descriptor['id']}?mode=side_by_side"
    )
    assert segment_response.status_code == 200
    side_unit = segment_response.get_json()['segment']['units'][0]
    assert set(side_unit['members']) == {'original', 'plain'}
    mapped = client.post(f"/api/reader/books/{db.ids['book_id']}/map", json={
        'target_mode': 'plain',
        'marker': {
            'mode': 'side_by_side', 'content_version': manifest['content_version'],
            'chapter_id': side_unit['chapter_id'], 'paragraph_id': side_unit['id'], 'offset': 0,
        },
    })
    assert mapped.status_code == 200
    assert mapped.get_json()['marker']['mode'] == 'plain'
    assert client.get(
        f"/api/reader/books/{db.ids['book_id']}/segments/not-a-real-segment?mode=original"
    ).status_code == 404
    assert client.get(
        f"/api/reader/books/{db.ids['book_id']}/manifest",
        headers={'If-None-Match': manifest_response.headers['ETag']},
    ).status_code == 304


def test_api_summary_configs(client):
    resp = client.get('/api/summary-configs')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# API routes — categories / discover / related
# ---------------------------------------------------------------------------

def test_api_categories_list(client):
    resp = client.get('/api/categories')
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['categories']) == 2


def test_api_category_detail(client, db):
    resp = client.get(f"/api/categories/{db.ids['cat_fiction']}")
    assert resp.status_code == 200


def test_api_category_books(client, db):
    resp = client.get(f"/api/categories/{db.ids['cat_fiction']}/books")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True


def test_api_book_categories(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/categories")
    assert resp.status_code == 200


def test_api_book_related(client, db):
    resp = client.get(f"/api/books/{db.ids['book_id']}/related")
    assert resp.status_code == 200


def test_api_discover_carousels(client):
    resp = client.get('/api/discover/carousels')
    assert resp.status_code == 200


def test_api_books_by_author(client):
    resp = client.get('/api/books/by-author/Jane%20Doe')
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API routes — authors
# ---------------------------------------------------------------------------

def test_api_author_detail(client):
    resp = client.get('/api/authors/jane-doe')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert data['author']['name'] == 'Jane Doe'


def test_api_author_detail_not_found(client):
    resp = client.get('/api/authors/nobody-here')
    assert resp.status_code == 404


def test_api_author_books(client):
    resp = client.get('/api/authors/jane-doe/books')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert len(data['books']) == 2


def test_api_author_books_not_found(client):
    resp = client.get('/api/authors/nobody-here/books')
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Blog routes (only registered when FEATURE_BLOG=True)
# ---------------------------------------------------------------------------

def test_blog_routes_absent_when_flag_off(client):
    # FEATURE_BLOG defaults to False; these must 404 cleanly, not error.
    assert client.get('/blog').status_code == 404
    assert client.get('/api/blog').status_code == 404


@pytest.fixture
def blog_client(db, monkeypatch):
    """A test client with FEATURE_BLOG forced on and app_base reloaded so
    the blog blueprint routes register (they're read at module-import time)."""
    import importlib
    import sys
    from backend import config as _config

    monkeypatch.setattr(_config, 'FEATURE_BLOG', True, raising=False)
    for mod in ['app_base', 'auth_routes', 'progress_routes', 'models', 'user_models']:
        sys.modules.pop(f'backend.{mod}', None)
    sys.modules['backend.config'] = _config

    app_base = importlib.import_module('backend.app_base')
    from backend.routes import common
    # Reloading app_base re-executes `db = models.Database()` (a fresh
    # instance pointing at the REAL config.DATABASE_PATH) and re-injects it
    # into common.db — patch that too, or route handlers read real data.
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    yield app_base.app.test_client()

    # Restore a clean backend.app_base for any test running after this one.
    sys.modules.pop('backend.app_base', None)
    monkeypatch.setattr(_config, 'FEATURE_BLOG', False, raising=False)
    importlib.import_module('backend.app_base')


def test_blog_index_page_when_flag_on(blog_client):
    assert blog_client.get('/blog').status_code == 200


def test_blog_post_page_when_flag_on(blog_client):
    assert blog_client.get('/blog/first-post').status_code == 200


def test_blog_post_page_not_found_when_flag_on(blog_client):
    assert blog_client.get('/blog/no-such-post').status_code == 404


def test_api_blog_list_when_flag_on(blog_client):
    resp = blog_client.get('/api/blog')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert len(data['posts']) == 1


def test_api_blog_post_when_flag_on(blog_client):
    resp = blog_client.get('/api/blog/first-post')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['success'] is True
    assert data['post']['title'] == 'First Post'


def test_api_blog_post_not_found_when_flag_on(blog_client):
    resp = blog_client.get('/api/blog/no-such-post')
    assert resp.status_code == 404
