"""Distill book folder format (version 1): load, validate, and read block text.

A book is a folder with `book.json` and `images/<file>.(jpg|png)`. See
docs/superpowers/specs/2026-10-24-distill-design.md section 5.2.
"""
import json
import re
from pathlib import Path
from typing import Optional

from PIL import Image

from shared.reader.blocks import block_text  # noqa: F401  (re-exported)

FORMAT_VERSION = 1
BLOCK_TYPES = frozenset({'p', 'h', 'ul', 'ol', 'quote', 'keypoints', 'table', 'image'})

_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
_LANG_RE = re.compile(r'^[a-z]{2}$')
_HTML_RE = re.compile(r'<[A-Za-z/!]')
_LINK_RE = re.compile(r'\[[^\]]*\]\([^)]*\)')
_IMAGE_FORMATS = {'.jpg': 'JPEG', '.png': 'PNG'}
_IMAGE_SUFFIXES = frozenset(_IMAGE_FORMATS)
CJK_RE = re.compile(r'[一-鿿]')
# Must match ReaderIndexMixin._reader_word_count in shared/reader/index.py.
_WORD_RE = re.compile(r"\b[\w’'-]+\b")


def load_book(folder: Path) -> dict:
    return json.loads((Path(folder) / 'book.json').read_text(encoding='utf-8'))


def list_images(folder: Path) -> list:
    """Sorted image files under folder/images (jpg and png only)."""
    images_dir = Path(folder) / 'images'
    if not images_dir.is_dir():
        return []
    return sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES)


def word_count(text: str) -> int:
    """Each CJK character counts one; other runs of word characters count one each."""
    return len(CJK_RE.findall(text)) + len(_WORD_RE.findall(CJK_RE.sub(' ', text)))


def _check_inline(text, where, errors):
    if not isinstance(text, str):
        errors.append(f'{where}: text must be a string')
        return
    if _HTML_RE.search(text):
        errors.append(f'{where}: raw HTML is not allowed')
    if _LINK_RE.search(text):
        errors.append(f'{where}: links are not allowed')
    if text.count('**') % 2:
        errors.append(f'{where}: unbalanced ** (bold)')
    if text.replace('**', '').count('*') % 2:
        errors.append(f'{where}: unbalanced * (italic)')


def _check_image(src, where, folder, errors):
    path = Path(src) if isinstance(src, str) else None
    ext = path.suffix.lower() if path else ''
    if (path is None or path.parent != Path('images') or ext not in _IMAGE_FORMATS):
        errors.append(f'{where}: image {src!r} must be images/<file>.jpg or .png')
        return
    full = Path(folder) / path
    if not full.is_file():
        errors.append(f'{where}: image file {src!r} not found')
        return
    try:
        with Image.open(full) as img:
            actual = img.format
    except Exception:
        errors.append(f'{where}: image {src!r} is not a readable image')
        return
    if actual != _IMAGE_FORMATS[ext]:
        errors.append(f'{where}: image {src!r} is actually {actual}, not {_IMAGE_FORMATS[ext]}')


def _check_list(value, where, errors):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f'{where}: must be a list of strings')
        return
    for i, v in enumerate(value):
        _check_inline(v, f'{where}[{i}]', errors)


def _check_block(block, where, folder, errors):
    if not isinstance(block, dict):
        errors.append(f'{where}: block must be an object')
        return
    btype = block.get('type')
    if btype not in BLOCK_TYPES:
        errors.append(f'{where}: unknown block type {btype!r}')
        return
    if btype in ('p', 'h', 'quote'):
        _check_inline(block.get('text'), where, errors)
    elif btype in ('ul', 'ol', 'keypoints'):
        _check_list(block.get('items'), f'{where}.items', errors)
    elif btype == 'table':
        _check_list(block.get('header'), f'{where}.header', errors)
        rows = block.get('rows')
        if not isinstance(rows, list):
            errors.append(f'{where}.rows: must be a list of rows')
        else:
            for i, row in enumerate(rows):
                _check_list(row, f'{where}.rows[{i}]', errors)
    else:  # image
        _check_image(block.get('src'), where, folder, errors)
        if block.get('caption') is not None:
            _check_inline(block['caption'], f'{where}.caption', errors)


def _check_blocks(blocks, where, folder, errors):
    if not isinstance(blocks, list):
        errors.append(f'{where}: must be a list of blocks')
        return
    for i, block in enumerate(blocks):
        _check_block(block, f'{where}[{i}]', folder, errors)


def validate_book(book: dict, folder: Path) -> list:
    errors = []
    if book.get('format') != FORMAT_VERSION:
        errors.append(f'format: must be {FORMAT_VERSION}')
    slug = book.get('slug')
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        errors.append('slug: required, lowercase letters, digits and hyphens')
    if not isinstance(book.get('title'), str) or not book['title'].strip():
        errors.append('title: required')
    if not isinstance(book.get('lang'), str) or not _LANG_RE.match(book['lang']):
        errors.append('lang: required, two lowercase letters')
    categories = book.get('categories', [])
    if not isinstance(categories, list) or any(not isinstance(c, str) or not c.strip() for c in categories):
        errors.append('categories: must be a list of non-empty strings')
    if book.get('cover') is not None:
        _check_image(book['cover'], 'cover', folder, errors)
    _check_blocks(book.get('overview', []), 'overview', folder, errors)
    _check_blocks(book.get('sources', []), 'sources', folder, errors)
    parts = book.get('parts')
    if not isinstance(parts, list):
        errors.append('parts: must be a list')
        return errors
    for pi, part in enumerate(parts):
        pwhere = f'parts[{pi}]'
        chapters = part.get('chapters') if isinstance(part, dict) else None
        if not isinstance(chapters, list):
            errors.append(f'{pwhere}.chapters: must be a list')
            continue
        for ci, chapter in enumerate(chapters):
            cwhere = f'{pwhere}.chapters[{ci}]'
            if not isinstance(chapter, dict) or not chapter.get('title'):
                errors.append(f'{cwhere}: title required')
                continue
            _check_blocks(chapter.get('blocks'), f'{cwhere}.blocks', folder, errors)
    return errors


def iter_chapters(book: dict) -> list:
    """(part_title, chapter_title, blocks) in reading order, Overview first if non-empty."""
    out: list = []
    if book.get('overview'):
        out.append((None, 'Overview', book['overview']))
    for part in book.get('parts', []):
        part_title: Optional[str] = part.get('title')
        for chapter in part.get('chapters', []):
            out.append((part_title, chapter['title'], chapter.get('blocks', [])))
    return out
