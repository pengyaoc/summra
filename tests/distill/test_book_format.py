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


def test_toc_repairs_preserve_meaningful_numbers_and_are_idempotent():
    rows = [
        {'part_title': 'Part I', 'title': '1. First'},
        {'part_title': 'Part II', 'title': '1. Second'},
        {'part_title': '1. Growth', 'title': '1.1 Time Spans'},
        {'part_title': '1. Growth', 'title': '1.2 Figures of Merit'},
        {'part_title': 'Math', 'title': '1. 1 + 1 = Two'},
        {'part_title': 'Years', 'title': '2020: A Year'},
        {'part_title': 'Book I', 'title': 'Chapter I: Labour'},
        {'part_title': 'Book II', 'title': 'Chapter I: Stock'},
        {'part_title': '上册', 'title': '第一章 引言'},
        {'part_title': '下册', 'title': '第一章 导言'},
    ]
    assert bf.normalize_toc_titles(rows) == rows
    broken = [{'part_title': '第一部分', 'title': '第一部分 — Introduction'},
              {'part_title': '第一部分', 'title': '1. 1 A heading'}]
    repaired = bf.normalize_toc_titles(broken, 'zh')
    assert [c['title'] for c in repaired] == ['本节概览', '1. A heading']
    assert bf.normalize_toc_titles(repaired, 'zh') == repaired
    assert broken[0]['title'].endswith(' — Introduction')  # input is not mutated


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
    assert chapters[-1] == (None, 'Source', book['sources'])
    book['overview'] = []
    assert bf.iter_chapters(book)[0][1] == '1. First'
    book['sources'] = []
    assert bf.iter_chapters(book)[-1][1] == '1. First'


def test_word_count_counts_cjk_characters_and_words():
    assert bf.word_count('你好，世界。') == 4
    assert bf.word_count('全球通史 is great') == 4 + 2
    assert bf.word_count("don't stop-start") == 2


def test_word_count_empty_text():
    assert bf.word_count('') == 0


def test_list_images_returns_sorted_jpg_and_png_files(tmp_path):
    (tmp_path / 'images').mkdir()
    for name in ('b.png', 'a.jpg', 'notes.txt', 'c.gif'):
        (tmp_path / 'images' / name).write_bytes(b'x')
    (tmp_path / 'images' / 'dir.jpg').mkdir()

    assert [p.name for p in bf.list_images(tmp_path)] == ['a.jpg', 'b.png']


def test_list_images_without_images_dir_is_empty(tmp_path):
    assert bf.list_images(tmp_path) == []


@pytest.mark.parametrize('categories', ['Science', [4], [''], ['  '], None])
def test_invalid_categories_rejected(folder, categories):
    book = _book()
    book['categories'] = categories
    assert any('categories' in error for error in bf.validate_book(book, folder))
