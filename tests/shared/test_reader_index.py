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


@pytest.fixture(params=['plainly', 'distill'])
def tracked(request, tmp_path):
    """The actual hosts, including their schema migrations and SQL triggers."""
    if request.param == 'plainly':
        from plainly.models import Database
        db = Database(tmp_path / 'plainly.db')
        with db.get_connection() as conn:
            for bid in (1, 2):
                conn.execute('INSERT INTO books (id, title, author, filename, slug) VALUES (?, ?, ?, ?, ?)',
                             (bid, f'Book {bid}', 'A', f'{bid}.txt', f'book-{bid}'))
                for number in (1, 2):
                    conn.execute('''INSERT INTO chapters
                        (book_id, chapter_number, chapter_title, chapter_text, modern_english_text, summary)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                        (bid, number, f'Chapter {number}', 'First original.\nSecond original.',
                         'First plain.\nSecond plain.', 'A summary.'))
    else:
        from distill.models import DistillDatabase
        db = DistillDatabase(tmp_path / 'distill.db')
        with db.get_connection() as conn:
            for bid in (1, 2):
                conn.execute('INSERT INTO books (id, title, author, slug, lang) VALUES (?, ?, ?, ?, ?)',
                             (bid, f'Book {bid}', 'A', f'book-{bid}', 'en'))
                for number in (1, 2):
                    conn.execute('INSERT INTO chapters (book_id, ordinal, title, blocks) VALUES (?, ?, ?, ?)',
                                 (bid, number, f'Chapter {number}',
                                  json.dumps([{'type': 'p', 'text': 'First block.'},
                                              {'type': 'p', 'text': 'Second block.'}])))
    return db


def test_tracked_freshness_and_totals_survive_restart_without_loading_text(tracked, monkeypatch):
    expected = {bid: {m['mode']: m['total_word_count'] for m in tracked.get_reader_manifest(bid)['modes']
                      if m['unit_count']} for bid in (1, 2)}
    first = tracked.ensure_reader_content(1)
    restarted = type(tracked)(tracked.db_path)
    def forbidden(*args):
        pytest.fail('clean index requested full content or manifest')
    for hook in ('_reader_load_book', '_reader_load_chapters', '_reader_source_checksum', 'get_reader_manifest'):
        monkeypatch.setattr(restarted, hook, forbidden)
    assert restarted.ensure_reader_content(1) == first
    assert restarted.library_word_totals([1, 2, 999]) == expected
    assert restarted.library_word_totals([]) == {}


def test_tracked_external_edits_and_chapter_moves_invalidate_both_books(tracked):
    versions = {bid: tracked.ensure_reader_content(bid)['version'] for bid in (1, 2)}
    with sqlite3.connect(tracked.db_path) as conn:
        number = 'ordinal' if 'ordinal' in {c[1] for c in conn.execute('PRAGMA table_info(chapters)')} else 'chapter_number'
        # Move a chapter through an independent connection, as an importer can.
        conn.execute(f'UPDATE chapters SET book_id = 2, {number} = 3 WHERE id = 1')
    for bid in (1, 2):
        assert tracked.ensure_reader_content(bid)['version'] == versions[bid] + 1
    with sqlite3.connect(tracked.db_path) as conn:
        conn.execute('DELETE FROM chapters WHERE id = 1')
    assert tracked.ensure_reader_content(2)['version'] == versions[2] + 2
    with tracked.get_connection() as conn:
        conn.execute('DELETE FROM books WHERE id = 1')
        assert conn.execute('SELECT 1 FROM reader_revision WHERE book_id = 1').fetchone() is None
    with pytest.raises(ValueError, match='Book not found'):
        tracked.ensure_reader_content(1)


def test_tracked_totals_refresh_only_the_edited_book(tracked, monkeypatch):
    first = tracked.library_word_totals([1, 2])
    with sqlite3.connect(tracked.db_path) as conn:
        if 'ordinal' in {c[1] for c in conn.execute('PRAGMA table_info(chapters)')}:
            conn.execute('UPDATE chapters SET blocks = ? WHERE id = 1',
                         (json.dumps([{'type': 'p', 'text': 'one two three four five six seven eight'}]),))
        else:
            conn.execute('UPDATE chapters SET chapter_text = ?, modern_english_text = ?, summary = ? WHERE id = 1',
                         ('one two three four five six seven eight', 'plain words', 'new summary words'))
    loads = []
    original = tracked._reader_load_chapters
    def load(conn, bid, chapter_ids=None):
        loads.append(bid)
        return original(conn, bid, chapter_ids)
    monkeypatch.setattr(tracked, '_reader_load_chapters', load)
    totals = tracked.library_word_totals([1, 2])
    assert loads == [1]
    assert totals[1] != first[1]
    assert totals[2] == first[2]
    manifest = tracked.get_reader_manifest(1)
    assert totals[1] == {m['mode']: m['total_word_count'] for m in manifest['modes'] if m['unit_count']}


def test_tracked_concurrent_workers_compile_once(tracked, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    calls = []
    original = tracked._compile_reader_content
    def compile(*args):
        calls.append(args[1])
        return original(*args)
    monkeypatch.setattr(tracked, '_compile_reader_content', compile)
    barrier = Barrier(2)
    def ensure(_):
        barrier.wait(timeout=5)
        return tracked.ensure_reader_content(1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        versions = list(pool.map(ensure, (1, 2)))
    assert versions[0] == versions[1]
    assert calls == [1]


def test_tracked_failed_compile_rolls_back_index_and_freshness(tracked, monkeypatch):
    first = tracked.ensure_reader_content(1)
    with tracked.get_connection() as conn:
        before = [tuple(r) for r in conn.execute('SELECT * FROM reader_unit WHERE book_id = 1')]
        # Renumbering changes structure for both hosts without changing unit IDs.
        number = 'ordinal' if 'ordinal' in {c[1] for c in conn.execute('PRAGMA table_info(chapters)')} else 'chapter_number'
        conn.execute(f'UPDATE chapters SET {number} = 3 WHERE id = 1')
    with monkeypatch.context() as patch:
        def fail(conn, *args):
            conn.execute('DELETE FROM reader_unit WHERE book_id = 1')
            raise RuntimeError('failed compiler')
        patch.setattr(tracked, '_compile_reader_content', fail)
        with pytest.raises(RuntimeError, match='failed compiler'):
            tracked.ensure_reader_content(1)
    with tracked.get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM reader_unit WHERE book_id = 1')] == before
        assert dict(conn.execute('SELECT * FROM reader_version WHERE book_id = 1').fetchone()) == first
        row = conn.execute('SELECT revision, indexed_revision FROM reader_revision WHERE book_id = 1').fetchone()
        assert row['revision'] != row['indexed_revision']
    assert tracked.ensure_reader_content(1)['version'] == first['version'] + 1


def test_tracked_upgrade_preserves_published_versions_units_and_markers(tracked):
    first = tracked.ensure_reader_content(1)
    mode = 'summary'
    marker = tracked.resolve_reader_marker(1, {'mode': mode, 'paragraph_id': '1.1', 'offset': 0})
    with tracked.get_connection() as conn:
        before = [tuple(r) for r in conn.execute('SELECT * FROM reader_unit')]
        triggers = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
        for trigger in triggers:
            conn.execute(f'DROP TRIGGER {trigger}')
        if tracked.__class__.__name__ == 'DistillDatabase':
            conn.execute('ALTER TABLE reader_revision RENAME TO distill_reader_revision')
            conn.execute('''CREATE TRIGGER distill_chapter_revision_update AFTER UPDATE ON chapters BEGIN
                UPDATE distill_reader_revision SET revision = revision + 1 WHERE book_id = NEW.book_id; END''')
        else:
            conn.execute('DROP TABLE reader_revision')
    upgraded = type(tracked)(tracked.db_path)
    assert upgraded.ensure_reader_content(1) == first
    assert upgraded.resolve_reader_marker(1, {'mode': mode, 'paragraph_id': '1.1', 'offset': 0}) == marker
    with upgraded.get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM reader_unit')] == before
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'distill_%revision%'").fetchone()
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    # Repeated startup must not erase a pending edit's dirty state.
    with sqlite3.connect(upgraded.db_path) as conn:
        column = 'title' if upgraded.__class__.__name__ == 'DistillDatabase' else 'chapter_title'
        conn.execute(f'UPDATE chapters SET {column} = ? WHERE id = 1', ('New title',))
    restarted = type(upgraded)(upgraded.db_path)
    assert restarted.ensure_reader_content(1)['version'] == first['version'] + 1
