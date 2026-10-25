"""shared.reader.blocks: the Python half of the shared block renderer (used
by server-rendered Kindle pages). The rendered text must equal block_text,
because the reader recovers a saved place by matching that text."""
import html
import json
import re
from pathlib import Path

import pytest

from shared.reader import blocks
from shared.reader.index import ReaderIndexMixin

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'reader_blocks'
CASES = json.loads((FIXTURES / 'blocks.json').read_text(encoding='utf-8'))
PAGINATED = re.compile(r'<(?:p|h[1-6]|blockquote|pre|ul|ol|figure)[\s>]', re.I)


def _dom_text(markup):
    return html.unescape(re.sub(r'<[^>]+>', '', str(markup)))


@pytest.mark.parametrize('case', CASES, ids=[c['name'] for c in CASES])
def test_render_block_matches_fixture(case):
    tag, class_name, content = blocks.render_block(case['block'])
    assert (tag, class_name, str(content)) == tuple(case['strict'].values())


@pytest.mark.parametrize('case', CASES, ids=[c['name'] for c in CASES])
def test_dom_text_matches_block_text(case):
    _, _, content = blocks.render_block(case['block'])
    normalize = ReaderIndexMixin._reader_normalize_quote
    assert normalize(_dom_text(content)) == normalize(blocks.block_text(case['block']))


@pytest.mark.parametrize('case', CASES, ids=[c['name'] for c in CASES])
def test_content_has_no_paginated_block_elements(case):
    _, _, content = blocks.render_block(case['block'])
    assert not PAGINATED.search(str(content))


def test_block_element_sets_data_i():
    assert blocks.block_element({'type': 'h', 'text': 'A *b*'}, 7) == \
        '<h3 class="reader-section-heading" data-i="7">A <em>b</em></h3>'
    assert blocks.block_element({'type': 'p', 'text': 'x'}, 0) == '<p data-i="0">x</p>'
    image = blocks.block_element({'type': 'image', 'src': 'images/a.png'}, 2, image_base='/b/')
    assert image == '<figure class="reader-figure" data-i="2"><img src="/b/images/a.png" alt=""></figure>'


def test_unknown_type_falls_back_to_p():
    assert blocks.render_block({'type': 'callout', 'text': 'Hi *there*'}) == ('p', '', 'Hi <em>there</em>')


def test_escape_matches_dom_text_escaping():
    """The Plainly golden's fallback half was produced by the browser's DOM
    escaping (textContent -> innerHTML). Units without inline markup must
    come out of escape_text identically."""
    units = json.loads((FIXTURES / 'plainly_units.json').read_text(encoding='utf-8'))
    golden = json.loads((FIXTURES / 'plainly_golden.json').read_text(encoding='utf-8'))['fallback']
    checked = 0
    for unit, rendered in zip(units, golden):
        value = unit.strip()
        if rendered['className'] or re.search(r'[*_]', value):
            continue
        assert blocks.escape_text(value) == rendered['content'], unit
        checked += 1
    assert checked >= 5
    assert blocks.escape_text('a b <&>"\'') == 'a&nbsp;b &lt;&amp;&gt;"\''


def test_book_format_block_text_is_shared():
    from distill import book_format
    assert book_format.block_text is blocks.block_text
    assert blocks.block_text({'type': 'verse', 'lines': ['*a*', 'b']}) == 'a\nb'
    assert blocks.block_text({'type': 'li', 'text': '• **x**'}) == '• x'
