"""The home page's "Where Most Readers Start" carousel is server-rendered.

Bug this guards against: the carousel used to render only after the JS
bundle loaded, executed, and fetched the full /api/books list — a serial
waterfall that left skeleton cards on screen for ~4-5s on mobile networks.
Rendering the cards in the HTML lets the browser start fetching covers
while it parses the page.
"""
import re

import pytest


@pytest.fixture
def db(test_db_path):
    from backend import models
    database = models.Database(db_path=test_db_path)
    # Insert in reverse rank order to prove the server ranks by the
    # curated list, not by insertion order or title.
    pride = database.add_book(title='Pride and Prejudice', author='Jane Austen',
                              filename='pg1342.txt', full_text='x')
    database.update_book_slug(pride, 'pride-and-prejudice')
    database.update_book_cover(pride, 1342, 'covers/5.png')

    frank = database.add_book(title='Frankenstein', author='Mary Shelley',
                              filename='pg84.txt', full_text='x')
    database.update_book_slug(frank, 'frankenstein')
    database.update_book_cover(frank, 84, 'covers/30.png')

    other = database.add_book(title='Not Ranked', author='Nobody',
                              filename='pg999999.txt', full_text='x')
    database.update_book_slug(other, 'not-ranked')
    database.update_book_cover(other, 999999, 'covers/99.jpg')
    return database


def _client(db, monkeypatch):
    from backend import app_base
    from backend.routes import common
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def _carousel(body):
    m = re.search(r'id="top-10-scroll">(.*?)</div>\s*<button class="carousel-nav-btn right"',
                  body, re.S)
    assert m, 'top-10 carousel not found in home HTML'
    return m.group(1)


def test_home_renders_ranked_cards_in_html(db, monkeypatch):
    body = _client(db, monkeypatch).get('/').get_data(as_text=True)
    carousel = _carousel(body)

    hrefs = re.findall(r'<a class="top-10-book-card" href="([^"]+)"', carousel)
    assert hrefs == ['/books/frankenstein', '/books/pride-and-prejudice']
    assert 'not-ranked' not in carousel
    assert 'skeleton-book-card' not in carousel

    # Cards follow the curated list order but carry no "No. N" badge (2026-10-14).
    assert 'book-card-rank' not in carousel and 'top-10-rank-number' not in carousel

    # WebP source + JPG fallback, mirroring getImageHtml() in app.js.
    assert 'srcset="/static/covers/30.webp"' in carousel
    assert 'src="/static/covers/30.jpg"' in carousel
    # Covers stay lazy: on a throttled mobile profile, eager covers starved
    # the render-blocking scripts (DCL +1.3s) while lazy ones — which load
    # as soon as layout puts them near the viewport — painted soonest.
    first_img = re.search(r'<img [^>]*>', carousel).group(0)
    assert 'loading="lazy"' in first_img


def test_home_cards_respect_url_prefix(db, monkeypatch):
    resp = _client(db, monkeypatch).get('/', headers={'X-Forwarded-Prefix': '/summrabook'})
    carousel = _carousel(resp.get_data(as_text=True))
    assert 'href="/summrabook/books/frankenstein"' in carousel
    assert 'srcset="/summrabook/static/covers/30.webp"' in carousel


def test_home_keeps_skeletons_when_no_ranked_books(test_db_path, monkeypatch):
    from backend import models
    empty = models.Database(db_path=test_db_path)
    resp = _client(empty, monkeypatch).get('/')
    assert resp.status_code == 200
    carousel = _carousel(resp.get_data(as_text=True))
    assert 'skeleton-book-card' in carousel
    assert 'top-10-book-card' not in carousel.replace('skeleton-book-card', '')
