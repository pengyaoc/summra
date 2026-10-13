"""Flask gzips HTML and JSON responses for clients that accept it.

Bug this guards against: prod's Apache front end compresses the static files
it serves itself but passes gunicorn's responses through as-is, so every
page's HTML (~45 KB) and JSON (/api/books ~57 KB, /api/discover/carousels
~100 KB) crossed the network uncompressed (5-10x larger than gzipped).
"""
import gzip
import json

import pytest


@pytest.fixture
def client(test_db_path, monkeypatch):
    from backend import app_base, models
    from backend.routes import common
    db = models.Database(db_path=test_db_path)
    for i in range(40):  # enough rows for /api/books to exceed the size floor
        bid = db.add_book(title=f'Book {i:02d}', author='Author', filename=f'{i}.txt', full_text='x')
        db.update_book_slug(bid, f'book-{i:02d}')
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


GZ = {'Accept-Encoding': 'gzip, deflate, br'}


def test_json_is_gzipped(client):
    plain = client.get('/api/books')
    resp = client.get('/api/books', headers=GZ)
    assert resp.headers['Content-Encoding'] == 'gzip'
    assert 'Accept-Encoding' in resp.headers['Vary']
    assert json.loads(gzip.decompress(resp.data)) == plain.get_json()
    assert int(resp.headers['Content-Length']) == len(resp.data) < len(plain.data)


def test_html_is_gzipped(client):
    resp = client.get('/', headers=GZ)
    assert resp.headers['Content-Encoding'] == 'gzip'
    # Structural marker, not copy: the home headings were rewritten in the
    # 2026-10 redesign ("Where Most Readers Start" became "Start here").
    assert b'id="hero-section"' in gzip.decompress(resp.data)


def test_not_gzipped_without_accept_encoding(client):
    resp = client.get('/api/books')
    assert 'Content-Encoding' not in resp.headers
    assert resp.get_json()['success'] is True


def test_tiny_responses_not_gzipped(client):
    resp = client.get('/api/auth/check', headers=GZ)
    assert 'Content-Encoding' not in resp.headers


def test_etag_stable_and_304_still_works(client):
    first = client.get('/api/books', headers=GZ)
    second = client.get('/api/books', headers=GZ)
    assert first.headers['ETag'] == second.headers['ETag']
    revalidate = client.get('/api/books', headers={**GZ, 'If-None-Match': first.headers['ETag']})
    assert revalidate.status_code == 304


def test_static_files_left_to_front_end(client):
    resp = client.get('/static/css/style.css', headers=GZ)
    assert resp.status_code == 200
    assert 'Content-Encoding' not in resp.headers
