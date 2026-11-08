from distill.audio.spoken import SpokenUnit, spoken_checksum, spoken_units

CHAPTER = {
    'id': 7, 'title': '1. First',
    'blocks': [
        {'type': 'p', 'text': 'Hello **world**.'},
        {'type': 'ul', 'items': ['a', '*b*']},
        {'type': 'table', 'header': ['h1', 'h2'], 'rows': [['x', 'y']]},
        {'type': 'quote', 'text': 'A quote.'},
        {'type': 'image', 'src': 'images/cover.jpg', 'caption': 'A caption'},
        {'type': 'keypoints', 'items': ['k1']},
    ],
}


def test_skips_table_and_image():
    assert [u.paragraph_id for u in spoken_units(CHAPTER)] == ['7.0', '7.1', '7.3', '7.5']


def test_list_items_are_parts():
    assert spoken_units(CHAPTER)[1] == SpokenUnit('7.1', ['a', 'b'])


def test_title_is_first_part():
    assert spoken_units(CHAPTER)[0].parts == ['1. First', 'Hello world.']


def test_only_tables_keeps_title():
    chapter = {'id': 9, 'title': 'T', 'blocks': [{'type': 'table', 'header': ['a'], 'rows': []}]}
    assert spoken_units(chapter) == [SpokenUnit('9.0', ['T'])]


def test_checksum_changes_with_text():
    same = spoken_checksum(spoken_units(CHAPTER))
    assert same == spoken_checksum(spoken_units(CHAPTER))
    edited = {**CHAPTER, 'blocks': [{'type': 'p', 'text': 'Hello world!'}] + CHAPTER['blocks'][1:]}
    assert spoken_checksum(spoken_units(edited)) != same
