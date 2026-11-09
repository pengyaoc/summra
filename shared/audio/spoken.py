"""What a chapter's audio says: the title, then the spoken blocks, per reader unit."""
import hashlib
import json
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
