"""Tests for scripts/lib/text.py — the shared chapter-title normalization
extracted from generate_summaries.py's SummaryGenerator.normalize_chapter_title
(a pure function with no dependency on SummaryGenerator's state).
"""
from scripts.lib.text import normalize_chapter_title, fix_roman_numerals_in_text


def test_normalize_chapter_title_basic_title_case():
    assert normalize_chapter_title("the adventures of huck") == "The Adventures of Huck"


def test_normalize_chapter_title_empty_and_none():
    assert normalize_chapter_title("") == ""
    assert normalize_chapter_title(None) is None


def test_normalize_chapter_title_roman_numerals_uppercased():
    assert normalize_chapter_title("chapter iv") == "Chapter IV"
    assert normalize_chapter_title("book xiv") == "Book XIV"


def test_normalize_chapter_title_dotted_abbreviation_preserved():
    assert normalize_chapter_title("meeting dr. m.d. smith") == "Meeting Dr. M.D. Smith"


def test_normalize_chapter_title_capitalizes_after_colon_and_period():
    result = normalize_chapter_title("huck.—miss watson: a new friend")
    assert "Miss" in result
    assert "A New Friend" in result


def test_normalize_chapter_title_quoted_text_always_capitalized():
    # Every word inside quotes is capitalized, including normally-lowercase
    # words like "of" — this is the existing (faithfully preserved) behavior.
    assert normalize_chapter_title('the "king of cats"') == 'The "King Of Cats"'


def test_fix_roman_numerals_in_text_uppercases_title_cased_numerals():
    assert fix_roman_numerals_in_text("Book Ii") == "Book II"
    assert fix_roman_numerals_in_text("Part Xiv") == "Part XIV"


def test_fix_roman_numerals_in_text_empty():
    assert fix_roman_numerals_in_text("") == ""
    assert fix_roman_numerals_in_text(None) is None


def test_normalize_chapter_title_matches_generate_summaries_delegate():
    """generate_summaries.SummaryGenerator.normalize_chapter_title must delegate
    to this shared function, not maintain its own parallel copy."""
    from scripts.content.generate_summaries import SummaryGenerator

    gen = SummaryGenerator.__new__(SummaryGenerator)  # skip __init__ (no API key needed)
    samples = [
        "the adventures of huck",
        "chapter iv",
        'the "king of cats"',
        "huck.—miss watson: a new friend",
        "meeting dr. m.d. smith",
    ]
    for title in samples:
        assert gen.normalize_chapter_title(title) == normalize_chapter_title(title)
