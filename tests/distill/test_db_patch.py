"""Incremental content deploys: send only the rows that differ, leave live-only books alone."""
import json
import sqlite3

import pytest

from distill.models import DistillDatabase
from distill.scripts.db_patch import apply_patch, build_patch, integrity_problems, main as patch_main, row_hashes


@pytest.fixture
def pair(tmp_path, sample_book, write_book):
    """A local DB and a live DB that start out identical."""
    local = DistillDatabase(tmp_path / 'local' / 'distill.db')
    book_id = local.import_book(write_book(sample_book))
    live_path = tmp_path / 'live.db'
    with sqlite3.connect(local.db_path) as source, sqlite3.connect(live_path) as target:
        source.backup(target)
    return local, live_path, book_id


def patch_for(local, live_path):
    with sqlite3.connect(live_path) as live:
        remote = row_hashes(live)
    with sqlite3.connect(local.db_path) as source:
        return json.loads(json.dumps(build_patch(source, remote)))


def dump(path, table):
    with sqlite3.connect(path) as conn:
        return conn.execute(f'SELECT * FROM {table} ORDER BY 1, 2').fetchall()


def count(patch):
    return sum(len(t['rows']) for t in patch['upsert'].values()) + sum(len(v) for v in patch['delete'].values())


def test_identical_databases_need_no_patch(pair):
    local, live, _ = pair
    assert count(patch_for(local, live)) == 0


def test_only_the_changed_row_is_sent(pair):
    local, live, book_id = pair
    chapter = local.get_chapters(book_id)[1]
    local.save_chapter_audio(chapter['id'], b'opus', [], 1, 'c', 'v', 'siri', 1.0)
    patch = patch_for(local, live)
    assert count(patch) == 1 and len(patch['upsert']['chapter_audio']['rows']) == 1
    apply_patch(live, patch)
    assert dump(live, 'chapter_audio') == dump(local.db_path, 'chapter_audio')
    assert count(patch_for(local, live)) == 0


def test_changed_audio_updates_in_place(pair):
    local, live, book_id = pair
    chapter = local.get_chapters(book_id)[0]
    local.save_chapter_audio(chapter['id'], b'one', [], 1, 'c', 'v', 'siri', 1.0)
    apply_patch(live, patch_for(local, live))
    local.save_chapter_audio(chapter['id'], b'two', [], 2, 'c', 'v', 'siri', 1.0)
    apply_patch(live, patch_for(local, live))
    assert dump(live, 'chapter_audio') == dump(local.db_path, 'chapter_audio')


def test_new_book_arrives_complete(pair, sample_book, write_book):
    local, live, _ = pair
    other = {**sample_book, 'slug': 'second-book', 'title': 'Second'}
    local.import_book(write_book(other))
    apply_patch(live, patch_for(local, live))
    for table in ('books', 'chapters', 'images', 'cover_thumbnails'):
        assert dump(live, table) == dump(local.db_path, table)
    with sqlite3.connect(live) as conn:
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_book_only_on_the_live_site_is_left_alone(pair):
    local, live, book_id = pair
    with sqlite3.connect(live) as conn:
        conn.execute("INSERT INTO books (id, slug, title, author, lang, sources, imported_at, content_checksum, categories) "
                     "VALUES (900, 'live-only', 'L', 'A', 'en', '[]', 'x', 'y', '[]')")
        conn.execute("INSERT INTO chapters (id, book_id, ordinal, title, blocks) VALUES (9000, 900, 1, 'T', '[]')")
    patch = patch_for(local, live)
    assert count(patch) == 0
    apply_patch(live, patch)
    assert any(row[0] == 900 for row in dump(live, 'books'))
    assert any(row[0] == 9000 for row in dump(live, 'chapters'))


def test_rows_removed_from_a_shared_book_are_removed_live(pair):
    local, live, book_id = pair
    chapter = local.get_chapters(book_id)[-1]
    with sqlite3.connect(local.db_path) as conn:
        conn.execute('DELETE FROM chapters WHERE id = ?', (chapter['id'],))
    apply_patch(live, patch_for(local, live))
    assert dump(live, 'chapters') == dump(local.db_path, 'chapters')


def test_same_id_for_different_books_is_refused(pair):
    local, live, book_id = pair
    with sqlite3.connect(live) as conn:
        conn.execute("UPDATE books SET slug = 'someone-else' WHERE id = ?", (book_id,))
    with pytest.raises(ValueError, match='someone-else'):
        patch_for(local, live)


def test_same_slug_under_another_id_is_refused(pair):
    local, live, book_id = pair
    with sqlite3.connect(live) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        for table, column in (('books', 'id'), ('chapters', 'book_id'), ('images', 'book_id')):
            conn.execute(f'UPDATE {table} SET {column} = 900 WHERE {column} = ?', (book_id,))
    with pytest.raises(ValueError, match='already'):
        patch_for(local, live)


def test_swapped_chapter_order_applies(pair):
    local, live, book_id = pair
    first, second = local.get_chapters(book_id)[:2]
    with sqlite3.connect(local.db_path) as conn:
        conn.execute('UPDATE chapters SET ordinal = -1 WHERE id = ?', (first['id'],))
        conn.execute('UPDATE chapters SET ordinal = ? WHERE id = ?', (first['ordinal'], second['id']))
        conn.execute('UPDATE chapters SET ordinal = ? WHERE id = ?', (second['ordinal'], first['id']))
    apply_patch(live, patch_for(local, live))
    assert dump(live, 'chapters') == dump(local.db_path, 'chapters')


def test_failure_changes_nothing(pair):
    local, live, book_id = pair
    chapter = local.get_chapters(book_id)[0]
    local.save_chapter_audio(chapter['id'], b'opus', [], 1, 'c', 'v', 'siri', 1.0)
    patch = patch_for(local, live)
    patch['upsert']['chapter_audio']['rows'][0][0] = 123456  # no such chapter
    before = dump(live, 'chapter_audio')
    with pytest.raises(ValueError, match='foreign key'):
        apply_patch(live, patch)
    assert dump(live, 'chapter_audio') == before


def test_a_changed_chapter_tells_the_reader_to_reindex(pair):
    local, live, book_id = pair
    with sqlite3.connect(live) as conn:
        before = conn.execute('SELECT revision FROM reader_revision WHERE book_id = ?', (book_id,)).fetchone()[0]
    with sqlite3.connect(local.db_path) as conn:
        conn.execute("UPDATE chapters SET title = 'New title' WHERE book_id = ? AND ordinal = 1", (book_id,))
    apply_patch(live, patch_for(local, live))
    with sqlite3.connect(live) as conn:
        assert conn.execute('SELECT revision FROM reader_revision WHERE book_id = ?', (book_id,)).fetchone()[0] > before


def test_a_healthy_database_has_no_integrity_problems(pair):
    _, live_path, _ = pair
    with sqlite3.connect(live_path) as live:
        assert integrity_problems(live) == []


def orphan_a_chapter(live_path):
    with sqlite3.connect(live_path) as live:  # foreign keys are off by default on this connection
        live.execute('UPDATE chapters SET book_id = 999999 WHERE id = (SELECT MIN(id) FROM chapters)')


def test_a_row_pointing_at_a_missing_parent_is_a_problem(pair):
    _, live_path, _ = pair
    orphan_a_chapter(live_path)
    with sqlite3.connect(live_path) as live:
        assert any('chapters' in problem for problem in integrity_problems(live))


def test_check_command_exits_nonzero_and_names_the_problem(pair, capsys):
    _, live_path, _ = pair
    orphan_a_chapter(live_path)

    with pytest.raises(SystemExit) as stopped:
        patch_main(['check', '--db', str(live_path)])

    assert stopped.value.code == 1
    assert 'chapters' in capsys.readouterr().out


def test_check_command_passes_a_healthy_database(pair, capsys):
    _, live_path, _ = pair

    patch_main(['check', '--db', str(live_path)])

    assert 'ok' in capsys.readouterr().out
