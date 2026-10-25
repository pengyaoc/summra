import json

import pytest

from distill.models import DistillDatabase


@pytest.fixture
def db(tmp_path):
    return DistillDatabase(tmp_path / 'distill.db')


def _chapter_blocks(book):
    return book['parts'][0]['chapters'][0]['blocks']


def test_import_round_trip(db, sample_book, write_book):
    book_id = db.import_book(write_book(sample_book))

    book = db.get_book(book_id)
    assert (book['slug'], book['title'], book['author'], book['lang']) == ('my-book', 'My Book', 'A. Writer', 'en')
    assert book['sources'] == sample_book['sources']
    assert db.get_book_by_slug('my-book')['id'] == book_id
    assert [b['id'] for b in db.list_books()] == [book_id]

    chapters = db.get_chapters(book_id)
    assert [(c['ordinal'], c['part_title'], c['title']) for c in chapters] == [
        (0, None, 'Overview'), (1, 'Part One', '1. First'), (2, 'Part One', '2. Second'), (3, None, '3. Third')]
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
    assert [c['ordinal'] for c in db.get_chapters(book_id)] == [0, 1, 2]


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
    assert modes['summary']['unit_count'] == 1 + 5 + 1 + 1
    for mode in ('original', 'plain', 'side_by_side'):
        assert modes[mode]['availability'] == 'unavailable'
    last = db.get_chapters(book_id)[-1]
    assert modes['summary']['terminal_paragraph_id'] == f"{last['id']}.0"
    assert [s['kind'] for s in manifest['structure']] == ['chapter', 'part', 'chapter', 'chapter', 'chapter']
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
