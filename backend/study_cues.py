"""Study cues for book cards, book pages and chapter lists: a plain
difficulty level, a reading time, and a one-line chapter summary excerpt.

Computed server-side in one place so the API, server-rendered pages and
Discover all agree (see docs/superpowers/specs/2026-10-12-site-redesign-design.md).
"""
import math
import re

WORDS_PER_MINUTE = 230

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


def _first_sentence(text):
    for match in re.finditer(r'[.!?]["”’)]?(?=\s|$)', text):
        before = text[:match.start()].split()
        last_word = before[-1].lower().strip('("“‘') if before else ''
        is_initial = len(last_word) == 1 and last_word.isalpha()
        if match.group().startswith('.') and (last_word in _ABBREVIATIONS or is_initial):
            continue
        return text[:match.end()]
    return text


def summary_excerpt(text, limit=160):
    """First sentence of the summary's first paragraph, without markdown,
    cut at a word boundary to at most `limit` characters (plus "…")."""
    if not text or not text.strip():
        return None
    paragraph = text.strip().split('\n\n', 1)[0]
    paragraph = re.sub(r'^\s*#+\s*', '', paragraph, flags=re.M)
    paragraph = re.sub(r'(\*\*|__|\*|_)(.+?)\1', r'\2', paragraph)
    paragraph = ' '.join(paragraph.split())
    sentence = _first_sentence(paragraph)
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(' ', 1)[0].rstrip(',;:') + '…'


def add_book_cues(book):
    """Add `level`, `reading_minutes` and `reading_time` to a book dict
    (in place) and return it."""
    book['level'] = level_label(book.get('cefr_level'))
    book['reading_minutes'] = reading_minutes(book.get('word_count'))
    book['reading_time'] = format_reading_time(book['reading_minutes'])
    return book


def add_chapter_cues(chapter):
    """Turn the metadata query's private `_text_words` / `_summary_head`
    columns into `reading_minutes` / `reading_time` / `summary_excerpt`
    (in place)."""
    chapter['reading_minutes'] = reading_minutes(chapter.pop('_text_words', None))
    chapter['reading_time'] = format_reading_time(chapter['reading_minutes'])
    chapter['summary_excerpt'] = summary_excerpt(chapter.pop('_summary_head', None))
    return chapter
