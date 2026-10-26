import re

from .conftest import ALLOWED, HEADERS

KINDLE_PW = ('Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ '
             '(KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+')
KINDLE_HEADERS = {**HEADERS, 'User-Agent': KINDLE_PW}


def kget(client, url):
    return client.get(url, headers=KINDLE_HEADERS)


def body(response):
    return response.get_data(as_text=True)


def save(client, **payload):
    payload = {'forward': False, 'seconds': 1, 'finished': False, 'text': 'summary', **payload}
    return client.post('/api/kindle/progress', json=payload, headers=KINDLE_HEADERS)


def big_book(sample_book, n=10):
    sample_book.update(slug='big-book', title='Big Book')
    sample_book['parts'] = [{'title': 'Part A', 'chapters': [
        {'title': f'{i}. Chapter {i}', 'blocks': [{'type': 'p', 'text': f'text {i}'}]} for i in range(1, n + 1)]}]
    return sample_book


def projection(user_db, book_id):
    return user_db.get_book_projection(user_db.upsert_user_by_email(ALLOWED), book_id)


def test_kindle_library_reading_now_and_all_books(app_env):
    client, _, _, book_id = app_env
    html = body(kget(client, '/'))
    assert 'class="kindle' in html and 'kindle.css' in html
    assert 'Reading now' not in html and 'href="/books/my-book"' in html
    assert 'name="q"' not in html and 'class="tabs"' not in html
    for _ in range(2):  # two forward page turns: the book counts as started
        assert save(client, book_id=book_id, ch=2, p=0, forward=True, seconds=30).status_code == 200
    html = body(kget(client, '/'))
    assert html.index('Reading now') < html.index('All books')
    assert 'href="/books/my-book/read"' in html and 'Chapter 2 of 3' in html


def test_kindle_library_paginates_all_books(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    for i in range(8):
        sample_book.update(slug=f'b{i}', title=f'Book {i}')
        content_db.import_book(write_book(sample_book))
    page1, page2 = body(kget(client, '/')), body(kget(client, '/?page=2'))
    assert len(re.findall(r'href="/books/[^"/]+"', page1)) == 7 and 'page=2' in page1
    assert len(re.findall(r'href="/books/[^"/]+"', page2)) == 2 and 'page=1' in page2


def test_kindle_book_contents_has_part_headings_and_paginates(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    html = body(kget(client, '/books/my-book'))
    assert html.count('class="part"') == 1 and 'Part One' in html
    assert 'href="/books/my-book/read?ch=1"' in html and 'href="/books/my-book/read?ch=3"' in html
    content_db.import_book(write_book(big_book(sample_book)))
    page1 = body(kget(client, '/books/big-book'))
    assert page1.count('/read?ch=') == 8 and 'page=2' in page1
    page2 = body(kget(client, '/books/big-book?page=2'))
    assert page2.count('/read?ch=') == 3  # the Overview and 10 chapters


def test_kindle_book_contents_marks_saved_place(app_env):
    client, _, _, book_id = app_env
    assert 'You are here' not in body(kget(client, '/books/my-book'))
    save(client, book_id=book_id, ch=2, p=0)
    html = body(kget(client, '/books/my-book'))
    assert 'Continue reading' in html and html.count('You are here') == 1
    assert html.index('read?ch=2') < html.index('You are here') < html.index('read?ch=3')


def test_kindle_reader_renders_blocks_with_data_i(app_env):
    html = body(kget(app_env[0], '/books/my-book/read?ch=1'))
    assert '<html lang="en" class="kindle' in html
    assert 'data-text="summary"' in html and 'shared/js/kindle.js' in html
    assert '<p data-i="0">one two three</p>' in html
    assert re.search(r'<ul[^>]* data-i="1"', html) and re.search(r'<table[^>]* data-i="2"', html)
    assert '<figure class="reader-figure" data-i="4"><img src="images/cover.jpg"' in html
    assert 'data-chars=' in html and 'data-before=' in html and 'data-sync="/api/kindle/progress"' in html
    assert 'type="module"' not in html


def test_kindle_reader_lang_follows_book(app_env, sample_book, write_book):
    client, content_db, _, _ = app_env
    sample_book.update(slug='zh-book', lang='zh')
    content_db.import_book(write_book(sample_book))
    assert '<html lang="zh" class="kindle' in body(kget(client, '/books/zh-book/read'))


def test_kindle_reader_has_no_text_row(app_env):
    html = body(kget(app_env[0], '/books/my-book/read?ch=1'))
    assert 'row-label">Text' not in html
    assert 'id="smaller"' in html


def test_kindle_reader_resumes_saved_chapter_and_index(app_env):
    client, _, _, book_id = app_env
    assert 'data-ch="0"' in body(kget(client, '/books/my-book/read'))
    save(client, book_id=book_id, ch=1, p=3)
    html = body(kget(client, '/books/my-book/read'))
    assert 'data-ch="1"' in html and 'data-start="3"' in html
    explicit = body(kget(client, '/books/my-book/read?ch=2'))
    assert 'data-ch="2"' in explicit and 'data-start="0"' in explicit
    assert kget(client, '/books/my-book/read?ch=99').status_code == 404
    assert kget(client, '/books/my-book/read?ch=x').status_code == 404


def test_kindle_progress_records_summary_marker_with_quote(app_env):
    client, content_db, user_db, book_id = app_env
    chapter = content_db.get_chapters(book_id)[1]
    response = save(client, book_id=book_id, ch=1, p=3, forward=True, seconds=5)
    assert response.status_code == 200 and response.get_json()['success'] is True
    state = projection(user_db, book_id)
    assert state['book']['last_mode'] == 'summary'
    marker = next(m for m in state['modes'] if m['mode'] == 'summary')['current_marker']
    assert marker['paragraph_id'] == f"{chapter['id']}.3"
    assert marker['quote'] == 'The fourth block has a distinctive phrase.'


def test_kindle_progress_quote_is_single_spaced(app_env):
    client, _, user_db, book_id = app_env
    save(client, book_id=book_id, ch=1, p=2)
    marker = projection(user_db, book_id)['modes'][0]['current_marker']
    assert marker['quote'] == 'h1 h2 x y'


def test_kindle_progress_rejects_unconfigured_text(app_env):
    client, _, _, book_id = app_env
    for bad in ({'text': 'plain'}, {'text': 'original'}, {'text': None}, {'p': -1}, {'p': '1'},
                {'p': 50}, {'ch': 99}, {'ch': 'x'}, {'book_id': 999}):
        assert save(client, **{'book_id': book_id, 'ch': 1, 'p': 0, **bad}).status_code == 400, bad


def test_kindle_progress_completion_on_last_block_forward_only(app_env):
    client, _, user_db, book_id = app_env
    save(client, book_id=book_id, ch=3, p=0, forward=False, finished=True)
    assert projection(user_db, book_id)['book']['status'] != 'finished'
    save(client, book_id=book_id, ch=2, p=0, forward=True, finished=True)
    assert projection(user_db, book_id)['book']['status'] != 'finished'
    save(client, book_id=book_id, ch=3, p=0, forward=True, finished=True)
    assert projection(user_db, book_id)['book']['status'] == 'finished'


def test_kindle_off_switch_serves_web_pages(app_env):
    client = app_env[0]
    html = body(client.get('/books/my-book/read?kindle=0', headers=KINDLE_HEADERS))
    assert 'class="kindle' not in html and 'window.READER_CONFIG' in html
    assert 'class="kindle' not in body(kget(client, '/'))
    assert 'class="kindle' in body(kget(client, '/?kindle=1'))
