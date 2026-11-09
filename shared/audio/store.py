"""Chapter recordings, shared by every content app.

One recording per chapter and reading mode. A host mixes in AudioStoreMixin and
supplies `media`, `get_connection`, `get_chapters` and `audio_spoken_units`.
"""
import json
import sqlite3
from contextlib import closing
from typing import Dict, List, Optional

from shared.audio.spoken import spoken_checksum

DEFAULT_MODE = 'summary'
# Recorded before long text was split: Siri cut off the end of long sentences.
# Still served until re-recorded.
CUT_OFF_VOICES = frozenset({'siri:zh-CN-D@1.0'})

_TABLE = '''(
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'summary',
    storage_key TEXT NOT NULL,
    text_checksum TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    voice TEXT NOT NULL,
    engine TEXT NOT NULL,
    rate REAL,
    timings TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deploy_key TEXT,
    PRIMARY KEY (chapter_id, mode)
)'''
_COPIED = 'chapter_id, storage_key, text_checksum, duration_ms, voice, engine, rate, timings, created_at, deploy_key'


def _columns(conn) -> set:
    return {row[1] for row in conn.execute('PRAGMA table_info(chapter_audio)')}


def create_audio_tables(conn: sqlite3.Connection) -> None:
    """Create the table, or bring an older one up to date. Safe to run repeatedly."""
    conn.execute(f'CREATE TABLE IF NOT EXISTS chapter_audio {_TABLE}')
    columns = _columns(conn)
    if 'deploy_key' not in columns:
        conn.execute('ALTER TABLE chapter_audio ADD COLUMN deploy_key TEXT')
    if 'mode' in columns:
        return
    # SQLite can't change a primary key in place: copy into a new table, in one transaction.
    conn.execute('DROP TABLE IF EXISTS chapter_audio_new')
    conn.execute(f'CREATE TABLE chapter_audio_new {_TABLE}')
    conn.execute(f"INSERT INTO chapter_audio_new (mode, {_COPIED}) SELECT 'summary', {_COPIED} FROM chapter_audio")
    conn.execute('DROP TABLE chapter_audio')
    conn.execute('ALTER TABLE chapter_audio_new RENAME TO chapter_audio')
    conn.commit()


class AudioStoreMixin:
    def save_chapter_audio(self, chapter_id: int, data: bytes, timings: List[Dict], duration_ms: int,
                           checksum: str, voice: str, engine: str, rate: Optional[float], mode: str = DEFAULT_MODE) -> str:
        """Store a chapter's rendered audio and timings; any older Opus copy is dropped."""
        key = self.media.put(data)
        with closing(self.get_connection()) as conn, conn:
            conn.execute('''INSERT OR REPLACE INTO chapter_audio
                (chapter_id, mode, storage_key, text_checksum, duration_ms, voice, engine, rate, timings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (chapter_id, mode, key, checksum, duration_ms, voice, engine, rate, json.dumps(timings)))
        return key

    def set_deploy_audio(self, chapter_id: int, data: bytes, mode: str = DEFAULT_MODE) -> str:
        """Store the Opus file the server sends for a chapter."""
        key = self.media.put(data)
        with closing(self.get_connection()) as conn, conn:
            conn.execute('UPDATE chapter_audio SET deploy_key = ? WHERE chapter_id = ? AND mode = ?', (key, chapter_id, mode))
        return key

    def get_chapter_audio_key(self, chapter_id: int, mode: str = DEFAULT_MODE) -> str:
        with closing(self.get_connection()) as conn:
            return conn.execute('SELECT storage_key FROM chapter_audio WHERE chapter_id = ? AND mode = ?',
                                (chapter_id, mode)).fetchone()[0]

    def missing_deploy_audio(self) -> List[int]:
        """Older chapters that have only AAC, with no Opus file yet."""
        with closing(self.get_connection()) as conn:
            return [row[0] for row in conn.execute(
                'SELECT chapter_id FROM chapter_audio WHERE deploy_key IS NULL ORDER BY chapter_id')]

    def _audio_by_chapter(self, book_id: int, mode: str):
        """[(chapter, audio row or None, current?)] in chapter order."""
        with closing(self.get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            rows = {r['chapter_id']: r for r in conn.execute(
                '''SELECT a.* FROM chapter_audio a JOIN chapters c ON c.id = a.chapter_id
                   WHERE c.book_id = ? AND a.mode = ?''', (book_id, mode))}
        result = []
        for chapter in self.get_chapters(book_id):
            row = rows.get(chapter['id'])
            current = bool(row) and row['text_checksum'] == spoken_checksum(self.audio_spoken_units(chapter, mode))
            result.append((chapter, row, current))
        return result

    def book_audio(self, book_id: int, mode: str = DEFAULT_MODE) -> List[Dict]:
        """Chapters whose audio matches their current text, in reading order."""
        return [{'chapter_id': c['id'], 'ordinal': c.get('ordinal', c.get('chapter_number')),
                 'title': c.get('title', c.get('chapter_title')),
                 'storage_key': row['storage_key'], 'deploy_key': row['deploy_key'], 'duration_ms': row['duration_ms'],
                 'timings': json.loads(row['timings'])}
                for c, row, current in self._audio_by_chapter(book_id, mode) if current]

    def stale_or_missing_audio(self, book_id: int, mode: str = DEFAULT_MODE) -> List[int]:
        return [c['id'] for c, row, current in self._audio_by_chapter(book_id, mode)
                if not current or row['voice'] in CUT_OFF_VOICES]
