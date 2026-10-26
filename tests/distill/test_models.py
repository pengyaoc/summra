import json

import pytest

from distill.models import DistillDatabase


@pytest.fixture
def db(tmp_path):
    return DistillDatabase(tmp_path / 'distill.db')


def _chapter_blocks(book):
    return book['parts'][0]['chapters'][0]['blocks']


def test_cover_backfill_is_idempotent_and_reimport_invalidates_variants(db, sample_book, write_book):
    from PIL import Image
    folder = write_book(sample_book)
    bid = db.import_book(folder)
    before_chapters = db.get_chapters(bid)
    token = db.get_book(bid)['cover_thumbnail_token']
    assert token and db.generate_cover_thumbnails() == 0
    with db.get_connection() as conn:
        conn.execute('DELETE FROM cover_thumbnails')
    assert db.get_book(bid)['cover_thumbnail_token'] is None
    assert db.generate_cover_thumbnails() == 1
    assert db.get_book(bid)['cover_thumbnail_token'] == token
    assert db.get_chapters(bid) == before_chapters
    Image.new('RGB', (600, 900), 'blue').save(folder / 'images' / 'cover.jpg')
    db.import_book(folder)
    new_token = db.get_book(bid)['cover_thumbnail_token']
    assert new_token != token
    assert db.get_cover_thumbnail('my-book', token, 'avif') is None
    assert db.get_cover_thumbnail('my-book', new_token, 'avif')
    assert db.generate_cover_thumbnails() == 0



def test_reader_index_freshness_survives_restart_and_external_edits(db, sample_book, write_book, monkeypatch):
    import sqlite3
    bid = db.import_book(write_book(sample_book))
    first = db.ensure_reader_content(bid)
    restarted = DistillDatabase(db.db_path)
    with monkeypatch.context() as patch:
        patch.setattr(restarted, '_reader_load_chapters', lambda *a: pytest.fail('unchanged content was loaded'))
        assert restarted.ensure_reader_content(bid) == first
        assert restarted.library_word_totals([bid])[bid]['summary'] > 0
    chapter = db.get_chapters(bid)[1]
    with sqlite3.connect(db.db_path) as conn:
        conn.execute('UPDATE chapters SET title = ? WHERE id = ?', ('Changed externally', chapter['id']))
    assert restarted.ensure_reader_content(bid)['version'] == first['version'] + 1
    assert restarted.get_reader_manifest(bid)['structure'][2]['title'] == 'Changed externally'


def test_index_freshness_does_not_swallow_concurrent_content_changes(db, sample_book, write_book, monkeypatch):
    bid = db.import_book(write_book(sample_book))
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    checksum = db._reader_source_checksum
    started = Event()
    pending = []

    def edit(chapter_id):
        started.set()
        with db.get_connection() as conn:
            conn.execute('UPDATE chapters SET title = ? WHERE id = ?', ('Concurrent title', chapter_id))

    with ThreadPoolExecutor(max_workers=1) as pool:
        def edit_during_checksum(chapters):
            if not pending:
                pending.append(pool.submit(edit, chapters[1]['id']))
                assert started.wait(2)
            return checksum(chapters)

        monkeypatch.setattr(db, '_reader_source_checksum', edit_during_checksum)
        old = db.ensure_reader_content(bid)
        pending[0].result(timeout=5)
    assert db.ensure_reader_content(bid)['version'] == old['version'] + 1




def test_append_sources_preserves_existing_chapters_and_reader_units(db, sample_book, write_book):
    sources = sample_book['sources']
    sample_book['sources'] = []
    bid = db.import_book(write_book(sample_book))
    before = db.get_chapters(bid)
    db.ensure_reader_content(bid)
    with db.get_connection() as conn:
        conn.execute('UPDATE books SET sources = ? WHERE id = ?', (json.dumps(sources), bid))
        units = [tuple(r) for r in conn.execute('SELECT * FROM reader_unit ORDER BY ordinal')]
    assert db.append_source_chapters() == [bid]
    assert db.get_chapters(bid) == before  # default is read-only preview
    assert db.append_source_chapters(dry_run=False) == [bid]
    after = db.get_chapters(bid)
    assert after[:-1] == before
    assert after[-1]['ordinal'] == before[-1]['ordinal'] + 1
    assert after[-1]['title'] == 'Source' and after[-1]['blocks'] == sources
    db.ensure_reader_content(bid)
    with db.get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM reader_unit ORDER BY ordinal')][:len(units)] == units
    assert db.append_source_chapters(dry_run=False) == []
    sample_book['sources'] = sources
    db.import_book(write_book(sample_book))
    assert db.get_chapters(bid) == after  # reimport preserves the new Source ID too


def test_empty_sources_do_not_add_a_chapter(db, sample_book, write_book):
    sample_book['sources'] = []
    bid = db.import_book(write_book(sample_book))
    assert db.get_chapters(bid)[-1]['title'] == '3. Third'
    assert db.append_source_chapters(dry_run=False) == []


def test_toc_repair_preserves_reader_coordinates_and_reimport(db, sample_book, write_book):
    sample_book['parts'][0]['chapters'][0]['title'] = '1. 1 First'
    folder = write_book(sample_book)
    bid = db.import_book(folder)
    chapters = db.get_chapters(bid)
    assert chapters[1]['title'] == '1. First'  # old folders cannot reintroduce the error
    with db.get_connection() as conn:
        conn.execute('UPDATE chapters SET title = ? WHERE id = ?', ('1. 1 First', chapters[1]['id']))
    db.ensure_reader_content(bid)
    with db.get_connection() as conn:
        before = [tuple(r) for r in conn.execute('SELECT * FROM reader_unit ORDER BY mode, ordinal')]
    preview = db.repair_toc()
    assert preview == [{'slug': 'my-book', 'id': chapters[1]['id'], 'before': '1. 1 First', 'after': '1. First'}]
    assert db.get_chapters(bid)[1]['title'] == '1. 1 First'
    assert db.repair_toc(dry_run=False) == preview
    db.ensure_reader_content(bid)
    after = db.get_chapters(bid)
    assert [(c['id'], c['ordinal'], c['part_title'], c['blocks']) for c in after] == [
        (c['id'], c['ordinal'], c['part_title'], c['blocks']) for c in chapters]
    with db.get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM reader_unit ORDER BY mode, ordinal')] == before
    assert db.repair_toc(dry_run=False) == []
    db.import_book(folder)
    assert db.get_chapters(bid) == after


def test_import_round_trip(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))

    book = db.get_book(book_id)
    assert (book['slug'], book['title'], book['author'], book['lang']) == ('my-book', 'My Book', 'A. Writer', 'en')
    assert book['sources'] == sample_book['sources']
    assert db.get_book_by_slug('my-book')['id'] == book_id
    assert [b['id'] for b in db.list_books()] == [book_id]

    chapters = db.get_chapters(book_id)
    assert [(c['ordinal'], c['part_title'], c['title']) for c in chapters] == [
        (0, None, 'Overview'), (1, 'Part One', '1. First'), (2, 'Part One', '2. Second'),
        (3, None, '3. Third'), (4, None, 'Source')]
    assert chapters[-1]['blocks'] == sample_book['sources']
    assert chapters[1]['blocks'] == _chapter_blocks(sample_book)

    mime, data = db.get_image(book_id, 'cover.jpg')
    assert mime == 'image/jpeg' and data[:2] == b'\xff\xd8'
    assert book['cover_image_id'] is not None
    assert db.get_image(book_id, 'missing.jpg') is None


def test_reimport_keeps_book_id_and_bumps_reader_version(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    chapter_ids = [c['id'] for c in db.get_chapters(book_id)]
    first = db.ensure_reader_content(book_id)

    sample_book['parts'][0]['chapters'][1]['blocks'][0]['text'] = 'Changed.'
    assert db.import_book(write_book(sample_book)) == book_id

    assert [c['id'] for c in db.get_chapters(book_id)] == chapter_ids
    assert db.ensure_reader_content(book_id)['version'] == first['version'] + 1
    assert len(db.list_books()) == 1


def test_reimport_with_fewer_chapters_drops_extras(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    del sample_book['parts'][1]
    db.import_book(write_book(sample_book))
    assert [c['ordinal'] for c in db.get_chapters(book_id)] == [0, 1, 2, 3]
    assert db.get_chapters(book_id)[-1]['title'] == 'Source'


def test_invalid_book_is_not_imported(db, sample_book, write_book):
    sample_book['title'] = ''
    _chapter_blocks(sample_book)[0]['text'] = '**unclosed'
    folder = write_book(sample_book)
    with pytest.raises(ValueError) as err:
        db.import_book(folder)
    assert 'title: required' in str(err.value) and 'blocks[0]' in str(err.value)
    assert db.list_books() == []


def test_manifest_counts_blocks_as_units(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    manifest = db.get_reader_manifest(book_id)
    modes = {m['mode']: m for m in manifest['modes']}
    assert modes['summary']['availability'] == 'available'
    assert modes['summary']['unit_count'] == 1 + 5 + 1 + 1 + 1
    for mode in ('original', 'plain', 'side_by_side'):
        assert modes[mode]['availability'] == 'unavailable'
    last = db.get_chapters(book_id)[-1]
    assert modes['summary']['terminal_paragraph_id'] == f"{last['id']}.0"
    assert [s['kind'] for s in manifest['structure']] == ['chapter', 'part', 'chapter', 'chapter', 'chapter', 'chapter']
    assert manifest['structure'][1]['title'] == 'Part One'


def test_segment_serves_block_json(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    db.ensure_reader_content(book_id)
    segment = db.get_reader_segment(book_id, 'summary.0', 'summary')
    assert json.loads(segment['units'][0]['content']) == {'type': 'p', 'text': 'Hello **world**.'}


def test_word_count_uses_visible_text_not_json(db):
    unit = json.dumps({'type': 'p', 'text': 'one two three'}, sort_keys=True)
    assert db._reader_word_count(unit) == 3
    assert db._reader_word_count('plain words here') == 3


def test_image_block_without_caption_is_a_unit(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    chapter = db.get_chapters(book_id)[1]
    image_ordinal = 4
    assert chapter['blocks'][image_ordinal]['type'] == 'image'
    db.ensure_reader_content(book_id)
    conn = db.get_connection()
    row = conn.execute(
        "SELECT word_count, gap FROM reader_unit WHERE book_id=? AND mode='summary' "
        "AND chapter_id=? AND chapter_ordinal=?", (book_id, chapter['id'], image_ordinal)).fetchone()
    conn.close()
    assert (row['word_count'], row['gap']) == (0, 0)
    paragraph_id = f"{chapter['id']}.{image_ordinal}"
    marker = {'mode': 'summary', 'chapter_id': chapter['id'], 'paragraph_id': paragraph_id, 'offset': 0}
    assert db.resolve_reader_marker(book_id, marker)['paragraph_id'] == paragraph_id


def test_cjk_text_counts_characters(db):
    mixed = json.dumps({'type': 'p', 'text': '全球通史 is **great**'}, ensure_ascii=False)
    assert db._reader_word_count(mixed) == 4 + 2
    assert db._reader_word_count(json.dumps({'type': 'p', 'text': '你好，世界。'}, ensure_ascii=False)) == 4


def test_normalize_quote_uses_visible_text(db):
    unit = json.dumps({'type': 'p', 'text': 'Hello **World**'})
    assert db._reader_normalize_quote(unit) == 'hello world'


def test_recover_marker_by_quote_after_reimport(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    chapter = db.get_chapters(book_id)[1]
    version = db.ensure_reader_content(book_id)['version']
    marker = {'mode': 'summary', 'content_version': version, 'chapter_id': chapter['id'],
              'paragraph_id': f"{chapter['id']}.3", 'offset': 0,
              'quote': 'The fourth block has a distinctive phrase.'}

    _chapter_blocks(sample_book).insert(0, {'type': 'p', 'text': 'Inserted before.'})
    db.import_book(write_book(sample_book))

    recovered = db.recover_reader_marker(book_id, marker)
    assert recovered['recovery_level'] == 'quote'
    assert recovered['paragraph_id'] == f"{chapter['id']}.4"


def test_library_hooks(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    chapters = db.get_chapters(book_id)
    assert db.library_books([book_id]) == {
        book_id: {'id': book_id, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer',
                  'cover_image_url': None}}
    assert db.chapter_titles([chapters[1]['id']]) == {
        chapters[1]['id']: {'id': chapters[1]['id'], 'chapter_number': 1, 'chapter_title': '1. First'}}
    assert db.library_books([]) == {} and db.chapter_titles([]) == {}


def test_deleting_book_cascades(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    conn = db.get_connection()
    with conn:
        conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
    assert conn.execute('SELECT COUNT(*) FROM chapters').fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM images').fetchone()[0] == 0
    conn.close()


def test_list_books_orders_by_title_case_insensitive_then_id(db, sample_book, write_book):
    ids = {}
    for slug, title in [('b1', 'banana'), ('a1', 'Apple'), ('c1', 'cherry'), ('b2', 'Banana')]:
        sample_book.update(slug=slug, title=title)
        ids[slug] = db.import_book(write_book(sample_book))

    assert [b['id'] for b in db.list_books()] == [ids['a1'], ids['b1'], ids['b2'], ids['c1']]


def test_get_book_cover_image_name(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    assert db.get_book(book_id)["cover_image"] == "cover.jpg"
    assert db.list_books()[0]["cover_image"] == "cover.jpg"

    del sample_book["cover"]
    assert db.get_book(db.import_book(write_book(sample_book)))["cover_image"] is None


def test_count_chapters_excludes_overview(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))
    assert db.count_chapters(book_id) == 4  # 3 chapters + Source, excluding Overview
    assert db.count_chapters(9999) == 0
    sample_book.update(slug='no-overview', overview=[])
    other = db.import_book(write_book(sample_book))
    assert db.count_chapters(other) == 3  # ordinals 0..3: the first chapter sits at ordinal 0


def test_categories_round_trip_and_old_schema_migration(tmp_path, sample_book, write_book):
    import sqlite3
    path = tmp_path / 'legacy.db'
    db = DistillDatabase(path)
    book_id = db.import_book(write_book(sample_book))
    with sqlite3.connect(path) as conn:
        conn.execute('ALTER TABLE books DROP COLUMN categories')
    db = DistillDatabase(path)
    assert db.get_book(book_id)['categories'] == []
    sample_book['categories'] = ['Science', 'History']
    db.import_book(write_book(sample_book))
    assert db.get_book(book_id)['categories'] == ['Science', 'History']
