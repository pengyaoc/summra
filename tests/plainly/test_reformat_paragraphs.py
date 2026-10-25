"""Tests for scripts/audits/reformat_paragraphs.py — pure transform logic."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.audits import reformat_paragraphs
from scripts.audits.reformat_paragraphs import reformat_chapter_text


def test_strips_leading_title_and_doubles_newlines():
    title = "The Wine-shop"
    body = "A large cask of wine.\nAll the people within reach."
    text = f"{title}\n{body}"
    out = reformat_chapter_text(text, title)
    assert out == "A large cask of wine.\n\nAll the people within reach."


def test_leaves_already_double_newlines_alone():
    title = "Ch"
    text = "Ch\nLine one.\n\nLine two."
    out = reformat_chapter_text(text, title)
    assert out == "Line one.\n\nLine two."


def test_no_title_prefix_means_no_strip():
    title = "Something Else"
    text = "Line one.\nLine two."
    out = reformat_chapter_text(text, title)
    assert out == "Line one.\n\nLine two."


def test_preserves_trailing_content_without_blank():
    title = "T"
    text = "T\na\nb\nc"
    out = reformat_chapter_text(text, title)
    assert out == "a\n\nb\n\nc"


def test_collapses_multiple_blank_lines_to_double():
    # Three consecutive newlines (blank line between) should stay as one separator.
    title = "T"
    text = "T\na\n\n\nb"
    out = reformat_chapter_text(text, title)
    # Existing \n\n\n is "already paragraph-separated" — leave alone (don't double again).
    assert out == "a\n\n\nb"


def test_empty_body_after_title_strip():
    out = reformat_chapter_text("Title\n", "Title")
    assert out == ""


def test_handles_title_with_special_regex_chars():
    title = "M. d'Artagnan?"
    text = f"{title}\nBody text."
    out = reformat_chapter_text(text, title)
    assert out == "Body text."


# ---------------------------------------------------------------------------
# --column flag tests (DB-level, end-to-end through main())
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
    # chapter_text: hard-wrapped + title prefix (needs reformat)
    # modern_english_text: also hard-wrapped + title prefix (needs reformat)
    conn.execute(
        "INSERT INTO chapters (id, book_id, chapter_number, chapter_title, "
        "chapter_text, modern_english_text) VALUES (?, ?, ?, ?, ?, ?)",
        (1, 1, 1, "Ch One",
         "Ch One\nOriginal para A.\nOriginal para B.",
         "Ch One\nModern para A.\nModern para B."),
    )
    conn.commit()
    conn.close()


def _run_main(db_path: Path, argv: list[str]) -> int:
    with patch.object(reformat_paragraphs, "DB_PATH", db_path), \
         patch.object(sys, "argv", ["reformat_paragraphs.py", *argv]):
        return reformat_paragraphs.main()


def test_default_column_updates_chapter_text_only(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)

    rc = _run_main(db, ["--book-id", "1"])
    assert rc == 0

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT chapter_text, modern_english_text FROM chapters WHERE id=1"
    ).fetchone()
    conn.close()
    # chapter_text reformatted: title stripped, single \n -> \n\n
    assert row[0] == "Original para A.\n\nOriginal para B."
    # modern_english_text untouched
    assert row[1] == "Ch One\nModern para A.\nModern para B."


def test_explicit_chapter_text_column_matches_default(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)

    rc = _run_main(db, ["--book-id", "1", "--column", "chapter_text"])
    assert rc == 0

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT chapter_text, modern_english_text FROM chapters WHERE id=1"
    ).fetchone()
    conn.close()
    assert row[0] == "Original para A.\n\nOriginal para B."
    assert row[1] == "Ch One\nModern para A.\nModern para B."


def test_column_modern_english_text_updates_modern_only(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)

    rc = _run_main(db, ["--book-id", "1", "--column", "modern_english_text"])
    assert rc == 0

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT chapter_text, modern_english_text FROM chapters WHERE id=1"
    ).fetchone()
    conn.close()
    # modern_english_text reformatted
    assert row[1] == "Modern para A.\n\nModern para B."
    # chapter_text untouched
    assert row[0] == "Ch One\nOriginal para A.\nOriginal para B."


def test_invalid_column_value_is_rejected(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)

    with pytest.raises(SystemExit) as excinfo:
        _run_main(db, ["--book-id", "1", "--column", "summary"])
    # argparse exits with code 2 on invalid choices
    assert excinfo.value.code == 2


def test_dry_run_does_not_write_modern_column(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)

    rc = _run_main(db, ["--book-id", "1", "--column", "modern_english_text", "--dry-run"])
    assert rc == 0

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT chapter_text, modern_english_text FROM chapters WHERE id=1"
    ).fetchone()
    conn.close()
    # Neither column should change in dry-run
    assert row[0] == "Ch One\nOriginal para A.\nOriginal para B."
    assert row[1] == "Ch One\nModern para A.\nModern para B."


@pytest.mark.parametrize("column", ["chapter_text", "modern_english_text"])
def test_idempotent_second_run_makes_zero_updates(tmp_path, capsys, column):
    db = tmp_path / "test.db"
    _build_db(db)

    rc1 = _run_main(db, ["--book-id", "1", "--column", column])
    assert rc1 == 0
    # Second run on already-reformatted text should result in 0 updates
    capsys.readouterr()  # clear
    rc2 = _run_main(db, ["--book-id", "1", "--column", column])
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "Updated 0/1 chapters." in out
