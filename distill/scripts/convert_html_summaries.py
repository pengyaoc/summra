"""One-time converter: owner's HTML book-summary pages -> Distill book folders.

Usage: python -m distill.scripts.convert_html_summaries <src_dir> --out <dir> [--only slug,...] [--pause SECONDS]

Needs beautifulsoup4 (distill/requirements-tools.txt). Writes <out>/<slug>/book.json and
images/, plus <out>/report.md and <out>/report.json. Source pages are only read.
"""
import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from PIL import Image

from distill.book_format import FORMAT_VERSION, block_text, word_count

MAX_WIDTH = 1600
THUMB_WIDTH = 1280
JPEG_QUALITY = 82
FEW_COLOURS = 32
FETCH_ATTEMPTS = 4
USER_AGENT = 'DistillConverter/1.0 (https://github.com/pengyaoc/summra; one-time personal import) python-urllib'

_INLINE_TAGS = frozenset({'a', 'b', 'strong', 'i', 'em', 'span', 'code', 'sup', 'sub', 'u', 'small', 'mark',
                          'abbr', 'cite', 's', 'br', 'kbd', 'q', 'font'})
_BLOCKISH = frozenset({'p', 'div', 'ul', 'ol', 'li', 'br', 'section', 'tr', 'td', 'th', 'blockquote',
                       'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'dt', 'dd'})
_SKIP_TAGS = frozenset({'script', 'style', 'button', 'nav', 'hr', 'noscript', 'meta', 'link', 'head'})
_SKIP_CLASSES = frozenset({'eyebrow', 'chapter-num', 'nav', 'tab-bar', 'listen-btn', 'kp-label',
                           'key-points-label', 'worklog', 'lightbox-overlay', 'lightbox-close'})
_KEYPOINT_CLASSES = frozenset({'keypoints-wrap', 'chapter-points'})
_LOSSY_TAGS = frozenset({'svg', 'iframe', 'canvas', 'video', 'audio', 'object', 'embed', 'picture'})
_KEYPOINT_LABEL_RE = re.compile(r'key\s*points?|要点|关键', re.I)
_KEYPOINT_HEADING_RE = re.compile(r'^(key\s*points?|要点|关键要点)\s*[:：]?$', re.I)
_CJK_RE = re.compile(r'[一-鿿]')
_HTML_RE = re.compile(r'<(?=[A-Za-z/!])')
_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_TITLE_SUFFIX_RE = re.compile(r'\s*[—–-]+\s*(Reading Companion|Book Summary|Chapter Summaries)\s*$', re.I)


@dataclass
class PageReport:
    slug: str
    title: str = ''
    chapters: int = 0
    words: int = 0
    images_embedded: int = 0
    images_downloaded: int = 0
    images_failed: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    empty_chapters: list = field(default_factory=list)
    flagged: bool = False
    author: Optional[str] = None
    lang: str = 'en'
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Fetching

def _fetch_with_retry(fetch: Callable[[str], bytes], url: str) -> bytes:
    """Call fetch, retrying only 429/5xx up to FETCH_ATTEMPTS with 1, 2, 4 s backoff."""
    for attempt in range(FETCH_ATTEMPTS):
        try:
            return fetch(url)
        except Exception as exc:
            code = getattr(exc, 'code', None)
            retriable = isinstance(code, int) and (code == 429 or 500 <= code < 600)
            if not retriable or attempt == FETCH_ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError('unreachable')


def make_fetcher(cache_dir: Path, pause: float = 1.0, timeout: float = 20) -> Callable[[str], bytes]:
    """urllib getter with a User-Agent, timeout, polite pause between downloads and a disk cache."""
    cache_dir = Path(cache_dir)
    try:  # python.org builds on macOS ship without a CA bundle
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = None

    def fetch(url: str) -> bytes:
        cached = cache_dir / hashlib.sha1(url.encode()).hexdigest()
        if cached.is_file():
            return cached.read_bytes()
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            data = response.read()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        time.sleep(pause)
        return data

    return fetch


# ---------------------------------------------------------------------------
# Image handling

_WIKIMEDIA_ORIGINAL_RE = re.compile(
    r'^(https://upload\.wikimedia\.org/wikipedia/commons)/([0-9a-f]/[0-9a-f]{2})/([^/]+\.(?:jpe?g|png))$', re.I)


def _wikimedia_thumb(url: str) -> Optional[str]:
    found = _WIKIMEDIA_ORIGINAL_RE.match(url)
    if not found:
        return None
    base, shard, name = found.groups()
    return f'{base}/thumb/{shard}/{name}/{THUMB_WIDTH}px-{name}'


class _ImageSaver:
    def __init__(self, images_dir: Path, fetch, report: PageReport):
        self.images_dir = images_dir
        self.fetch = fetch
        self.report = report
        self.by_digest = {}
        self.by_src = {}

    def save(self, src: str) -> Optional[str]:
        """Return 'images/<file>' for the image at src, or None (recorded as failed)."""
        src = (src or '').strip()
        if src in self.by_src:
            return self.by_src[src]
        result = None
        try:
            data, embedded = self._load(src)
            result = self._write(data)
            if embedded:
                self.report.images_embedded += 1
            else:
                self.report.images_downloaded += 1
        except Exception:
            self.report.images_failed.append(src[:120] if src else '(empty src)')
        self.by_src[src] = result
        return result

    def _load(self, src: str):
        if src.startswith('data:'):
            header, _, payload = src.partition(',')
            if header.endswith(';base64'):
                return base64.b64decode(payload), True
            return urllib.parse.unquote_to_bytes(payload), True
        if src.startswith(('http://', 'https://')):
            return self._download(src), False
        raise ValueError(f'unsupported image source {src[:40]!r}')

    def _download(self, src: str) -> bytes:
        thumb = _wikimedia_thumb(src)
        if thumb:  # Wikimedia rate-limits full-size originals hard; its own advice is to use thumbnails
            try:
                return _fetch_with_retry(self.fetch, thumb)
            except Exception:
                pass  # e.g. 400 when the original is narrower than the thumb width
        return _fetch_with_retry(self.fetch, src)

    def _write(self, data: bytes) -> str:
        digest = hashlib.sha1(data).hexdigest()
        if digest in self.by_digest:
            return self.by_digest[digest]
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.width > MAX_WIDTH:
                img = img.resize((MAX_WIDTH, max(1, round(img.height * MAX_WIDTH / img.width))), Image.LANCZOS)
            has_alpha = img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info)
            few_colours = img.mode == 'P' and len(img.getcolors(256) or range(257)) <= FEW_COLOURS
            png = has_alpha or few_colours
            if png:
                out = img if img.mode == 'P' and not has_alpha else img.convert('RGBA' if has_alpha else 'RGB')
            else:
                out = img.convert('RGB')
            self.images_dir.mkdir(parents=True, exist_ok=True)
            name = f'img-{len(self.by_digest) + 1:03d}.{"png" if png else "jpg"}'
            if png:
                out.save(self.images_dir / name, 'PNG')
            else:
                out.save(self.images_dir / name, 'JPEG', quality=JPEG_QUALITY)
        self.by_digest[digest] = f'images/{name}'
        return self.by_digest[digest]


# ---------------------------------------------------------------------------
# HTML -> blocks

def _classes(el) -> set:
    return set(el.get('class') or [])


class _Walker:
    """Walk one tab's DOM, yielding ('chapter', title) and ('block', dict) events."""

    def __init__(self, saver: _ImageSaver, report: PageReport):
        self.saver = saver
        self.report = report
        self.skip_ids = set()
        self.keypoint_lists = set()

    # -- inline text ------------------------------------------------------
    def inline(self, node) -> str:
        text = self._inline(node, bold=False, italic=False)
        text = re.sub(r'\s+', ' ', text).strip()
        text = _HTML_RE.sub('‹', text)
        return _LINK_RE.sub(r'[\1]', text)

    def _inline(self, node, bold: bool, italic: bool) -> str:
        parts = []
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                parts.append(str(child).replace('*', ''))
                continue
            if not isinstance(child, Tag) or id(child) in self.skip_ids:
                continue
            name = child.name
            if name in _SKIP_TAGS or name == 'img' or _classes(child) & (_SKIP_CLASSES | {'credit'}):
                continue
            inner = self._inline(child, bold or name in ('b', 'strong'), italic or name in ('i', 'em'))
            if name in ('b', 'strong') and not bold:
                inner = self._wrap(inner, '**')
            elif name in ('i', 'em') and not italic:
                inner = self._wrap(inner, '*')
            if name in _BLOCKISH:
                inner = f' {inner} '
            parts.append(inner)
        return ''.join(parts)

    @staticmethod
    def _wrap(inner: str, marker: str) -> str:
        core = inner.strip()
        if not core:
            return inner
        lead = inner[:len(inner) - len(inner.lstrip())]
        trail = inner[len(inner.rstrip()):]
        return f'{lead}{marker}{core}{marker}{trail}'

    # -- images -----------------------------------------------------------
    def image_block(self, img: Tag, caption: Optional[str] = None) -> Optional[dict]:
        src = self.saver.save(img.get('src') or img.get('data-src') or '')
        if not src:
            return None
        return {'type': 'image', 'src': src, 'caption': caption or None}

    def figure_blocks(self, fig: Tag):
        caption_el = fig.find('figcaption')
        caption = self.inline(caption_el) if caption_el else ''
        first = True
        for img in fig.find_all('img'):
            block = self.image_block(img, caption if first else None)
            if block:
                first = False
                yield ('block', block)

    # -- containers -------------------------------------------------------
    def walk_children(self, el, in_chapter: bool):
        run = []

        def flush():
            if run:
                text = self.inline(_Fragment(run))
                if text:
                    yield ('block', {'type': 'p', 'text': text})
                run.clear()

        for child in list(el.children):
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                run.append(child)
            elif isinstance(child, Tag):
                if (child.name in _INLINE_TAGS and not child.find(['img', 'figure', 'table'])
                        and not _classes(child) & _SKIP_CLASSES):
                    run.append(child)
                else:
                    yield from flush()
                    yield from self.walk(child, in_chapter)
        yield from flush()

    def walk(self, el: Tag, in_chapter: bool):
        name = el.name
        classes = _classes(el)
        if id(el) in self.skip_ids or name in _SKIP_TAGS or classes & _SKIP_CLASSES:
            return
        if name in _LOSSY_TAGS:
            self.note_dropped(name)
        elif name in ('div', 'section', 'article') and 'chapter' in classes:
            yield from self.chapter(el)
        elif name in ('h2', 'h3', 'h4', 'h5', 'h6') and self._labels_list(el):
            return
        elif name == 'h3' and not in_chapter:
            title = self.inline(el)
            if title:
                yield ('chapter', title)
        elif name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            text = self.inline(el)
            if text:
                yield ('block', {'type': 'h', 'text': text})
        elif name == 'p':
            if el.find(['img', 'figure']):
                yield from self.walk_children(el, in_chapter)
            else:
                text = self.inline(el)
                if text:
                    yield ('block', {'type': 'p', 'text': text})
        elif name == 'pre':
            text = self.inline(el)
            if text:
                yield ('block', {'type': 'p', 'text': text})
        elif name in ('ul', 'ol'):
            yield from self.list_block(el)
        elif name == 'blockquote':
            text = self.inline(el)
            if text:
                yield ('block', {'type': 'quote', 'text': text})
        elif name == 'table':
            yield from self.table_block(el)
        elif name == 'figure':
            yield from self.figure_blocks(el)
        elif name == 'img':
            block = self.image_block(el)
            if block:
                yield ('block', block)
        elif classes & _KEYPOINT_CLASSES:
            yield from self.keypoints_container(el, in_chapter)
        elif 'callout' in classes or 'warning-callout' in classes or any(c.endswith('-callout') for c in classes):
            yield from self.callout(el)
        else:
            yield from self.walk_children(el, in_chapter or name in ('div', 'section', 'article') and bool(classes & {'card'}))

    def _labels_list(self, heading: Tag) -> bool:
        """A 'Key Points' heading directly before a list marks that list as keypoints, not a new chapter."""
        if not _KEYPOINT_HEADING_RE.match(self.inline(heading)):
            return False
        sibling = heading.find_next_sibling()
        if sibling is None or sibling.name not in ('ul', 'ol'):
            return False
        self.keypoint_lists.add(id(sibling))
        return True

    def note_dropped(self, label: str):
        self.report.dropped.append(label)

    def list_block(self, el: Tag):
        top = [li for li in el.find_all('li') if li.find_parent(['ul', 'ol']) is el]
        items = [t for t in (self.inline(li) for li in top) if t]
        if not items:
            return
        if 'keypoints' in _classes(el) or id(el) in self.keypoint_lists:
            btype = 'keypoints'
        else:
            btype = el.name
        yield ('block', {'type': btype, 'items': items})

    def table_block(self, el: Tag):
        rows = [tr for tr in el.find_all('tr') if tr.find_parent('table') is el]
        grid = []
        header_row = None
        for tr in rows:
            cells = tr.find_all(['td', 'th'], recursive=False)
            texts = [self.inline(c) for c in cells]
            if not any(texts):
                continue
            is_header = tr.find_parent('thead') is not None or all(c.name == 'th' for c in cells)
            if is_header and header_row is None and not grid:
                header_row = texts
            else:
                grid.append(texts)
        if header_row is None and grid:
            header_row = grid.pop(0)
        if header_row is not None:
            yield ('block', {'type': 'table', 'header': header_row, 'rows': grid})

    def keypoints_container(self, el: Tag, in_chapter: bool):
        lists = [ul for ul in el.find_all(['ul', 'ol']) if not ul.find_parent(['ul', 'ol'])]
        for child in el.children:
            if isinstance(child, Tag) and child.name in ('h4', 'h5', 'h6', 'p') and not child.find(['ul', 'ol']):
                text = self.inline(child)
                if len(text) <= 40 and (child.name != 'p' or lists):
                    self.skip_ids.add(id(child))
        items = [t for ul in lists for t in (self.inline(li) for li in ul.find_all('li', recursive=False)) if t]
        for kind, payload in self.walk_children(el, in_chapter):
            if kind == 'block' and payload['type'] in ('ul', 'ol', 'keypoints'):
                continue
            yield (kind, payload)
        if items:
            yield ('block', {'type': 'keypoints', 'items': items})

    def callout(self, el: Tag):
        kids = [c for c in el.children if isinstance(c, Tag)]
        label = next((c for c in kids if c.name in ('h4', 'h5', 'h6')), None)
        if all(c.name in ('h4', 'h5', 'h6', 'p') for c in kids) and not any(c.find(['img', 'figure']) for c in kids):
            paragraphs = [self.inline(c) for c in kids if c.name == 'p']
            title = self.inline(label) if label else ''
            text = ' '.join(([f'**{title}**'] if title else []) + [p for p in paragraphs if p])
            if text:
                yield ('block', {'type': 'quote', 'text': text})
            return
        if label and _KEYPOINT_LABEL_RE.search(self.inline(label)):
            self.skip_ids.add(id(label))
            lists = [ul for ul in el.find_all(['ul', 'ol']) if not ul.find_parent(['ul', 'ol'])]
            items = [t for ul in lists for t in (self.inline(li) for li in ul.find_all('li', recursive=False)) if t]
            for kind, payload in self.walk_children(el, True):
                if kind == 'block' and payload['type'] in ('ul', 'ol', 'keypoints'):
                    continue
                yield (kind, payload)
            if items:
                yield ('block', {'type': 'keypoints', 'items': items})
            return
        yield from self.walk_children(el, True)

    def chapter(self, el: Tag):
        heading = el.find(['h2', 'h3', 'h4'])
        num_el = el.find(class_=['chapter-num', 'eyebrow'])
        num = self.inline(num_el) if num_el else ''
        title = self.inline(heading) if heading else ''
        if heading:
            self.skip_ids.add(id(heading))
        if not title and not num:
            yield from self.walk_children(el, True)
            return
        yield ('chapter', self.chapter_title(num, title))
        yield from self.walk_children(el, True)

    @staticmethod
    def chapter_title(num: str, title: str) -> str:
        if not num:
            return title
        if not title:
            return num
        digits = re.search(r'\d+', num)
        if digits:
            label = f'{digits.group()}. '
        elif num.startswith('第'):
            label = f'{num} '
        elif num.lower() == title.lower():
            return title
        else:
            label = f'{num}: '
        return title if title.startswith(label.strip()) else label + title


class _Fragment:
    """Minimal node wrapper so a run of sibling inline nodes goes through _Walker.inline."""
    def __init__(self, nodes):
        self.children = nodes


def _events_to_blocks(events) -> list:
    """Flatten events for tabs that have no chapters (Overview, Sources): headings become h blocks."""
    out = []
    for kind, payload in events:
        out.append(payload if kind == 'block' else {'type': 'h', 'text': payload})
    return out


# ---------------------------------------------------------------------------
# Page conversion

_NAME_STOPWORDS = frozenset({'the', 'a', 'an', 'why', 'how', 'what', 'and', 'of'})
_NAME = r"[A-Z][\w.'’-]*(?:\s(?:[A-Z][\w.'’-]*|&|and|de|van|von))*"
_AUTHOR_PATTERNS = (rf"({_NAME})[’']s\s", rf"^({_NAME})(?:,| —| –| -)", rf"(?:—|–|\.)\s*({_NAME})[’']s\s")


def _guess_author(subtitle: str) -> Optional[str]:
    """Best effort: a Chinese '著' byline, or a two-plus-word name next to a possessive or leading the subtitle."""
    zh = re.match(r'\s*([一-鿿][一-鿿·\s]*?)\s*著', subtitle)
    if zh:
        return zh.group(1).strip()
    for pattern in _AUTHOR_PATTERNS:
        for found in re.finditer(pattern, subtitle):
            name = re.sub(r'\s+', ' ', found.group(1)).strip(' ,')
            words = name.split()
            if len(words) >= 2 and words[0].lower() not in _NAME_STOPWORDS:
                return name
    return None


def _author_from_overview(overview: list) -> Optional[str]:
    """Fallback: the first 'Firstname Lastname (' in the opening overview paragraphs."""
    for block in [b for b in overview if b['type'] == 'p'][:3]:
        found = re.search(rf'({_NAME}) \(', block['text'].replace('*', ''))
        if found and len(found.group(1).split()) >= 2 and found.group(1).split()[0].lower() not in _NAME_STOPWORDS:
            return found.group(1)
    return None


def _text_stats(blocks_lists) -> float:
    cjk = total = 0
    for blocks in blocks_lists:
        for block in blocks:
            text = block_text(block)
            cjk += len(_CJK_RE.findall(text))
            total += len(re.sub(r'\s', '', text))
    return cjk / total if total else 0.0


def _tab_buttons(soup) -> dict:
    labels = {}
    for btn in soup.select('.tab-btn'):
        found = re.search(r"switchTab\(\s*['\"]([^'\"]+)['\"]", btn.get('onclick') or '')
        if found:
            labels[found.group(1)] = re.sub(r'\s+', ' ', btn.get_text(' ', strip=True))
    return labels


def convert_page(html: str, slug: str, out_dir: Path, fetch: Callable[[str], bytes]) -> PageReport:
    soup = BeautifulSoup(html, 'html.parser')
    report = PageReport(slug=slug)
    folder = Path(out_dir) / slug
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    saver = _ImageSaver(folder / 'images', fetch, report)
    walker = _Walker(saver, report)

    hero = soup.select_one('.hero')
    h1 = hero.find('h1') if hero else soup.find('h1')
    title = walker.inline(h1) if h1 else (soup.title.get_text(strip=True) if soup.title else slug)
    title = _TITLE_SUFFIX_RE.sub('', title).replace('*', '').strip() or slug
    subtitle_el = hero.select_one('.subtitle') if hero else None
    subtitle = subtitle_el.get_text(' ', strip=True) if subtitle_el else ''
    report.title = title
    report.author = _guess_author(subtitle)

    cover = None
    if hero:
        for img in hero.find_all('img'):
            cover = saver.save(img.get('src') or '')
            if cover:
                break

    labels = _tab_buttons(soup)
    overview, sources, parts = [], [], []
    for tab in soup.select('div.tab-content[id^=tab-]'):
        key = tab['id'][len('tab-'):]
        if 'worklog' in key:
            continue
        events = list(walker.walk_children(tab, False))
        if key == 'overview':
            overview = _events_to_blocks(events)
        elif key == 'sources':
            sources = _events_to_blocks(events)
        else:
            part_title = labels.get(key) or key
            parts.append(_build_part(part_title, events, report))

    if report.author is None:
        report.author = _author_from_overview(overview)

    if cover is None:
        for i, block in enumerate(overview):
            if block['type'] == 'image' and re.search(r'cover|封面', _alt_of(soup, block, saver), re.I):
                cover = block['src']
                del overview[i]
                break

    parts = [p for p in parts if p['chapters']]
    report.chapters = sum(len(p['chapters']) for p in parts)
    all_blocks = [overview] + [c['blocks'] for p in parts for c in p['chapters']]
    report.words = sum(word_count(block_text(b)) for blocks in all_blocks for b in blocks)
    report.lang = 'zh' if _text_stats(all_blocks) > 0.3 else 'en'

    book = {'format': FORMAT_VERSION, 'slug': slug, 'title': title, 'author': report.author,
            'lang': report.lang, 'cover': cover, 'overview': overview, 'parts': parts, 'sources': sources}
    (folder / 'book.json').write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding='utf-8')
    report.dropped = sorted(set(report.dropped))
    report.flagged = bool(report.chapters == 0 or report.dropped or report.empty_chapters or report.images_failed)
    return report


def _alt_of(soup, block, saver) -> str:
    """Alt text of the first <img> whose saved file is block['src'] (used to spot cover images)."""
    for src, saved in saver.by_src.items():
        if saved == block['src']:
            for img in soup.find_all('img'):
                if (img.get('src') or '').strip() == src:
                    return img.get('alt') or ''
    return ''


def _build_part(part_title: str, events: list, report: PageReport) -> dict:
    intro, chapters = [], []
    for kind, payload in events:
        if kind == 'chapter':
            chapters.append({'title': payload, 'blocks': []})
        elif chapters:
            chapters[-1]['blocks'].append(payload)
        else:
            intro.append(payload)
    kept = []
    if any(b['type'] != 'h' for b in intro):
        kept.append({'title': f'{part_title} — Introduction', 'blocks': intro})
    for chapter in chapters:
        if chapter['blocks']:
            kept.append(chapter)
        else:
            report.empty_chapters.append(f'{part_title} / {chapter["title"]}')
    return {'title': part_title, 'chapters': kept}


# ---------------------------------------------------------------------------
# Batch driver

def _slug_for(path: Path) -> str:
    slug = re.sub(r'-(book-)?summary$', '', path.stem.lower())
    return re.sub(r'[^a-z0-9]+', '-', slug).strip('-')


def _dup_key(title: str) -> str:
    return re.sub(r'\W+', '', re.split(r'\s[—–-]\s|[:：]', title)[0].lower())


def _authors_compatible(a: Optional[str], b: Optional[str]) -> bool:
    """True when either author is unknown or the two share a name word (Klein vs Diamandis: False)."""
    if not a or not b:
        return True
    words = lambda name: {w for w in re.findall(r'\w+', name.lower()) if len(w) > 2 and w != 'and'}  # noqa: E731
    return bool(words(a) & words(b))


def find_duplicates(reports: list) -> list:
    """Groups of pages with the same normalised title prefix and compatible authors."""
    by_key = {}
    for r in reports:
        if r.title:
            by_key.setdefault(_dup_key(r.title), []).append(r)
    groups = []
    for members in by_key.values():
        remaining = list(members)
        while remaining:
            first = remaining.pop(0)
            group = [first] + [r for r in remaining if _authors_compatible(first.author, r.author)]
            remaining = [r for r in remaining if r not in group]
            if len(group) > 1:
                groups.append(sorted(r.slug for r in group))
    return sorted(groups)


def _write_reports(out: Path, reports: list, duplicates: list) -> None:
    (out / 'report.json').write_text(
        json.dumps({'pages': [asdict(r) for r in reports], 'duplicates': duplicates}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    lines = ['# Conversion report', '', f'{len(reports)} pages, {sum(r.flagged for r in reports)} flagged.', '',
             '| slug | title | chapters | words | emb | dl | failed | flagged |', '|---|---|---|---|---|---|---|---|']
    for r in reports:
        lines.append(f'| {r.slug} | {r.title} | {r.chapters} | {r.words} | {r.images_embedded} | '
                     f'{r.images_downloaded} | {len(r.images_failed)} | {"FLAG" if r.flagged else ""} |')
    lines += ['', '## Flagged', '']
    for r in (r for r in reports if r.flagged):
        lines.append(f'- **{r.slug}**: chapters={r.chapters}' + ''.join(
            f'; {label}={value}' for label, value in (
                ('dropped', r.dropped), ('empty_chapters', r.empty_chapters),
                ('images_failed', r.images_failed), ('error', r.error)) if value))
    lines += ['', '## Likely duplicates', '']
    lines += [f'- {", ".join(group)}' for group in duplicates] or ['- none']
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description='Convert HTML book summaries to Distill book folders.')
    parser.add_argument('src_dir', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--only', help='comma-separated slugs to convert')
    parser.add_argument('--pause', type=float, default=1.0, help='seconds to wait after each download')
    args = parser.parse_args(argv)

    only = set(args.only.split(',')) if args.only else None
    args.out.mkdir(parents=True, exist_ok=True)
    fetch = make_fetcher(args.out / '_cache', pause=args.pause)
    reports = []
    for path in sorted(args.src_dir.glob('*.html')):
        slug = _slug_for(path)
        if only and slug not in only:
            continue
        try:
            report = convert_page(path.read_text(encoding='utf-8', errors='replace'), slug, args.out, fetch)
        except Exception as exc:
            report = PageReport(slug=slug, flagged=True, error=f'{type(exc).__name__}: {exc}')
        print(f'{slug}: {report.chapters} chapters, {report.words} words'
              f'{", FLAGGED" if report.flagged else ""}', flush=True)
        reports.append(report)
    _write_reports(args.out, reports, find_duplicates(reports))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
