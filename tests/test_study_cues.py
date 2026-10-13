"""Study cues shown on book cards, book pages and chapter lists (redesign
phase 2): a plain difficulty level derived from books.cefr_level, a reading
time, and a one-line chapter summary excerpt.

Computed server-side once so every consumer (/api/books, /api/books/<id>,
/api/books/<id>/chapters, Discover, Categories) shows the same values.

Note: chapters.word_count stores the *summary's* word count, not the
chapter's, so chapter reading time must come from chapter_text.
"""
import pytest

from backend.study_cues import format_reading_time, level_label, reading_minutes, summary_excerpt


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


# --- summary_excerpt -------------------------------------------------------

def test_excerpt_is_first_sentence_without_markdown():
    text = ('In **Letter 1**, Walton writes from St. Petersburgh. He is full of hope.\n\n'
            'Second paragraph.')
    assert summary_excerpt(text) == 'In Letter 1, Walton writes from St. Petersburgh.'


def test_excerpt_truncates_long_sentence_at_word_boundary():
    text = 'word ' * 100
    excerpt = summary_excerpt(text, limit=40)
    assert excerpt.endswith('…')
    assert len(excerpt) <= 41
    assert not excerpt[:-1].endswith(' ')
    assert excerpt[:-1].split() == ['word'] * len(excerpt[:-1].split())


def test_excerpt_strips_leading_heading_marks():
    assert summary_excerpt('## Chapter 1\nVictor begins. More.') == 'Chapter 1 Victor begins.'


@pytest.mark.parametrize('text', [None, '', '  \n '])
def test_excerpt_is_none_for_empty_summary(text):
    assert summary_excerpt(text) is None


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


def test_api_chapters_include_reading_time_from_text_and_excerpt(client, db):
    data = client.get(f'/api/books/{db.book_id}/chapters').get_json()
    chapters = {c['chapter_number']: c for c in data['sections'][0]['chapters']}
    # ~500 words of chapter text → 3 min. (The summary is 7 words, so a
    # summary-based count would give 1.)
    assert chapters[1]['reading_minutes'] == 3
    assert chapters[1]['reading_time'] == '3 min'
    assert chapters[1]['summary_excerpt'] == 'Victor begins his tale.'
    assert chapters[2]['reading_minutes'] is None
    assert chapters[2]['summary_excerpt'] is None
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
