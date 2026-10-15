"""Study cues shown on book cards, book pages and chapter lists (redesign
phase 2): a plain difficulty level derived from books.cefr_level, a reading
time, and .

Computed server-side once so every consumer (/api/books, /api/books/<id>,
/api/books/<id>/chapters, Discover, Categories) shows the same values.

Note: chapters.word_count stores the *summary's* word count, not the
chapter's, so chapter reading time must come from chapter_text.
"""
import pytest

from backend.study_cues import format_reading_time, level_label, reading_minutes


# --- level_label -----------------------------------------------------------

@pytest.mark.parametrize('cefr, expected', [
    ('A1', 'Easy'),
    ('A2', 'Easy'),
    ('A2-B1', 'Easy'),
    ('B1', 'Easy'),
    ('B1-B2', 'Moderate'),
    ('B2', 'Moderate'),
    ('B2-C1', 'Challenging'),
    ('C1', 'Challenging'),
    ('C1-C2', 'Challenging'),
    ('C2', 'Challenging'),
    (' b2 ', 'Moderate'),
])
def test_level_label_uses_upper_bound_of_cefr_range(cefr, expected):
    assert level_label(cefr) == expected


@pytest.mark.parametrize('cefr', [None, '', '   ', 'unknown', 'D1'])
def test_level_label_is_none_when_level_missing_or_unrecognised(cefr):
    assert level_label(cefr) is None


# --- reading_minutes -------------------------------------------------------

@pytest.mark.parametrize('words, expected', [
    (1, 1),
    (229, 1),
    (230, 1),
    (231, 2),
    (75042, 327),
])
def test_reading_minutes_rounds_up_at_230_wpm(words, expected):
    assert reading_minutes(words) == expected


@pytest.mark.parametrize('words', [None, 0, -5])
def test_reading_minutes_is_none_without_words(words):
    assert reading_minutes(words) is None


# --- format_reading_time -------------------------------------------------

@pytest.mark.parametrize('minutes, expected', [
    (1, '1 min'),
    (59, '59 min'),
    (60, '1 hr'),
    (74, '1 hr'),
    (75, '1½ hrs'),
    (105, '2 hrs'),
    (327, '5½ hrs'),
    (600, '10 hrs'),
])
def test_format_reading_time_uses_minutes_then_half_hours(minutes, expected):
    assert format_reading_time(minutes) == expected


@pytest.mark.parametrize('minutes', [None, 0])
def test_format_reading_time_is_none_without_minutes(minutes):
    assert format_reading_time(minutes) is None


# --- wiring into the data layer and APIs ----------------------------------

@pytest.fixture
def db(test_db_path):
    from backend import models
    database = models.Database(db_path=test_db_path)
    book_id = database.add_book(title='Cue Book', author='A', filename='c.txt',
                                full_text='word ' * 460)  # 460 words → 2 min
    conn = database.get_connection()
    conn.execute("UPDATE books SET cefr_level = 'B1-B2', slug = 'cue-book' WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    database.add_chapter(book_id, 1, 'Chapter 1', summary='**Victor** begins his tale. Then more.',
                         chapter_text='one two three\nfour five\n\nsix ' + 'w ' * 494)  # ~500 words
    database.add_chapter(book_id, 2, 'Chapter 2', summary='', chapter_text=None)
    database.book_id = book_id
    return database


@pytest.fixture
def client(db, monkeypatch):
    from backend import app_base
    from backend.routes import common
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def test_get_all_books_includes_cues(db):
    book = db.get_all_books()[0]
    assert book['level'] == 'Moderate'
    assert book['reading_minutes'] == 2
    assert book['reading_time'] == '2 min'


def test_api_books_includes_cues(client):
    book = client.get('/api/books').get_json()['books'][0]
    assert (book['level'], book['reading_minutes']) == ('Moderate', 2)


def test_api_book_detail_includes_cues(client, db):
    book = client.get(f'/api/books/{db.book_id}').get_json()['book']
    assert (book['level'], book['reading_minutes']) == ('Moderate', 2)


def test_api_chapters_include_reading_time_from_text(client, db):
    data = client.get(f'/api/books/{db.book_id}/chapters').get_json()
    chapters = {c['chapter_number']: c for c in data['sections'][0]['chapters']}
    # ~500 words of chapter text → 3 min. (The summary is 7 words, so a
    # summary-based count would give 1.)
    assert chapters[1]['reading_minutes'] == 3
    assert chapters[1]['reading_time'] == '3 min'
    assert chapters[2]['reading_minutes'] is None
    # The chapter list shows no summary excerpt (removed 2026-10-13: cut-off
    # snippets that mostly restated the chapter title).
    assert 'summary_excerpt' not in chapters[1]
    # Internal helper columns must not leak into the API.
    assert not any(k.startswith('_') for k in chapters[1])


def test_author_and_related_book_lists_include_cues(db):
    """Author pages and "You may also like" render the shared book card,
    which shows the level and reading time."""
    from backend import models
    conn = db.get_connection()
    conn.execute("INSERT INTO authors (name) VALUES ('A')")
    author_id = conn.execute("SELECT id FROM authors WHERE name = 'A'").fetchone()[0]
    conn.execute('UPDATE books SET author_id = ?', (author_id,))
    conn.commit()
    conn.close()
    other = db.add_book(title='Other', author='A', filename='o.txt', full_text='x', author_id=author_id)

    for books in (db.get_books_by_author_id(author_id),
                  db.get_books_by_author_name('A'),
                  db.get_related_books(other)['by_author']):
        cue = {b['title']: (b['level'], b['reading_time']) for b in books}
        assert cue['Cue Book'] == ('Moderate', '2 min'), books


# --- reading grade (ATOS), ages (AR interest level), school lists ------------

from backend.study_cues import add_book_cues, ages_for, grade_band, grade_label


@pytest.mark.parametrize('atos, band, label', [
    (None, None, None), (4.5, '3-5', 'Grade 4'), (5.9, '3-5', 'Grade 5'), (6.0, '6-8', 'Grade 6'),
    (8.9, '6-8', 'Grade 8'), (9.1, '9-10', 'Grade 9'), (10.9, '9-10', 'Grade 10'),
    (11.0, '11-12', 'Grade 11'), (12.4, '11-12', 'Grade 12'), (13.8, '11-12', 'College'),
])
def test_grade_band_and_label(atos, band, label):
    assert grade_band(atos) == band and grade_label(atos) == label


@pytest.mark.parametrize('interest, key, label', [
    (None, None, None), ('LG (K-3)', 'lg', 'Ages 5–9'), ('MG (4-8)', 'mg', 'Ages 9–14'),
    ('MG+ (6 and up)', 'mg-plus', 'Ages 11+'), ('UG (9-12)', 'ug', 'Ages 14+'), ('??', None, None),
])
def test_ages_from_interest_level(interest, key, label):
    assert ages_for(interest) == (key, label)


def test_add_book_cues_adds_grade_ages_and_school_lists():
    book = add_book_cues({'cefr_level': 'B2', 'word_count': 50_000, 'atos_level': 7.3, 'interest_level': 'UG (9-12)',
                          'school_lists': '[{"list": "Common Core exemplar", "grade_band": "11–12", "source": "https://x"}]'})
    assert (book['grade'], book['grade_label'], book['grade_band']) == (7.3, 'Grade 7', '6-8')
    assert (book['ages'], book['ages_label']) == ('ug', 'Ages 14+')
    assert book['school_lists'][0]['grade_band'] == '11–12' and book['on_school_list'] is True


def test_add_book_cues_without_new_metadata():
    book = add_book_cues({'cefr_level': None, 'word_count': None})
    assert book['grade'] is None and book['grade_band'] is None and book['ages'] is None
    assert book['school_lists'] == [] and book['on_school_list'] is False
