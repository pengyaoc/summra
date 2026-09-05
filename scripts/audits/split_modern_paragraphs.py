#!/usr/bin/env python3
"""
Manually align modern_english_text paragraphs against chapter_text.

Use --inspect to see both versions side-by-side with paragraph indices.
Then use --split / --merge to add or remove paragraph breaks in the
modern text until counts align with the original.

Splits are specified as "paragraph_index:char_offset" (1-indexed).
The split inserts a paragraph break at that offset within that paragraph.
Multiple splits per call are applied right-to-left within each paragraph
so offsets don't shift each other.

Merges are specified as comma-separated paragraph indices to merge with
the FOLLOWING paragraph (so merge=1 joins paragraphs 1 and 2 into one).
Multiple merges are applied right-to-left.

Splits are applied BEFORE merges. Indices in --merge refer to paragraph
positions AFTER splits have been applied.

Usage:
    PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id 60 --chapter-number 12 --inspect
    PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id 60 --chapter-number 12 --split "5:200,7:100" --dry-run
    PYTHONPATH=backend venv/bin/python scripts/audits/split_modern_paragraphs.py --book-id 60 --chapter-number 12 --split "5:200" --merge "1"

No LLM calls — pure DB rewrite of modern_english_text.
"""
import argparse
import sys
from typing import List, Tuple, Optional

from backend import config
from scripts.lib.db import get_connection

DB_PATH = config.DATABASE_PATH

SEP = "\n\n"


def parse_splits(arg: Optional[str]) -> List[Tuple[int, int]]:
    """Parse '5:200,7:100,12:50' into [(5,200),(7,100),(12,50)]."""
    if not arg:
        return []
    out: List[Tuple[int, int]] = []
    for chunk in arg.split(","):
        chunk = chunk.strip()
        if ":" not in chunk:
            raise ValueError(f"Invalid split spec '{chunk}': expected 'idx:offset'")
        a, b = chunk.split(":", 1)
        out.append((int(a), int(b)))
    return out


def parse_merges(arg: Optional[str]) -> List[int]:
    """Parse '1,3,5' into [1, 3, 5]."""
    if not arg:
        return []
    return [int(x.strip()) for x in arg.split(",")]


def apply_splits_and_merges(
    text: str,
    splits: List[Tuple[int, int]],
    merges: List[int],
) -> str:
    """
    Apply splits (insert paragraph break inside a paragraph) and then
    merges (join two adjacent paragraphs) to the text. 1-indexed.
    """
    paras = text.split(SEP)

    # SPLITS: group by paragraph index, sort offsets descending within each,
    # so later splits don't shift earlier ones.
    by_para: dict[int, List[int]] = {}
    for p_idx, offset in splits:
        if p_idx < 1 or p_idx > len(paras):
            raise ValueError(
                f"Split paragraph index {p_idx} out of range (1..{len(paras)})"
            )
        by_para.setdefault(p_idx, []).append(offset)

    # Apply splits paragraph by paragraph
    new_paras: List[str] = []
    for i, p in enumerate(paras, start=1):
        if i in by_para:
            offsets = sorted(set(by_para[i]), reverse=True)
            for off in offsets:
                if off < 0 or off > len(p):
                    raise ValueError(
                        f"Split offset {off} out of range for paragraph {i} (len={len(p)})"
                    )
            # split positions ascending to walk through cleanly
            offsets_asc = sorted(set(by_para[i]))
            pieces: List[str] = []
            prev = 0
            for off in offsets_asc:
                pieces.append(p[prev:off])
                prev = off
            pieces.append(p[prev:])
            new_paras.extend(pieces)
        else:
            new_paras.append(p)

    # MERGES: idx N joins paragraphs N and N+1 with a single space.
    # Apply right-to-left so earlier indices stay valid.
    for m_idx in sorted(set(merges), reverse=True):
        if m_idx < 1 or m_idx >= len(new_paras):
            raise ValueError(
                f"Cannot merge at index {m_idx}: must be in 1..{len(new_paras)-1}"
            )
        joined = new_paras[m_idx - 1].rstrip() + " " + new_paras[m_idx].lstrip()
        new_paras = new_paras[: m_idx - 1] + [joined] + new_paras[m_idx + 1:]

    return SEP.join(new_paras)


def _print_side_by_side(orig: str, modern: str, snippet_chars: int = 100) -> None:
    o = orig.split(SEP)
    m = modern.split(SEP)
    width = max(len(o), len(m))
    print(f"Original paragraphs: {len(o)}")
    print(f"Modern paragraphs:   {len(m)}")
    print(f"Diff: {len(o) - len(m):+d}")
    print()
    for i in range(width):
        op = o[i] if i < len(o) else "<no more>"
        mp = m[i] if i < len(m) else "<no more>"
        print(f"[O{i+1}] ({len(op)} chars) {op[:snippet_chars]}")
        print(f"[M{i+1}] ({len(mp)} chars) {mp[:snippet_chars]}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book-id", type=int, required=True)
    ap.add_argument("--chapter-number", type=int, required=True)
    ap.add_argument("--inspect", action="store_true",
                    help="Print original and modern paragraphs side-by-side.")
    ap.add_argument("--split", type=str, default="",
                    help="Comma-separated 'para_idx:char_offset' splits to apply.")
    ap.add_argument("--merge", type=str, default="",
                    help="Comma-separated paragraph indices to merge with the next.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show before/after without writing.")
    ap.add_argument("--snippet", type=int, default=100,
                    help="Chars per paragraph in inspect output.")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = get_connection(DB_PATH)
    row = conn.execute(
        "SELECT c.id, c.chapter_text, c.modern_english_text, b.title AS book_title "
        "FROM chapters c JOIN books b ON b.id = c.book_id "
        "WHERE c.book_id = ? AND c.chapter_number = ?",
        (args.book_id, args.chapter_number),
    ).fetchone()
    if not row:
        print(
            f"ERROR: chapter {args.chapter_number} of book {args.book_id} not found",
            file=sys.stderr,
        )
        return 2

    orig = row["chapter_text"] or ""
    modern = row["modern_english_text"] or ""
    print(f"Book: {row['book_title']} (id {args.book_id}), chapter {args.chapter_number}")

    if args.inspect:
        _print_side_by_side(orig, modern, snippet_chars=args.snippet)
        return 0

    splits = parse_splits(args.split)
    merges = parse_merges(args.merge)
    if not splits and not merges:
        print("Nothing to do — pass --inspect, --split, or --merge.", file=sys.stderr)
        return 2

    try:
        new_modern = apply_splits_and_merges(modern, splits, merges)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    before_n = len(modern.split(SEP))
    after_n = len(new_modern.split(SEP))
    orig_n = len(orig.split(SEP))
    print(f"Modern paragraphs: {before_n} -> {after_n} (original has {orig_n})")

    if args.dry_run:
        print("DRY RUN: no DB write performed.")
    else:
        conn.execute(
            "UPDATE chapters SET modern_english_text = ? WHERE id = ?",
            (new_modern, row["id"]),
        )
        conn.commit()
        print("Updated.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
