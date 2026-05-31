#!/usr/bin/env python3
"""
Reformat hard-wrapped chapter_text so paragraph boundaries match the
modern_english_text format.

Origin: Some books (e.g. A Tale of Two Cities, book_id 41) were ingested
with paragraphs separated by single \\n instead of \\n\\n. This makes the
generate_modern_english.py paragraph-count validator (which splits on
\\n\\n) report Orig=1 vs Modern=N, even though Gemini correctly produced
N paragraphs by treating each single \\n as a boundary.

This script converts single-newline paragraph breaks to double-newline
form, and strips any leading title-prefix line that duplicates
chapters.chapter_title. It does NOT call any LLM — pure DB rewrite.

Usage:
    PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id 41 --dry-run
    PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id 41
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "database.db"


def reformat_chapter_text(text: str, title: str) -> str:
    """
    Strip a leading 'TITLE\\n' prefix if present, then convert any single
    \\n separators to \\n\\n. Existing \\n\\n+ runs are left untouched
    (already paragraph-separated).
    """
    prefix = f"{title}\n"
    if text.startswith(prefix):
        text = text[len(prefix):]
    # Replace any \n that is NOT adjacent to another \n with \n\n.
    text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)
    return text


def count_paragraphs(text: str) -> int:
    """Match the validator in generate_modern_english.py:395."""
    return len(text.strip().split("\n\n")) if text.strip() else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--column", choices=["chapter_text", "modern_english_text"],
                    default="chapter_text",
                    help="Which column to reformat (default: chapter_text).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show before/after paragraph counts; do not write to DB.")
    args = ap.parse_args()

    target_col = args.column
    other_col = "modern_english_text" if target_col == "chapter_text" else "chapter_text"

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    book = conn.execute("SELECT id, title, is_poetry FROM books WHERE id = ?",
                        (args.book_id,)).fetchone()
    if not book:
        print(f"ERROR: book_id {args.book_id} not found", file=sys.stderr)
        return 2
    if book["is_poetry"]:
        print(f"ERROR: book_id {args.book_id} ('{book['title']}') is flagged is_poetry=1. "
              "Refusing to reformat — single \\n is a verse-line break, not a paragraph "
              "boundary, and doubling them would explode the layout.", file=sys.stderr)
        return 3
    print(f"Book: {book['title']} (id {book['id']})")
    print(f"Reformatting column: {target_col}")

    rows = conn.execute(
        f"SELECT id, chapter_number, chapter_title, {target_col} AS target_text, "
        f"{other_col} AS other_text FROM chapters WHERE book_id = ? "
        "ORDER BY chapter_number",
        (args.book_id,),
    ).fetchall()

    changed = 0
    print(f"\n{'ch':>4} {'before_para':>12} {'after_para':>12} {'other_para':>12} {'match':>6}")
    print(f"{'-'*4} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")
    for r in rows:
        before = count_paragraphs(r["target_text"] or "")
        new_text = reformat_chapter_text(r["target_text"] or "", r["chapter_title"] or "")
        after = count_paragraphs(new_text)
        other_para = count_paragraphs(r["other_text"] or "")
        match = "OK" if abs(after - other_para) <= 2 else "DIFF"
        will_change = new_text != (r["target_text"] or "")
        if will_change:
            changed += 1
            if not args.dry_run:
                conn.execute(
                    f"UPDATE chapters SET {target_col} = ? WHERE id = ?",
                    (new_text, r["id"]),
                )
        marker = "*" if will_change else " "
        print(f"{r['chapter_number']:>4}{marker}{before:>11} {after:>12} {other_para:>12} {match:>6}")

    if args.dry_run:
        print(f"\nDRY RUN: would update {changed}/{len(rows)} chapters. No DB writes performed.")
    else:
        conn.commit()
        print(f"\nUpdated {changed}/{len(rows)} chapters.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
