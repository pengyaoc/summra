import json

import pytest
from PIL import Image

from distill import book_format as bf


def _book():
    return {
        'format': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer',
        'lang': 'en', 'cover': 'images/cover.jpg',
        'overview': [{'type': 'p', 'text': 'Hello **world**.'}],
        'parts': [{'title': None, 'chapters': [
            {'title': '1. First', 'blocks': [
                {'type': 'p', 'text': 'Para.'},
                {'type': 'ul', 'items': ['a', 'b']},
                {'type': 'table', 'header': ['h1', 'h2'], 'rows': [['x', 'y']]},
                {'type': 'image', 'src': 'images/cover.jpg', 'caption': 'cap'},
            ]}]}],
        'sources': [{'type': 'p', 'text': 'src'}],
    }


@pytest.fixture
def folder(tmp_path):
    (tmp_path / 'images').mkdir()
    Image.new('RGB', (4, 4), 'red').save(tmp_path / 'images' / 'cover.jpg', 'JPEG')
    (tmp_path / 'book.json').write_text(json.dumps(_book()))
    return tmp_path


def _first_blocks(book):
    return book['parts'][0]['chapters'][0]['blocks']


def test_valid_book_has_no_errors(folder):
    book = bf.load_book(folder)
    assert bf.validate_book(book, folder) == []


def test_unknown_block_type_reported_with_path(folder):
    book = _book()
    book['parts'].insert(0, {'title': 'P0', 'chapters': []})
    book['parts'][1]['chapters'][0]['blocks'].insert(0, {'type': 'div', 'text': 'x'})
    errs = bf.validate_book(book, folder)
    assert "parts[1].chapters[0].blocks[0]: unknown block type 'div'" in errs


def test_missing_image_file_reported(folder):
    book = _book()
    _first_blocks(book)[3]['src'] = 'images/nope.jpg'
    errs = bf.validate_book(book, folder)
    assert any('parts[0].chapters[0].blocks[3]' in e and 'nope.jpg' in e for e in errs)


def test_webp_image_rejected(folder):
    Image.new('RGB', (4, 4)).save(folder / 'images' / 'w.webp', 'WEBP')
    book = _book()
    _first_blocks(book)[3]['src'] = 'images/w.webp'
    errs = bf.validate_book(book, folder)
    assert any('blocks[3]' in e and 'w.webp' in e for e in errs)


def test_image_content_must_match_extension(folder):
    Image.new('RGB', (4, 4)).save(folder / 'images' / 'fake.jpg', 'PNG')
    book = _book()
    book['cover'] = 'images/fake.jpg'
    assert any(e.startswith('cover') for e in bf.validate_book(book, folder))


def test_raw_html_and_links_rejected(folder):
    for bad in ('<b>x</b>', '[a](http://x)'):
        book = _book()
        _first_blocks(book)[0]['text'] = bad
        errs = bf.validate_book(book, folder)
        assert any('parts[0].chapters[0].blocks[0]' in e for e in errs), bad


def test_unbalanced_bold_rejected(folder):
    book = _book()
    _first_blocks(book)[0]['text'] = '**x'
    errs = bf.validate_book(book, folder)
    assert any('parts[0].chapters[0].blocks[0]' in e for e in errs)


def test_malformed_table_rejected(folder):
    book = _book()
    _first_blocks(book)[2]['rows'] = 'oops'
    errs = bf.validate_book(book, folder)
    assert any('blocks[2]' in e for e in errs)


@pytest.mark.parametrize('field,value', [
    ('slug', None), ('title', None), ('format', 2), ('slug', 'Bad Slug'), ('lang', 'english'),
])
def test_required_fields(folder, field, value):
    book = _book()
    if value is None:
        del book[field]
    else:
        book[field] = value
    errs = bf.validate_book(book, folder)
    assert errs and any(field in e for e in errs)


def test_block_text_strips_markup():
    assert bf.block_text({'type': 'p', 'text': '**a** *b*'}) == 'a b'
    assert bf.block_text({'type': 'ul', 'items': ['*x*', 'y']}) == 'x\ny'
    assert bf.block_text({'type': 'table', 'header': ['h'], 'rows': [['a', 'b']]}) == 'h a b'
    assert bf.block_text({'type': 'image', 'src': 'images/a.jpg'}) == ''
    assert bf.block_text({'type': 'image', 'src': 'images/a.jpg', 'caption': 'c'}) == 'c'


def test_iter_chapters_overview_first():
    book = _book()
    chapters = bf.iter_chapters(book)
    assert chapters[0] == (None, 'Overview', book['overview'])
    assert chapters[1][:2] == (None, '1. First')
    book['overview'] = []
    assert bf.iter_chapters(book)[0][1] == '1. First'
