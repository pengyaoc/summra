#!/usr/bin/env python3
"""
Plain English written by an agent (not the Gemini generator), one
paragraph per original paragraph, gated before it reaches the database.
Process doc: docs/agent_plain_english_workflow.md.

Paragraphs are the blank-line blocks of chapter_text (prose paragraphs, or
verse passages from scripts/content/segment_verse_passages.py). Workflow:

    export  — write <dir>/in/ch<N>/<start>.md: one prompt per chunk of about
              --max-chars, built from the Gemini generator's own prompt
              (ModernEnglishGenerator.build_single_chapter_prompt) with
              numbered paragraphs and a JSON output section.
    check   — validate <dir>/out/ch<N>/*.json against the gate below.
    review  — write <dir>/review/ch<N>.md: original and Plain English paired
              by paragraph, for the Sonnet quality check.
    apply   — write modern_english_text for chapters that pass, joined by
              blank lines so paragraph i pairs with original paragraph i.

Rewriter output: any number of JSON files per chapter, each
{"start": <1-based paragraph number>, "paragraphs": ["...", ...]}.

Gate (any failure blocks apply for that chapter): exact paragraph count;
each paragraph one line, ending at a sentence terminator (unless kept
verbatim, e.g. a heading), per-paragraph
length ratio within [0.5, 1.3] of the original; chapter ratio within
[0.50, 1.10]; no summary language ("this passage", "the poet", ...) unless
the chapter's original uses the same phrase (commentary such as a preface).

Usage:
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py export --book-id 66 --dir <dir> [--chapter N]
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py check --book-id 66 --dir <dir> [--chapter N]
    PYTHONPATH=backend:. venv/bin/python scripts/content/passage_rewrite.py apply --book-id 66 --dir <dir> [--dry-run]
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
_TERMINATOR = re.compile(r"[.?!][’”'\")\]_]*$")
_SUMMARY = re.compile(r"\b(this passage|this section|the poet|the narrator|summar\w*)\b", re.IGNORECASE)


def check_passages(originals, rewrites):
    """Return a list of gate failures; empty means the chapter passes."""
    if len(originals) != len(rewrites):
        return [f"passage count: {len(originals)} verse vs {len(rewrites)} plain"]
    errors = []
    chapter_text = " ".join(originals).lower()
    for i, (verse, plain) in enumerate(zip(originals, rewrites), start=1):
        plain = plain or ""
        ratio = len(plain) / max(1, len(verse))
        if not plain.strip():
            errors.append(f"P{i}: empty")
            continue
        if "\n" in plain.strip():
            errors.append(f"P{i}: line break inside paragraph")
        if not _TERMINATOR.search(plain.strip()) and plain.strip() != verse.strip():
            errors.append(f"P{i}: does not end at a sentence terminator: …{plain.strip()[-40:]!r}")
        if not PASSAGE_RATIO[0] <= ratio <= PASSAGE_RATIO[1]:
            errors.append(f"P{i}: length ratio {ratio:.2f} outside {PASSAGE_RATIO}")
        summary = _SUMMARY.search(plain)
        if summary and summary.group(0).lower() not in chapter_text:
            errors.append(f"P{i}: summary language {summary.group(0)!r}")
    total = sum(len(p or "") for p in rewrites) / max(1, sum(len(v) for v in originals))
    if not CHAPTER_RATIO[0] <= total <= CHAPTER_RATIO[1]:
        errors.append(f"chapter length ratio {total:.2f} outside {CHAPTER_RATIO}")
    return errors


def chunk_paragraphs(paragraphs, max_chars):
    """Split into consecutive chunks of at most max_chars (a longer single
    paragraph stands alone). Returns [(1-based start, [paragraphs])]."""
    chunks, current, size = [], [], 0
    for i, p in enumerate(paragraphs, start=1):
        if current and size + len(p) > max_chars:
            chunks.append((i - len(current), current))
            current, size = [], 0
        current.append(p)
        size += len(p)
    if current:
        chunks.append((len(paragraphs) - len(current) + 1, current))
    return chunks


_AGENT_OUTPUT = """

AGENT OUTPUT FORMAT (replaces the output requirements above):
- The original text above is {n} paragraphs, numbered [P{start}] to [P{end}]. The numbers are labels only; do not copy them.
- Write one plain English paragraph per numbered paragraph, in order: exactly {n}.
- Each paragraph is a single line (no line breaks inside it) and ends with a sentence terminator (. ! ? or a closing quote after one).
- A heading paragraph (a book title, ARGUMENT., a caption-like title line) stays verbatim.
- Write the result with the Write tool to {out_path} as JSON:
  {{"start": {start}, "paragraphs": ["...", "..."]}}
"""


def build_chunk_prompt(book_title, book_author, chapter_title, start, paragraphs, out_path):
    """The Gemini generator's prompt for these paragraphs, plus agent output rules."""
    from scripts.content.generate_modern_english import ModernEnglishGenerator
    numbered = "\n\n".join(f"[P{start + i}] {p}" for i, p in enumerate(paragraphs))
    prompt = ModernEnglishGenerator.build_single_chapter_prompt(book_title, book_author, chapter_title, numbered)
    return prompt + _AGENT_OUTPUT.format(n=len(paragraphs), start=start,
                                         end=start + len(paragraphs) - 1, out_path=out_path)


def format_pairs(originals, rewrites):
    """Original and Plain English paired by position, for a reviewer."""
    blocks = []
    for i, verse in enumerate(originals, start=1):
        plain = rewrites[i - 1] if i <= len(rewrites) else None
        ratio = f"{len(plain) / max(1, len(verse)):.2f}" if plain else "-"
        blocks.append(f"### P{i} (ratio {ratio})\nORIGINAL: {verse}\nPLAIN: {plain or '(missing)'}\n")
    return "\n".join(blocks)


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
    book = conn.execute("SELECT title, author FROM books WHERE id = ?", (args.book_id,)).fetchone()
    for r in _chapters(conn, args.book_id, args.chapter):
        n = r["chapter_number"]
        out = Path(args.dir) / "in" / f"ch{n}"
        out.mkdir(parents=True, exist_ok=True)
        passages = _passages(r["chapter_text"])
        chunks = chunk_paragraphs(passages, args.max_chars)
        for start, paragraphs in chunks:
            result = (Path(args.dir) / "out" / f"ch{n}" / f"{start:03d}.json").resolve()
            (out / f"{start:03d}.md").write_text(build_chunk_prompt(
                book["title"], book["author"], r["chapter_title"], start, paragraphs, result))
        print(f"ch{n}: {len(passages)} paragraphs in {len(chunks)} chunks")
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


def review(conn, args):
    out = Path(args.dir) / "review"
    out.mkdir(parents=True, exist_ok=True)
    for r in _chapters(conn, args.book_id, args.chapter):
        n = r["chapter_number"]
        rewrites, _ = _load_rewrites(Path(args.dir) / "out" / f"ch{n}")
        (out / f"ch{n}.md").write_text(format_pairs(_passages(r["chapter_text"]), rewrites))
        print(f"ch{n}: {out / f'ch{n}.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["export", "check", "review", "apply"])
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--chapter", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chars", type=int, default=12000, help="export: chunk size")
    args = ap.parse_args()
    conn = get_connection(DB_PATH)
    try:
        if args.command == "export":
            return export(conn, args)
        if args.command == "review":
            return review(conn, args)
        return check(conn, args, write=args.command == "apply")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
