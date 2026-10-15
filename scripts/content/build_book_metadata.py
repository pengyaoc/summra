"""Build scripts/content/book_metadata.json from the metadata audit.

    PYTHONPATH=. venv/bin/python scripts/content/build_book_metadata.py

Inputs (data/metadata_audit/, gitignored working files):
  audit_part{1,2,3}.json  Sonnet audits: Gutenberg Library of Congress
                          subjects and class, 1–3 BISAC-based genres with
                          sources, audience.
  atos_part{1,2,3}.json   ATOS book level + interest level of the unabridged
                          edition, from Renaissance's AR BookFinder.

The output is the reviewed record that apply_book_metadata.py writes into a
database. Genres are grouped into display categories (CATEGORIES); the
build refuses categories with fewer than MIN_BOOKS books, so the Categories
page never shows a one-book shelf.
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'data' / 'metadata_audit'
OUT = Path(__file__).resolve().parent / 'book_metadata.json'
MIN_BOOKS = 3

# Display categories, each a BISAC subject heading (the US book-industry
# standard, maintained by BISG) or two sibling headings bookstores shelve
# together because each alone would hold fewer than MIN_BOOKS of our books.
CATEGORIES = {
    'Action & Adventure': (['FIC002000'], 'Journeys, danger and daring escapes.'),
    'Science Fiction': (['FIC028000'], 'Inventions, other worlds and the future, imagined.'),
    'Fantasy': (['FIC009000'], 'Magic, impossible creatures and worlds that work by their own rules.'),
    'Mystery & Detective': (['FIC022000'], 'Crimes, clues and the detectives who solve them.'),
    'Horror & Gothic': (['FIC015000'], 'Ghosts, monsters, crumbling castles and dread.'),
    'Romance': (['FIC027000'], 'Love stories, courtship and marriage.'),
    'Historical Fiction': (['FIC014000'], 'Stories set in real periods of the past.'),
    'Humor & Satire': (['FIC016000', 'FIC052000'], 'Comedy, wit and stories that mock the powerful.'),
    'War & Military': (['FIC032000'], 'Soldiers, battles and what war does to people.'),
    'Coming of Age': (['FIC043000'], 'Growing up: young people finding out who they are.'),
    'Literary Fiction': (['FIC019000'], 'Character-driven novels read for their ideas and style.'),
    'Short Stories': (['FIC029000'], 'Collections of short fiction.'),
    'Fairy Tales, Folklore & Mythology': (['FIC010000'], 'Fairy tales, myths, legends and epics of gods and heroes.'),
    'Poetry & Drama': (['POE000000', 'DRA000000'], 'Epic poems and plays.'),
    'Philosophy & Religion': (['PHI000000', 'REL000000'], 'Big questions about how to live, belief and meaning.'),
    'History & Biography': (['HIS000000', 'BIO000000'], 'Real lives and real events.'),
    'Economics, Politics & Science': (['BUS069000', 'POL000000', 'SCI000000'], 'The treatises that shaped economics, politics and science.'),
}
# Audit genre → display category (None drops it: Travel only fit two books,
# both of which keep other categories).
GENRE_TO_CATEGORY = {**{name: name for name in CATEGORIES},
                     'Poetry': 'Poetry & Drama', 'Drama': 'Poetry & Drama',
                     'Philosophy': 'Philosophy & Religion', 'Religion': 'Philosophy & Religion',
                     'History': 'History & Biography', 'Biography & Memoir': 'History & Biography',
                     'Economics': 'Economics, Politics & Science', 'Political Science': 'Economics, Politics & Science',
                     'Science & Nature': 'Economics, Politics & Science', 'Travel': None}

# Old category (before this regrouping) → the category its page now redirects
# to; None sends it to the Categories page (origin and catch-all labels such
# as "British Literature" or "Novels" have no single honest replacement).
OLD_CATEGORY_REDIRECTS = {
    'Adventure': 'Action & Adventure', 'Biographies': 'History & Biography',
    'Poetry': 'Poetry & Drama', 'Play & Drama': 'Poetry & Drama',
    'Crime, Thrillers & Mystery': 'Mystery & Detective', 'Law & Criminology': 'Mystery & Detective',
    'Mythology, Legends & Folklore': 'Fairy Tales, Folklore & Mythology', 'Humour': 'Humor & Satire',
    'Science & Technology': 'Science Fiction', 'Biology': 'Economics, Politics & Science',
    'Economics': 'Economics, Politics & Science', 'Politics': 'Economics, Politics & Science',
    'History': 'History & Biography', 'Ancient History': 'History & Biography', 'Modern History': 'History & Biography',
    'American History': 'Historical Fiction', 'European History': 'Historical Fiction',
    'History - Early Modern (c. 1450-1750)': 'Historical Fiction',
    'Essays, Letters & Speeches': 'Philosophy & Religion', 'Religion & Philosophy': 'Philosophy & Religion',
    'American Literature': None, 'British Literature': None, 'French Literature': None, 'German Literature': None,
    'Russian Literature': None, 'Classic Literature': None, 'Novels': None, "Children's Literature": None,
    'Arts & Culture': None, 'Travel Writing': None, 'Nature Writing': None,
}

# Reviewed corrections to the audit: (slug, category to drop, why).
REMOVE = [
    ('the-great-gatsby', 'Historical Fiction', 'written in 1925 about 1922 — contemporary, not historical'),
    ('uncle-toms-cabin', 'Historical Fiction', 'written in 1852 about its own time — contemporary, not historical'),
]

# Common Core State Standards for ELA, Appendix B: Text Exemplars (NGA Center
# & CCSSO, 2010). Verified by searching the full OCR'd text of the archived
# PDF for every title (the agents' own matches were incomplete).
APPENDIX_B = 'https://web.archive.org/web/2019/http://www.corestandards.org/assets/Appendix_B.pdf'
COMMON_CORE = {
    'the-wonderful-wizard-of-oz': 'K–1 (read-aloud)',
    'alices-adventures-in-wonderland': '4–5',
    'little-women-or-meg-jo-beth-and-amy': '6–8',
    'the-adventures-of-tom-sawyer': '6–8',
    'narrative-of-the-life-of-frederick-douglass-an-american-slave': '6–8',
    'the-odyssey': '9–10',
    'metamorphosis': '9–10',
    'pride-and-prejudice': '11–12',
    'jane-eyre': '11–12',
    'the-scarlet-letter': '11–12',
    'crime-and-punishment': '11–12',
    'the-great-gatsby': '11–12',
    'don-quixote': '11–12',
    'the-importance-of-being-earnest': '11–12',
}


_INTEREST = {'LG': 'LG (K-3)', 'MG': 'MG (4-8)', 'MG+': 'MG+ (6 and up)', 'UG': 'UG (9-12)'}


def _interest(text):
    """AR interest level in one form ('UG (9-12)'), however the lookup wrote it."""
    match = re.search(r'\b(MG\+|MG|UG|LG)', text or '')
    return _INTEREST[match.group(1)] if match else None


def _load(prefix):
    rows = []
    for part in (1, 2, 3):
        path = AUDIT / f'{prefix}_part{part}.json'
        if path.exists():
            rows += json.loads(path.read_text())
    return {row['slug']: row for row in rows}


def build():
    audits, atos, inputs = _load('audit'), _load('atos'), _load('books')
    books = {}
    for slug, audit in sorted(audits.items()):
        categories = []
        for genre in audit['genres']:
            category = GENRE_TO_CATEGORY[genre]
            if category and category not in categories:
                categories.append(category)
        categories = [c for c in categories if (slug, c) not in {(r[0], r[1]) for r in REMOVE}]
        level = atos.get(slug) or {}
        books[slug] = {
            'categories': categories,
            'audience': audit['audience'],
            'sources': [f"https://www.gutenberg.org/ebooks/{inputs[slug]['gutenberg_id']}",
                        *audit.get('genre_sources', [])],
            'loc_subjects': audit.get('gutenberg_subjects', []),
            'school_lists': [{'list': 'Common Core exemplar', 'grade_band': COMMON_CORE[slug], 'source': APPENDIX_B}]
                            if slug in COMMON_CORE else [],
            'reading_level': {'atos': level['atos_book_level'], 'interest': _interest(level.get('interest_level')),
                              'source': level['source_url']}
                             if level.get('found') and level.get('atos_book_level') else None,
        }
        books[slug]['sources'] = [s for s in books[slug]['sources'] if s]
    counts = Counter(c for book in books.values() for c in book['categories'])
    thin = {name: n for name, n in counts.items() if n < MIN_BOOKS}
    if thin:
        raise SystemExit(f'Categories with fewer than {MIN_BOOKS} books: {thin}')
    used = {name: {'bisac': CATEGORIES[name][0], 'description': CATEGORIES[name][1]} for name in CATEGORIES if name in counts}
    return {'categories': used, 'category_redirects': OLD_CATEGORY_REDIRECTS, 'books': books}


if __name__ == '__main__':
    meta = build()
    OUT.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + '\n')
    counts = Counter(c for book in meta['books'].values() for c in book['categories'])
    print(f"{len(meta['books'])} books → {OUT.relative_to(ROOT)}")
    for name, n in counts.most_common():
        print(f'  {n:3}  {name}')
    print(f"reading levels: {sum(1 for b in meta['books'].values() if b['reading_level'])}/{len(meta['books'])}")
