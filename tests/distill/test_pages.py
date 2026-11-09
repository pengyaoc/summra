import html as html_module
import json
import re

import pytest

from shared.auth.pchauth.config import AuthConfig
from shared.auth.user_models import UserDatabase

from .conftest import HEADERS, pin_platform_globals


def get(client, url, **kw):
    return client.get(url, headers=HEADERS, **kw)


def _mutation(book_id, chapter_id, unit=1):
    marker = {'mode': 'summary', 'chapter_id': chapter_id, 'paragraph_id': f'{chapter_id}.{unit}', 'offset': 0.5}
    return {
        'mutation_id': 'm1', 'device_id': 'd1', 'device_sequence': 1, 'base_revision': 0,
        'book_id': book_id, 'mode': 'summary', 'event_cause': 'page_turn', 'current_marker': marker,
        'qualified_furthest_marker': marker, 'sequential_boundaries_delta': 2,
    }


def test_library_lists_books_newest_first(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    sample_book.update(slug='newer-book', title='Newer Book')
    sample_book.pop('cover')
    content_db.import_book(write_book(sample_book))
    html = get(client, '/').get_data(as_text=True)
    assert 'id="library-heading"' in html
    assert html.index('/books/newer-book?') < html.index('/books/my-book?')
    # A book with no cover gets a title placeholder instead of a broken image.
    assert 'book-cover-placeholder' in html
    token = content_db.get_book_by_slug('my-book')['cover_thumbnail_token']
    assert f'/books/my-book/cover/{token}.avif' in html
    assert f'/books/my-book/cover/{token}.webp' in html
    assert f'/books/my-book/cover/{token}.jpg' in html


def test_library_with_no_progress_has_no_reading_now(tmp_path, monkeypatch):
    from distill.app_base import create_app
    from distill.models import DistillDatabase
    pin_platform_globals(monkeypatch)
    app = create_app(DistillDatabase(tmp_path / 'c.db'), UserDatabase(tmp_path / 'u.db'), AuthConfig(mode='off'))
    response = app.test_client().get('/')
    assert response.status_code == 200
    assert 'Reading now' not in response.get_data(as_text=True)


def test_library_reading_now_shows_progress_label(app_env):
    client, content_db, _, book_id = app_env
    assert 'class="home-now"' not in get(client, '/').get_data(as_text=True)
    chapter = content_db.get_chapters(book_id)[1]
    assert client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']),
                       headers=HEADERS).status_code == 200
    html = get(client, '/').get_data(as_text=True)
    assert 'Chapter 1 of 4' in html
    assert 'href="/books/my-book/read?return=/"' in html


def test_library_counts_chapters_without_loading_blocks(app_env, monkeypatch):
    client, content_db, _, book_id = app_env
    chapter = content_db.get_chapters(book_id)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']), headers=HEADERS)

    def boom(_book_id):
        raise AssertionError('library must not load chapter blocks')
    monkeypatch.setattr(content_db, 'get_chapters', boom)
    assert 'Chapter 1 of 4' in get(client, '/').get_data(as_text=True)


def test_home_and_book_pages_do_not_build_full_reader_manifests(app_env, monkeypatch):
    client, db, _, bid = app_env
    chapter = db.get_chapters(bid)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(bid, chapter['id']), headers=HEADERS)
    monkeypatch.setattr(db, 'get_reader_manifest', lambda *a: (_ for _ in ()).throw(
        AssertionError('library must not construct a full manifest')))
    monkeypatch.setattr(db, '_reader_load_chapters', lambda *a: (_ for _ in ()).throw(
        AssertionError('library must not parse chapter text')))
    assert get(client, '/books/my-book').status_code == 200
    monkeypatch.setattr(db, 'count_chapters', lambda *a: (_ for _ in ()).throw(
        AssertionError('home must batch chapter counts')))
    assert get(client, '/').status_code == 200
    assert get(client, '/api/library').status_code == 200


def test_book_page_toc_grouped_by_part_and_overview_first(app_env):
    client, content_db, _, book_id = app_env
    chapters = content_db.get_chapters(book_id)
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert '<h1' in html and 'My Book' in html and 'A. Writer' in html
    assert '>Start</a>' in html and 'href="/books/my-book/read?return=/"' in html
    links = re.findall(r'href="/books/my-book/read\?chapter=(\d+)&amp;return=/"', html)
    assert links == [str(c['id']) for c in chapters]
    assert html.index('Overview') < html.index('Part One') < html.index('1. First') < html.index('3. Third')
    # The untitled part gets no heading of its own.
    assert html.count('class="toc-part-title"') == 1


def test_book_page_builds_toc_without_loading_blocks(app_env, monkeypatch):
    client, content_db, _, book_id = app_env
    chapter = content_db.get_chapters(book_id)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']), headers=HEADERS)

    def boom(_book_id):
        raise AssertionError('book page must not load chapter blocks')
    monkeypatch.setattr(content_db, 'get_chapters', boom)
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert 'Part One' in html and '3. Third' in html
    assert 'Chapter 1 of 4' in html


def test_book_page_continue_reading_when_in_progress(app_env):
    client, content_db, _, book_id = app_env
    chapter = content_db.get_chapters(book_id)[2]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id'], unit=0), headers=HEADERS)
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert '>Continue</a>' in html and 'Chapter 2 of 4' in html


def test_sources_are_a_final_reader_chapter_instead_of_a_separate_section(app_env, sample_book, write_book):
    client, content_db, _, book_id = app_env
    sample_book['sources'] = [{'type': 'p', 'text': 'src **bold**'},
                              {'type': 'image', 'src': 'images/cover.jpg', 'caption': None}]
    content_db.import_book(write_book(sample_book))
    html = get(client, '/books/my-book').get_data(as_text=True)
    source = content_db.get_chapters(book_id)[-1]
    assert f'read?chapter={source["id"]}&amp;return=/">Source</a>' in html
    assert 'distill-sources' not in html and 'src <strong>bold</strong>' not in html
    assert source['title'] == 'Source' and source['part_title'] is None
    manifest = get(client, f'/api/reader/books/{book_id}/manifest').get_json()['manifest']
    assert manifest['structure'][-1]['title'] == 'Source'
    units = []
    for segment in manifest['segments']:
        payload = get(client, f'/api/reader/books/{book_id}/segments/{segment["id"]}?mode=summary').get_json()
        units.extend(payload['segment']['units'])
    assert [json.loads(unit['content']) for unit in units[-2:]] == sample_book['sources']


def test_reader_shell_has_platform_partials_and_no_mode_selector(app_env):
    client = app_env[0]
    response = get(client, '/books/my-book/read')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<html lang="en"' in html
    assert '<body class="on-chapter-page on-reader-page"' in html
    assert 'id="continuous-reader-section"' in html and 'hidden" id="continuous-reader-section"' not in html
    assert 'id="reading-settings-panel"' in html
    assert 'reader-mode-settings' not in html and 'data-reader-settings-mode' not in html
    assert 'window.APP_BASE_PATH' in html
    book = json.loads(html_module.unescape(re.search(r'data-book="([^"]*)"', html).group(1)))
    assert book == {'id': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer', 'return_url': '/', 'cover': book['cover']}
    assert book['cover'].startswith('/books/my-book/cover/')
    names = [s.split('?')[0] for s in re.findall(r'<script[^>]*src="([^"]+)"', html)]
    assert names.index('/static/shared/js/base_path.js') < names.index('/static/shared/js/reader_state.js') \
        < names.index('/static/js/distill_shell.js')
    assert html.index('window.READER_CONFIG') < html.index('/static/shared/js/reader_state.js')
    assert '<script type="module" src="/static/js/distill_shell.js' in html


def test_reader_shell_serialises_distill_config(app_env):
    html = get(app_env[0], '/books/my-book/read').get_data(as_text=True)
    config = json.loads(re.search(r'window\.READER_CONFIG = (\{.*?\});</script>', html).group(1))
    assert config['cache_db_name'] == 'distill-reader-v1'
    assert [m['id'] for m in config['modes']] == ['summary']
    assert config['extra_page_blocks'] == 'figure.reader-figure, table.reader-grid'
    assert config['flow_complex_blocks'] is True


def test_reader_lang_follows_book(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    sample_book.update(slug='zh-book', lang='zh')
    content_db.import_book(write_book(sample_book))
    assert '<html lang="zh"' in get(client, '/books/zh-book/read').get_data(as_text=True)


def test_unknown_slug_404_page(client):
    for url in ('/books/nope', '/books/nope/read'):
        response = get(client, url)
        assert response.status_code == 404, url
        assert 'Book not found' in response.get_data(as_text=True)
        assert response.headers['Cache-Control'] == 'private, no-cache'


def test_page_routes_require_allow_listed_identity(client):
    for url in ('/', '/books/my-book', '/books/my-book/read'):
        assert client.get(url).status_code == 401, url
        assert client.get(url, headers={'X-Remote-Email': 'stranger@example.com'}).status_code == 403, url
        assert get(client, url).status_code == 200, url


def test_progress_label_cases():
    from distill.routes import progress_label
    assert progress_label(None, 12) == ''
    assert progress_label({'current_chapter': None}, 12) == ''
    assert progress_label({'current_chapter': {'chapter_number': 0}}, 12) == 'Overview'
    assert progress_label({'current_chapter': {'chapter_number': 3}}, 12) == 'Chapter 3 of 12'


def test_library_combines_search_language_and_category(app_env, sample_book, write_book):
    client, db, _, _ = app_env
    sample_book.update(slug='chinese-science', title='细胞传', author='悉达多', lang='zh', categories=['Science'])
    db.import_book(write_book(sample_book))
    sample_book.update(slug='english-science', title='Cell Biology', lang='en')
    db.import_book(write_book(sample_book))
    html = get(client, '/?q=细胞&lang=zh&category=Science').get_data(as_text=True)
    assert 'href="/books/chinese-science?return=' in html
    assert 'href="/books/english-science"' not in html
    assert 'href="/books/my-book?return=' not in html
    assert '1 of 3 books' in html
    assert 'name="q"' in html and 'name="lang"' in html and 'name="category"' in html
    assert 'No books match' in get(client, '/?q=nonexistent').get_data(as_text=True)
    assert 'href="/books/my-book?return=' in get(client, '/?q=a. WRITER').get_data(as_text=True)


def test_library_filter_escapes_query_and_keeps_category_options(client):
    html = get(client, '/?q=%22%3E%3Cscript%3E&lang=invalid').get_data(as_text=True)
    assert '<script>' not in html.split('name="q"', 1)[1].split('</form>', 1)[0]
    assert 'Uncategorized' in html


def test_legacy_book_category_mapping():
    from distill.routes import book_categories
    assert book_categories({'slug': 'atomic-habits', 'categories': []}) == ['Personal growth']
    assert book_categories({'slug': 'unknown', 'categories': []}) == ['Uncategorized']
    assert book_categories({'slug': 'atomic-habits', 'categories': ['Custom']}) == ['Custom']


def test_drop_logo_is_fixed_and_picker_removed(client):
    html = get(client, '/').get_data(as_text=True)
    assert 'data-logo-mark="drop"' in html
    assert 'data-logo-mark="book"' not in html
    assert 'Explore logos' not in html
    assert 'distill-logo' not in html


def test_typeahead_catalog_ignores_query_but_respects_filters(app_env, sample_book, write_book):
    client, db, _, _ = app_env
    sample_book.update(slug='science-zh', title='细胞传', lang='zh', categories=['Science'])
    db.import_book(write_book(sample_book))
    html = get(client, '/?q=missing&lang=zh&category=Science').get_data(as_text=True)
    catalog = json.loads(re.search(r'<script id="distill-search-catalog" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert catalog == [{'title': '细胞传', 'author': 'A. Writer', 'slug': 'science-zh', 'lang': 'zh'}]
    assert 'role="combobox"' in html
    assert 'role="listbox"' in html
    assert 'aria-controls="distill-search-options"' in html


@pytest.mark.parametrize('value', ['https://evil.example/', '//evil.example/', '/other/', '//[', '/\\evil.example/'])
def test_library_return_rejects_external_or_malformed_destinations(client, value):
    html = get(client, '/books/my-book', query_string={'return': value}).get_data(as_text=True)
    assert 'class="distill-back" href="/"' in html


def test_library_status_sort_estimates_and_safe_return(app_env, sample_book, write_book):
    client, db, _, bid = app_env
    chapter = db.get_chapters(bid)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(bid, chapter['id']), headers=HEADERS)
    sample_book.update(slug='another-book', title='Another Book')
    db.import_book(write_book(sample_book))
    html = get(client, '/?sort=title&status=unread').get_data(as_text=True)
    grid = html.split('<div class="distill-grid">')[1].split('</section>')[0]
    assert '/books/another-book?' in grid and '/books/my-book?' not in grid
    assert 'About ' in grid and ' min' in grid
    url = '/?lang=en&sort=title&q=Book'
    html = get(client, '/books/my-book', query_string={'return': url}).get_data(as_text=True)
    assert 'href="/?lang=en&amp;sort=title&amp;q=Book"' in html
    prefixed = client.get('/?sort=title', headers={**HEADERS, 'X-Forwarded-Prefix': '/distill'}).get_data(as_text=True)
    assert 'return=/distill/%3Fsort%3Dtitle' in prefixed


def test_finished_book_has_history_read_again_and_source_location(app_env):
    client, db, _, bid = app_env
    manifest = db.get_reader_manifest(bid)
    terminal = next(m for m in manifest['modes'] if m['mode'] == 'summary')['terminal_paragraph_id']
    chapter_id, unit = map(int, terminal.split('.'))
    mutation = _mutation(bid, chapter_id, unit)
    mutation.update(event_cause='manual_finish', terminal_dwell_ms=2000, sequential_terminal_entry=True)
    assert client.post('/api/progress/v2/mutations', json=mutation, headers=HEADERS).status_code == 200
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert 'Finished · 100%' in html and 'Read from beginning' in html and 'Mark unfinished' in html
    assert 'restart=1' in html
    home = get(client, '/').get_data(as_text=True)
    assert 'finished-heading' not in home  # Finished is a view inside Library, not a shelf
    finished = get(client, '/?tab=library&status=finished').get_data(as_text=True)
    assert '/books/my-book?' in finished
    from distill.routes import progress_label
    assert progress_label({'current_chapter': {'chapter_number': 4, 'chapter_title': 'Source'}}, 4) == 'Source'


def test_unfinish_accepts_projection_marker_with_its_mode(app_env):
    client, db, _, bid = app_env
    chapter = db.get_chapters(bid)[1]
    payload = _mutation(bid, chapter['id'])
    client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS)
    projection = get(client, f'/api/progress/v2/books/{bid}').get_json()['projection']
    mode = projection['modes'][0]
    payload.update(mutation_id='unfinish-review', device_id='unfinish-device',
                   base_revision=mode['revision'], event_cause='manual_unfinish',
                   current_marker={**mode['current_marker'], 'mode': mode['mode']})
    response = client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json()['projection']['book']['status'] == 'in_progress'


def test_finished_book_default_action_keeps_newer_saved_place(app_env):
    client, db, _, bid = app_env
    manifest = db.get_reader_manifest(bid)
    terminal = next(mode for mode in manifest['modes'] if mode['mode'] == 'summary')['terminal_paragraph_id']
    chapter_id, unit = map(int, terminal.split('.'))
    payload = _mutation(bid, chapter_id, unit)
    payload.update(event_cause='manual_finish', terminal_dwell_ms=2000, sequential_terminal_entry=True)
    assert client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS).status_code == 200
    projection = get(client, f'/api/progress/v2/books/{bid}').get_json()['projection']
    # Rereading updates the current place while preserving completion history.
    chapter = db.get_chapters(bid)[1]
    payload = _mutation(bid, chapter['id'])
    payload.update(mutation_id='reread', device_sequence=2, base_revision=projection['modes'][0]['revision'])
    assert client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS).status_code == 200
    before = get(client, f'/api/progress/v2/books/{bid}').get_json()['projection']
    assert before['book']['status'] == 'finished'
    html = get(client, '/books/my-book').get_data(as_text=True)
    primary = re.search(r'class="home-action home-action-primary" href="([^"]+)"', html).group(1)
    assert 'restart=' not in primary
    assert '>Continue</a>' in html and 'Saved place: 1. First' in html
    assert 'Read from beginning' in html and 'restart=1' in html
    assert get(client, f'/api/progress/v2/books/{bid}').get_json()['projection'] == before


def test_last_page_does_not_mark_distill_read_and_explicit_action_preserves_place(app_env):
    client, db, users, bid = app_env
    manifest = db.get_reader_manifest(bid)
    terminal = next(mode for mode in manifest['modes'] if mode['mode'] == 'summary')['terminal_paragraph_id']
    chapter_id, unit = map(int, terminal.split('.'))
    payload = _mutation(bid, chapter_id, unit)
    payload.update(event_cause='completion', terminal_dwell_ms=2000, sequential_terminal_entry=True)
    response = client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json()['projection']['book']['status'] == 'in_progress'
    before = get(client, f'/api/progress/v2/books/{bid}').get_json()['projection']['modes'][0]
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert 'Mark as read' in html
    response = client.post(f'/api/progress/v2/books/{bid}/status', json={'status': 'read'}, headers=HEADERS)
    assert response.status_code == 200
    projection = response.get_json()['projection']
    assert projection['book']['status'] == 'finished'
    assert projection['modes'][0]['current_marker'] == before['current_marker']
    assert projection['modes'][0]['furthest_marker'] == before['furthest_marker']
    assert users.clear_automatic_completions() == 0
    assert get(client, f'/api/progress/v2/books/{bid}').get_json()['projection']['book']['status'] == 'finished'
    response = client.post(f'/api/progress/v2/books/{bid}/status', json={'status': 'reading'}, headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json()['projection']['book']['status'] == 'in_progress'


def test_mark_as_read_works_without_prior_reader_state_and_requires_json_identity(app_env):
    client, db, _, bid = app_env
    path = f'/api/progress/v2/books/{bid}/status'
    assert client.post(path, json={'status': 'read'}).status_code == 401
    assert client.post(path, data='status=read', headers=HEADERS).status_code == 400
    assert client.post(path, json={'status': 'invalid'}, headers=HEADERS).status_code == 400
    response = client.post(path, json={'status': 'read'}, headers=HEADERS)
    assert response.status_code == 200
    projection = response.get_json()['projection']
    assert projection['book']['status'] == 'finished'
    assert projection['modes'][0]['current_marker']['chapter_id'] == db.get_chapters(bid)[0]['id']
    assert 'Mark unfinished' in get(client, '/books/my-book').get_data(as_text=True)


def test_reading_desk_opens_saved_part_and_escapes_overview(app_env, sample_book, write_book):
    client, db, _, book_id = app_env
    sample_book['parts'][1]['title'] = 'Part Two'
    sample_book['overview'] = [{'type': 'p', 'text': 'Book overview & context.'}]
    db.import_book(write_book(sample_book))
    chapter = db.get_chapters(book_id)[3]
    response = client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id'], unit=0), headers=HEADERS)
    assert response.status_code == 200
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert 'Book overview &amp; context.' in html
    parts = re.findall(r'<details class="distill-toc-part"( open)?>\s*<summary class="toc-part-title">([^<]+)', html)
    assert parts == [('', 'Part One'), (' open', 'Part Two')]
    assert f'aria-current="location" href="/books/my-book/read?chapter={chapter["id"]}' in html


def test_chinese_titles_keep_their_language_on_the_home_page(app_env, sample_book, write_book):
    client, db, _, _ = app_env
    sample_book.update(slug='chinese-book', title='全球通史——从史前史到21世纪', lang='zh')
    book_id = db.import_book(write_book(sample_book))
    chapter = db.get_chapters(book_id)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']), headers=HEADERS)
    home = get(client, '/').get_data(as_text=True)
    assert '<title>Distill</title>' in home
    assert 'class="distill-tile" lang="zh"' in get(client, '/?tab=library').get_data(as_text=True)
    assert 'class="home-book" lang="zh"' in home and '全球通史——从史前史到21世纪</h2>' in home
    book = get(client, '/books/chinese-book').get_data(as_text=True)
    assert '<html lang="zh"' in book
    assert '<h1>全球通史<span class="distill-book-subtitle">从史前史到21世纪</span></h1>' in book


def _start_reading(client, db, bid):
    chapter = db.get_chapters(bid)[1]
    assert client.post('/api/progress/v2/mutations', json=_mutation(bid, chapter['id']), headers=HEADERS).status_code == 200


def _home_now(html):
    return html.split('class="home-now"')[1].split('id="library"')[0]


def test_home_shows_the_current_book_above_the_whole_library(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    html = get(client, '/').get_data(as_text=True)
    now = _home_now(html)
    assert 'My Book' in now and 'A. Writer' in now and 'Chapter 1 of 4' in now and 'min left' in now
    assert 'class="home-action home-action-primary" href="/books/my-book/read?return=/"' in now
    assert '>Continue</a>' in now
    assert html.index('class="home-now"') < html.index('id="library"') < html.index('distill-grid')
    assert 'type="search"' in html and 'distill-tabs' not in html


def test_home_offers_listen_beside_continue(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    html = get(client, '/').get_data(as_text=True)
    now = _home_now(html)
    assert f'data-listen-book="{bid}"' in now and 'data-listen-slug="my-book"' in now
    assert 'id="player-mini"' in html and 'js/distill_shell.js' in html and 'js/reader_state.js' in html


def test_home_without_a_book_in_progress_is_just_the_library(app_env):
    html = get(app_env[0], '/').get_data(as_text=True)
    assert 'class="home-now"' not in html and 'data-listen-book' not in html
    assert 'id="library"' in html and 'distill-grid' in html and 'distill-header' in html


def test_home_time_left_shrinks_with_progress(app_env, monkeypatch):
    from distill.routes import minutes_left
    assert minutes_left(100, 0) == 100 and minutes_left(100, 40) == 60
    assert minutes_left(100, 100) == 1 and minutes_left(7, 99) == 1
    assert minutes_left(100, None) == 100


def test_home_lists_other_books_in_progress(app_env, sample_book, write_book):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    sample_book.update(slug='other-book', title='Other Book')
    db.import_book(write_book(sample_book))
    second = db.get_book_by_slug('other-book')['id']
    payload = _mutation(second, db.get_chapters(second)[1]['id'])
    payload.update(mutation_id='m2', device_sequence=2)
    assert client.post('/api/progress/v2/mutations', json=payload, headers=HEADERS).status_code == 200
    html = get(client, '/').get_data(as_text=True)
    now = _home_now(html)
    assert 'Also reading' in now and now.count('My Book') + now.count('Other Book') >= 2
    assert 'href="/books/' in now.split('Also reading')[1]


def test_old_tab_links_still_open_home(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    for url in ('/?tab=reading', '/?tab=library', '/?tab=nonsense'):
        html = get(client, url).get_data(as_text=True)
        assert 'class="home-now"' in html and 'distill-grid' in html


def test_filtering_returns_to_the_library_section_while_reading(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    html = get(client, '/?lang=en&status=unread').get_data(as_text=True)
    assert 'action="/#library"' in html and 'name="tab"' not in html
    switch = html.split('distill-status-switch')[1].split('</nav>')[0]
    assert switch.count('#library"') == 3 and 'tab=' not in switch
    summary = html.split('distill-filter-summary')[1].split('</div>')[0]
    assert 'href="/#library"' in summary


def test_filtering_does_not_jump_past_the_header_with_nothing_in_progress(app_env):
    html = get(app_env[0], '/?lang=en&status=unread').get_data(as_text=True)
    assert '#library' not in html.split('</main>')[0]
    assert 'action="/"' in html


def test_logo_sits_in_the_book_panel_while_reading(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    html = get(client, '/').get_data(as_text=True)
    assert html.count('class="distill-header"') == 1
    assert html.index('class="home-now"') < html.index('class="distill-header"') < html.index('class="home-book"')
    assert 'home-search-link' in html.split('class="distill-header"')[1].split('</header>')[0]


def test_status_switch_shares_the_filter_form(app_env):
    html = get(app_env[0], '/').get_data(as_text=True)
    form = html.split('class="distill-filters"')[1].split('</form>')[0]
    assert 'distill-status-switch' in form and form.index('distill-status-switch') < form.index('type="search"')


def test_home_keeps_the_deploy_prefix(app_env):
    client, db, _, bid = app_env
    _start_reading(client, db, bid)
    html = client.get('/', headers={**HEADERS, 'X-Forwarded-Prefix': '/distill'}).get_data(as_text=True)
    now = _home_now(html)
    assert 'href="/distill/books/my-book/read?return=' in now
    assert 'action="/distill/#library"' in html


def test_book_page_has_continue_and_listen_side_by_side(app_env):
    client, db, _, bid = app_env
    fresh = get(client, '/books/my-book').get_data(as_text=True)
    assert '>Start</a>' in fresh and f'data-listen-book="{bid}"' in fresh and 'js/distill_shell.js' in fresh
    assert 'distill-resume-listening' not in fresh
    _start_reading(client, db, bid)
    assert '>Continue</a>' in get(client, '/books/my-book').get_data(as_text=True)


def test_status_switch_replaces_the_dropdown_and_keeps_other_filters(app_env):
    html = get(app_env[0], '/?tab=library&lang=en&status=unread').get_data(as_text=True)
    assert 'name="status"' in html and '<select name="status"' not in html
    switch = html.split('distill-status-switch')[1].split('</nav>')[0]
    assert 'aria-current="page">Unread<' in switch
    assert 'status=finished' in switch and switch.count('lang=en') == 3


def test_library_filters_have_no_submit_button_and_a_toggle(app_env):
    html = get(app_env[0], '/?tab=library&lang=zh&sort=title').get_data(as_text=True)
    assert 'Find books</button>' not in html and 'distill-filter-panel' in html
    toggle = html.split('distill-filter-toggle')[1].split('</button>')[0]
    assert '中文' in toggle and 'Title' in toggle
