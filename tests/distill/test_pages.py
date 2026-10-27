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
    assert 'All books' in html
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
    assert 'Reading now' not in get(client, '/').get_data(as_text=True)
    chapter = content_db.get_chapters(book_id)[1]
    assert client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']),
                       headers=HEADERS).status_code == 200
    html = get(client, '/').get_data(as_text=True)
    assert 'Reading now' in html
    assert 'Chapter 1 of 4' in html
    assert 'href="/books/my-book/read?return=/"' in html
    assert html.index('Reading now') < html.index('All books')


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
    assert 'Start reading' in html and 'href="/books/my-book/read?return=/"' in html
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
    assert 'Continue reading' in html and 'Chapter 2 of 4' in html


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
    book = json.loads(re.search(r'window\.DISTILL_BOOK = (\{.*?\});', html).group(1))
    assert book == {'id': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer', 'return_url': '/'}
    names = [s.split('?')[0] for s in re.findall(r'<script[^>]*src="([^"]+)"', html)]
    assert names.index('/static/shared/js/base_path.js') < names.index('/static/shared/js/reader_state.js') \
        < names.index('/static/js/distill_reader.js')
    assert html.index('window.READER_CONFIG') < html.index('/static/shared/js/reader_state.js')
    assert '<script type="module" src="/static/js/distill_reader.js' in html


def test_reader_shell_serialises_distill_config(app_env):
    html = get(app_env[0], '/books/my-book/read').get_data(as_text=True)
    config = json.loads(re.search(r'window\.READER_CONFIG = (\{.*?\});</script>', html).group(1))
    assert config['cache_db_name'] == 'distill-reader-v1'
    assert [m['id'] for m in config['modes']] == ['summary']
    assert config['extra_page_blocks'] == 'figure.reader-figure'
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
    assert catalog == [{'title': '细胞传', 'author': 'A. Writer', 'slug': 'science-zh'}]
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
    # Only the All books grid is filtered; Reading now remains available above it.
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
    assert 'id="finished-heading"' in home and 'Resume' in home
    assert home.index('id="finished-heading"') < home.index('id="all-books-heading"')
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
    primary = re.search(r'class="library-read-action" href="([^"]+)"', html).group(1)
    assert 'restart=' not in primary
    assert 'Continue reading' in html and 'Saved place: 1. First' in html
    assert 'Read from beginning' in html and 'restart=1' in html
    home = get(client, '/').get_data(as_text=True)
    history = home.split('id="finished-heading"')[1].split('id="all-books-heading"')[0]
    assert 'Resume' in history and '1. First' in history and 'restart=1' not in history
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
