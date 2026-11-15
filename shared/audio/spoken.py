"""What a chapter's audio says: the title, then the spoken blocks, per reader unit."""
import hashlib
import json
import re
from typing import List, NamedTuple

from shared.reader.blocks import block_text

_TEXT_TYPES = ('p', 'h', 'quote')
_LIST_TYPES = ('ul', 'ol', 'keypoints')


class SpokenUnit(NamedTuple):
    paragraph_id: str  # the reader unit id, "<chapter_id>.<block_index>"
    parts: List[str]   # one per list item; title is prepended to the first unit


def _parts(block: dict) -> List[str]:
    if block.get('type') in _TEXT_TYPES:
        return [block_text(block)]
    if block.get('type') in _LIST_TYPES:
        return [block_text({'type': 'p', 'text': item}) for item in block.get('items', [])]
    return []


_CLOSERS = '”"’）」』】》)]'
_OPENERS = '“"‘(（「『【《['
# A Chinese sentence end always ends a sentence. An English one does when a space and
# a capital, digit or opening mark follow, unless it closes an abbreviation or initial.
_CJK_END = re.compile(rf'[。！？…]+[{re.escape(_CLOSERS)}]*')
_LATIN_END = re.compile(rf'[.!?]+[{re.escape(_CLOSERS)}]*(?=\s+[\p{{Lu}}\d{re.escape(_OPENERS)}]|[\u4e00-\u9fff])'
                        .replace('\\p{Lu}', 'A-Z\u00c0-\u00de'))
_ABBREVIATIONS = {'mr', 'mrs', 'ms', 'dr', 'st', 'vs', 'etc', 'prof', 'jr', 'sr', 'no', 'fig', 'p', 'pp', 'vol',
                  'e.g', 'i.e', 'cf', 'al', 'inc', 'ltd', 'co', 'mt', 'gen', 'col', 'lt', 'sgt', 'rev', 'ed', 'eds'}


def _abbreviation_before(text: str, end: int) -> bool:
    if text[end] != '.':
        return False
    word = re.search(r'[\w.]*$', text[:end]).group().lower()
    return word in _ABBREVIATIONS or bool(re.fullmatch(r'(?:[a-z]\.)*[a-z]', word))  # J. or U.S.


def split_sentences(text: str) -> List[str]:
    """Sentences of one spoken part, in order; whitespace between them is dropped."""
    ends = {m.end() for m in _CJK_END.finditer(text)}
    ends |= {m.end() for m in _LATIN_END.finditer(text) if not _abbreviation_before(text, m.start())}
    sentences, start = [], 0
    for end in sorted(ends) + [len(text)]:
        piece = text[start:end].strip()
        if piece:
            sentences.append(piece)
        start = end
    return sentences


def spoken_units(chapter: dict) -> List[SpokenUnit]:
    units = []
    for index, block in enumerate(chapter['blocks']):
        parts = [p for p in _parts(block) if p.strip()]
        if parts:
            units.append(SpokenUnit(f"{chapter['id']}.{index}", parts))
    title = chapter['title']
    if not units:
        return [SpokenUnit(f"{chapter['id']}.0", [title])]
    first = units[0]
    units[0] = SpokenUnit(first.paragraph_id, [title, *first.parts])
    return units


def spoken_checksum(units: List[SpokenUnit]) -> str:
    canonical = json.dumps([[u.paragraph_id, u.parts] for u in units], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
