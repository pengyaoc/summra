"""Reading levels describe the original; Plain English has its own target.

Plain English rewrites are written for about an 8th-grade reader (the
generate_modern_english.py prompt, 2026-05-31), so a book's published ATOS
grade says how hard its *original* is. Every place that shows that grade
labels it as the original's; books without a Plain English version are
marked "Original only" and can be filtered out on Discover.
"""
import re

import pytest


@pytest.fixture
def db(test_db_path):
    from backend import models
    db = models.Database(db_path=test_db_path)
    rows = [
        # title, slug, ATOS, Plain English text (None = original only)
        ('Pride and Prejudice', 'pride-and-prejudice', 12.0, 'Everyone knows a rich single man needs a wife.'),
        ('Cranford', 'cranford', None, None),
        ('Blank Plain', 'blank-plain', 7.3, ' \n\t '),   # whitespace only counts as none
    ]
    for title, slug, atos, plain in rows:
        book_id = db.add_book(title=title, author='Anon', filename=f'{slug}.txt', full_text='x')
        conn = db.get_connection()
        conn.execute('UPDATE books SET slug = ?, atos_level = ?, word_count = 120000 WHERE id = ?', (slug, atos, book_id))
        conn.commit()
        conn.close()
        db.add_chapter(book_id, 1, 'Chapter 1', summary='S.', chapter_text='It is a truth.', modern_english_text=plain)
    return db


@pytest.fixture
def client(db, monkeypatch):
    from backend import app_base
    from backend.routes import common
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def _by_slug(books):
    return {b['slug']: b for b in books}


# --- data ----------------------------------------------------------------------

def test_listings_say_which_books_have_plain_english(db):
    books = _by_slug(db.get_all_books())
    assert books['pride-and-prejudice']['has_plain_english'] is True
    assert books['cranford']['has_plain_english'] is False
    assert books['blank-plain']['has_plain_english'] is False


def test_api_books_carries_the_flag(client):
    books = _by_slug(client.get('/api/books').get_json()['books'])
    assert books['pride-and-prejudice']['has_plain_english'] is True
    assert books['cranford']['has_plain_english'] is False


# --- Discover ------------------------------------------------------------------

def _card(body, slug):
    return re.search(rf'<a class="book-card" href="/books/{slug}".*?</a>', body, re.S).group(0)


def test_discover_labels_the_grade_as_the_originals(client):
    body = client.get('/discover').get_data(as_text=True)
    assert 'aria-label="Original’s level"' in body
    assert '>Original: Grade 12</span>' in _card(body, 'pride-and-prejudice')
    assert 'Easiest original first' in body
    intro = re.search(r'<header class="discover-header">(.*?)</header>', body, re.S).group(1)
    assert 'grade 8' in intro and 'Every book is rewritten' not in intro


def test_discover_marks_original_only_books(client):
    body = client.get('/discover').get_data(as_text=True)
    assert 'data-plain="no"' in _card(body, 'cranford') and 'Original only' in _card(body, 'cranford')
    assert 'data-plain="yes"' in _card(body, 'pride-and-prejudice')
    assert 'Original only' not in _card(body, 'pride-and-prejudice')


def test_discover_plain_english_filter(client):
    body = client.get('/discover?plain=yes').get_data(as_text=True)
    assert 'data-filter-plain="yes"' in body
    assert re.search(r'data-filter="plain" data-value="yes" aria-pressed="true"', body)
    assert re.search(r'id="discover-count"[^>]*>1 book<', body)


def test_discover_ignores_an_unknown_plain_value(client):
    body = client.get('/discover?plain=maybe').get_data(as_text=True)
    assert 'data-filter-plain="all"' in body


# --- book page -----------------------------------------------------------------

def _meta(body):
    return re.search(r'<p class="book-meta" id="book-meta">(.*?)</p>', body, re.S).group(1)


def test_book_page_states_both_levels(client):
    meta = _meta(client.get('/books/pride-and-prejudice').get_data(as_text=True))
    assert '>Original: Grade 12</span>' in meta
    assert 'Plain English · grade 8' in meta


def test_book_page_without_plain_english_says_original_only(client):
    meta = _meta(client.get('/books/cranford').get_data(as_text=True))
    assert 'Original only' in meta and 'Plain English' not in meta


# --- home --------------------------------------------------------------------

def _levels_section(body):
    return re.search(r'<section [^>]*id="reading-levels"[^>]*>(.*?)</section>', body, re.S).group(1)


def test_home_levels_section_leads_with_the_plain_english_target(client):
    section = _levels_section(client.get('/').get_data(as_text=True))
    assert 'grade 8' in section, 'say what level Plain English is written for'
    assert "original" in section.lower() and 'ATOS' in section
    assert '1 of 3 books' in section, 'live count of books with Plain English'
    assert 'Original only' in section
