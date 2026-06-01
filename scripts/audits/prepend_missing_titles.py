#!/usr/bin/env python3
"""
Step 5a: For each chapter where the original's first paragraph is the chapter
title but the modern translation dropped it, prepend the body-cased title to
the modern text. Idempotent — refuses to act if modern already starts with the
title (case-insensitive).

Usage:
    PYTHONPATH=backend venv/bin/python scripts/audits/prepend_missing_titles.py --book-id 80 --dry-run
    PYTHONPATH=backend venv/bin/python scripts/audits/prepend_missing_titles.py --book-id 80
"""
import argparse
import sqlite3
import sys

DB_PATH = "data/database.db"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--book-id", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    db = sqlite3.connect(DB_PATH)
    rows = list(
        db.execute(
            "SELECT chapter_number, chapter_title, chapter_text, modern_english_text "
            "FROM chapters WHERE book_id=? ORDER BY chapter_number",
            (args.book_id,),
        )
    )

    fixed = 0
    for n, title, ot, mt in rows:
        if mt is None or not mt.strip():
            continue
        if not title:
            continue
        op_first = ot.split("\n\n")[0].strip() if ot else ""
        mp_first = mt.split("\n\n")[0].strip()

        # Heuristic: original's first paragraph IS the title (short and matches title)
        if not (
            title.lower() in op_first.lower()
            and len(op_first) < len(title) + 25
        ):
            continue
        # And modern's first paragraph is NOT the title
        if title.lower() in mp_first.lower() and len(mp_first) < len(title) + 25:
            continue

        body_title = op_first  # preserve original casing
        new_mt = f"{body_title}\n\n{mt}"
        print(f"  ch.{n}: prepend {body_title!r}")
        if not args.dry_run:
            db.execute(
                "UPDATE chapters SET modern_english_text=? WHERE book_id=? AND chapter_number=?",
                (new_mt, args.book_id, n),
            )
        fixed += 1

    if not args.dry_run:
        db.commit()
    print(f"Fixed {fixed} chapter(s) in book {args.book_id}{' (dry-run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
