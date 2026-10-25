"""Kindle e-ink mode: a Kindle's experimental browser gets a lean,
server-rendered, paginated reading UI instead of the SPA. Every other browser
keeps the normal site.
"""
import re

import pytest

from shared.kindle import is_kindle_user_agent

KINDLE_PW = ('Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ '
             '(KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+')
KINDLE_KEYBOARD = ('Mozilla/5.0 (Linux; U; en-US) AppleWebKit/528.5+ (KHTML, like Gecko, '
                   'Safari/528.5+) Version/4.0 Kindle/3.0 (screen 600x800; rotate)')
FIRE_HD = ('Mozilla/5.0 (Linux; Android 9; KFTRWI) AppleWebKit/537.36 (KHTML, like Gecko) '
           'Silk/112.3.1 like Chrome/112.0.5615.213 Safari/537.36')
FIRE_OLD = ('Mozilla/5.0 (Linux; U; Android 2.3.4; en-us; Kindle Fire Build/GINGERBREAD) '
            'AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1')
DESKTOP = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')


@pytest.mark.parametrize('ua', [KINDLE_PW, KINDLE_KEYBOARD])
def test_eink_kindles_are_detected(ua):
    assert is_kindle_user_agent(ua)


@pytest.mark.parametrize('ua', [FIRE_HD, FIRE_OLD, DESKTOP, '', None])
def test_fire_tablets_and_other_browsers_are_not(ua):
    assert not is_kindle_user_agent(ua)


@pytest.fixture
def client(test_db_path, monkeypatch):
    from plainly import app_base, models
    from plainly.routes import common
    db = models.Database(db_path=test_db_path)
    book = db.add_book(title='Moby & Dick', author='Herman Melville', filename='pg2701.txt', full_text='x')
    db.update_book_slug(book, 'moby-dick')
    db.add_chapter(book, 1, 'Loomings', 's', chapter_text='Loomings\n\nCall me Ishmael.\n\nSome years ago <never mind>.',
                   modern_english_text='Loomings\n\nMy name is Ishmael.\n\nA few years ago.')
    db.add_chapter(book, 2, 'The Carpet-Bag', 's', chapter_text='I stuffed a shirt or two.',
                   modern_english_text='I packed a shirt or two.')
    db.add_chapter(book, 3, 'The Spouter-Inn', 's', chapter_text='Entering that gable-ended inn.')
    other = db.add_book(title='Zeta Original Only', author='Anon', filename='z.txt', full_text='x')
    db.update_book_slug(other, 'zeta')
    db.add_chapter(other, 1, 'One', 's', chapter_text='Only the original.')
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    # Reading progress goes to a throwaway user DB; signed out unless a test
    # signs in (the auth boundary is kindle._signed_in_user_id).
    from shared.progress import routes as progress_routes
    from shared.auth import user_models
    from plainly.routes import kindle
    users = user_models.UserDatabase(test_db_path.with_name(test_db_path.stem + '_users.db'))
    monkeypatch.setattr(progress_routes, 'user_db', users)
    monkeypatch.setattr(progress_routes, 'content_db', db)
    monkeypatch.setattr(kindle, '_signed_in_user_id', lambda: None)
    app_base.app.testing = True
    c = app_base.app.test_client()
    c.book_id = book
    c.users = users
    c.db = db
    return c


def kget(client, path, **kw):
    return client.get(path, headers={'User-Agent': KINDLE_PW}, **kw)


def body(resp):
    return resp.get_data(as_text=True)


def test_kindle_home_is_the_eink_library(client):
    resp = kget(client, '/')
    html = body(resp)
    assert resp.status_code == 200
    assert 'class="kindle' in html
    assert 'app.min.js' not in html and 'app.js' not in html
    assert 'kindle.css' in html
    assert 'Moby &amp; Dick' in html
    assert 'href="/books/moby-dick"' in html
    assert 'User-Agent' in resp.headers.get('Vary', '')


def test_library_lists_plain_english_books_by_default_and_all_on_request(client):
    assert 'Zeta Original Only' not in body(kget(client, '/'))
    assert 'Zeta Original Only' in body(kget(client, '/?show=all'))


def test_library_search_filters_by_title_or_author(client):
    html = body(kget(client, '/?show=all&q=melville'))
    assert 'Moby &amp; Dick' in html and 'Zeta Original Only' not in html


def test_library_paginates_instead_of_scrolling(client):
    from plainly.routes import common
    for i in range(12):
        b = common.db.add_book(title=f'Book {i:02d}', author='A', filename=f'b{i}.txt', full_text='x')
        common.db.update_book_slug(b, f'book-{i}')
    html = body(kget(client, '/?show=all'))
    assert 'Book 00' in html and 'Zeta Original Only' not in html
    assert re.search(r'href="/\?show=all&amp;page=2"', html)
    assert 'Zeta Original Only' in body(kget(client, '/?show=all&page=2'))


def test_desktop_browser_still_gets_the_spa(client):
    html = body(client.get('/', headers={'User-Agent': DESKTOP}))
    assert 'class="kindle' not in html
    assert 'app' in html and 'kindle.css' not in html


def test_kindle_param_zero_opts_out_and_is_remembered(client):
    html = body(kget(client, '/?kindle=0'))
    assert 'class="kindle' not in html
    assert 'class="kindle' not in body(kget(client, '/'))
    assert 'class="kindle' in body(kget(client, '/?kindle=1'))
    assert 'class="kindle' in body(kget(client, '/'))


def test_kindle_book_page_has_read_buttons_and_contents(client):
    html = body(kget(client, '/books/moby-dick'))
    assert '<h1' in html and 'Moby &amp; Dick' in html and 'Herman Melville' in html
    assert 'href="/books/moby-dick/read?ch=1&amp;text=plain"' in html
    assert 'href="/books/moby-dick/read?ch=1&amp;text=original"' in html
    for title in ('Loomings', 'The Carpet-Bag', 'The Spouter-Inn'):
        assert title in html


def test_reader_shows_plain_english_paragraphs_by_default(client):
    html = body(kget(client, '/books/moby-dick/read?ch=1'))
    assert 'kindle.js' in html
    assert re.search(r'<h1[^>]*>Loomings</h1>', html)
    assert '<p data-i="1">My name is Ishmael.</p>' in html
    # The title paragraph is shown once, as the heading.
    assert html.count('Loomings') == 2  # <title> + heading
    assert 'href="/books/moby-dick/read?ch=2' in html


def test_reader_original_text_is_escaped(client):
    html = body(kget(client, '/books/moby-dick/read?ch=1&text=original'))
    assert '<p data-i="1">Call me Ishmael.</p>' in html
    assert 'Some years ago &lt;never mind&gt;.' in html


def test_reader_falls_back_to_original_when_chapter_has_no_plain_english(client):
    html = body(kget(client, '/books/moby-dick/read?ch=3&text=plain'))
    assert 'Entering that gable-ended inn.' in html
    assert 'Plain English isn' in html


def test_reader_resumes_from_saved_position_cookie(client):
    client.set_cookie('kpos_%d' % client.book_id, '2.0')
    html = body(kget(client, '/books/moby-dick/read'))
    assert 'I packed a shirt or two.' in html
    assert 'data-start="0"' in html


def test_chapter_url_opens_kindle_reader_at_that_chapter(client):
    html = body(kget(client, '/books/moby-dick/chapters/2'))
    assert 'I packed a shirt or two.' in html and 'kindle.js' in html


def test_reader_missing_chapter_and_book_are_404(client):
    assert kget(client, '/books/moby-dick/read?ch=99').status_code == 404
    assert kget(client, '/books/moby-dick/read?ch=abc').status_code == 404
    assert kget(client, '/books/nope/read').status_code == 404
    assert kget(client, '/books/nope').status_code == 404


def test_font_size_cookie_sets_reader_class(client):
    client.set_cookie('kfs', '5')
    assert 'fs-5' in body(kget(client, '/books/moby-dick/read?ch=1'))
    client.set_cookie('kfs', '99')
    assert 'fs-3' in body(kget(client, '/books/moby-dick/read?ch=1'))


def test_continue_reading_from_last_book_cookie(client):
    client.set_cookie('klast', 'moby-dick')
    html = body(kget(client, '/'))
    assert 'Continue reading' in html
    assert 'href="/books/moby-dick/read"' in html


def test_reader_renders_underscore_and_asterisk_italics_like_the_web_reader(client):
    from plainly.routes import common
    common.db.add_chapter(client.book_id, 2, 'The Carpet-Bag', 's',
                          modern_english_text='"_You_ want it," said *she*, <b>not</b> snake_case_name.')
    html = body(kget(client, '/books/moby-dick/read?ch=2'))
    assert '<em>You</em> want it," said <em>she</em>, &lt;b&gt;not&lt;/b&gt; snake_case_name.' in html.replace('&#34;', '"')


# ---- Sign-in and synced progress ----

def sign_in(client, monkeypatch, email='reader@example.com'):
    from plainly.routes import kindle
    user_id = client.users.upsert_user_by_email(email)
    monkeypatch.setattr(kindle, '_signed_in_user_id', lambda: user_id)
    return user_id


def save(client, **payload):
    return client.post('/api/kindle/progress', json=payload, headers={'User-Agent': KINDLE_PW})


def unit_id(client, chapter_number, ordinal):
    from plainly.models import Database
    chapter = client.db.get_chapter(client.book_id, chapter_number)
    return Database._reader_unit_id(chapter['id'], ordinal)


def test_signed_out_library_and_book_page_link_to_sign_in(client):
    for path in ('/', '/books/moby-dick'):
        html = body(kget(client, path))
        assert 'href="/login?logout=%2Flogin"' in html, path
        assert 'Sign in' in html


def test_signed_in_pages_show_account_instead_of_sign_in(client, monkeypatch):
    sign_in(client, monkeypatch)
    html = body(kget(client, '/'))
    assert 'Sign in' not in html
    assert 'reader@example.com' in html


def test_reader_only_syncs_when_signed_in(client, monkeypatch):
    assert 'data-sync' not in body(kget(client, '/books/moby-dick/read?ch=1'))
    sign_in(client, monkeypatch)
    assert 'data-sync="/api/kindle/progress"' in body(kget(client, '/books/moby-dick/read?ch=1'))


def test_saving_progress_requires_sign_in(client):
    assert save(client, book_id=client.book_id, ch=1, p=1, text='plain').status_code == 401


def test_kindle_page_turn_is_saved_as_web_reader_progress(client, monkeypatch):
    user = sign_in(client, monkeypatch)
    resp = save(client, book_id=client.book_id, ch=1, p=2, text='plain', forward=True, seconds=20)
    assert resp.status_code == 200, resp.get_json()
    projection = client.users.get_book_projection(user, client.book_id)
    assert projection['book']['last_mode'] == 'plain'
    plain = next(m for m in projection['modes'] if m['mode'] == 'plain')
    assert plain['current_marker']['paragraph_id'] == unit_id(client, 1, 2)
    assert plain['furthest_marker']['paragraph_id'] == unit_id(client, 1, 2)


def test_turning_back_does_not_lower_furthest_point(client, monkeypatch):
    user = sign_in(client, monkeypatch)
    assert save(client, book_id=client.book_id, ch=2, p=0, text='plain', forward=True).status_code == 200
    assert save(client, book_id=client.book_id, ch=1, p=1, text='plain', forward=False).status_code == 200
    plain = next(m for m in client.users.get_book_projection(user, client.book_id)['modes'] if m['mode'] == 'plain')
    assert plain['current_marker']['paragraph_id'] == unit_id(client, 1, 1)
    assert plain['furthest_marker']['paragraph_id'] == unit_id(client, 2, 0)


@pytest.mark.parametrize('bad', [
    {'ch': 99, 'p': 0, 'text': 'plain'},
    {'ch': 1, 'p': 50, 'text': 'plain'},
    {'ch': 1, 'p': 0, 'text': 'summary'},
    {'ch': 'x', 'p': 0, 'text': 'plain'},
    {'book_id': 999999, 'ch': 1, 'p': 0, 'text': 'plain'},
])
def test_bad_progress_is_rejected(client, monkeypatch, bad):
    sign_in(client, monkeypatch)
    assert save(client, **{'book_id': client.book_id, **bad}).status_code == 400


def test_reader_resumes_where_the_web_reader_left_off(client, monkeypatch):
    """Progress saved by the web reader (here: Side by Side, which shares the
    paragraph ids) opens the Kindle reader on the same chapter and paragraph,
    and wins over this device's cookie."""
    user = sign_in(client, monkeypatch)
    marker = client.db.resolve_reader_marker(client.book_id, {
        'mode': 'side_by_side', 'paragraph_id': unit_id(client, 2, 0), 'offset': 0})
    client.users.apply_mutation(user, {
        'mutation_id': 'web-1', 'device_id': 'web', 'device_sequence': 1, 'book_id': client.book_id,
        'mode': 'side_by_side', 'event_cause': 'page_turn', 'base_revision': 0,
    }, marker, marker)
    client.set_cookie('kpos_%d' % client.book_id, '1.1')
    html = body(kget(client, '/books/moby-dick/read'))
    assert 'I packed a shirt or two.' in html
    assert 'data-text="plain"' in html and 'data-start="0"' in html


def test_reader_resumes_original_text_from_server(client, monkeypatch):
    user = sign_in(client, monkeypatch)
    assert save(client, book_id=client.book_id, ch=1, p=2, text='original').status_code == 200
    html = body(kget(client, '/books/moby-dick/read'))
    assert 'data-text="original"' in html and 'data-ch="1"' in html and 'data-start="2"' in html


def test_signed_in_library_continue_reading_comes_from_account(client, monkeypatch):
    sign_in(client, monkeypatch)
    for i in range(3):  # enough reading for the book to count as started
        assert save(client, book_id=client.book_id, ch=1, p=i % 3, text='plain', forward=True, seconds=30).status_code == 200
    html = body(kget(client, '/'))
    assert 'Reading now' in html and 'href="/books/moby-dick/read"' in html


def test_reaching_the_last_paragraph_finishes_the_book(client, monkeypatch):
    user = sign_in(client, monkeypatch)
    resp = save(client, book_id=client.book_id, ch=2, p=0, text='original', forward=True, finished=True)
    assert client.users.get_book_projection(user, client.book_id)['book']['status'] != 'finished'
    # The book's last paragraph in the original is chapter 3's only one.
    resp = save(client, book_id=client.book_id, ch=3, p=0, text='original', forward=True, finished=True)
    assert resp.status_code == 200
    assert client.users.get_book_projection(user, client.book_id)['book']['status'] == 'finished'


def test_account_without_email_says_signed_in_without_blank_name(client, monkeypatch):
    sign_in(client, monkeypatch, email='')
    html = body(kget(client, '/'))
    assert 'Signed in as .' not in html and 'Signed in.' in html


# ---- Reading now: books in progress with progress, on the home page ----

def start_reading(client, slug_or_id, ch=1, p=0, text='plain'):
    book_id = slug_or_id if isinstance(slug_or_id, int) else client.db.get_book_by_slug(slug_or_id)['id']
    for _ in range(2):  # two forward page turns: the book counts as started
        assert save(client, book_id=book_id, ch=ch, p=p, text=text, forward=True, seconds=30).status_code == 200


def add_book(client, n):
    book = client.db.add_book(title=f'Extra {n}', author='Writer', filename=f'e{n}.txt', full_text='x')
    client.db.update_book_slug(book, f'extra-{n}')
    client.db.add_chapter(book, 1, 'Only', 's', chapter_text='One.\n\nTwo.', modern_english_text='One.\n\nTwo.')
    return book


def reading_section(html):
    m = re.search(r'<section class="reading"(.*?)</section>', html, re.S)
    return m.group(1) if m else ''


def test_home_lists_books_in_progress_with_chapter_and_progress(client, monkeypatch):
    sign_in(client, monkeypatch)
    user = client.users.upsert_user_by_email('reader@example.com')
    start_reading(client, 'moby-dick', ch=2, p=0)
    start_reading(client, 'zeta', text='original')
    conn = client.users.get_connection()  # read times have 1 s resolution: make Moby the older one
    conn.execute("UPDATE book_reading_state SET last_meaningful_read_at = '2026-01-01 00:00:00' "
                 "WHERE user_id = ? AND book_id = ?", (user, client.book_id))
    conn.commit()
    conn.close()
    section = reading_section(body(kget(client, '/')))
    assert 'Reading now' in section
    assert 'Moby &amp; Dick' in section and 'Zeta Original Only' in section
    assert section.index('Zeta Original Only') < section.index('Moby &amp; Dick')  # most recent first
    assert 'The Carpet-Bag' in section
    assert re.search(r'\d+%', section)
    assert re.search(r'class="bar"><span style="width: ?\d+%', section)
    assert 'href="/books/moby-dick/read"' in section


def test_home_shows_three_books_and_links_to_all(client, monkeypatch):
    sign_in(client, monkeypatch)
    for n in range(4):
        start_reading(client, add_book(client, n))
    html = body(kget(client, '/'))
    section = reading_section(html)
    assert section.count('class="bar"') == 3
    assert 'href="/?show=reading"' in section and 'See all 4' in section
    full = reading_section(body(kget(client, '/?show=reading')))
    assert full.count('class="bar"') == 4
    assert 'See all' not in full


def test_reading_list_paginates(client, monkeypatch):
    from plainly.routes import kindle
    monkeypatch.setattr(kindle, 'LIBRARY_PAGE_SIZE', 2)
    sign_in(client, monkeypatch)
    for n in range(3):
        start_reading(client, add_book(client, n))
    html = body(kget(client, '/?show=reading'))
    assert reading_section(html).count('class="bar"') == 2
    assert 'href="/?show=reading&amp;page=2"' in html
    assert reading_section(body(kget(client, '/?show=reading&page=2'))).count('class="bar"') == 1


def test_signed_out_home_has_no_reading_now_section(client):
    assert reading_section(body(kget(client, '/'))) == ''
    assert reading_section(body(kget(client, '/?show=reading'))) == ''


def test_progress_endpoint_is_404_when_the_kindle_feature_is_off(client, monkeypatch):
    from dataclasses import replace
    from plainly.routes import kindle
    from plainly.reader_config import PLAINLY_READER
    from shared.reader.config import ReaderFeatures
    sign_in(client, monkeypatch)
    off = replace(PLAINLY_READER, features=ReaderFeatures(kindle=False), kindle=None)
    monkeypatch.setattr(kindle, 'PLAINLY_READER', off)
    assert save(client, book_id=client.book_id, ch=1, p=0, text='plain').status_code == 404
