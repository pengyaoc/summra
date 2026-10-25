"""Book detail page renders its header (title, author, cover) server-side and
embeds everything the client needs to render without /api/books.

Bug this guards against: /books/<slug> shipped an empty header and the client
waited for the full /api/books catalog just to resolve the slug before
fetching the book's own data — seconds of blank page on mobile networks.
"""
import json
import re

import pytest


@pytest.fixture
def client(test_db_path, monkeypatch):
    from plainly import app_base, models
    from plainly.routes import common
    db = models.Database(db_path=test_db_path)
    book_id = db.add_book(title='Journey & Co', author='Jules Verne',
                          filename='pg18857.txt', full_text='x')
    db.update_book_slug(book_id, 'journey-co')
    db.update_book_cover(book_id, 18857, 'covers/69.png')
    plain = db.add_book(title='No Cover', author='Anon', filename='nc.txt', full_text='x')
    db.update_book_slug(plain, 'no-cover')
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    c = app_base.app.test_client()
    c.book_id = book_id
    return c


def _initial_data(body):
    m = re.search(r'window\.__INITIAL_DATA__ = (\{.*?\});\n', body)
    assert m, '__INITIAL_DATA__ missing'
    return json.loads(m.group(1))


def test_book_header_is_server_rendered(client):
    body = client.get('/books/journey-co').get_data(as_text=True)
    assert re.search(r'<h2 id="book-title">Journey &amp; Co</h2>', body)
    assert re.search(r'id="book-author">by <a href="/authors/jules-verne" class="author-link">Jules Verne</a>', body)

    cover = re.search(r'<picture id="book-info-cover">(.*?)</picture>', body, re.S)
    assert cover, 'cover <picture> not server-rendered'
    assert 'srcset="/static/covers/69.webp"' in cover.group(1)
    assert 'src="/static/covers/69.jpg"' in cover.group(1)
    assert 'loading="lazy"' not in cover.group(1)


def test_initial_data_carries_book_fields_client_needs(client):
    data = _initial_data(client.get('/books/journey-co').get_data(as_text=True))
    assert data['book'] == {
        'id': client.book_id, 'title': 'Journey & Co', 'author': 'Jules Verne',
        'slug': 'journey-co', 'cover_image_url': '/static/covers/69.png',
    }


@pytest.mark.parametrize('suffix', ['/summary', '/read', '/chapters/1'])
def test_other_book_routes_embed_same_book_shape(client, suffix):
    """The client renders these routes from __INITIAL_DATA__.book too, and may
    reuse that object for the book page after in-app navigation."""
    from plainly.routes import common
    common.db.add_summary(client.book_id, 'concise', 'Concise.')
    common.db.add_summary(client.book_id, 'medium', 'Medium.')
    common.db.add_chapter(client.book_id, 1, 'One', 'Summary.', chapter_text='Text.')
    resp = client.get(f'/books/journey-co{suffix}')
    assert resp.status_code == 200
    assert _initial_data(resp.get_data(as_text=True))['book'] == {
        'id': client.book_id, 'title': 'Journey & Co', 'author': 'Jules Verne',
        'slug': 'journey-co', 'cover_image_url': '/static/covers/69.png',
    }


def test_book_without_cover_keeps_hidden_placeholder(client):
    body = client.get('/books/no-cover').get_data(as_text=True)
    assert '<picture id="book-info-cover">' not in body
    assert re.search(r'<img id="book-info-cover" class="book-detail-cover hidden"', body)
    assert _initial_data(body)['book']['cover_image_url'] is None


def test_prefixed_book_header_urls(client):
    body = client.get('/books/journey-co', headers={'X-Forwarded-Prefix': '/summrabook'}).get_data(as_text=True)
    assert 'href="/summrabook/authors/jules-verne"' in body
    assert 'srcset="/summrabook/static/covers/69.webp"' in body
