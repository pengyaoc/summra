"""Discover page (redesign phase 4): one filterable grid of book cards,
server-rendered so first paint isn't blank.

Filters are reading grade (ATOS band: 3–5, 6–8, 9–10, 11–12+), ages (AR
interest level), Common Core school lists and length (Short / Medium /
Long), read from ?grade= / ?ages= / ?school= / ?length= and applied by CSS
through data attributes on the grid; ?sort= orders the cards. The client
only flips those attributes, so server and client share one mechanism.
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
    # title, cefr, words, ATOS, AR interest level, Common Core
    ('Zeta Tale', 'A2', 20_000, 4.6, 'MG (4-8)', True),             # Grade 4, ages 9–14, Short
    ('Alpha Saga', 'C1', 200_000, 11.7, 'UG (9-12)', False),         # Grade 11, ages 14+, Long
    ('Mid Story', 'B2', 80_000, 7.3, 'MG+ (6 and up)', False),       # Grade 7, ages 11+, Medium
    ('No Level', None, 30_000, None, None, False),                   # no reading level, Short
]


@pytest.fixture
def client(test_db_path, monkeypatch):
    from backend import app_base, models
    from backend.routes import common
    db = models.Database(db_path=test_db_path)
    ids = [db.add_book(title=book[0], author='Anon', filename=f'{book[0]}.txt', full_text='x') for book in BOOKS]
    conn = db.get_connection()
    for book_id, (title, cefr, words, atos, interest, school) in zip(ids, BOOKS):
        slug = title.lower().replace(' ', '-')
        lists = '[{"list": "Common Core exemplar", "grade_band": "4–5", "source": "https://x"}]' if school else None
        conn.execute('UPDATE books SET cefr_level = ?, word_count = ?, slug = ?, cover_image_url = ?, atos_level = ?, '
                     'interest_level = ?, school_lists = ? WHERE id = ?',
                     (cefr, words, slug, f'covers/{book_id}.png', atos, interest, lists, book_id))
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


FILTERS = ('grade', 'ages', 'school', 'length')


def _all_filters_off(attrs):
    return all(f'data-filter-{f}="all"' in attrs for f in FILTERS)


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
    zeta, untagged = cards[3][1], cards[2][1]
    for attr in ('data-grade="3-5"', 'data-ages="mg"', 'data-school="yes"', 'data-length="short"', 'data-minutes="87"'):
        assert attr in zeta, attr
    for attr in ('data-grade="none"', 'data-ages="none"', 'data-school="no"'):
        assert attr in untagged, attr
    assert _all_filters_off(attrs)


def test_discover_card_matches_client_card_markup(client):
    """Same structure createBookCard() builds in app.js: cover box with serif
    title placeholder + webp/jpg picture, title, author, grade tag, time."""
    _, grid = _grid(client.get('/discover').get_data(as_text=True))
    card = re.search(r'<a class="book-card" href="/books/zeta-tale".*?</a>', grid, re.S).group(0)
    assert '<span class="book-card-cover-title" aria-hidden="true">Zeta Tale</span>' in card
    assert re.search(r'<source srcset="/static/covers/\d+\.webp" type="image/webp">', card)
    assert re.search(r'<img src="/static/covers/\d+\.jpg" alt="Zeta Tale cover" loading="lazy"', card)
    assert '<p class="book-card-author">Anon</p>' in card
    assert '<span class="grade-tag grade-tag--3-5">Grade 4</span>' in card
    assert '<span class="book-card-time">1½ hrs</span>' in card


def test_discover_reads_filters_from_query(client):
    body = client.get('/discover?grade=3-5&ages=mg&school=yes&length=short').get_data(as_text=True)
    attrs, _ = _grid(body)
    for attr in ('data-filter-grade="3-5"', 'data-filter-ages="mg"', 'data-filter-school="yes"', 'data-filter-length="short"'):
        assert attr in attrs, attr
    assert re.search(r'data-filter="grade" data-value="3-5"[^>]*aria-pressed="true"', body)
    assert re.search(r'data-filter="grade" data-value="all"[^>]*aria-pressed="false"', body)
    assert re.search(r'id="discover-count"[^>]*>1 book<', body)


def test_discover_counts_each_filter(client):
    count = lambda q: re.search(r'id="discover-count"[^>]*>(\d+) book', client.get(f'/discover?{q}').get_data(as_text=True)).group(1)
    assert count('grade=11-12') == '1' and count('ages=ug') == '1' and count('school=yes') == '1' and count('grade=9-10') == '0'


@pytest.mark.parametrize('query', ['grade=hard', 'ages=old', 'school=maybe', 'length=epic', 'grade=', 'sort=random', 'level=easy'])
def test_discover_ignores_unknown_filter_values(client, query):
    body = client.get(f'/discover?{query}').get_data(as_text=True)
    attrs, grid = _grid(body)
    assert _all_filters_off(attrs)
    assert len(_cards(grid)) == 4
    assert re.search(r'id="discover-count"[^>]*>4 books<', body)


def test_discover_sorts_shortest_first(client):
    _, grid = _grid(client.get('/discover?sort=shortest').get_data(as_text=True))
    assert [c[2] for c in _cards(grid)] == ['Zeta Tale', 'No Level', 'Mid Story', 'Alpha Saga']


def test_discover_sorts_easiest_first_by_reading_grade_untagged_last(client):
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
