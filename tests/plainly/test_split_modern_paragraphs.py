"""Tests for scripts/audits/split_modern_paragraphs.py — paragraph alignment tool."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.audits import split_modern_paragraphs as smp
from scripts.audits.split_modern_paragraphs import (
    apply_splits_and_merges,
    parse_splits,
    parse_merges,
)


# ---------------------------------------------------------------------------
# Pure transform: apply_splits_and_merges
# ---------------------------------------------------------------------------

def test_no_changes_returns_unmodified_text():
    text = "para one.\n\npara two.\n\npara three."
    assert apply_splits_and_merges(text, splits=[], merges=[]) == text


def test_single_split_in_middle_paragraph():
    text = "first.\n\nsecond half-A. second half-B.\n\nthird."
    # Paragraph 2 is "second half-A. second half-B." (29 chars).
    # Split at offset 15 → s[:15]="second half-A. ", s[15:]="second half-B."
    out = apply_splits_and_merges(text, splits=[(2, 15)], merges=[])
    assert out == "first.\n\nsecond half-A. \n\nsecond half-B.\n\nthird."


def test_multiple_splits_in_same_paragraph_applied_right_to_left():
    # Original paragraph 1: "AAA BBB CCC" (11 chars)
    # Splits at idx 1 char 4 ("AAA "|"BBB CCC") AND idx 1 char 8 ("AAA BBB "|"CCC")
    # Right-to-left ensures the char-8 split doesn't shift the char-4 split.
    text = "AAA BBB CCC"
    out = apply_splits_and_merges(text, splits=[(1, 4), (1, 8)], merges=[])
    assert out == "AAA \n\nBBB \n\nCCC"


def test_splits_across_multiple_paragraphs():
    text = "A1. A2.\n\nB1. B2."
    # Split paragraph 1 at char 4, and paragraph 2 at char 4
    out = apply_splits_and_merges(text, splits=[(1, 4), (2, 4)], merges=[])
    assert out == "A1. \n\nA2.\n\nB1. \n\nB2."


def test_single_merge_combines_two_paragraphs():
    text = "first.\n\nsecond.\n\nthird."
    # merge=1 joins paragraph 1 ("first.") and paragraph 2 ("second.")
    out = apply_splits_and_merges(text, splits=[], merges=[1])
    assert out == "first. second.\n\nthird."


def test_multiple_merges_applied_right_to_left():
    text = "A.\n\nB.\n\nC.\n\nD."
    out = apply_splits_and_merges(text, splits=[], merges=[1, 2, 3])
    assert out == "A. B. C. D."


def test_splits_then_merges_combined():
    # First split paragraph 1 ("AAA BBB") at char 4, giving ["AAA ", "BBB", "C."]
    # Then merge between 2 and 3, giving ["AAA ", "BBB C."]
    text = "AAA BBB\n\nC."
    out = apply_splits_and_merges(text, splits=[(1, 4)], merges=[2])
    assert out == "AAA \n\nBBB C."


def test_split_out_of_range_paragraph_index_raises():
    text = "only.\n\none."
    with pytest.raises(ValueError, match="paragraph"):
        apply_splits_and_merges(text, splits=[(5, 0)], merges=[])


def test_split_char_offset_beyond_paragraph_length_raises():
    text = "short.\n\nstill short."
    with pytest.raises(ValueError, match="offset"):
        apply_splits_and_merges(text, splits=[(1, 100)], merges=[])


def test_merge_out_of_range_index_raises():
    text = "a.\n\nb."
    with pytest.raises(ValueError, match="merge"):
        apply_splits_and_merges(text, splits=[], merges=[5])


# ---------------------------------------------------------------------------
# Argument parsers
# ---------------------------------------------------------------------------

def test_parse_splits_single():
    assert parse_splits("5:200") == [(5, 200)]


def test_parse_splits_multiple():
    assert parse_splits("5:200,7:100,12:50") == [(5, 200), (7, 100), (12, 50)]


def test_parse_splits_empty():
    assert parse_splits("") == []
    assert parse_splits(None) == []


def test_parse_splits_invalid_format():
    with pytest.raises(ValueError):
        parse_splits("5")  # missing colon
    with pytest.raises(ValueError):
        parse_splits("a:b")  # non-numeric


def test_parse_merges():
    assert parse_merges("1,3,5") == [1, 3, 5]
    assert parse_merges("") == []
    assert parse_merges(None) == []


def test_parse_merges_invalid():
    with pytest.raises(ValueError):
        parse_merges("a,b")


# ---------------------------------------------------------------------------
# DB integration through main()
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    is_poetry INTEGER DEFAULT 0
);
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    chapter_title TEXT,
    chapter_text TEXT,
    modern_english_text TEXT
);
"""


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO books (id, title, is_poetry) VALUES (1, 'Test Book', 0)")
    conn.execute(
        "INSERT INTO chapters (id, book_id, chapter_number, chapter_title, "
        "chapter_text, modern_english_text) VALUES (?, ?, ?, ?, ?, ?)",
        (1, 1, 1, "Ch One",
         "Para one orig.\n\nPara two orig.\n\nPara three orig.",
         "Para one modern. Para two modern.\n\nPara three modern."),
    )
    conn.commit()
    conn.close()


def _run_main(db_path: Path, argv: list[str]) -> int:
    with patch.object(smp, "DB_PATH", db_path), \
         patch.object(sys, "argv", ["split_modern_paragraphs.py", *argv]):
        return smp.main()


def test_inspect_does_not_modify_db(tmp_path, capsys):
    db = tmp_path / "test.db"
    _build_db(db)
    rc = _run_main(db, ["--book-id", "1", "--chapter-number", "1", "--inspect"])
    assert rc == 0
    out = capsys.readouterr().out
    # Should show paragraphs from both sides numbered
    assert "[O1]" in out
    assert "[M1]" in out

    conn = sqlite3.connect(db)
    mt = conn.execute("SELECT modern_english_text FROM chapters WHERE id=1").fetchone()[0]
    conn.close()
    assert mt == "Para one modern. Para two modern.\n\nPara three modern."


def test_split_modifies_modern_text(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    # Modern paragraph 1 is "Para one modern. Para two modern." (33 chars)
    # Split at char 16 (right after "Para one modern.") → produces a leading-space para 2.
    rc = _run_main(db, ["--book-id", "1", "--chapter-number", "1", "--split", "1:16"])
    assert rc == 0

    conn = sqlite3.connect(db)
    mt = conn.execute("SELECT modern_english_text FROM chapters WHERE id=1").fetchone()[0]
    conn.close()
    assert mt == "Para one modern.\n\n Para two modern.\n\nPara three modern."


def test_dry_run_does_not_persist(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    rc = _run_main(db, ["--book-id", "1", "--chapter-number", "1",
                        "--split", "1:16", "--dry-run"])
    assert rc == 0
    conn = sqlite3.connect(db)
    mt = conn.execute("SELECT modern_english_text FROM chapters WHERE id=1").fetchone()[0]
    conn.close()
    assert mt == "Para one modern. Para two modern.\n\nPara three modern."  # unchanged


def test_missing_book_returns_error_code(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    rc = _run_main(db, ["--book-id", "999", "--chapter-number", "1", "--inspect"])
    assert rc != 0


def test_missing_chapter_returns_error_code(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    rc = _run_main(db, ["--book-id", "1", "--chapter-number", "99", "--inspect"])
    assert rc != 0


def test_invalid_split_offset_aborts_and_does_not_modify_db(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    # Modern paragraph 1 is "Para one modern. Para two modern." (33 chars).
    # Split at char 999 is well beyond, should fail validation cleanly.
    rc = _run_main(db, ["--book-id", "1", "--chapter-number", "1", "--split", "1:999"])
    assert rc != 0

    conn = sqlite3.connect(db)
    mt = conn.execute("SELECT modern_english_text FROM chapters WHERE id=1").fetchone()[0]
    conn.close()
    # DB unchanged
    assert mt == "Para one modern. Para two modern.\n\nPara three modern."
