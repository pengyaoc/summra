"""Recordings live in shared code, one per chapter and reading mode."""
import sqlite3

import pytest

from distill.models import DistillDatabase
from shared.audio.spoken import spoken_checksum, spoken_units
from shared.audio.store import create_audio_tables


@pytest.fixture
def db(tmp_path, sample_book, write_book):
    database = DistillDatabase(tmp_path / 'distill.db')
    database.book_id = database.import_book(write_book(sample_book))
    return database


def save(db, chapter, data=b'audio', mode='summary'):
    checksum = spoken_checksum(spoken_units(chapter))
    return db.save_chapter_audio(chapter['id'], data, [], 10, checksum, 'v', 'say', None, mode=mode)


def columns(path):
    with sqlite3.connect(path) as conn:
        return [row[1] for row in conn.execute('PRAGMA table_info(chapter_audio)')]


OLD_TABLE = '''CREATE TABLE chapter_audio (
    chapter_id INTEGER PRIMARY KEY REFERENCES chapters(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL, text_checksum TEXT NOT NULL, duration_ms INTEGER NOT NULL,
    voice TEXT NOT NULL, engine TEXT NOT NULL, rate REAL, timings TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, deploy_key TEXT)'''


def old_database(db):
    """Rewind `db` to the one-recording-per-chapter table, with two rows."""
    chapters = db.get_chapters(db.book_id)[:2]
    with sqlite3.connect(db.db_path) as conn:
        conn.execute('DROP TABLE chapter_audio')
        conn.execute(OLD_TABLE)
        for chapter in chapters:
            conn.execute("INSERT INTO chapter_audio (chapter_id, storage_key, text_checksum, duration_ms, voice, engine, timings, deploy_key) "
                         "VALUES (?, 'key', 'sum', 5, 'v', 'say', '[]', 'opus')", (chapter['id'],))
    return [c['id'] for c in chapters]


def test_old_recordings_migrate_as_summary(db):
    ids = old_database(db)
    DistillDatabase(db.db_path)
    with sqlite3.connect(db.db_path) as conn:
        rows = conn.execute('SELECT chapter_id, mode, storage_key, deploy_key FROM chapter_audio ORDER BY 1').fetchall()
        primary = sorted((r[5], r[1]) for r in conn.execute('PRAGMA table_info(chapter_audio)') if r[5])
    assert rows == [(ids[0], 'summary', 'key', 'opus'), (ids[1], 'summary', 'key', 'opus')]
    assert primary == [(1, 'chapter_id'), (2, 'mode')]


def test_migration_runs_once_and_keeps_rows(db):
    old_database(db)
    DistillDatabase(db.db_path)
    before = columns(db.db_path)
    with sqlite3.connect(db.db_path) as conn:
        first = conn.execute('SELECT * FROM chapter_audio ORDER BY 1, 2').fetchall()
        create_audio_tables(conn)
        assert conn.execute('SELECT * FROM chapter_audio ORDER BY 1, 2').fetchall() == first
    assert columns(db.db_path) == before


def test_two_modes_coexist_for_a_chapter(db):
    chapter = db.get_chapters(db.book_id)[0]
    save(db, chapter, b'summary-audio')
    save(db, chapter, b'plain-audio', mode='plain')
    assert len(db.book_audio(db.book_id)) == 1
    assert len(db.book_audio(db.book_id, mode='plain')) == 1
    assert db.book_audio(db.book_id)[0]['storage_key'] != db.book_audio(db.book_id, mode='plain')[0]['storage_key']
    assert db.book_audio(db.book_id, mode='original') == []


def test_stale_text_hides_only_that_mode(db, monkeypatch):
    chapter = db.get_chapters(db.book_id)[0]
    save(db, chapter)
    save(db, chapter, mode='plain')
    original = db.audio_spoken_units
    monkeypatch.setattr(db, 'audio_spoken_units', lambda ch, mode: [] if mode == 'plain' else original(ch, mode))
    assert len(db.book_audio(db.book_id)) == 1
    assert db.book_audio(db.book_id, mode='plain') == []


def test_deleting_a_chapter_removes_its_recordings(db):
    chapter = db.get_chapters(db.book_id)[0]
    save(db, chapter)
    save(db, chapter, mode='plain')
    with sqlite3.connect(db.db_path) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('DELETE FROM chapter_audio WHERE chapter_id = -1')
        conn.execute('DELETE FROM chapters WHERE id = ?', (chapter['id'],))
        assert conn.execute('SELECT COUNT(*) FROM chapter_audio WHERE chapter_id = ?', (chapter['id'],)).fetchone()[0] == 0
