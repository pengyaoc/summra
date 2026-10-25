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
    from plainly import models
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
    from plainly import app_base
    from plainly.routes import common
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
    assert '<span class="book-meta-item">3 chapters</span>' in meta
    assert '<span class="book-meta-item">5½ hrs</span>' in meta
    assert '<span class="plain-english-badge">Plain English · grade 8</span>' in meta


def test_no_level_tag_without_a_published_grade(client):
    """Only published reading levels are shown. plain-book has an estimated
    CEFR level (C1) but no ATOS grade, so neither its book page nor its card
    gets a level tag (no Easy / Moderate / Challenging fallback)."""
    meta = _meta(client.get('/books/plain-book').get_data(as_text=True))
    assert 'level-tag' not in meta and 'grade-tag' not in meta
    assert 'Challenging' not in meta
    discover = client.get('/discover').get_data(as_text=True)
    card = re.search(r'<a class="book-card" href="/books/plain-book".*?</a>', discover, re.S).group(0)
    assert 'level-tag' not in card and 'Challenging' not in card


def test_meta_row_omits_missing_level_and_plain_english(client):
    meta = _meta(client.get('/books/old-book').get_data(as_text=True))
    assert 'level-tag' not in meta
    assert 'plain-english-badge' not in meta
    assert '<span class="book-meta-item">1 chapter</span>' in meta
    assert '<span class="book-meta-item">14 min</span>' in meta


def test_side_by_side_link_only_with_plain_english(client):
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert re.search(r'<a class="btn-secondary book-sxs-link" id="book-sxs-link" href="/books/plain-book/read\?mode=side_by_side">(<svg.*?</svg>)?Read side by side</a>', body, re.S)
    body = client.get('/books/old-book').get_data(as_text=True)
    assert re.search(r'<a class="btn-secondary book-sxs-link hidden" id="book-sxs-link"', body)


def test_start_reading_label(client):
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert re.search(r'<span id="book-read-label">Start reading</span>', body)


def test_page_section_order(client):
    """Summaries → chapters → reading guides → about the author → you may
    also like. There is no "About this book": it repeated the summary."""
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert 'id="about-section"' not in body and 'About this book' not in body
    ids = ['summary-tabs-section', 'chapters-section', 'reading-guide-section',
           'about-author-section', 'related-books-section']
    positions = [body.index(f'id="{i}"') for i in ids]
    assert positions == sorted(positions), dict(zip(ids, positions))


def test_chapters_api_book_carries_level_and_reading_time(client, db):
    data = client.get(f"/api/books/{db.ids['with_modern']}/chapters").get_json()
    assert data['book']['level'] == 'Challenging'
    assert data['book']['reading_time'] == '5½ hrs'


def test_chapters_api_book_carries_grade_ages_and_school_lists(client, db):
    """The client re-renders the meta row from this payload on in-app navigation."""
    conn = db.get_connection()
    conn.execute("UPDATE books SET atos_level=7.3, interest_level='MG (4-8)', school_lists=? WHERE id=?",
                 ('[{"list": "Common Core exemplar", "grade_band": "6–8", "source": "https://x.test"}]', db.ids['with_modern']))
    conn.commit()
    conn.close()
    book = client.get(f"/api/books/{db.ids['with_modern']}/chapters").get_json()['book']
    assert (book['grade_label'], book['grade_band'], book['ages_label']) == ('Grade 7', '6-8', 'Ages 9–14')
    assert book['school_lists'][0]['grade_band'] == '6–8'


def test_breadcrumb_structured_data_points_at_discover(client):
    """Books folded into Discover; the old crumb pointed at /all-books,
    which never existed."""
    body = client.get('/books/plain-book').get_data(as_text=True)
    assert '/all-books' not in body
    assert re.search(r'"name":\s*"Discover"', body), 'Discover crumb missing'


def test_meta_row_shows_reading_grade_ages_and_school_list(client, db):
    conn = db.get_connection()
    conn.execute("UPDATE books SET atos_level=11.7, interest_level='UG (9-12)', school_lists=? WHERE id=?",
                 ('[{"list": "Common Core exemplar", "grade_band": "11–12", "source": "https://example.test/b"}]', db.ids['with_modern']))
    conn.commit()
    conn.close()
    meta = _meta(client.get('/books/plain-book').get_data(as_text=True))
    assert '<span class="grade-tag grade-tag--11-12">Original: Grade 11</span>' in meta
    assert 'level-tag' not in meta, 'one difficulty scale: the published grade replaces the CEFR label'
    assert '<span class="book-meta-item">Ages 14+</span>' in meta
    assert re.search(r'<a class="school-list-badge" href="https://example.test/b"[^>]*>Common Core · grades 11–12</a>', meta)
