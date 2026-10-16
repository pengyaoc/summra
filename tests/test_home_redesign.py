"""Home page (redesign phase 6).

The hero leads with Summra's differentiator: an opening sentence from a
classic next to its plain-English rewrite, pulled from real chapters. Below
it: "Start here" (the ranked top-10 shelf, now with level and reading time),
"Find a book at the right level" (grade-band links into a filtered Discover,
plus where reading levels, age fit and school lists come from).
"""
import re
from pathlib import Path

import pytest

from backend.study_cues import split_sentences


# --- split_sentences ---------------------------------------------------------

def test_split_sentences_keeps_whole_sentences_without_truncating():
    long = 'Word ' * 60 + 'end. Next.'
    assert split_sentences(long) == [' '.join(long.split()[:-1]), 'Next.']


def test_split_sentences_strips_markdown_and_respects_abbreviations():
    assert split_sentences('**Mr. Utterson** the lawyer was a man. He smiled.') == \
        ['Mr. Utterson the lawyer was a man.', 'He smiled.']


def test_split_sentences_empty():
    assert split_sentences('') == [] and split_sentences(None) == []


# --- matching the plain-English rewrite to the original sentence ------------

from backend.routes.pages import _hero_pair


def test_pair_keeps_every_plain_sentence_a_split_long_sentence_became():
    original = 'A crowd stood before a wooden edifice, the door of which was studded with iron spikes.'
    plain = 'A crowd stood in front of a wooden building. The door was covered with iron spikes.'
    assert _hero_pair(original, plain) == (original, plain)


def test_pair_stops_where_the_original_second_sentence_starts():
    original = 'My name being Pirrip, my infant tongue made it Pip. So I called myself Pip, and came to be called Pip.'
    plain = 'My name was Pirrip, but as a baby I could only say Pip. So I called myself Pip, and everyone called me Pip.'
    assert _hero_pair(original, plain) == ('My name being Pirrip, my infant tongue made it Pip.',
                                           'My name was Pirrip, but as a baby I could only say Pip.')


def test_pair_handles_a_one_sentence_rewrite_and_missing_text():
    assert _hero_pair('It is a truth universally acknowledged.', 'Everyone knows.') == \
        ('It is a truth universally acknowledged.', 'Everyone knows.')
    assert _hero_pair('', 'Plain.') is None and _hero_pair('Original.', None) is None


# --- home page ---------------------------------------------------------------

@pytest.fixture
def client(test_db_path, monkeypatch):
    from backend import app_base, models
    from backend.routes import common, pages
    db = models.Database(db_path=test_db_path)
    pp = db.add_book(title='Pride and Prejudice', author='Jane Austen', filename='pg1342.txt', full_text='x')
    db.update_book_slug(pp, 'pride-and-prejudice')
    db.update_book_cover(pp, 1342, 'covers/5.png')
    no_modern = db.add_book(title='Jane Eyre', author='Charlotte Brontë', filename='pg1260.txt', full_text='x')
    db.update_book_slug(no_modern, 'jane-eyre')
    easy = db.add_book(title='Easy One', author='A', filename='e.txt', full_text='x')
    conn = db.get_connection()
    conn.execute("UPDATE books SET cefr_level='B2', word_count=120000, atos_level=12.0 WHERE id=?", (pp,))
    conn.execute("UPDATE books SET cefr_level='A2', slug='easy-one', atos_level=4.6 WHERE id=?", (easy,))
    conn.commit()
    conn.close()
    db.add_chapter(pp, 1, 'Chapter 1', summary='S.',
                   chapter_text='Chapter 1\n\nIt is a truth universally acknowledged, that a single man must be in want of a wife.\n\nMore.',
                   modern_english_text='Chapter 1\n\nEveryone knows that a single man with a lot of money needs a wife.\n\nMore.')
    db.add_chapter(no_modern, 1, 'Chapter 1', summary='S.', chapter_text='There was no walk.')
    monkeypatch.setattr(pages, 'HERO_EXAMPLES', [('pride-and-prejudice', 1), ('jane-eyre', 1), ('missing-book', 1)])
    monkeypatch.setattr(app_base, 'db', db)
    monkeypatch.setattr(common, 'db', db)
    app_base.app.testing = True
    return app_base.app.test_client()


def test_hero_shows_original_and_plain_english_sentence(client):
    body = client.get('/').get_data(as_text=True)
    pairs = re.findall(r'<figure class="hero-sentence"[^>]*>(.*?)</figure>', body, re.S)
    # Books without a plain-English rewrite (or missing) are skipped.
    assert len(pairs) == 1, pairs
    pair = pairs[0]
    assert 'It is a truth universally acknowledged, that a single man must be in want of a wife.' in pair
    assert 'Everyone knows that a single man with a lot of money needs a wife.' in pair
    caption = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', pair, re.S).group(1)
    assert 'Pride and Prejudice' in caption and 'Jane Austen' in caption, caption
    assert 'Chapter 1' not in re.sub(r'<figcaption.*?</figcaption>', '', pair, flags=re.S), \
        'the chapter title paragraph must not be used as the sentence'


def test_hero_has_no_cover_wall_or_clipart(client):
    body = client.get('/').get_data(as_text=True)
    assert 'images/infographic' not in body and 'images/chapter_view' not in body


def _grade_card(body, band):
    m = re.search(rf'<a class="grade-card grade-card--{band}" href="/discover\?grade={band}"[^>]*>(.*?)</a>', body, re.S)
    return m and m.group(1)


def test_right_level_section_links_grade_bands_into_discover(client):
    body = client.get('/').get_data(as_text=True)
    for band, count in [('3-5', '1 book'), ('6-8', '0 books'), ('9-10', '0 books'), ('11-12', '1 book')]:
        card = _grade_card(body, band)
        assert card and count in card, (band, card)


def test_right_level_section_explains_its_sources(client):
    body = client.get('/').get_data(as_text=True)
    section = re.search(r'<section [^>]*id="reading-levels"[^>]*>(.*?)</section>', body, re.S).group(1)
    assert 'ATOS' in section and 'arbookfind.com' in section, 'reading level: published ATOS levels, linked'
    assert 'Interest' in section, 'age fit: AR interest levels'
    assert 'Common Core' in section and 'Appendix_B.pdf' in section, 'school lists, linked'
    assert 'Flesch' in section, 'say why a simple formula is not used'
    assert 'How it works' not in body and 'Choose by level' not in body


def test_start_here_cards_have_cues_and_no_rank_badge(client):
    body = client.get('/').get_data(as_text=True)
    carousel = re.search(r'id="top-10-scroll">(.*?)</div>\s*<button class="carousel-nav-btn right"', body, re.S).group(1)
    card = re.search(r'<a class="top-10-book-card" href="/books/pride-and-prejudice".*?</a>', carousel, re.S).group(0)
    assert 'book-card-rank' not in card, 'no "No. N" badge on the cover'
    assert '<h3 class="book-card-title">Pride and Prejudice</h3>' in card
    assert '<span class="grade-tag grade-tag--11-12">Original: Grade 12</span>' in card
    assert '<span class="book-card-time">8½ hrs</span>' in card


def test_hero_hidden_on_server_rendered_discover(client):
    body = client.get('/discover').get_data(as_text=True)
    assert re.search(r'<div id="hero-section" class="hidden">', body)


def test_home_content_is_in_every_page_for_in_app_navigation(client):
    """#hero-section is rendered (hidden) on every page so client-side
    navigation home can just reveal it — its examples and counts must be
    there too, not only on /."""
    body = client.get('/categories').get_data(as_text=True)
    assert 'Everyone knows that a single man with a lot of money needs a wife.' in body
    assert '1 book' in (_grade_card(body, '3-5') or '')


# --- the curated hero examples (real content database) ------------------------

REAL_DB = Path(__file__).resolve().parent.parent / 'data' / 'database.db'


# App imports can create an empty database, so existence alone is not opt-in.
@pytest.mark.content
@pytest.mark.skipif(not REAL_DB.exists(), reason='needs the content database')
def test_hero_examples_are_famous_hard_sentences(monkeypatch):
    """Every configured example resolves, and each is the kind of sentence a
    student actually gets stuck on: long and hard in the original, clearly
    shorter or simpler in plain English."""
    from backend.models import Database
    from backend.routes import common, pages
    monkeypatch.setattr(common, 'db', Database(str(REAL_DB)))
    examples = pages._hero_examples()
    assert len(examples) == len(pages.HERO_EXAMPLES) >= 5, [e['slug'] for e in examples]
    for ex in examples:
        words = len(ex['original'].split())
        assert words >= 15, (ex['slug'], ex['original'])
        assert ex['plain'] != ex['original'], ex['slug']
    slugs = {e['slug'] for e in examples}
    assert {'pride-and-prejudice', 'great-expectations'} <= slugs
    assert not slugs & {'jane-eyre', 'frankenstein'}, 'openings too easy to show off a rewrite'


# --- Continue reading is server-rendered (no late pop-in) ---------------------

class _StubUserDb:
    """The user database boundary: just the reading-state lookup."""
    def __init__(self, states):
        self.states = states

    def get_library_projection(self, user_id):
        return self.states


def _continue_section(body):
    return re.search(r'<section class="([^"]*)" id="home-continue"[^>]*>(.*?)</section>', body, re.S)


def test_continue_reading_is_in_the_first_html_for_a_reader_with_progress(client, monkeypatch):
    from backend import app_base
    from backend.routes import pages
    from backend.routes.pages import progress_routes  # the module pages.py uses (another test reloads it)
    monkeypatch.setattr(pages, '_signed_in_user_id', lambda: 7)  # auth boundary: a signed-in reader
    book_id = app_base.db.get_book_by_slug('pride-and-prejudice')['id']
    monkeypatch.setattr(progress_routes, 'content_db', app_base.db)
    monkeypatch.setattr(progress_routes, 'user_db', _StubUserDb([{
        'book_id': book_id, 'status': 'in_progress', 'last_mode': 'plain', 'last_mode_state': None,
        'last_meaningful_read_at': '2026-10-13', 'finished_at': None}]))
    resp = client.get('/')
    classes, inner = _continue_section(resp.get_data(as_text=True)).groups()
    assert 'hidden' not in classes.split()
    assert 'class="library-card"' in inner and 'Pride and Prejudice' in inner
    assert 'covers/5.webp' in inner, 'cover rendered server-side too'
    assert 'private' in resp.headers['Cache-Control'], 'personal HTML must not enter shared caches'


def test_continue_reading_absent_without_progress(client, monkeypatch):
    from backend import app_base
    from backend.routes.pages import progress_routes
    monkeypatch.setattr(progress_routes, 'content_db', app_base.db)
    monkeypatch.setattr(progress_routes, 'user_db', _StubUserDb([]))
    classes, inner = _continue_section(client.get('/').get_data(as_text=True)).groups()
    assert 'hidden' in classes.split() and 'class="library-card"' not in inner
