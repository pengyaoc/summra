#!/usr/bin/env python3
"""
Group verse lines into passages separated by blank lines, so a poem's
original text pairs one passage with one Plain English paragraph.

Background: Paradise Lost (pg26) has no verse-paragraph breaks in its
source, so each Book is one block of 650-1,190 lines. The reader treats
each blank-line block of a poetry book as one unit; without passages,
nothing aligns.

A passage ends at a line that closes a sentence, as near `target` lines
as possible within [min_lines, max_lines]. Fallbacks, in order: a line
ending in ';' or ':' within range; the next sentence end up to
`hard_max` lines; a hard break at `hard_max`. A tail shorter than
`min_lines` merges into the previous passage if that stays <= hard_max.

Idempotent (existing blank lines are ignored and re-derived). No LLM calls.

Usage:
    PYTHONPATH=backend venv/bin/python scripts/content/segment_verse_passages.py --book-id 102 --dry-run
    PYTHONPATH=backend venv/bin/python scripts/content/segment_verse_passages.py --book-id 102
"""
import argparse
import re
import sys

from backend import config
from scripts.lib.db import get_connection

DB_PATH = config.DATABASE_PATH

_SENTENCE_END = re.compile(r"[.?!][’”'\")\]]*\s*$")
_CLAUSE_END = re.compile(r"[;:][’”'\")\]]*\s*$")


def _break_after(lines, start, target, min_lines, max_lines, hard_max):
    """Return the passage length for the passage starting at `start`."""
    remaining = len(lines) - start

    def in_range(pattern):
        return [n for n in range(min_lines, min(max_lines, remaining) + 1)
                if pattern.search(lines[start + n - 1])]

    for pattern in (_SENTENCE_END, _CLAUSE_END):
        candidates = in_range(pattern)
        if candidates:
            return min(candidates, key=lambda n: (abs(n - target), n))
    for n in range(max_lines + 1, min(hard_max, remaining) + 1):
        if _SENTENCE_END.search(lines[start + n - 1]):
            return n
    return min(hard_max, remaining)


def segment_verse(text: str, target: int = 20, min_lines: int = 12,
                  max_lines: int = 30, hard_max: int = 45) -> str:
    lines = [line.rstrip() for line in (text or "").split("\n") if line.strip()]
    passages = []
    start = 0
    while start < len(lines):
        n = _break_after(lines, start, target, min_lines, max_lines, hard_max)
        passages.append(lines[start:start + n])
        start += n
    if (len(passages) > 1 and len(passages[-1]) < min_lines
            and len(passages[-2]) + len(passages[-1]) <= hard_max):
        passages[-2].extend(passages.pop())
    return "\n\n".join("\n".join(p) for p in passages)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--target", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection(DB_PATH)
    book = conn.execute("SELECT is_poetry FROM books WHERE id = ?", (args.book_id,)).fetchone()
    if not book or not book["is_poetry"]:
        print(f"ERROR: book {args.book_id} is missing or not flagged is_poetry", file=sys.stderr)
        return 2
    rows = conn.execute(
        "SELECT id, chapter_number, chapter_text FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (args.book_id,),
    ).fetchall()
    print(f"{'ch':>4} {'lines':>6} {'passages':>9} {'min':>4} {'max':>4} {'non-sentence ends':>18}")
    for r in rows:
        new_text = segment_verse(r["chapter_text"], target=args.target)
        passages = [p.split("\n") for p in new_text.split("\n\n")]
        sizes = [len(p) for p in passages]
        soft = sum(1 for p in passages if not _SENTENCE_END.search(p[-1]))
        print(f"{r['chapter_number']:>4} {sum(sizes):>6} {len(sizes):>9} {min(sizes):>4} {max(sizes):>4} {soft:>18}")
        if not args.dry_run and new_text != r["chapter_text"]:
            conn.execute("UPDATE chapters SET chapter_text = ? WHERE id = ?", (new_text, r["id"]))
    if args.dry_run:
        print("\nDRY RUN: no changes written.")
    else:
        conn.commit()
        print("\nUpdated chapter_text.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
