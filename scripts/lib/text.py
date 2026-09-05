"""Shared chapter/book-title text normalization for scripts.

Before this, `normalize_chapter_title` existed as `SummaryGenerator`'s method in
generate_summaries.py (the canonical, most-evolved version — Roman numeral and
dotted-abbreviation handling) and as independent, progressively-diverging
copies in backfill_chapter_title_case.py and fix_invisible_man_titles.py.
`fix_roman_numerals_in_text` was a free function in the same file.
`normalize_book_title` was a free function in generate_summaries.py, byte-
identical to a second copy in scripts/migrations/migrate_book_titles.py. All
three are pure text transforms with no dependency on SummaryGenerator's
state, so they live here instead:

    from scripts.lib.text import (
        normalize_chapter_title, fix_roman_numerals_in_text, normalize_book_title,
    )
"""
import re


def normalize_chapter_title(title: str) -> str:
    """
    Normalize chapter title to use consistent title case.
    Converts to title case while preserving certain words in lowercase.
    Handles special cases:
    - Words inside quotes are always capitalized (including first word)
    - Words after em-dashes (—) are capitalized
    - Words after colons (:) are capitalized
    - Words after periods (.) are capitalized
    - Dotted abbreviations (M.D., Ph.D., U.S.A.) keep their uppercase letters
    - Roman numerals (I, II, III, ...) are always fully uppercase
    """
    if not title or not title.strip():
        return title

    # Words that should remain lowercase in titles (unless first word, after punctuation, or in quotes)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    # Dotted abbreviations like 'M.D.', 'Ph.D.', 'U.S.A.' — at least 2 internal dots
    # separating short alpha runs. These should never be lowercased by .capitalize().
    dotted_abbrev_pattern = re.compile(r'^(?:[A-Za-z]{1,3}\.){2,}$')

    def smart_capitalize(word: str) -> str:
        """Like str.capitalize() but title-cases each dotted segment in abbreviations.

        'M.D.'  -> 'M.D.'
        'PH.D.' -> 'Ph.D.'
        'U.S.A.'-> 'U.S.A.'
        'hello' -> 'Hello'
        """
        if dotted_abbrev_pattern.match(word):
            # Title-case each dot-separated segment: 'PH.D.' -> 'Ph.D.'
            return '.'.join(seg.capitalize() for seg in word.split('.'))
        return word.capitalize()

    # First, handle em-dashes by adding spaces around them
    # This ensures "Huck.—miss" becomes "Huck.— miss" so we can capitalize properly
    title = title.replace('—', ' — ')
    # Also handle colons followed directly by letters
    title = re.sub(r':(\S)', r': \1', title)
    # Collapse multiple spaces into one
    title = re.sub(r'\s+', ' ', title).strip()

    # Track whether we're inside quotes and if we need to capitalize next word
    in_quotes = False
    capitalize_next = True  # Always capitalize first word
    result = []

    # Roman numeral detection pattern (case-insensitive)
    # Matches I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, etc.
    roman_pattern = re.compile(r'^[IVXLCDM]+$', re.IGNORECASE)

    # Split on whitespace while preserving spaces
    words = title.split()

    for i, word in enumerate(words):
        # Check if word contains quotes (opening or closing)
        # Handle both straight quotes and curly quotes (U+201C LEFT, U+201D RIGHT)
        has_quote = '"' in word or '“' in word or '”' in word
        starts_with_quote = word.startswith('"') or word.startswith('“') or word.startswith('”')

        if has_quote:
            in_quotes = not in_quotes

        # Handle standalone em-dash
        if word == '—':
            result.append(word)
            capitalize_next = True
            continue

        # Check if this word is a Roman numeral (case-insensitive)
        # If so, always uppercase it entirely
        if roman_pattern.match(word):
            result.append(word.upper())
            capitalize_next = False
            continue

        if starts_with_quote:
            # Word starts with quote - capitalize first letter after quote
            # e.g., "it -> "It
            if len(word) > 1:
                # Get the quote character and rest of word
                quote_char = word[0]
                rest = word[1:]
                # Check if rest is a Roman numeral
                if roman_pattern.match(rest):
                    result.append(quote_char + rest.upper())
                elif capitalize_next:
                    result.append(quote_char + rest.capitalize())
                else:
                    # First letter after quote should be capitalized
                    result.append(quote_char + rest[0].upper() + rest[1:].lower() if len(rest) > 1 else quote_char + rest.upper())
            else:
                result.append(word)
            capitalize_next = False
            in_quotes = True  # We're now inside quotes
        elif capitalize_next or in_quotes:
            # Capitalize this word
            result.append(smart_capitalize(word))
            capitalize_next = False
        elif word.lower() in lowercase_words:
            # Keep as lowercase
            result.append(word.lower())
        else:
            # Default: capitalize
            result.append(smart_capitalize(word))

        # Check if we should capitalize the NEXT word
        # This happens after colon (:) or period (.)
        if result[-1].endswith(':') or result[-1].endswith('.'):
            capitalize_next = True

    # Clean up: remove spaces before em-dashes and after em-dashes when followed by punctuation
    result_str = ' '.join(result)
    result_str = result_str.replace(' — ', '—')

    return result_str


def fix_roman_numerals_in_text(text):
    """
    Convert all title-cased Roman numerals in text to uppercase.

    This ensures that Roman numerals in chapter/book titles are always uppercase,
    regardless of whether they were title-cased in the original text.

    Examples:
        "Book Ii" -> "Book II"
        "Part Xiv" -> "Part XIV"
        "Book Xxiii" -> "Book XXIII"
        "Emperors Theodosius Ii" -> "Emperors Theodosius II"
    """
    if not text:
        return text

    # Pattern matches title-case Roman numerals (e.g., Ii, Iii, Iv, Vi, Vii, etc.)
    pattern = r'\b(Ii|Iii|Iv|Vi|Vii|Viii|Ix|Xi|Xii|Xiii|Xiv|Xv|Xvi|Xvii|Xviii|Xix|Xx|Xxi|Xxii|Xxiii|Xxiv|Xxv|Xxvi|Xxvii|Xxviii|Xxix|Xxx)\b'

    def replace_with_uppercase(match):
        return match.group(1).upper()

    return re.sub(pattern, replace_with_uppercase, text)


def normalize_book_title(title):
    """
    Normalize book title to follow consistent formatting rules:
    1. Title Case (capitalize first letter of each word, except articles/prepositions)
    2. Truncate at first colon (:) or semicolon (;)

    Examples:
        "jane eyre: an autobiography" -> "Jane Eyre"
        "MOBY DICK; Or, The Whale" -> "Moby Dick"
        "the great gatsby" -> "The Great Gatsby"

    Args:
        title: Raw book title string

    Returns:
        Normalized title string
    """
    if not title or not title.strip():
        return title

    # Step 1: Truncate at first colon or semicolon
    # Find first occurrence of : or ;
    colon_pos = title.find(':')
    semicolon_pos = title.find(';')

    # Determine which comes first
    if colon_pos != -1 and semicolon_pos != -1:
        truncate_pos = min(colon_pos, semicolon_pos)
    elif colon_pos != -1:
        truncate_pos = colon_pos
    elif semicolon_pos != -1:
        truncate_pos = semicolon_pos
    else:
        truncate_pos = len(title)

    # Truncate title
    title = title[:truncate_pos].strip()

    # Step 2: Apply Title Case
    # Words that should remain lowercase (unless first word)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    words = title.split()
    result = []

    for i, word in enumerate(words):
        # Handle hyphenated words - capitalize each part
        if '-' in word:
            parts = word.split('-')
            capitalized_parts = []
            for j, part in enumerate(parts):
                # First part or parts that aren't lowercase words
                if j == 0 or part.lower() not in lowercase_words:
                    capitalized_parts.append(part.capitalize())
                else:
                    capitalized_parts.append(part.lower())
            result.append('-'.join(capitalized_parts))
        # Always capitalize first word
        elif i == 0:
            result.append(word.capitalize())
        # Keep lowercase words as lowercase (unless after colon/period)
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # Otherwise capitalize
        else:
            result.append(word.capitalize())

    return ' '.join(result)
