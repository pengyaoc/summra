#!/usr/bin/env python3
"""
Strip decorative section-divider paragraphs (e.g. '* * * * *') from
chapter_text and modern_english_text so paragraph counts align.

Background: some Gutenberg books use rows of asterisks, dashes, or dots
as scene-break markers (Carroll's Alice does this 6 times in ch.1).
Gemini correctly ignores these when translating, so the modern text
ends up with fewer paragraphs than the (un-stripped) original. Stripping
the dividers from chapter_text aligns the counts without losing content.

Idempotent. No LLM calls.

Usage:
    PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id 1 --dry-run
    PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id 1
"""
import argparse
import re
import sys

from backend import config
from scripts.lib.db import get_connection

DB_PATH = config.DATABASE_PATH

SEP = "\n\n"

# A paragraph is a "divider" when it's entirely whitespace plus repeated
# decorative chars (asterisks, dashes, dots, ellipses, bullets).
_DIVIDER_CHARS = set("*-.…•·~_=")
_DIVIDER_RE = re.compile(r"^[\s\*\-\.…•·~_=]+$")


def is_divider_paragraph(p: str) -> bool:
    """True if the paragraph is purely whitespace + decorative chars."""
    s = p.strip()
    if not s:
        return False  # empty/whitespace handled elsewhere
    # Must match the divider regex AND contain at least one decorative char
    if not _DIVIDER_RE.match(s):
        return False
    return any(ch in _DIVIDER_CHARS for ch in s)


def strip_dividers(text: str) -> str:
    """Remove paragraphs that are entirely decorative dividers."""
    if not text:
        return text
    paras = text.split(SEP)
    kept = [p for p in paras if not is_divider_paragraph(p)]
    return SEP.join(kept)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--column", choices=["chapter_text", "modern_english_text", "both"],
                    default="both",
                    help="Which column(s) to strip (default: both).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = get_connection(DB_PATH)
    rows = conn.execute(
        "SELECT id, chapter_number, chapter_text, modern_english_text "
        "FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (args.book_id,),
    ).fetchall()
    if not rows:
        print(f"ERROR: no chapters for book_id {args.book_id}", file=sys.stderr)
        return 2

    cols = ["chapter_text", "modern_english_text"] if args.column == "both" else [args.column]
    print(f"Stripping decorative dividers from book_id {args.book_id}, column(s): {cols}")
    print(f"{'ch':>4}  " + "  ".join(f"{c:>22}" for c in cols))
    print(f"{'-'*4}  " + "  ".join("-" * 22 for _ in cols))

    changed_rows = 0
    for r in rows:
        deltas = []
        updates = {}
        for col in cols:
            text = r[col] or ""
            before = len(text.split(SEP)) if text.strip() else 0
            new_text = strip_dividers(text)
            after = len(new_text.split(SEP)) if new_text.strip() else 0
            removed = before - after
            deltas.append(f"{before:>3}→{after:<3} (-{removed:>2})")
            if removed > 0 and new_text != text:
                updates[col] = new_text
        if updates:
            changed_rows += 1
            if not args.dry_run:
                for col, val in updates.items():
                    conn.execute(f"UPDATE chapters SET {col} = ? WHERE id = ?",
                                 (val, r["id"]))
        marker = "*" if updates else " "
        print(f"{r['chapter_number']:>3}{marker}  " + "  ".join(f"{d:>22}" for d in deltas))

    if args.dry_run:
        print(f"\nDRY RUN: would update {changed_rows}/{len(rows)} rows.")
    else:
        conn.commit()
        print(f"\nUpdated {changed_rows}/{len(rows)} rows.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
