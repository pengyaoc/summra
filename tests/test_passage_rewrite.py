"""Tests for scripts/content/passage_rewrite.py (verse Plain English gate)."""
from scripts.content.passage_rewrite import check_passages

VERSE = "Of Man’s first disobedience, and the fruit\nOf that forbidden tree whose mortal taste\nBrought death into the World, and all our woe."
GOOD = "Sing about how people first disobeyed God, and the fruit of the forbidden tree that brought death and all our sorrow."


def test_matching_passages_pass():
    assert check_passages([VERSE, VERSE], [GOOD, GOOD]) == []


def test_count_mismatch_fails():
    errors = check_passages([VERSE, VERSE], [GOOD])
    assert any("count" in e for e in errors)


def test_missing_terminator_fails():
    errors = check_passages([VERSE], [GOOD[:-1] + " and all our sor"])
    assert errors and "P1" in errors[0]


def test_closing_quote_terminator_passes():
    assert check_passages([VERSE], [GOOD[:-1] + ".”"]) == []


def test_line_break_inside_paragraph_fails():
    errors = check_passages([VERSE], [GOOD.replace(" the fruit", "\nthe fruit")])
    assert any("line break" in e for e in errors)


def test_too_short_passage_fails():
    errors = check_passages([VERSE], ["People disobeyed God."])
    assert any("ratio" in e for e in errors)


def test_summary_language_fails():
    errors = check_passages([VERSE], ["In this passage, the poet asks the Muse to sing of how people first disobeyed God."])
    assert any("summary" in e for e in errors)


def test_empty_rewrite_fails():
    assert check_passages([VERSE], [""])
