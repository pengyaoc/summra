"""Home page (redesign phase 6).

The hero leads with Summra's differentiator: an opening sentence from a
classic next to its plain-English rewrite, pulled from real chapters. Below
it: "Start here" (the ranked top-10 shelf, now with level and reading time),
"Choose by level" (three links into a filtered Discover) and "How it works".
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
    conn.execute("UPDATE books SET cefr_level='B2', word_count=120000 WHERE id=?", (pp,))
    conn.execute("UPDATE books SET cefr_level='A2', slug='easy-one' WHERE id=?", (easy,))
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


def test_choose_by_level_links_into_filtered_discover(client):
    body = client.get('/').get_data(as_text=True)
    for level, count in [('easy', '1 book'), ('moderate', '1 book'), ('challenging', '0 books')]:
        m = re.search(rf'<a class="level-card level-card--{level}" href="/discover\?level={level}"[^>]*>(.*?)</a>', body, re.S)
        assert m, level
        assert count in m.group(1)


def test_start_here_cards_keep_rank_and_add_cues(client):
    body = client.get('/').get_data(as_text=True)
    carousel = re.search(r'id="top-10-scroll">(.*?)</div>\s*<button class="carousel-nav-btn right"', body, re.S).group(1)
    card = re.search(r'<a class="top-10-book-card" href="/books/pride-and-prejudice".*?</a>', carousel, re.S).group(0)
    assert 'top-10-rank-number">3<' in card
    assert '<h3 class="book-card-title">Pride and Prejudice</h3>' in card
    assert '<span class="level-tag level-tag--moderate">Moderate</span>' in card
    assert '<span class="book-card-time">8½ hrs</span>' in card


def test_hero_hidden_on_server_rendered_discover(client):
    body = client.get('/discover').get_data(as_text=True)
    assert re.search(r'<div id="hero-section" class="hidden">', body)


def test_home_content_is_in_every_page_for_in_app_navigation(client):
    """#hero-section is rendered (hidden) on every page so client-side
    navigation home can just reveal it — its examples and counts must be
    there too, not only on /."""
    body = client.get('/books').get_data(as_text=True)
    assert 'Everyone knows that a single man with a lot of money needs a wife.' in body
    assert re.search(r'level-card--easy" href="/discover\?level=easy"[^>]*>.*?1 book', body, re.S)


# --- the curated hero examples (real content database) ------------------------

REAL_DB = Path(__file__).resolve().parent.parent / 'data' / 'database.db'


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
    scarlet = next(e for e in examples if e['slug'] == 'the-scarlet-letter')
    assert 'spikes' in scarlet['plain'], 'the rewrite split the sentence; both halves must be shown'
