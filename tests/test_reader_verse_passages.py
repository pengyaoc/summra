"""Poetry books align by verse passage, not by line.

Bug this guards against: the reader split every source line into its own
unit, so Paradise Lost paired one verse line with a whole Plain English
paragraph and the remaining lines got false "unavailable" gaps. For an
is_poetry book a blank-line block is one unit and keeps its line breaks.
"""
import pytest

PASSAGE_1 = "Of Man’s first disobedience, and the fruit\nOf that forbidden tree whose mortal taste\nBrought death into the World."
PASSAGE_2 = "Sing, Heavenly Muse, that, on the secret top\nOf Oreb, or of Sinai, didst inspire."
PLAIN = "Sing about the first time people disobeyed God.\n\nSing, heavenly Muse, who inspired Moses."


def _units(db, book_id, mode):
    manifest = db.get_reader_manifest(book_id)
    units = []
    for descriptor in (d for d in manifest['segments'] if d['mode'] == mode):
        units.extend(db.get_reader_segment(book_id, descriptor['id'], mode)['units'])
    return units


@pytest.fixture
def db(test_db_path):
    from backend import models
    return models.Database(db_path=test_db_path)


def _add(db, is_poetry, original):
    book_id = db.add_book(title='Poem', author='A', filename='p.txt', full_text='x', is_poetry=is_poetry)
    db.add_chapter(book_id, 1, 'Book I', 'Summary.', original, modern_english_text=PLAIN)
    return book_id


def test_poetry_side_by_side_pairs_passages(db):
    book_id = _add(db, True, f"{PASSAGE_1}\n\n{PASSAGE_2}")
    rows = _units(db, book_id, 'side_by_side')
    assert len(rows) == 2
    assert rows[0]['members']['original']['content'] == PASSAGE_1
    assert rows[0]['members']['plain']['content'].startswith('Sing about the first time')
    assert rows[1]['members']['original']['content'] == PASSAGE_2
    assert all(row['members']['plain']['available'] for row in rows)


def test_poetry_original_mode_keeps_line_breaks(db):
    book_id = _add(db, True, f"{PASSAGE_1}\n\n{PASSAGE_2}")
    units = _units(db, book_id, 'original')
    assert [u['content'] for u in units] == [PASSAGE_1, PASSAGE_2]
    assert units[0]['word_count'] == 19


def test_prose_still_splits_every_line(db):
    book_id = _add(db, False, f"{PASSAGE_1}\n\n{PASSAGE_2}")
    assert len(_units(db, book_id, 'original')) == 5


def test_poetry_flag_change_republishes(db):
    book_id = _add(db, False, f"{PASSAGE_1}\n\n{PASSAGE_2}")
    assert len(_units(db, book_id, 'original')) == 5
    db.update_book_poetry_flag(book_id, True)
    assert len(_units(db, book_id, 'original')) == 2
