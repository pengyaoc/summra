import json
import re

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
    assert html.index('/books/newer-book"') < html.index('/books/my-book"')
    # A book with no cover gets a title placeholder instead of a broken image.
    assert 'book-cover-placeholder' in html
    assert '/books/my-book/images/cover.jpg' in html


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
    assert 'Chapter 1 of 3' in html
    assert 'href="/books/my-book/read"' in html
    assert html.index('Reading now') < html.index('All books')


def test_library_counts_chapters_without_loading_blocks(app_env, monkeypatch):
    client, content_db, _, book_id = app_env
    chapter = content_db.get_chapters(book_id)[1]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id']), headers=HEADERS)

    def boom(_book_id):
        raise AssertionError('library must not load chapter blocks')
    monkeypatch.setattr(content_db, 'get_chapters', boom)
    assert 'Chapter 1 of 3' in get(client, '/').get_data(as_text=True)


def test_book_page_toc_grouped_by_part_and_overview_first(app_env):
    client, content_db, _, book_id = app_env
    chapters = content_db.get_chapters(book_id)
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert '<h1' in html and 'My Book' in html and 'A. Writer' in html
    assert 'Start reading' in html and 'href="/books/my-book/read"' in html
    links = re.findall(r'href="/books/my-book/read\?chapter=(\d+)"', html)
    assert links == [str(c['id']) for c in chapters]
    assert html.index('Overview') < html.index('Part One') < html.index('1. First') < html.index('3. Third')
    # The untitled part gets no heading of its own.
    assert html.count('class="toc-part-title"') == 1


def test_book_page_continue_reading_when_in_progress(app_env):
    client, content_db, _, book_id = app_env
    chapter = content_db.get_chapters(book_id)[2]
    client.post('/api/progress/v2/mutations', json=_mutation(book_id, chapter['id'], unit=0), headers=HEADERS)
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert 'Continue reading' in html and 'Chapter 2 of 3' in html


def test_book_page_sources_rendered(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    sample_book['sources'] = [{'type': 'p', 'text': 'src **bold**'},
                              {'type': 'image', 'src': 'images/cover.jpg', 'caption': None}]
    content_db.import_book(write_book(sample_book))
    html = get(client, '/books/my-book').get_data(as_text=True)
    assert '<p data-i="0">src <strong>bold</strong></p>' in html
    assert 'src="/books/my-book/images/cover.jpg"' in html


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
    assert book == {'id': 1, 'slug': 'my-book', 'title': 'My Book', 'author': 'A. Writer'}
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
    assert config['extra_page_blocks'] == 'table.reader-table, figure.reader-figure'


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
