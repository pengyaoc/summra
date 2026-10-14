"""Discover page (redesign phase 4): one filterable grid of book cards,
server-rendered so first paint isn't blank.

Filters are level (Easy / Moderate / Challenging) and length (Short /
Medium / Long), read from ?level= / ?length= and applied by CSS through
data attributes on the grid; ?sort= orders the cards. The client only
flips those attributes, so server and client share one mechanism.
"""
import re

import pytest

from backend.study_cues import add_book_cues, length_label


# --- length_label ----------------------------------------------------------

@pytest.mark.parametrize('words, expected', [
    (1, 'Short'),
    (49_999, 'Short'),
    (50_000, 'Medium'),
    (119_999, 'Medium'),
    (120_000, 'Long'),
])
def test_length_label_buckets(words, expected):
    assert length_label(words) == expected


@pytest.mark.parametrize('words', [None, 0])
def test_length_label_is_none_without_words(words):
    assert length_label(words) is None


def test_add_book_cues_adds_length():
    assert add_book_cues({'word_count': 60_000, 'cefr_level': None})['length'] == 'Medium'


# --- /discover ---------------------------------------------------------------

BOOKS = [
    # title, cefr, words
    ('Zeta Tale', 'A2', 20_000),        # Easy, Short, 87 min
    ('Alpha Saga', 'C1', 200_000),      # Challenging, Long
    ('Mid Story', 'B2', 80_000),        # Moderate, Medium
    ('No Level', None, 30_000),         # untagged, Short
]


@pytest.fixture
def client(test_db_path, monkeypatch):
    from backend import app_base, models
    from backend.routes import common
    db = models.Database(db_path=test_db_path)
    ids = [db.add_book(title=title, author='Anon', filename=f'{title}.txt', full_text='x')
           for title, _, _ in BOOKS]
    conn = db.get_connection()
    for book_id, (title, cefr, words) in zip(ids, BOOKS):
        slug = title.lower().replace(' ', '-')
        conn.execute('UPDATE books SET cefr_level = ?, word_count = ?, slug = ?, cover_image_url = ? WHERE id = ?',
                     (cefr, words, slug, f'covers/{book_id}.png', book_id))
    conn.commit()
    conn.close()
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def _grid(body):
    m = re.search(r'<div class="books-grid discover-grid"([^>]*)>(.*?)</div>\s*<p class="discover-empty', body, re.S)
    assert m, 'discover grid not server-rendered'
    return m.group(1), m.group(2)


def _cards(grid_html):
    return re.findall(r'<a class="book-card" href="([^"]+)"([^>]*)>.*?<h3 class="book-card-title">([^<]+)</h3>', grid_html, re.S)


def test_discover_server_renders_every_book_as_a_card(client):
    resp = client.get('/discover')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert re.search(r'<section class="discover-section\s*" id="discover-section"', body), \
        'discover section should be visible on /discover'
    attrs, grid = _grid(body)
    cards = _cards(grid)
    assert [c[2] for c in cards] == ['Alpha Saga', 'Mid Story', 'No Level', 'Zeta Tale']  # A–Z by default
    assert cards[3][0] == '/books/zeta-tale'
    assert 'data-level="easy"' in cards[3][1] and 'data-length="short"' in cards[3][1]
    assert 'data-minutes="87"' in cards[3][1]
    assert 'data-level="none"' in cards[2][1]
    assert 'data-filter-level="all"' in attrs and 'data-filter-length="all"' in attrs


def test_discover_card_matches_client_card_markup(client):
    """Same structure createBookCard() builds in app.js: cover box with serif
    title placeholder + webp/jpg picture, title, author, level tag, time."""
    _, grid = _grid(client.get('/discover').get_data(as_text=True))
    card = re.search(r'<a class="book-card" href="/books/zeta-tale".*?</a>', grid, re.S).group(0)
    assert '<span class="book-card-cover-title" aria-hidden="true">Zeta Tale</span>' in card
    assert re.search(r'<source srcset="/static/covers/\d+\.webp" type="image/webp">', card)
    assert re.search(r'<img src="/static/covers/\d+\.jpg" alt="Zeta Tale cover" loading="lazy"', card)
    assert '<p class="book-card-author">Anon</p>' in card
    assert '<span class="level-tag level-tag--easy">Easy</span>' in card
    assert '<span class="book-card-time">1½ hrs</span>' in card


def test_discover_reads_filters_from_query(client):
    body = client.get('/discover?level=easy&length=short').get_data(as_text=True)
    attrs, _ = _grid(body)
    assert 'data-filter-level="easy"' in attrs and 'data-filter-length="short"' in attrs
    assert re.search(r'data-filter="level" data-value="easy"[^>]*aria-pressed="true"', body)
    assert re.search(r'data-filter="level" data-value="all"[^>]*aria-pressed="false"', body)
    assert re.search(r'id="discover-count"[^>]*>1 book<', body)


@pytest.mark.parametrize('query', ['level=hard', 'length=epic', 'level=', 'sort=random'])
def test_discover_ignores_unknown_filter_values(client, query):
    body = client.get(f'/discover?{query}').get_data(as_text=True)
    attrs, grid = _grid(body)
    assert 'data-filter-level="all"' in attrs and 'data-filter-length="all"' in attrs
    assert len(_cards(grid)) == 4
    assert re.search(r'id="discover-count"[^>]*>4 books<', body)


def test_discover_sorts_shortest_first(client):
    _, grid = _grid(client.get('/discover?sort=shortest').get_data(as_text=True))
    assert [c[2] for c in _cards(grid)] == ['Zeta Tale', 'No Level', 'Mid Story', 'Alpha Saga']


def test_discover_sorts_easiest_first_with_untagged_last(client):
    _, grid = _grid(client.get('/discover?sort=easiest').get_data(as_text=True))
    assert [c[2] for c in _cards(grid)] == ['Zeta Tale', 'Mid Story', 'Alpha Saga', 'No Level']


def test_other_pages_do_not_render_the_discover_grid(client):
    body = client.get('/categories').get_data(as_text=True)
    assert 'class="books-grid discover-grid"' in body  # shell present for SPA navigation…
    assert re.search(r'<section class="discover-section hidden" id="discover-section"', body)
    _, grid = _grid(body)
    assert _cards(grid) == []  # …but empty; the client fills it


def test_discover_carousels_api_is_gone(client):
    """Replaced by the server-rendered grid; nothing else used it."""
    assert client.get('/api/discover/carousels').status_code == 404
