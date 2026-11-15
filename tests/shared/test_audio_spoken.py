from shared.audio.spoken import SpokenUnit, spoken_checksum, spoken_units

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


# Sentences: what the reader highlights while a new recording plays.
from shared.audio.spoken import split_sentences  # noqa: E402


def test_split_sentences_english():
    assert split_sentences('One thing. Two things! Three? Four') == ['One thing.', 'Two things!', 'Three?', 'Four']


def test_split_sentences_keeps_abbreviations_initials_and_decimals():
    text = 'Mr. Smith met Dr. Jones in the U.S. last year, e.g. in May. It cost 3.5 dollars. J. K. Rowling agreed.'
    assert split_sentences(text) == ['Mr. Smith met Dr. Jones in the U.S. last year, e.g. in May.',
                                     'It cost 3.5 dollars.', 'J. K. Rowling agreed.']


def test_split_sentences_keeps_closing_quotes_and_brackets():
    assert split_sentences('He said, “Stop.” Then he left. (It was late.) Done.') == [
        'He said, “Stop.”', 'Then he left.', '(It was late.)', 'Done.']


def test_split_sentences_lowercase_after_period_is_not_a_new_sentence():
    assert split_sentences('See p. 5 and fig. three for more.') == ['See p. 5 and fig. three for more.']


def test_split_sentences_chinese():
    assert split_sentences('读书很好。运动也好！为什么？“对。”最后') == ['读书很好。', '运动也好！', '为什么？', '“对。”', '最后']


def test_split_sentences_empty_and_whitespace():
    assert split_sentences('') == []
    assert split_sentences('   \n ') == []
    assert split_sentences('  Only one  ') == ['Only one']
