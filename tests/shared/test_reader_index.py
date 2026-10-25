"""shared.reader indexes any host's content through hooks, with no Plainly
tables: here a bare `chapters(body)` table whose lines are summary units."""
import hashlib
import json
import sqlite3

import pytest

from shared.reader.index import ReaderIndexMixin, create_reader_tables


class FakeContent(ReaderIndexMixin):
    def __init__(self, path):
        self.path = path
        conn = self.get_connection()
        create_reader_tables(conn.cursor())
        conn.execute('''CREATE TABLE chapters (id INTEGER PRIMARY KEY, book_id INTEGER,
                        chapter_number INTEGER, chapter_title TEXT, body TEXT)''')
        conn.commit()
        conn.close()

    def get_connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_chapter(self, chapter_id, number, title, body, book_id=1):
        with self.get_connection() as conn:
            conn.execute('INSERT INTO chapters VALUES (?, ?, ?, ?, ?)', (chapter_id, book_id, number, title, body))

    def get_book(self, book_id):
        return {'id': book_id} if book_id == 1 else None

    def _reader_load_book(self, conn, book_id):
        return {'id': book_id, 'verse': False} if book_id == 1 else None

    def _reader_load_chapters(self, conn, book_id, chapter_ids=None):
        query, params = 'SELECT * FROM chapters WHERE book_id = ?', [book_id]
        if chapter_ids is not None:
            query += f" AND id IN ({','.join('?' * len(chapter_ids))})"
            params += list(chapter_ids)
        return [dict(row) for row in conn.execute(query + ' ORDER BY chapter_number', params)]

    def _reader_chapter_units(self, chapter, verse, plain_coverage):
        return {'summary': self._reader_split_paragraphs(chapter['body']), 'original': [], 'plain': []}

    def _reader_plain_coverage(self, chapters):
        return False

    def _reader_source_checksum(self, chapters):
        return hashlib.sha256(json.dumps([c['body'] for c in chapters]).encode('utf-8')).hexdigest()

    def _reader_structure(self, conn, book_id):
        return []


@pytest.fixture
def fake(tmp_path):
    return FakeContent(tmp_path / 'content.db')


def test_manifest_counts_units_without_plainly(fake):
    fake.add_chapter(1, 1, 'One', 'a b\nc d e')
    fake.add_chapter(2, 1, 'Two', 'f')
    manifest = fake.get_reader_manifest(1)
    summary = next(m for m in manifest['modes'] if m['mode'] == 'summary')
    assert summary['terminal_paragraph_id'] == '2.0'


def test_marker_resolves_to_word_position(fake):
    fake.add_chapter(1, 1, 'One', 'a b\nc d e')
    m = fake.resolve_reader_marker(1, {'mode': 'summary', 'paragraph_id': '1.1', 'offset': 0})
    assert (m['ordinal'], m['word_position']) == (1, 2)


def test_unknown_paragraph_is_rejected(fake):
    fake.add_chapter(1, 1, 'One', 'a')
    assert fake.resolve_reader_marker(1, {'mode': 'summary', 'paragraph_id': '1.9'}) is None


def test_unknown_book_is_rejected(fake):
    with pytest.raises(ValueError):
        fake.ensure_reader_content(2)
