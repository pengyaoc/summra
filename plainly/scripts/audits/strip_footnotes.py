#!/usr/bin/env python3
"""
Strip editor footnotes from chapter_text: inline markers like `[42]` and a
trailing block that starts with a paragraph reading exactly `Footnotes`.

Background: Project Gutenberg editions with endnotes (e.g. pg6130, Pope's
Iliad) keep `[n]` markers in the text and append every note after the last
chapter, so the last chapter carries hundreds of note paragraphs. Editor
notes are not the author's text (workflow lesson #9): Plain English skips
them, so the original must too, or paragraph counts never line up.

Idempotent. No LLM calls. `[Illustration: ]` and other non-numeric
brackets are left alone (see strip_illustration_captions.py).

Usage:
    PYTHONPATH=plainly venv/bin/python plainly/scripts/audits/strip_footnotes.py --book-id 66 --dry-run
    PYTHONPATH=plainly venv/bin/python plainly/scripts/audits/strip_footnotes.py --book-id 66
"""
import argparse
import re
import sys

from plainly import config
from plainly.scripts.lib.db import get_connection

DB_PATH = config.DATABASE_PATH

SEP = "\n\n"
_MARKER = re.compile(r"[ \t]*\[\d+\]")


def strip_footnotes(text: str) -> tuple[str, int, int]:
    """Return (new_text, n_markers_removed, n_paragraphs_dropped)."""
    if not text:
        return text, 0, 0
    paras = text.split(SEP)
    dropped = 0
    for i, p in enumerate(paras):
        if p.strip() == "Footnotes":
            dropped = len(paras) - i
            paras = paras[:i]
            break
    text, markers = _MARKER.subn("", SEP.join(paras))
    return text, markers, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection(DB_PATH)
    rows = conn.execute(
        "SELECT id, chapter_number, chapter_text FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (args.book_id,),
    ).fetchall()
    if not rows:
        print(f"ERROR: no chapters for book_id {args.book_id}", file=sys.stderr)
        return 2

    changed = 0
    for r in rows:
        new, markers, dropped = strip_footnotes(r["chapter_text"])
        if new == r["chapter_text"]:
            continue
        changed += 1
        print(f"ch{r['chapter_number']}: {markers} markers, {dropped} trailing note paragraphs")
        if not args.dry_run:
            conn.execute("UPDATE chapters SET chapter_text = ? WHERE id = ?", (new, r["id"]))
    if not args.dry_run:
        conn.commit()
    print(f"{'Would change' if args.dry_run else 'Changed'} {changed} chapters")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
