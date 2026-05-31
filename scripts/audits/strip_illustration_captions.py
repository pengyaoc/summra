#!/usr/bin/env python3
"""
Strip illustration captions and Gutenberg front-/back-matter labels from
chapter_text so paragraph counts align with what Gemini produces.

Background: many Project Gutenberg books include illustration captions as
their own paragraphs in the source text. Gemini correctly omits these from
its plain-English translation (they're not prose), but the result is that
modern_english_text has fewer paragraphs than chapter_text. Stripping
captions from chapter_text aligns the two.

Caption-paragraph detection rules (all must match):
  1. Length < 100 chars
  2. Last character is NOT a terminal punctuation mark (. ! ? " ' ” ’)
  3. First character is NOT an opening quote (" “ ' ‘) — protects dialogue
  4. First character is NOT a lowercase letter — protects sentence fragments
     that were truncated by accident (real dialogue/prose almost never
     begins with lowercase after a paragraph break)
  5. Not entirely uppercase if it's also short — covers `LITTLE WOMEN.` style
     headers that should be preserved as titles (those usually end with `.`
     anyway, caught by rule 2)

Additionally, paragraphs matching known front-matter labels are stripped:
  - 'Contents', 'Preface', 'List of Illustrations', 'Tail-piece'
  - 'Tail-piece to Contents', 'Tail-piece to Illustrations'
  - 'Part First', 'Part Second', 'Part First.', 'Part Second.'

Trailing transcriber/publisher notes (anchored to end of chapter) matching:
  - paragraphs starting with 'On page N' (transcription corrections)
  - 'Transcriber's Note', 'Transcriber's Notes'
  - 'Project Gutenberg', 'TRANSCRIBER'
are also stripped.

Idempotent. No LLM calls. Safe to run before generate_modern_english.py.

Usage:
    PYTHONPATH=backend venv/bin/python scripts/audits/strip_illustration_captions.py --book-id 36 --dry-run
    PYTHONPATH=backend venv/bin/python scripts/audits/strip_illustration_captions.py --book-id 36
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "database.db"

SEP = "\n\n"

# Punctuation that signals "this is a complete sentence/utterance"
_TERMINAL_PUNCT = set('.!?":\'”’)')

# Opening quote marks — never strip dialogue
_OPENING_QUOTES = set('"“‘\'')

# Known front-matter labels that should always be stripped (case-insensitive
# match against the stripped paragraph text). These are not normal prose.
_FRONT_MATTER_LABELS = {
    "contents",
    "preface",
    "list of illustrations",
    "tail-piece",
    "tail-piece to contents",
    "tail-piece to illustrations",
    "part first",
    "part second",
    "part first.",
    "part second.",
    "illustrations",
    "illustrations.",
}

# Trailing trash signatures — only stripped if they appear in the tail of
# the chapter (after we've found prose). Anchored to chapter-end to avoid
# false positives in body text.
_TRAILING_NOISE_PREFIXES = (
    "on page ",
    "transcriber's note",
    "transcriber's notes",
    "project gutenberg",
    "transcriber",
    "this is a list of",
    "the final page is",
    "after the novel",
    "most of the novels",
    "we included l",  # truncated, but pattern from Little Women ch.47
)


def looks_like_caption(p: str) -> bool:
    """True if paragraph looks like an illustration caption (not prose)."""
    s = p.strip()
    if not s:
        return False

    # Rule: known front-matter label
    if s.lower().rstrip(".,;:") in _FRONT_MATTER_LABELS:
        return True
    if s.lower() in _FRONT_MATTER_LABELS:
        return True

    # Captions are short
    if len(s) >= 100:
        return False

    # Real dialogue starts with an opening quote — never strip
    if s[0] in _OPENING_QUOTES:
        return False

    # Real prose paragraphs typically end with terminal punctuation
    last_char = s[-1]
    if last_char in _TERMINAL_PUNCT:
        return False

    # A truly all-caps short paragraph like 'CHAPTER I' or 'LITTLE WOMEN'
    # could be a title — but those usually end in '.' so will already have
    # been returned False above. If it slipped past, treat as caption.
    return True


def is_trailing_noise(p: str) -> bool:
    """True if paragraph is a transcriber/publisher note (trailing trash)."""
    s = p.strip().lower()
    if not s:
        return False
    return any(s.startswith(prefix) for prefix in _TRAILING_NOISE_PREFIXES)


def strip_captions(text: str) -> tuple[str, int, int]:
    """Remove caption-like paragraphs and trailing transcriber notes.

    Returns (new_text, n_captions_removed, n_trailing_removed).
    """
    if not text:
        return text, 0, 0
    paras = text.split(SEP)

    # Strip captions from anywhere
    kept = []
    n_captions = 0
    for p in paras:
        if looks_like_caption(p):
            n_captions += 1
            continue
        kept.append(p)

    # Strip trailing noise: walk backward from end, drop paragraphs matching
    # noise patterns until we hit real prose
    n_trailing = 0
    while kept and is_trailing_noise(kept[-1]):
        kept.pop()
        n_trailing += 1

    return SEP.join(kept), n_captions, n_trailing


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument(
        "--column",
        choices=["chapter_text", "modern_english_text", "both"],
        default="chapter_text",
        help="Which column(s) to strip (default: chapter_text only — modern "
             "should already be clean since Gemini ignores captions).",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, chapter_number, chapter_text, modern_english_text "
        "FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (args.book_id,),
    ).fetchall()
    if not rows:
        print(f"ERROR: no chapters for book_id {args.book_id}", file=sys.stderr)
        return 2

    cols = (["chapter_text", "modern_english_text"]
            if args.column == "both" else [args.column])
    print(f"Stripping illustration captions from book_id {args.book_id}, "
          f"column(s): {cols}")
    print(f"{'ch':>4}  " + "  ".join(
        f"{c+' before→after (caps/trail)':>34}" for c in cols))
    print(f"{'-'*4}  " + "  ".join("-" * 34 for _ in cols))

    changed_rows = 0
    for r in rows:
        deltas = []
        updates = {}
        for col in cols:
            text = r[col] or ""
            before = len(text.split(SEP)) if text.strip() else 0
            new_text, n_caps, n_trail = strip_captions(text)
            after = len(new_text.split(SEP)) if new_text.strip() else 0
            deltas.append(f"{before:>4}→{after:<4} ({n_caps:>2}/{n_trail:>2})")
            if (n_caps + n_trail) > 0 and new_text != text:
                updates[col] = new_text
        if updates:
            changed_rows += 1
            if not args.dry_run:
                for col, val in updates.items():
                    conn.execute(
                        f"UPDATE chapters SET {col} = ? WHERE id = ?",
                        (val, r["id"]),
                    )
        marker = "*" if updates else " "
        print(f"{r['chapter_number']:>3}{marker}  " + "  ".join(
            f"{d:>34}" for d in deltas))

    if args.dry_run:
        print(f"\nDRY RUN: would update {changed_rows}/{len(rows)} rows.")
    else:
        conn.commit()
        print(f"\nUpdated {changed_rows}/{len(rows)} rows.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
