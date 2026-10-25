import io
import json
import urllib.error
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip('bs4')

from distill.book_format import load_book, validate_book  # noqa: E402
from distill.scripts import convert_html_summaries as conv  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures'


def _jpeg_bytes(size=(8, 8)):
    buf = io.BytesIO()
    Image.new('RGB', size, (10, 120, 200)).save(buf, 'JPEG')
    return buf.getvalue()


def _no_fetch(url):
    raise AssertionError(f'unexpected fetch of {url}')


def _convert(name, tmp_path, fetch=_no_fetch):
    html = (FIXTURES / name).read_text(encoding='utf-8')
    slug = name.split('.')[0].replace('_', '-')
    report = conv.convert_page(html, slug, tmp_path, fetch)
    return report, load_book(tmp_path / slug)


def test_tabs_become_parts_and_overview(tmp_path):
    report, book = _convert('page_a.html', tmp_path)

    assert book['title'] == 'Tiny Book'
    assert book['author'] == 'Jane Doe'
    assert book['lang'] == 'en'
    assert [b['type'] for b in book['overview']] == ['h', 'p', 'p', 'table']
    assert [p['title'] for p in book['parts']] == ['The Basics']
    titles = [c['title'] for c in book['parts'][0]['chapters']]
    assert titles == ['The Basics — Introduction', 'Why Small Works', 'Counting Things']
    assert book['sources'] == [{'type': 'h', 'text': 'Sources & Notes'},
                               {'type': 'p', 'text': 'Edition used: first.'}]
    assert report.chapters == 3


def test_div_chapter_with_number_and_no_overview(tmp_path):
    report, book = _convert('page_b.html', tmp_path)

    assert book['overview'] == []
    assert [p['title'] for p in book['parts']] == ['Part One', 'Part Two']
    assert [c['title'] for c in book['parts'][0]['chapters']] == ['1. The Start', '2. The Middle']
    middle = book['parts'][0]['chapters'][1]['blocks']
    assert middle[-1] == {'type': 'quote', 'text': '**Remember** Be careful.'}


def test_worklog_dropped(tmp_path):
    _, book = _convert('page_a.html', tmp_path)

    assert 'did a thing' not in json.dumps(book)
    assert 'Worklog' not in json.dumps(book)


def test_keypoints_and_table_blocks(tmp_path):
    _, book = _convert('page_a.html', tmp_path)

    blocks = book['parts'][0]['chapters'][1]['blocks']
    assert [b['type'] for b in blocks] == ['image', 'p', 'ul', 'h', 'ol', 'quote', 'keypoints']
    assert blocks[-1] == {'type': 'keypoints', 'items': ['Point one', 'Point *two*']}
    assert blocks[3] == {'type': 'h', 'text': 'A sub-heading'}
    second = book['parts'][0]['chapters'][2]['blocks']
    assert second[-1] == {'type': 'keypoints', 'items': ['Count them']}  # label paragraph dropped
    table = book['overview'][-1]
    assert table == {'type': 'table', 'header': ['Tab', 'Theme'], 'rows': [['Basics', 'Why **small**']]}


def test_inline_markup_converted(tmp_path):
    _, book = _convert('page_a.html', tmp_path)

    lead, second = book['overview'][1], book['overview'][2]
    assert lead['text'].startswith('Small things **matter** a lot')
    assert '*' not in lead['text'].replace('**matter**', '')  # literal stars dropped
    assert second['text'].startswith('Plain *italic* and a linked phrase and a **bold *both*** run.')
    assert '‹b literal' in second['text']
    assert 'x < y' in second['text']  # a lone < before a space is left alone


def test_data_uri_image_written_as_jpeg_or_png(tmp_path):
    report, book = _convert('page_a.html', tmp_path)

    image = book['parts'][0]['chapters'][1]['blocks'][0]
    assert image['caption'] == 'A red square.'  # credit span removed
    path = tmp_path / 'page-a' / image['src']
    assert path.suffix in ('.jpg', '.png')
    with Image.open(path) as img:
        assert img.format == ('JPEG' if path.suffix == '.jpg' else 'PNG')
    assert report.images_embedded == 1 and report.images_downloaded == 0


def test_hotlink_retries_on_429_then_succeeds(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(conv.time, 'sleep', sleeps.append)
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith('missing.jpg'):
            raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
        if len(calls) <= 2:
            raise urllib.error.HTTPError(url, 429, 'Too Many', {}, None)
        return _jpeg_bytes()

    report, book = _convert('page_c.html', tmp_path, fetch)

    assert sleeps == [1, 2]
    assert report.images_downloaded == 1
    assert book['overview'][1]['type'] == 'image'
    assert report.images_failed == ['https://img.example.com/missing.jpg']
    assert calls.count('https://img.example.com/missing.jpg') == 1  # 404 is not retried


def test_hotlink_failure_reported_not_raised(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(conv.time, 'sleep', sleeps.append)
    calls = []

    def fetch(url):
        calls.append(url)
        raise urllib.error.HTTPError(url, 503, 'Unavailable', {}, None)

    report, book = _convert('page_c.html', tmp_path, fetch)

    assert len(report.images_failed) == 2
    assert report.flagged
    assert len(calls) == 8  # 4 bounded attempts per image
    assert sleeps == [1, 2, 4] * 2
    assert all(b['type'] != 'image' for b in book['overview'])
    assert report.images_downloaded == 0


def test_generic_fetch_error_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(conv.time, 'sleep', lambda s: pytest.fail('should not sleep'))

    def fetch(url):
        raise TimeoutError('boom')

    report, _ = _convert('page_c.html', tmp_path, fetch)

    assert len(report.images_failed) == 2


def test_svg_and_unreadable_images_are_failed(tmp_path):
    html = ('<div class="hero"><h1>S</h1></div><div class="tab-content" id="tab-overview">'
            '<figure><img src="data:image/svg+xml;utf8,&lt;svg/&gt;"></figure>'
            '<figure><img src=""></figure><p>text</p></div>')
    report = conv.convert_page(html, 's', tmp_path, _no_fetch)

    assert len(report.images_failed) == 2
    assert report.flagged


def test_report_fields_and_flags(tmp_path):
    a, _ = _convert('page_a.html', tmp_path)
    b, _ = _convert('page_b.html', tmp_path)

    assert not a.flagged and a.words > 0 and a.empty_chapters == []
    assert b.flagged
    assert b.empty_chapters == ['Part Two / 4. Empty One']
    assert b.dropped == ['svg']
    assert [c for c in (tmp_path / 'page-b').iterdir()] == [tmp_path / 'page-b' / 'book.json']


def test_cjk_language_and_author(tmp_path):
    report, book = _convert('page_c.html', tmp_path, lambda url: _jpeg_bytes())

    assert book['lang'] == 'zh'
    assert book['author'] == '张三'
    assert report.words > 20


@pytest.mark.parametrize('name', ['page_a.html', 'page_b.html', 'page_c.html'])
def test_output_passes_validate_book(name, tmp_path):
    _, book = _convert(name, tmp_path, lambda url: _jpeg_bytes() if 'pic' in url else (_ for _ in ()).throw(OSError()))
    slug = book['slug']

    assert validate_book(book, tmp_path / slug) == []


def test_main_writes_reports_and_flags_duplicates(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    page = (FIXTURES / 'page_b.html').read_text(encoding='utf-8')
    (src / 'abundance-book-summary.html').write_text(page.replace('<h1>Chaptered</h1>', '<h1>Abundance: The Future</h1>'))
    (src / 'abundance-other.html').write_text(page.replace('<h1>Chaptered</h1>', '<h1>Abundance &mdash; Reading Companion</h1>'))
    (src / 'unrelated.html').write_text(page)
    (src / 'moc.md').write_text('# not html')
    out = tmp_path / 'out'

    assert conv.main([str(src), '--out', str(out), '--only', 'abundance,abundance-other,unrelated']) == 0
    report = json.loads((out / 'report.json').read_text())

    assert sorted(p['slug'] for p in report['pages']) == ['abundance', 'abundance-other', 'unrelated']
    assert report['duplicates'] == [['abundance', 'abundance-other']]
    md = (out / 'report.md').read_text()
    assert 'Likely duplicates' in md and 'abundance-other' in md


def test_wikimedia_original_tries_thumbnail_first_then_original(tmp_path):
    original = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Pic.jpg'
    thumb = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Pic.jpg/1280px-Pic.jpg'
    html = (f'<div class="tab-content" id="tab-overview"><figure><img src="{original}"></figure>'
            f'<figure><img src="https://upload.wikimedia.org/wikipedia/commons/c/cd/Two.jpg"></figure></div>')
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith('1280px-Two.jpg'):
            raise urllib.error.HTTPError(url, 400, 'not scaled', {}, None)
        return _jpeg_bytes()

    report = conv.convert_page(html, 'w', tmp_path, fetch)

    assert calls[0] == thumb
    assert calls[1:] == ['https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Two.jpg/1280px-Two.jpg',
                         'https://upload.wikimedia.org/wikipedia/commons/c/cd/Two.jpg']
    assert report.images_downloaded == 2 and report.images_failed == []


def test_main_passes_pause_to_fetcher(tmp_path, monkeypatch):
    seen = {}

    def fake_make_fetcher(cache_dir, pause=1.0, timeout=20):
        seen['pause'] = pause
        return _no_fetch

    monkeypatch.setattr(conv, 'make_fetcher', fake_make_fetcher)
    src = tmp_path / 'src'
    src.mkdir()

    assert conv.main([str(src), '--out', str(tmp_path / 'out'), '--pause', '3']) == 0
    assert seen['pause'] == 3.0


def test_key_points_heading_labels_following_list_instead_of_starting_chapter(tmp_path):
    html = ('<div class="hero"><h1>K</h1></div><div class="tab-content" id="tab-p1">'
            '<section><h3>Real Chapter</h3><p>Body text.</p></section>'
            '<section id="c-keypoints"><h3>Key Points</h3><ul><li>One</li><li>Two</li></ul></section></div>')
    report = conv.convert_page(html, 'k', tmp_path, _no_fetch)
    book = load_book(tmp_path / 'k')

    chapters = book['parts'][0]['chapters']
    assert [c['title'] for c in chapters] == ['Real Chapter']
    assert chapters[0]['blocks'][-1] == {'type': 'keypoints', 'items': ['One', 'Two']}
    assert report.chapters == 1


@pytest.mark.parametrize('subtitle, author', [
    ('Jeff Hawkins’ theory of minds', None),
    ('A chapter-by-chapter companion to James Clear’s guide to tiny changes', 'James Clear'),
    ('Max Tegmark, 2017 — a chapter-by-chapter companion', 'Max Tegmark'),
    ('Viktor E. Frankl — a reading companion', 'Viktor E. Frankl'),
    ('How Google, Bono, and the Gates Foundation Rock the World', None),
    ('Why That’s a Good Thing — Salman Khan’s chapter-by-chapter case', 'Salman Khan'),
    ('Africa, Africans, and the Making of the Modern World', None),
    ('A Neuroscientist’s Quest for What Makes Us Human', None),
    ('Smil’s case that inventions arrive slower', None),
    ('悉达多·穆克吉 著 — 一部史诗', '悉达多·穆克吉'),
])
def test_author_guess_is_conservative(subtitle, author):
    assert conv._guess_author(subtitle) == author


def test_same_title_different_authors_is_not_a_duplicate():
    mk = lambda slug, title, author: conv.PageReport(slug=slug, title=title, author=author)  # noqa: E731
    reports = [mk('a1', 'Abundance: The Future', 'Peter Diamandis and Steven Kotler'),
               mk('a2', 'Abundance', 'Ezra Klein and Derek Thompson'),
               mk('b1', 'Antifragile: Things', 'Nassim Taleb'), mk('b2', 'Antifragile', None),
               mk('c1', 'Growth', 'Vaclav Smil'), mk('c2', 'Growth: More', 'V. Smil')]

    assert conv.find_duplicates(reports) == [['b1', 'b2'], ['c1', 'c2']]


def test_author_falls_back_to_name_before_parenthesis_in_overview(tmp_path):
    html = ('<div class="hero"><h1>T</h1><p class="subtitle">A liberal case for building.</p></div>'
            '<div class="tab-content" id="tab-overview"><p>America wants more. Ezra Klein (columnist) and '
            'Derek Thompson (writer) argue.</p></div>')
    conv.convert_page(html, 't', tmp_path, _no_fetch)

    assert load_book(tmp_path / 't')['author'] == 'Ezra Klein'


def _page(*tabs, buttons=''):
    return (f'<div class="hero"><h1>F</h1></div><div class="tab-bar">{buttons}</div>'
            + ''.join(f'<div class="tab-content" id="tab-{i}">{body}</div>' for i, body in tabs))


def test_notes_tab_becomes_sources_and_nested_worklog_is_skipped(tmp_path):
    html = _page(('p1', '<h3>Ch</h3><p>Body.</p>'),
                 ('notes', '<section><h2>How this page was made</h2><p>Method text.</p></section>'
                           '<section id="worklog"><span class="eyebrow">Worklog</span><h2>Update Log</h2>'
                           '<div class="worklog"><div class="worklog-desc">Initial publish</div></div></section>'))
    report = conv.convert_page(html, 'n', tmp_path, _no_fetch)
    book = load_book(tmp_path / 'n')

    assert [p['title'] for p in book['parts']] == ['p1']
    assert book['sources'] == [{'type': 'h', 'text': 'How this page was made'},
                               {'type': 'p', 'text': 'Method text.'}]
    assert 'Update Log' not in json.dumps(book) and 'Initial publish' not in json.dumps(book)
    assert report.chapters == 1


def test_tab_with_sources_label_becomes_sources(tmp_path):
    buttons = ('<button class="tab-btn" onclick="switchTab(\'refs\')">Sources &amp; Notes</button>'
               '<button class="tab-btn" onclick="switchTab(\'p1\')">Part</button>')
    html = _page(('p1', '<h3>Ch</h3><p>Body.</p>'), ('refs', '<p>Edition used.</p>'), buttons=buttons)
    conv.convert_page(html, 'r', tmp_path, _no_fetch)
    book = load_book(tmp_path / 'r')

    assert [p['title'] for p in book['parts']] == ['Part']
    assert book['sources'] == [{'type': 'p', 'text': 'Edition used.'}]


def test_failed_image_caption_is_reported_as_dropped(tmp_path):
    html = _page(('overview', '<figure><img src="data:image/svg+xml;utf8,x"><figcaption>Lost words here</figcaption></figure>'))
    report = conv.convert_page(html, 'd', tmp_path, _no_fetch)

    assert any('Lost words here' in d for d in report.dropped)
    assert report.flagged


def test_cover_image_caption_is_kept_as_paragraph(tmp_path):
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
    import base64
    uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    html = _page(('overview', f'<figure><img src="{uri}" alt="Book cover: X"><figcaption>X, by Y (Press, 2018)</figcaption></figure><p>Hi.</p>'))
    report = conv.convert_page(html, 'cv', tmp_path, _no_fetch)
    book = load_book(tmp_path / 'cv')

    assert book['cover'].startswith('images/')
    assert book['overview'] == [{'type': 'p', 'text': 'X, by Y (Press, 2018)'}, {'type': 'p', 'text': 'Hi.'}]
    assert report.dropped == []


def test_unexpected_keypoint_label_is_reported(tmp_path):
    html = _page(('p1', '<section class="part-intro"><h2>Only A Heading</h2></section>'
                        '<h3>Ch</h3><div class="chapter-points"><p><strong>Remember these:</strong></p><ul><li>a</li></ul></div>'
                        '<div class="keypoints-wrap"><h4>Key points</h4><ul class="keypoints"><li>b</li></ul></div>'))
    report = conv.convert_page(html, 'kp', tmp_path, _no_fetch)

    assert any('Remember these' in d for d in report.dropped)
    assert not any('Only A Heading' in d for d in report.dropped)  # kept as a block (fix round 2)
    assert not any('Key points' in d for d in report.dropped)  # the expected label is not a loss


def test_picture_element_keeps_its_img(tmp_path):
    uri = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAYAAAAGCAIAAABvrngfAAAAFElEQVR4nGM8ISfHgAqY0PhUFgIAdYgBEED+8ToAAAAASUVORK5CYII='
    html = _page(('overview', f'<picture><source srcset="x.webp"><img src="{uri}"></picture>'))
    conv.convert_page(html, 'pc', tmp_path, _no_fetch)

    assert load_book(tmp_path / 'pc')['overview'][0]['type'] == 'image'


def _heading_only_part(tmp_path, label, heading, name='hp'):
    buttons = f'<button class="tab-btn" onclick="switchTab(\'p1\')">{label}</button>'
    html = _page(('p1', f'<section class="part-intro"><h2>{heading}</h2></section><h3>Ch</h3><p>Body.</p>'), buttons=buttons)
    report = conv.convert_page(html, name, tmp_path, _no_fetch)
    return report, load_book(tmp_path / name)['parts'][0]


def test_heading_only_intro_equal_to_part_title_is_dropped_silently(tmp_path):
    report, part = _heading_only_part(tmp_path, '1733–1737', '1733-1737')

    assert part['title'] == '1733–1737'
    assert part['chapters'][0]['blocks'] == [{'type': 'p', 'text': 'Body.'}]
    assert report.dropped == [] and not report.flagged


def test_heading_only_intro_extending_part_title_becomes_part_title(tmp_path):
    report, part = _heading_only_part(tmp_path, 'Part I', 'Part I: The “Discovery” of Africa')

    assert part['title'] == 'Part I: The “Discovery” of Africa'
    assert part['chapters'][0]['blocks'] == [{'type': 'p', 'text': 'Body.'}]
    assert report.dropped == []


def test_part_title_prefix_must_end_at_a_word_boundary(tmp_path):
    _, part = _heading_only_part(tmp_path, 'Part I', 'Part II: Something')

    assert part['title'] == 'Part I'
    assert part['chapters'][0]['blocks'][0] == {'type': 'h', 'text': 'Part II: Something'}


def test_other_heading_only_intro_is_kept_as_h_block_in_first_chapter(tmp_path):
    report, part = _heading_only_part(tmp_path, '1st Law: Make It Obvious', 'Cue: make the cues visible')

    assert part['title'] == '1st Law: Make It Obvious'
    assert part['chapters'][0]['blocks'][:2] == [{'type': 'h', 'text': 'Cue: make the cues visible'},
                                                {'type': 'p', 'text': 'Body.'}]
    assert report.dropped == []
