"""Book page (redesign phase 5): server-rendered meta row and actions, and
the section order on the page.

Meta row: level tag · N chapters · reading time · "Plain English" badge (only
when a plain-English rewrite exists). Actions: "Start reading" plus a "Read
side by side" link that only shows when there's plain English to compare.
"""
import re

import pytest


@pytest.fixture
def db(test_db_path):
    from backend import models
    database = models.Database(db_path=test_db_path)
    with_modern = database.add_book(title='Plain Book', author='Ann Author', filename='p.txt', full_text='x')
    without = database.add_book(title='Old Book', author='Ann Author', filename='o.txt', full_text='x')
    conn = database.get_connection()
    conn.execute("UPDATE books SET slug='plain-book', cefr_level='C1', word_count=75042 WHERE id=?", (with_modern,))
    conn.execute("UPDATE books SET slug='old-book', cefr_level=NULL, word_count=3000 WHERE id=?", (without,))
    conn.commit()
    conn.close()
    for n in (1, 2, 3):
        database.add_chapter(with_modern, n, f'Chapter {n}', summary='S.', chapter_text='t',
                             modern_english_text='m' if n == 1 else None)
    database.add_chapter(without, 1, 'Only', summary='S.', chapter_text='t')
    database.ids = {'with_modern': with_modern, 'without': without}
    return database


@pytest.fixture
def client(db, monkeypatch):
    from backend import app_base
    from backend.routes import common
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def test_count_chapters(db):
    assert db.count_chapters(db.ids['with_modern']) == 3
    assert db.count_chapters(db.ids['without']) == 1
    assert db.count_chapters(999_999) == 0


def _meta(body):
    m = re.search(r'<p class="book-meta" id="book-meta">(.*?)</p>', body, re.S)
    assert m, 'book meta row not server-rendered'
    return m.group(1)


def test_meta_row_is_server_rendered(client):
    meta = _meta(client.get('/books/plain-book').get_data(as_text=True))
    assert '<span class="level-tag level-tag--challenging">Challenging</span>' in meta
    assert '<span class="book-meta-item">3 chapters</span>' in meta
    assert '<span class="book-meta-item">5½ hrs</span>' in meta
    assert '<span class="plain-english-badge">Plain English</span>' in meta


def test_meta_row_omits_missing_level_and_plain_english(client):
    meta = _meta(client.get('/books/old-book').get_data(as_text=True))
    assert 'level-tag' not in meta
    assert 'plain-english-badge' not in meta
    assert '<span class="book-meta-item">1 chapter</span>' in meta
    assert '<span class="book-meta-item">14 min</span>' in meta


def test_side_by_side_link_only_with_plain_english(client):
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert re.search(r'<a class="btn-secondary book-sxs-link" id="book-sxs-link" href="/books/plain-book/read\?mode=side_by_side">Read side by side</a>', body)
    body = client.get('/books/old-book').get_data(as_text=True)
    assert re.search(r'<a class="btn-secondary book-sxs-link hidden" id="book-sxs-link"', body)


def test_start_reading_label(client):
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert re.search(r'<span id="book-read-label">Start reading</span>', body)


def test_page_section_order(client):
    """About this book → summaries → chapters → reading guides → about the
    author → you may also like."""
    body = client.get('/books/plain-book').get_data(as_text=True)
    ids = ['about-section', 'summary-tabs-section', 'chapters-section', 'reading-guide-section',
           'about-author-section', 'related-books-section']
    positions = [body.index(f'id="{i}"') for i in ids]
    assert positions == sorted(positions), dict(zip(ids, positions))


def test_chapters_api_book_carries_level_and_reading_time(client, db):
    data = client.get(f"/api/books/{db.ids['with_modern']}/chapters").get_json()
    assert data['book']['level'] == 'Challenging'
    assert data['book']['reading_time'] == '5½ hrs'
