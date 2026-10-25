"""Study cues for book cards, book pages and chapter lists: a plain
difficulty level and a reading time (plus the sentence splitter the home
hero uses).

Computed server-side in one place so the API, server-rendered pages and
Discover all agree (see docs/superpowers/specs/2026-10-12-site-redesign-design.md).
"""
import json
import math
import re

WORDS_PER_MINUTE = 230

# Book length buckets for Discover, by word count: under 50k ("read in a
# day or two"), under 120k, and longer.
SHORT_MAX_WORDS = 50_000
MEDIUM_MAX_WORDS = 120_000

# CEFR → plain label, keyed on the *upper* bound of a range ("B1-B2" reads as
# B2), so a book is never labelled easier than its hardest stretch.
_LEVEL_BY_CEFR = {
    'A1': 'Easy', 'A2': 'Easy', 'B1': 'Easy',
    'B2': 'Moderate',
    'C1': 'Challenging', 'C2': 'Challenging',
}

# Words ending in "." that don't end a sentence.
_ABBREVIATIONS = {'mr', 'mrs', 'ms', 'dr', 'st', 'jr', 'sr', 'mt', 'vs', 'no', 'vol', 'ch'}


def level_label(cefr):
    """'Easy' / 'Moderate' / 'Challenging' for a CEFR level or range, else None."""
    if not cefr or not cefr.strip():
        return None
    upper = cefr.strip().upper().split('-')[-1].strip()
    return _LEVEL_BY_CEFR.get(upper)


def reading_minutes(words):
    """Whole minutes to read `words` words, rounded up; None without words."""
    if not words or words <= 0:
        return None
    return math.ceil(words / WORDS_PER_MINUTE)


def length_label(words):
    """'Short' / 'Medium' / 'Long' for a book's word count, else None."""
    if not words or words <= 0:
        return None
    if words < SHORT_MAX_WORDS:
        return 'Short'
    return 'Medium' if words < MEDIUM_MAX_WORDS else 'Long'


def format_reading_time(minutes):
    """"8 min" under an hour, else hours to the nearest half ("5½ hrs")."""
    if not minutes:
        return None
    if minutes < 60:
        return f'{minutes} min'
    halves = math.floor(minutes / 30 + 0.5)
    hours, half = divmod(halves, 2)
    label = f"{hours}{'½' if half else ''}"
    return f'{label} hr' if halves == 2 else f'{label} hrs'


def split_sentences(paragraph):
    """A paragraph's sentences, without markdown, on one line each."""
    if not paragraph or not paragraph.strip():
        return []
    text = re.sub(r'^\s*#+\s*', '', paragraph.strip(), flags=re.M)
    text = ' '.join(re.sub(r'(\*\*|__|\*|_)(.+?)\1', r'\2', text).split())
    sentences, start = [], 0
    for match in re.finditer(r'[.!?]["”’)]?(?=\s|$)', text):
        before = text[:match.start()].split()
        last_word = before[-1].lower().strip('("“‘') if before else ''
        is_initial = len(last_word) == 1 and last_word.isalpha()
        if match.group().startswith('.') and (last_word in _ABBREVIATIONS or is_initial):
            continue
        sentences.append(text[start:match.end()].strip())
        start = match.end()
    if text[start:].strip():
        sentences.append(text[start:].strip())
    return sentences


def grade_band(atos):
    """Discover grade filter bucket for an ATOS book level: '3-5', '6-8',
    '9-10' or '11-12' (college-level books included), else None."""
    if atos is None:
        return None
    grade = math.floor(atos)
    if grade <= 5:
        return '3-5'
    if grade <= 8:
        return '6-8'
    return '9-10' if grade <= 10 else '11-12'


def grade_label(atos):
    """'Grade 7' for an ATOS level of 7.x — the US grade (and month) a typical
    student can read it in; 13 and up is 'College'."""
    if atos is None:
        return None
    grade = math.floor(atos)
    return 'College' if grade >= 13 else f'Grade {grade}'


# Renaissance's AR interest levels (content maturity, not difficulty) as ages:
# LG = grades K–3, MG = 4–8, MG+ = 6 and up, UG = 9–12.
_AGES = {'LG': ('lg', 'Ages 5–9'), 'MG': ('mg', 'Ages 9–14'), 'MG+': ('mg-plus', 'Ages 11+'), 'UG': ('ug', 'Ages 14+')}


def ages_for(interest_level):
    """(filter key, label) for an AR interest level like 'MG+ (6 and up)'."""
    code = (interest_level or '').split(' ', 1)[0]
    return _AGES.get(code, (None, None))


def add_book_cues(book):
    """Add `level`, `reading_minutes`, `reading_time`, `length`, reading grade
    (`grade`, `grade_label`, `grade_band`), `ages`/`ages_label` and
    `school_lists`/`on_school_list` to a book dict (in place) and return it."""
    book['level'] = level_label(book.get('cefr_level'))
    book['reading_minutes'] = reading_minutes(book.get('word_count'))
    book['reading_time'] = format_reading_time(book['reading_minutes'])
    book['length'] = length_label(book.get('word_count'))
    book['grade'] = book.get('atos_level')
    book['grade_label'] = grade_label(book['grade'])
    book['grade_band'] = grade_band(book['grade'])
    book['ages'], book['ages_label'] = ages_for(book.get('interest_level'))
    lists = book.get('school_lists')
    book['school_lists'] = json.loads(lists) if isinstance(lists, str) and lists else (lists or [])
    book['on_school_list'] = bool(book['school_lists'])
    return book


def add_chapter_cues(chapter):
    """Turn the metadata query's private `_text_words` column into
    `reading_minutes` / `reading_time` (in place)."""
    chapter['reading_minutes'] = reading_minutes(chapter.pop('_text_words', None))
    chapter['reading_time'] = format_reading_time(chapter['reading_minutes'])
    return chapter
