"""Reader storage keeps book text once, in `chapters`.

Bug this guards against: the reader compiled a second copy of every
paragraph (plus normalized quotes, 37-char UUID keys in four tables, and
every retired version), and `books.full_text` held the raw book again — a
~130MB library grew to 0.8-1.2GB. Now `reader_unit` holds only integer
coordinates and counts; segment text is re-split from `chapters` on read.
"""
import pytest

READER_TABLES = {'reader_version', 'reader_unit'}
OLD_TABLES = {
    'reader_content_version', 'reader_mode_manifest', 'reader_structure_entry', 'reader_segment',
    'reader_paragraph', 'reader_alignment_row', 'reader_alignment_member', 'reader_paragraph_mapping',
}


@pytest.fixture
def db(test_db_path):
    from backend import models
    return models.Database(db_path=test_db_path)


def _book(db, original="First paragraph.\nSecond paragraph.", plain="First plain.\nSecond plain."):
    book_id = db.add_book(title='Store', author='A', filename='store.txt', full_text='ignored text')
    chapter_id = db.add_chapter(book_id, 1, 'One', 'Summary one.', original, modern_english_text=plain)
    return book_id, chapter_id


def _segment_units(db, book_id, mode):
    manifest = db.get_reader_manifest(book_id)
    units = []
    for descriptor in (d for d in manifest['segments'] if d['mode'] == mode):
        units.extend(db.get_reader_segment(book_id, descriptor['id'], mode)['units'])
    return units


def _tables(db):
    conn = db.get_connection()
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _columns(db, table):
    conn = db.get_connection()
    try:
        return {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
    finally:
        conn.close()


def test_reader_tables_hold_no_text(db):
    book_id, _ = _book(db)
    db.get_reader_manifest(book_id)
    tables = _tables(db)
    assert READER_TABLES <= tables
    assert not (OLD_TABLES & tables)
    assert not {'content', 'normalized_quote', 'quote', 'text'} & _columns(db, 'reader_unit')


def test_books_table_has_no_full_text(db):
    book_id, _ = _book(db)
    assert 'full_text' not in _columns(db, 'books')
    assert 'full_text' not in db.get_book(book_id)


def test_segment_text_comes_from_chapters(db):
    book_id, chapter_id = _book(db)
    original = _segment_units(db, book_id, 'original')
    assert [u['content'] for u in original] == ['First paragraph.', 'Second paragraph.']
    assert [u['id'] for u in original] == [f'{chapter_id}.0', f'{chapter_id}.1']
    side = _segment_units(db, book_id, 'side_by_side')
    assert side[1]['members']['plain']['content'] == 'Second plain.'
    assert side[1]['members']['original']['content'] == 'Second paragraph.'


def test_recompile_replaces_units_and_keeps_no_history(db):
    book_id, _ = _book(db)
    first = db.get_reader_manifest(book_id)
    db.add_chapter(book_id, 1, 'One', 'Summary one.', "New opening.\nFirst paragraph.\nSecond paragraph.",
                   modern_english_text="New plain.\nFirst plain.\nSecond plain.")
    second = db.get_reader_manifest(book_id)
    assert second['content_version'] == first['content_version'] + 1
    conn = db.get_connection()
    try:
        versions = conn.execute('SELECT COUNT(*) FROM reader_version WHERE book_id = ?', (book_id,)).fetchone()[0]
        units = conn.execute("SELECT COUNT(*) FROM reader_unit WHERE book_id = ? AND mode = 'original'",
                             (book_id,)).fetchone()[0]
    finally:
        conn.close()
    assert versions == 1
    assert units == 3


def test_old_marker_recovers_by_quote_after_insertion(db):
    book_id, chapter_id = _book(db)
    first = db.get_reader_manifest(book_id)
    db.add_chapter(book_id, 1, 'One', 'Summary one.', "New opening.\nFirst paragraph.\nSecond paragraph.",
                   modern_english_text="New plain.\nFirst plain.\nSecond plain.")
    recovered = db.recover_reader_marker(book_id, {
        'mode': 'original', 'content_version': first['content_version'], 'chapter_id': chapter_id,
        'paragraph_id': f'{chapter_id}.1', 'offset': 0.5, 'quote': 'Second paragraph.',
    })
    assert recovered['paragraph_id'] == f'{chapter_id}.2'
    assert recovered['recovery_level'] == 'quote'


def test_old_marker_without_quote_match_falls_back_to_position(db):
    book_id, chapter_id = _book(db)
    first = db.get_reader_manifest(book_id)
    db.add_chapter(book_id, 1, 'One', 'Summary one.', "Rewritten one.\nRewritten two.",
                   modern_english_text="P1.\nP2.")
    recovered = db.recover_reader_marker(book_id, {
        'mode': 'original', 'content_version': first['content_version'], 'chapter_id': chapter_id,
        'paragraph_id': f'{chapter_id}.1', 'offset': 0, 'quote': 'gone entirely',
    })
    assert recovered['paragraph_id'] == f'{chapter_id}.1'
    assert recovered['recovery_level'] == 'ordinal'


def test_mapping_between_modes_is_positional(db):
    book_id, chapter_id = _book(db)
    manifest = db.get_reader_manifest(book_id)
    marker = {'mode': 'original', 'content_version': manifest['content_version'], 'chapter_id': chapter_id,
              'paragraph_id': f'{chapter_id}.1', 'offset': 0}
    assert db.map_reader_marker(book_id, marker, 'plain')['paragraph_id'] == f'{chapter_id}.1'
    assert db.map_reader_marker(book_id, marker, 'side_by_side')['paragraph_id'] == f'{chapter_id}.1'
    assert db.map_reader_marker(book_id, marker, 'summary')['paragraph_id'] == f'{chapter_id}.0'


def test_unknown_ids_resolve_to_nothing(db):
    book_id, _ = _book(db)
    manifest = db.get_reader_manifest(book_id)
    assert db.get_reader_segment(book_id, 'not-a-real-segment', 'original') is None
    assert db.resolve_reader_marker(book_id, {
        'mode': 'original', 'content_version': manifest['content_version'], 'paragraph_id': 'para_x', 'offset': 0,
    }) is None


def test_marker_with_unresolvable_id_recovers_by_quote_even_at_same_version(db):
    # Version numbers restart after the storage migration, so an old marker
    # can carry the current version number with an old-format ID.
    book_id, chapter_id = _book(db)
    manifest = db.get_reader_manifest(book_id)
    recovered = db.recover_reader_marker(book_id, {
        'mode': 'original', 'content_version': manifest['content_version'], 'chapter_id': chapter_id,
        'paragraph_id': 'para_f6575ed5c27a4caf90e935f75581b450', 'offset': 0.2, 'quote': 'Second paragraph.',
    })
    assert recovered['paragraph_id'] == f'{chapter_id}.1'
    assert recovered['recovery_level'] == 'quote'


def test_migration_continues_version_numbers_from_old_tables(test_db_path):
    # Markers saved before the migration carry old version numbers; the
    # first new version must be higher so the client treats them as stale.
    import sqlite3
    from backend import models
    db = models.Database(db_path=test_db_path)
    book_id, _ = _book(db)
    conn = sqlite3.connect(test_db_path)
    conn.execute("DROP TABLE reader_version")
    conn.execute("CREATE TABLE reader_content_version (id INTEGER PRIMARY KEY, book_id INTEGER, version INTEGER)")
    conn.executemany("INSERT INTO reader_content_version (book_id, version) VALUES (?, ?)", [(book_id, 1), (book_id, 3)])
    conn.commit()
    conn.close()
    db = models.Database(db_path=test_db_path)
    assert db.get_reader_manifest(book_id)['content_version'] == 4
    assert 'reader_content_version' not in _tables(db)


def test_source_checksum_is_stable_for_fixture_book(db):
    # Saved reading positions are tied to source_checksum; moving the reader
    # index into shared/ must not change it for existing books.
    book_id = db.add_book(title='Pinned', author='A', filename='pinned.txt', full_text='ignored text')
    db.add_chapter(book_id, 1, 'One', 'Summary one.', 'First paragraph.\nSecond paragraph.',
                   modern_english_text='First plain.\nSecond plain.')
    db.add_chapter(book_id, 2, 'Two', 'Summary two.', 'Third paragraph.', modern_english_text='Third plain.')
    version = db.ensure_reader_content(book_id)
    assert version['source_checksum'] == 'b6a1f7374cb20c818f4534ef272287bef3bcd6c11189f4eeee3c0551a29bc7dc'
