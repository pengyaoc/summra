"""Book metadata (genres, audience, school lists, reading levels).

`scripts/content/book_metadata.json` is the reviewed, sourced record —
built by scripts/content/build_book_metadata.py from the Sonnet audits and
published reading levels — and `apply_book_metadata.py` writes it into a
database (local or the prod VM) idempotently.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

from backend import models
from scripts.content.apply_book_metadata import apply_metadata

METADATA = Path(__file__).resolve().parent.parent / 'scripts' / 'content' / 'book_metadata.json'


@pytest.fixture(scope='module')
def meta():
    return json.loads(METADATA.read_text())


def test_every_category_is_a_sourced_bisac_grouping_with_at_least_three_books(meta):
    counts = Counter(c for book in meta['books'].values() for c in book['categories'])
    assert set(counts) <= set(meta['categories'])
    for name, n in counts.items():
        assert n >= 3, f'{name!r} has only {n} book(s) — no one-off categories'
        assert meta['categories'][name]['bisac'], f'{name!r} needs its BISAC source'


def test_every_book_has_one_to_three_categories_and_an_audience(meta):
    for slug, book in meta['books'].items():
        assert 1 <= len(book['categories']) <= 3, slug
        assert book['audience'] in ('Children', 'Young Adult', 'Adult'), slug
        assert book['sources'], f'{slug}: genres must cite sources'


def test_school_lists_and_reading_levels_cite_a_source(meta):
    for slug, book in meta['books'].items():
        for entry in book['school_lists']:
            assert entry['list'] and entry['grade_band'] and entry['source'].startswith('http'), slug
        level = book.get('reading_level')
        if level:
            assert 0 < level['atos'] <= 13 and level['source'].startswith('http'), slug


def _db_with_books(test_db_path):
    db = models.Database(db_path=test_db_path)
    ids = {}
    for slug in ('alpha', 'beta', 'gamma'):
        ids[slug] = db.add_book(title=slug.title(), author='A', filename=f'{slug}.txt', full_text='x')
        db.update_book_slug(ids[slug], slug)
    old = db.add_category('Novels')
    conn = db.get_connection()
    conn.execute('INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)', (ids['alpha'], old))
    conn.commit()
    conn.close()
    return db, ids


SAMPLE = {
    'categories': {'Fantasy': {'bisac': ['FIC009000'], 'description': 'Magic and other worlds.'}},
    'books': {
        slug: {'categories': ['Fantasy'], 'audience': 'Children', 'sources': ['https://example.test'],
               'school_lists': [{'list': 'Common Core exemplar', 'grade_band': '4–5', 'source': 'https://example.test/b'}] if slug == 'alpha' else [],
               'reading_level': {'atos': 6.4, 'interest': 'MG (4-8)', 'source': 'https://example.test/ar'} if slug == 'beta' else None}
        for slug in ('alpha', 'beta', 'gamma', 'not-in-db')
    },
}


def test_apply_replaces_categories_and_sets_columns(test_db_path):
    db, ids = _db_with_books(test_db_path)
    report = apply_metadata(db, SAMPLE)
    assert report['missing'] == ['not-in-db']
    names = {c['name'] for c in db.get_all_categories()}
    assert names == {'Fantasy'}, 'old ad-hoc categories are removed'
    beta = db.get_book_by_slug('beta')
    assert beta['atos_level'] == 6.4 and beta['interest_level'] == 'MG (4-8)' and beta['audience'] == 'Children'
    assert json.loads(db.get_book_by_slug('alpha')['school_lists'])[0]['grade_band'] == '4–5'
    assert db.get_book_by_slug('gamma')['atos_level'] is None


def test_apply_is_idempotent(test_db_path):
    db, _ = _db_with_books(test_db_path)
    apply_metadata(db, SAMPLE)
    second = apply_metadata(db, SAMPLE)
    assert second['changed'] == 0
    assert len(db.get_all_categories()) == 1
