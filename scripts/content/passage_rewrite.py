#!/usr/bin/env python3
"""
Plain English for verse books, one prose paragraph per verse passage,
written by an agent (not the Gemini generator) and gated before it
reaches the database.

Passages come from scripts/content/segment_verse_passages.py (blank-line
blocks in chapter_text). Workflow:

    export  — write <dir>/in/ch<N>.md: numbered passages for the rewriter.
    check   — validate <dir>/out/ch<N>/*.json against the gate below.
    apply   — write modern_english_text for chapters that pass, joined by
              blank lines so paragraph i pairs with passage i.

Rewriter output: any number of JSON files per chapter, each
{"start": <1-based passage number>, "paragraphs": ["...", ...]}.

Gate (any failure blocks apply for that chapter): exact passage count;
each paragraph one line, ending at a sentence terminator, per-passage
length ratio within [0.5, 1.3] of the verse; chapter ratio within
[0.50, 1.10]; no summary language ("this passage", "the poet", ...).

Usage:
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py export --book-id 102 --dir <dir>
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py check --book-id 102 --dir <dir> [--chapter N]
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id 102 --dir <dir> [--dry-run]
"""
import argparse
import json
import re
import sys
from pathlib import Path

from backend import config
from scripts.lib.db import get_connection

DB_PATH = config.DATABASE_PATH

PASSAGE_RATIO = (0.5, 1.3)
CHAPTER_RATIO = (0.50, 1.10)
_TERMINATOR = re.compile(r"[.?!][’”'\")\]]*$")
_SUMMARY = re.compile(r"\b(this passage|this section|the poet|the narrator|summar\w*)\b", re.IGNORECASE)


def check_passages(originals, rewrites):
    """Return a list of gate failures; empty means the chapter passes."""
    if len(originals) != len(rewrites):
        return [f"passage count: {len(originals)} verse vs {len(rewrites)} plain"]
    errors = []
    for i, (verse, plain) in enumerate(zip(originals, rewrites), start=1):
        plain = plain or ""
        ratio = len(plain) / max(1, len(verse))
        if not plain.strip():
            errors.append(f"P{i}: empty")
            continue
        if "\n" in plain.strip():
            errors.append(f"P{i}: line break inside paragraph")
        if not _TERMINATOR.search(plain.strip()):
            errors.append(f"P{i}: does not end at a sentence terminator: …{plain.strip()[-40:]!r}")
        if not PASSAGE_RATIO[0] <= ratio <= PASSAGE_RATIO[1]:
            errors.append(f"P{i}: length ratio {ratio:.2f} outside {PASSAGE_RATIO}")
        if _SUMMARY.search(plain):
            errors.append(f"P{i}: summary language {_SUMMARY.search(plain).group(0)!r}")
    total = sum(len(p or "") for p in rewrites) / max(1, sum(len(v) for v in originals))
    if not CHAPTER_RATIO[0] <= total <= CHAPTER_RATIO[1]:
        errors.append(f"chapter length ratio {total:.2f} outside {CHAPTER_RATIO}")
    return errors


def _passages(text):
    return [p for p in (text or "").split("\n\n") if p.strip()]


def _load_rewrites(chapter_dir: Path):
    parts = []
    for path in sorted(chapter_dir.glob("*.json")):
        data = json.loads(path.read_text())
        parts.append((data["start"], data["paragraphs"], path.name))
    parts.sort()
    rewrites, errors = [], []
    for start, paragraphs, name in parts:
        if start != len(rewrites) + 1:
            errors.append(f"{name}: starts at P{start}, expected P{len(rewrites) + 1}")
        rewrites.extend(p.strip() for p in paragraphs)
    return rewrites, errors


def _chapters(conn, book_id, only=None):
    rows = conn.execute(
        "SELECT id, chapter_number, chapter_title, chapter_text FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (book_id,),
    ).fetchall()
    return [r for r in rows if only is None or r["chapter_number"] == only]


def export(conn, args):
    out = Path(args.dir) / "in"
    out.mkdir(parents=True, exist_ok=True)
    for r in _chapters(conn, args.book_id, args.chapter):
        passages = _passages(r["chapter_text"])
        body = "\n\n".join(f"### P{i}\n{p}" for i, p in enumerate(passages, start=1))
        (out / f"ch{r['chapter_number']}.md").write_text(
            f"# {r['chapter_title']} — {len(passages)} passages\n\n{body}\n")
        print(f"ch{r['chapter_number']}: {len(passages)} passages")
    return 0


def check(conn, args, write=False):
    failed = 0
    for r in _chapters(conn, args.book_id, args.chapter):
        n = r["chapter_number"]
        originals = _passages(r["chapter_text"])
        rewrites, errors = _load_rewrites(Path(args.dir) / "out" / f"ch{n}")
        errors += check_passages(originals, rewrites)
        if errors:
            failed += 1
            print(f"ch{n}: FAIL ({len(errors)})")
            for e in errors[:40]:
                print(f"  {e}")
            continue
        ratio = sum(map(len, rewrites)) / sum(map(len, originals))
        print(f"ch{n}: PASS {len(rewrites)} passages, ratio {ratio:.2f}")
        if write and not args.dry_run:
            conn.execute("UPDATE chapters SET modern_english_text = ? WHERE id = ?",
                         ("\n\n".join(rewrites), r["id"]))
    if write and not args.dry_run:
        conn.commit()
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["export", "check", "apply"])
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--chapter", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = get_connection(DB_PATH)
    try:
        if args.command == "export":
            return export(conn, args)
        return check(conn, args, write=args.command == "apply")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
