import copy
import json

import pytest
from PIL import Image

SAMPLE_BOOK = {
    'format': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer',
    'lang': 'en', 'cover': 'images/cover.jpg',
    'overview': [{'type': 'p', 'text': 'Hello **world**.'}],
    'parts': [
        {'title': 'Part One', 'chapters': [
            {'title': '1. First', 'blocks': [
                {'type': 'p', 'text': 'one two three'},
                {'type': 'ul', 'items': ['a', 'b']},
                {'type': 'table', 'header': ['h1', 'h2'], 'rows': [['x', 'y']]},
                {'type': 'p', 'text': 'The fourth block has a distinctive phrase.'},
                {'type': 'image', 'src': 'images/cover.jpg', 'caption': None},
            ]},
            {'title': '2. Second', 'blocks': [{'type': 'p', 'text': 'Second chapter.'}]},
        ]},
        {'title': None, 'chapters': [
            {'title': '3. Third', 'blocks': [{'type': 'p', 'text': 'Last block.'}]},
        ]},
    ],
    'sources': [{'type': 'p', 'text': 'src'}],
}


@pytest.fixture
def sample_book():
    return copy.deepcopy(SAMPLE_BOOK)


@pytest.fixture
def write_book(tmp_path):
    """write_book(book_dict) -> folder holding book.json and images/cover.jpg."""
    def _write(book):
        (tmp_path / 'images').mkdir(exist_ok=True)
        Image.new('RGB', (4, 4), 'red').save(tmp_path / 'images' / 'cover.jpg', 'JPEG')
        (tmp_path / 'book.json').write_text(json.dumps(book, ensure_ascii=False))
        return tmp_path
    return _write
