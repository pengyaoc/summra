"""The shared block render vocabulary, in Python for server-rendered pages
(Kindle). shared/static/js/blocks.js renders the same blocks for the web
reader; tests/shared/test_block_parity.py keeps the two identical.

Block types: p, h, verse, li, quote, ul, ol, keypoints, table, image. Inline
markup is 'strict' only (escape, then **bold** and *italic*): 'markdown'
needs marked, which exists only in the browser.
"""
import re

from markupsafe import Markup

_STRONG_RE = re.compile(r'\*\*(.+?)\*\*')
_EM_RE = re.compile(r'\*(.+?)\*')


def escape_text(s) -> str:
    """What the DOM produces for a text node's innerHTML (JS escapeText)."""
    return (str(s or '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace(' ', '&nbsp;'))


def _quote_attr(s) -> str:
    return escape_text(s).replace('"', '&quot;')


def format_inline(text) -> Markup:
    html = escape_text((text or '').strip())
    html = _STRONG_RE.sub(r'<strong>\1</strong>', html)
    return Markup(_EM_RE.sub(r'<em>\1</em>', html))


def render_block(block, image_base='') -> tuple:
    """(tag, class_name, content) for one block, as JS renderBlock returns."""
    block = block or {}
    btype = block.get('type')

    def items(values):
        return '\n'.join(f'<li>{format_inline(v)}</li>' for v in values or [])

    def cells(row, tag):
        return ' '.join(f'<{tag}>{format_inline(c)}</{tag}>' for c in row or [])

    if btype == 'h':
        return 'h3', 'reader-section-heading', format_inline(block.get('text'))
    if btype == 'verse':
        return 'p', 'reader-verse', Markup('<br>\n'.join(format_inline(l) for l in block.get('lines') or []))
    if btype == 'li':
        return 'p', 'reader-list-item', format_inline(block.get('text'))
    if btype == 'quote':
        return 'blockquote', 'reader-quote', format_inline(block.get('text'))
    if btype in ('ul', 'ol'):
        return btype, 'reader-list', Markup(items(block.get('items')))
    if btype == 'keypoints':
        return 'ul', 'reader-keypoints', Markup(items(block.get('items')))
    if btype == 'table':
        header = block.get('header')
        head = f'<thead><tr>{cells(header, "th")}</tr></thead> ' if header else ''
        rows = '\n'.join(f'<tr>{cells(row, "td")}</tr>' for row in block.get('rows') or [])
        return 'table', 'reader-table', Markup(f'{head}<tbody>{rows}</tbody>')
    if btype == 'image':
        caption = block.get('caption')
        figcaption = f' <figcaption>{format_inline(caption)}</figcaption>' if caption else ''
        return 'figure', 'reader-figure', Markup(
            f'<img src="{image_base}{_quote_attr(block.get("src"))}" alt="">{figcaption}')
    return 'p', '', format_inline(block.get('text'))


def block_element(block, index, image_base='') -> Markup:
    tag, class_name, content = render_block(block, image_base)
    attr = f' class="{class_name}"' if class_name else ''
    return Markup(f'<{tag}{attr} data-i="{index}">{content}</{tag}>')


def _strip_markup(text: str) -> str:
    return text.replace('**', '').replace('*', '')


def block_text(block: dict) -> str:
    """The plain text a block shows, for word counts and quote recovery."""
    btype = block.get('type')
    if btype in ('p', 'h', 'quote', 'li'):
        return _strip_markup(block.get('text', ''))
    if btype in ('ul', 'ol', 'keypoints'):
        return '\n'.join(_strip_markup(i) for i in block.get('items', []))
    if btype == 'verse':
        return '\n'.join(_strip_markup(line) for line in block.get('lines', []))
    if btype == 'table':
        cells = list(block.get('header', []))
        for row in block.get('rows', []):
            cells.extend(row)
        return ' '.join(_strip_markup(c) for c in cells)
    if btype == 'image':
        return _strip_markup(block.get('caption') or '')
    return ''
