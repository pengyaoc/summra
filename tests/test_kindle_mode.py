"""Kindle e-ink mode: a Kindle's experimental browser gets a lean,
server-rendered, paginated reading UI instead of the SPA. Every other browser
keeps the normal site.
"""
import re

import pytest

from backend.kindle import is_kindle_user_agent

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
    from backend import app_base, models
    from backend.routes import common
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
    app_base.app.testing = True
    c = app_base.app.test_client()
    c.book_id = book
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
    from backend.routes import common
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


def test_kindle_script_is_es5(client):
    """The older Kindle browser is WebKit 531 (Safari 4): no let/const,
    arrow functions, classes, template literals or classList."""
    from pathlib import Path
    src = (Path(__file__).parents[1] / 'frontend/static/js/kindle.js').read_text()
    for pattern in (r'\blet\s', r'\bconst\s', r'=>', r'\bclass\s', '`', r'classList'):
        assert not re.search(pattern, src), pattern


def test_reader_renders_underscore_and_asterisk_italics_like_the_web_reader(client):
    from backend.routes import common
    common.db.add_chapter(client.book_id, 2, 'The Carpet-Bag', 's',
                          modern_english_text='"_You_ want it," said *she*, <b>not</b> snake_case_name.')
    html = body(kget(client, '/books/moby-dick/read?ch=2'))
    assert '<em>You</em> want it," said <em>she</em>, &lt;b&gt;not&lt;/b&gt; snake_case_name.' in html.replace('&#34;', '"')
