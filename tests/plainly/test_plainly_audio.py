"""Plainly plays recordings through the same store and API as Distill: add a recording and it appears."""
import pytest

from shared.audio.spoken import spoken_checksum


@pytest.fixture
def db(test_db_path, tmp_path):
    from plainly import models
    database = models.Database(db_path=test_db_path)
    database.media.root = tmp_path / 'media'
    book_id = database.add_book(title='The Test Novel', author='Jane Doe', filename='t.txt', full_text='Full.')
    database.update_book_slug(book_id, 'the-test-novel')
    database.add_chapter(book_id, 1, 'Chapter One', 'A summary.', chapter_text='First paragraph.\n\nSecond paragraph.')
    database.book_id = book_id
    return database


@pytest.fixture
def client(db, monkeypatch):
    from plainly import app_base
    from plainly.routes import common
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def record(db, mode='original'):
    chapter = db.get_chapters(db.book_id)[0]
    units = db.audio_spoken_units(chapter, mode)
    timings = [{'paragraph_id': unit.paragraph_id, 'start_ms': i * 1000, 'end_ms': i * 1000 + 900} for i, unit in enumerate(units)]
    db.save_chapter_audio(chapter['id'], b'audio' * 50, timings, 2000, spoken_checksum(units), 'v', 'say', None, mode=mode)
    return chapter, timings


def test_a_recorded_chapter_appears_in_the_api(db, client):
    chapter, timings = record(db)
    data = client.get('/api/books/the-test-novel/audio?mode=original').get_json()
    assert data['book_id'] == db.book_id
    assert [c['chapter_id'] for c in data['chapters']] == [chapter['id']]
    assert data['chapters'][0]['timings'] == timings
    assert data['chapters'][0]['title'] == 'Chapter One'
    assert 'mode=original' in data['chapters'][0]['url']
    assert client.get(data['chapters'][0]['url']).status_code == 200


def test_spoken_units_use_the_reader_unit_ids(db):
    chapter = db.get_chapters(db.book_id)[0]
    units = db.audio_spoken_units(chapter, 'original')
    assert [u.paragraph_id for u in units] == [f"{chapter['id']}.0", f"{chapter['id']}.1"]
    assert [u.parts for u in units] == [['First paragraph.'], ['Second paragraph.']]


def test_a_mode_with_no_recording_is_empty(db, client):
    record(db)
    assert client.get('/api/books/the-test-novel/audio?mode=plain').get_json()['chapters'] == []
    assert client.get('/api/books/the-test-novel/audio').get_json()['chapters'] == []


def test_an_edited_chapter_hides_its_audio(db, client):
    record(db)
    chapter = db.get_chapters(db.book_id)[0]
    with db.get_connection() as conn:
        conn.execute('UPDATE chapters SET chapter_text = ? WHERE id = ?', ('Changed.\n\nText.', chapter['id']))
    assert client.get('/api/books/the-test-novel/audio?mode=original').get_json()['chapters'] == []


def test_an_unknown_book_is_not_found(client):
    assert client.get('/api/books/no-such-book/audio').status_code == 404
