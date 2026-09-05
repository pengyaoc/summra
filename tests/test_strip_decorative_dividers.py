"""Tests for scripts/audits/strip_decorative_dividers.py."""
import sys
from pathlib import Path

from scripts.audits.strip_decorative_dividers import is_divider_paragraph, strip_dividers


def test_asterisk_row_is_divider():
    assert is_divider_paragraph("* * * * * * *")
    assert is_divider_paragraph("* * *")
    assert is_divider_paragraph("***")


def test_asterisk_row_with_extra_whitespace():
    assert is_divider_paragraph("   * * * * *   ")
    assert is_divider_paragraph("\t* * *\t")


def test_dash_or_dot_row_is_divider():
    assert is_divider_paragraph("- - - - -")
    assert is_divider_paragraph(". . . . .")
    assert is_divider_paragraph("---")
    assert is_divider_paragraph("…")  # ellipsis


def test_short_alphabetic_text_is_NOT_divider():
    assert not is_divider_paragraph("Chapter 1")
    assert not is_divider_paragraph("THE END")
    assert not is_divider_paragraph("Alice")


def test_long_text_is_NOT_divider():
    assert not is_divider_paragraph("This is a normal paragraph with words and ** asterisks **")


def test_strip_removes_only_divider_paragraphs():
    text = "Para A.\n\n* * * * *\n\nPara B.\n\n* * *\n\nPara C."
    out = strip_dividers(text)
    assert out == "Para A.\n\nPara B.\n\nPara C."


def test_strip_preserves_text_unchanged_when_no_dividers():
    text = "Para A.\n\nPara B.\n\nPara C."
    assert strip_dividers(text) == text


def test_strip_handles_leading_and_trailing_dividers():
    text = "* * *\n\nFirst para.\n\nLast para.\n\n* * *"
    assert strip_dividers(text) == "First para.\n\nLast para."


def test_strip_returns_empty_for_only_dividers():
    text = "* * *\n\n* * * * *\n\n* * *"
    assert strip_dividers(text) == ""
