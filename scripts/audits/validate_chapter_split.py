"""Validate chapter splits for an ingested book.

Deterministic grep-style checks + optional LLM digest for Claude to read.

Usage:
    PYTHONPATH=backend python scripts/audits/validate_chapter_split.py --book-id 107
    PYTHONPATH=backend python scripts/audits/validate_chapter_split.py --book-id 107 --llm-digest
    PYTHONPATH=backend python scripts/audits/validate_chapter_split.py --file data/books/pg244.txt

Exit codes:
    0 = all deterministic checks pass
    1 = at least one deterministic FAIL
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


from backend import models  # noqa: E402
from backend import config  # noqa: E402
from scripts.content.generate_summaries import SummaryGenerator  # noqa: E402


SNIPPET_LEN = 200
MAX_CHAPTERS_IN_DIGEST = 60
DEFAULT_CHAR_TOLERANCE = 0.05
ADJACENT_OVERLAP_WINDOW = 300
MIN_CHAPTER_CHARS = 100


@dataclass
class Finding:
    level: str  # "fail" | "warn" | "info"
    name: str
    msg: str


@dataclass
class ValidationResult:
    book: Optional[Dict] = None
    chapters: List[Dict] = field(default_factory=list)
    sections: List[Dict] = field(default_factory=list)
    toc: Dict[str, str] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    source_normalized_chars: int = 0
    detected_total_chars: int = 0

    def add(self, level: str, name: str, msg: str) -> None:
        self.findings.append(Finding(level, name, msg))

    def has_fail(self) -> bool:
        return any(f.level == "fail" for f in self.findings)


def _strip_punct_lower(text: str) -> str:
    """Lowercase, replace punctuation/whitespace with single space, collapse runs."""
    s = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", s).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def load_source(file_path: Path) -> Tuple[str, str]:
    """Return (raw_text, gutenberg_body_text)."""
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    # Use a dummy SummaryGenerator just for the static-style helpers.
    gen = _make_generator()
    body = gen.extract_gutenberg_content(raw)
    return raw, body


def _make_generator() -> SummaryGenerator:
    # SummaryGenerator requires an api_key arg; the helpers we use don't call the API.
    return SummaryGenerator(api_key="dummy")


def check_count_matches_toc(result: ValidationResult) -> None:
    n_chapters = len(result.chapters)
    n_toc = len(result.toc)
    n_sections = len([s for s in result.sections if s.get("section_title") or s.get("section_number") is not None])
    if n_toc == 0:
        result.add(
            "warn",
            "count_matches_toc",
            f"No TOC extracted — cannot cross-check count. Detected {n_chapters} chapters.",
        )
        return
    # Two-level / multi-part books: extract_toc often returns only one part's
    # worth of entries. Compare against n_toc * n_sections too.
    candidates = [n_toc]
    if n_sections >= 2:
        candidates.append(n_toc * n_sections)
    if n_chapters in candidates:
        result.add(
            "info",
            "count_matches_toc",
            f"Chapter count ({n_chapters}) matches TOC × sections (toc={n_toc}, sections={n_sections}).",
        )
        return
    # Off-by-one against either candidate is a WARN (preface chapter etc.)
    if any(abs(n_chapters - c) <= 1 for c in candidates):
        result.add(
            "warn",
            "count_matches_toc",
            f"Chapter count near TOC×sections: detected={n_chapters}, toc={n_toc}, sections={n_sections} (off-by-one, possibly preface).",
        )
        return
    # Multi-section books where each section has a different chapter count
    # (e.g. pg3268: TOC lists 13 chapters but actual volumes have 13+12+14+19).
    # If detected count is within +/- (n_sections * 5) of n_toc * n_sections, treat as WARN.
    if n_sections >= 2:
        expected = n_toc * n_sections
        # Allow per-section variance of up to ~50% of average chapter count, capped at 10
        tolerance = max(n_sections * 5, 10)
        if abs(n_chapters - expected) <= tolerance:
            result.add(
                "warn",
                "count_matches_toc",
                f"Chapter count near TOC×sections: detected={n_chapters}, "
                f"toc={n_toc}, sections={n_sections}, expected~{expected} "
                f"(variance within ±{tolerance}; sections may have differing chapter counts).",
            )
            return
    result.add(
        "fail",
        "count_matches_toc",
        f"Chapter count mismatch: detected={n_chapters}, toc={n_toc}, sections={n_sections}.",
    )


def check_monotone_ordering(result: ValidationResult) -> None:
    numbers = [c["chapter_number"] for c in result.chapters]
    if numbers != sorted(numbers):
        result.add("fail", "monotone_ordering", f"Chapter numbers not sorted: {numbers}")
        return
    if len(set(numbers)) != len(numbers):
        dupes = [n for n in numbers if numbers.count(n) > 1]
        result.add("fail", "monotone_ordering", f"Duplicate chapter numbers: {sorted(set(dupes))}")
        return

    # Two-level encoding: if any chapter_number >= 100, expect blocks like 101..N0X, 201..N0Y
    two_level = any(n >= 100 for n in numbers)
    if two_level:
        by_part: Dict[int, List[int]] = {}
        for n in numbers:
            by_part.setdefault(n // 100, []).append(n % 100)
        for part, inner in sorted(by_part.items()):
            if inner != list(range(1, len(inner) + 1)):
                result.add(
                    "fail",
                    "monotone_ordering",
                    f"Part {part}: inner numbers not contiguous from 1: {inner}",
                )
                return
        result.add(
            "info",
            "monotone_ordering",
            f"Two-level encoding looks contiguous across {len(by_part)} parts.",
        )
        return

    # Flat numbering: allow chapter 0 (preface) per WORK_LOG convention.
    # Expect either 0..N-1 or 1..N — both are valid contiguous flat sequences.
    start = numbers[0]
    expected = list(range(start, start + len(numbers)))
    if numbers != expected:
        result.add(
            "warn",
            "monotone_ordering",
            f"Flat numbering not contiguous (got {numbers[:3]}..{numbers[-3:]}).",
        )
    elif start not in (0, 1):
        result.add(
            "warn",
            "monotone_ordering",
            f"Flat numbering starts at {start} (expected 0 for preface or 1).",
        )
    else:
        kind = "preface+chapters" if start == 0 else "chapters"
        result.add(
            "info",
            "monotone_ordering",
            f"Flat numbering {start}..{numbers[-1]} contiguous ({kind}).",
        )


def check_no_duplicate_titles(result: ValidationResult) -> None:
    # Bucket by section_id (None bucket if no sections)
    buckets: Dict[Optional[int], List[Tuple[int, str]]] = {}
    for c in result.chapters:
        key = c.get("section_id")
        title = (c.get("chapter_title") or "").strip().lower()
        buckets.setdefault(key, []).append((c["chapter_number"], title))

    for section_id, items in buckets.items():
        seen: Dict[str, int] = {}
        dupes: List[Tuple[int, int, str]] = []
        for num, title in items:
            if not title:
                continue
            if title in seen:
                dupes.append((seen[title], num, title))
            else:
                seen[title] = num
        if dupes:
            msg = "; ".join(f"ch {a} and ch {b} both '{t}'" for a, b, t in dupes)
            scope = f"section {section_id}" if section_id else "book"
            result.add("fail", "no_duplicate_titles", f"Duplicate titles in {scope}: {msg}")
    if not any(f.name == "no_duplicate_titles" for f in result.findings):
        result.add("info", "no_duplicate_titles", "No duplicate chapter titles.")


def check_min_text_length(result: ValidationResult) -> None:
    short = [
        (c["chapter_number"], c.get("chapter_title", ""), len(c.get("chapter_text") or ""))
        for c in result.chapters
        if len(c.get("chapter_text") or "") < MIN_CHAPTER_CHARS
    ]
    if short:
        msg = "; ".join(f"ch {n} '{t}' = {ln} chars" for n, t, ln in short)
        result.add("fail", "min_text_length", f"Chapters under {MIN_CHAPTER_CHARS} chars: {msg}")
    else:
        result.add(
            "info",
            "min_text_length",
            f"All {len(result.chapters)} chapters above {MIN_CHAPTER_CHARS} chars.",
        )


def check_total_chars(result: ValidationResult, tolerance: float, is_poetry: bool) -> None:
    gen = _make_generator()
    body_normalized_len = len(gen.normalize_chapter_text(_source_body_for_compare(result), is_poetry))
    detected_total = sum(len(c.get("chapter_text") or "") for c in result.chapters)
    result.source_normalized_chars = body_normalized_len
    result.detected_total_chars = detected_total
    if body_normalized_len == 0:
        result.add("warn", "total_chars", "Source body length is 0 after extract — cannot compare.")
        return
    delta = detected_total - body_normalized_len
    delta_pct = delta / body_normalized_len
    msg = (
        f"detected={detected_total:,} chars, source(normalized)={body_normalized_len:,} chars, "
        f"delta={delta:+,} ({delta_pct:+.2%}), tolerance=±{tolerance:.0%}"
    )
    if abs(delta_pct) <= tolerance:
        result.add("info", "total_chars", msg)
    else:
        # Detected significantly less than source = likely missing content (worse than slightly more)
        level = "fail" if delta_pct < -tolerance else "warn"
        result.add(level, "total_chars", msg)


def _source_body_for_compare(result: ValidationResult) -> str:
    # Stored on result by load_inputs
    return getattr(result, "_source_body", "")


def check_first_chapter_opens_body(result: ValidationResult) -> None:
    """Check that the first numbered chapter's opening text appears in the source body.

    This is a weaker check than "first chapter is verbatim the body opener" — title
    pages, dedications, and epigraphs frequently sit between the Gutenberg header
    and chapter 1, so demanding exact alignment causes false positives. Instead we
    just confirm chapter 1's opening is *somewhere* in the source body. Failure
    means the chapter probably contains foreign content (e.g. TOC, frontmatter).
    """
    if not result.chapters:
        return
    body = _source_body_for_compare(result)
    if not body:
        return
    # Find first numbered chapter (skip preface=ch0)
    target = None
    for c in result.chapters:
        n = c["chapter_number"]
        if n == 1 or n == 101:
            target = c
            break
    if target is None:
        for c in result.chapters:
            if c["chapter_number"] != 0:
                target = c
                break
    if target is None:
        target = result.chapters[0]

    text = (target.get("chapter_text") or "").strip()
    if len(text) < 60:
        result.add(
            "warn",
            "first_chapter_opens_body",
            f"Chapter {target['chapter_number']} too short to verify against body.",
        )
        return

    # Take the first sentence-ish (~60 non-space chars after stripping any leading title line)
    text_lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    # Skip the title line if it's short and roughly matches chapter_title
    if text_lines and len(text_lines[0]) < 60:
        text_lines = text_lines[1:] or text_lines
    opener = " ".join(text_lines[:3])[:120]
    opener_norm = _strip_punct_lower(opener)[:60]
    body_norm = _strip_punct_lower(body)
    if len(opener_norm) < 30:
        result.add(
            "warn",
            "first_chapter_opens_body",
            "Could not isolate chapter opening for body cross-check.",
        )
        return
    if opener_norm in body_norm:
        result.add(
            "info",
            "first_chapter_opens_body",
            f"Chapter {target['chapter_number']} opener found in source body ('{opener[:60]}…').",
        )
    else:
        result.add(
            "fail",
            "first_chapter_opens_body",
            f"Chapter {target['chapter_number']} opener NOT found in source body — likely TOC/frontmatter contamination: '{opener[:60]}…'",
        )


def check_no_adjacent_overlap(result: ValidationResult) -> None:
    overlaps: List[str] = []
    chapters = result.chapters
    # Minimum shared run (in normalized chars) to count as suspicious overlap.
    # ~150 chars ≈ a full sentence — long enough to rule out coincidence.
    MIN_SHARED = 150
    for i in range(len(chapters) - 1):
        a_text = chapters[i].get("chapter_text") or ""
        b_text = chapters[i + 1].get("chapter_text") or ""
        if not a_text or not b_text:
            continue
        a_tail = _strip_punct_lower(a_text[-ADJACENT_OVERLAP_WINDOW:])
        b_head = _strip_punct_lower(b_text[:ADJACENT_OVERLAP_WINDOW])
        if len(a_tail) < MIN_SHARED or len(b_head) < MIN_SHARED:
            continue
        # Try shrinking suffix of a_tail until one is found in b_head.
        # Stops at MIN_SHARED — anything shorter is plausibly coincidental.
        for size in range(len(a_tail), MIN_SHARED - 1, -1):
            suffix = a_tail[-size:]
            if suffix in b_head:
                overlaps.append(
                    f"ch {chapters[i]['chapter_number']} tail ({size} chars) appears at head of ch {chapters[i+1]['chapter_number']}"
                )
                break
        else:
            # Also check the reverse direction (b_head in a_tail) for asymmetric bugs
            for size in range(len(b_head), MIN_SHARED - 1, -1):
                prefix = b_head[:size]
                if prefix in a_tail:
                    overlaps.append(
                        f"ch {chapters[i+1]['chapter_number']} head ({size} chars) appears in tail of ch {chapters[i]['chapter_number']}"
                    )
                    break
    if overlaps:
        result.add("fail", "no_adjacent_overlap", "; ".join(overlaps))
    else:
        result.add(
            "info",
            "no_adjacent_overlap",
            f"No adjacent-chapter overlap across {len(chapters)} chapters.",
        )


def check_section_subtitle_quality(result: ValidationResult) -> None:
    """Catch obviously broken section titles (just punctuation, single non-letter char).

    Empty/None titles are fine — some PARTs legitimately have no subtitle
    (e.g. pg244 PART I in A Study in Scarlet). What's a bug is a title that's
    JUST punctuation like '.' or '—'.
    """
    # Drop ghost sections (no id, no number, no title — sometimes appear in get_book_structure output)
    sections = [
        s for s in result.sections
        if s.get("section_title") or s.get("section_number") is not None
    ]
    if not sections:
        return
    bad: List[str] = []
    for s in sections:
        title = (s.get("section_title") or "").strip()
        # Empty/None is fine — bare PART markers exist in the wild
        if not title:
            continue
        # Non-empty but no letters/digits = broken (just punctuation)
        if not re.search(r"[A-Za-z0-9]", title):
            bad.append(f"section {s.get('section_number')} title='{title}'")
    if bad:
        result.add(
            "warn",
            "section_subtitle_quality",
            "Section subtitle looks broken (punctuation only): " + "; ".join(bad),
        )
    else:
        result.add(
            "info",
            "section_subtitle_quality",
            f"All {len(sections)} section subtitles look reasonable ({sum(1 for s in sections if (s.get('section_title') or '').strip())} non-empty).",
        )


def load_inputs(
    book_id: Optional[int], file_path: Optional[Path]
) -> ValidationResult:
    result = ValidationResult()
    db = models.Database()
    gen = _make_generator()

    if book_id is not None:
        book = db.get_book(book_id)
        if not book:
            raise SystemExit(f"book_id={book_id} not found in database")
        result.book = book
        result.chapters = db.get_chapters(book_id)
        try:
            structure = db.get_book_structure(book_id)
            raw_sections = structure.get("sections", []) if isinstance(structure, dict) else []
            # get_book_structure returns {'number': ..., 'title': ...}; normalize
            # to the section_number/section_title naming the rest of the script uses.
            result.sections = [
                {
                    "id": s.get("id"),
                    "section_number": s.get("section_number", s.get("number")),
                    "section_title": s.get("section_title", s.get("title")),
                }
                for s in raw_sections
            ]
        except Exception:
            result.sections = []

        # Resolve source file — prefer explicit, fall back to book.filename
        if file_path is None:
            fname = book.get("filename")
            if fname:
                candidate = REPO_ROOT / "data" / "books" / fname
                if candidate.exists():
                    file_path = candidate

    if file_path is not None and file_path.exists():
        raw, body = load_source(file_path)
        result._source_body = body  # type: ignore[attr-defined]
        toc, _ = gen.extract_toc(raw)
        result.toc = toc or {}
    else:
        result._source_body = ""  # type: ignore[attr-defined]
        result.add("warn", "source_file", "Source file not found — skipping TOC and char-total checks.")

    return result


def run_all_checks(result: ValidationResult, tolerance: float) -> None:
    is_poetry = bool(result.book and result.book.get("is_poetry"))
    if result.toc:
        check_count_matches_toc(result)
    elif getattr(result, "_source_body", ""):
        result.add(
            "warn",
            "count_matches_toc",
            f"TOC empty — skipping count check. Detected {len(result.chapters)} chapters.",
        )
    check_monotone_ordering(result)
    check_no_duplicate_titles(result)
    check_min_text_length(result)
    if getattr(result, "_source_body", ""):
        check_total_chars(result, tolerance, is_poetry)
        check_first_chapter_opens_body(result)
    check_no_adjacent_overlap(result)
    check_section_subtitle_quality(result)


def render_report(result: ValidationResult) -> None:
    if result.book:
        print("=" * 70)
        print(f"Book id={result.book.get('id')}  title={result.book.get('title')!r}")
        print(f"     author={result.book.get('author')!r}  file={result.book.get('filename')!r}")
        print(f"     chapters={len(result.chapters)}  sections={len(result.sections)}  toc_entries={len(result.toc)}")
        print("=" * 70)
    levels_order = {"fail": 0, "warn": 1, "info": 2}
    for f in sorted(result.findings, key=lambda x: (levels_order.get(x.level, 9), x.name)):
        prefix = {"fail": "✗ FAIL", "warn": "! WARN", "info": "✓ PASS"}.get(f.level, f.level)
        print(f"  [{prefix}] {f.name}: {f.msg}")
    print("-" * 70)
    n_fail = sum(1 for f in result.findings if f.level == "fail")
    n_warn = sum(1 for f in result.findings if f.level == "warn")
    n_info = sum(1 for f in result.findings if f.level == "info")
    print(f"  Summary: {n_fail} FAIL, {n_warn} WARN, {n_info} PASS")


def render_json(result: ValidationResult) -> None:
    payload = {
        "book_id": result.book.get("id") if result.book else None,
        "title": result.book.get("title") if result.book else None,
        "chapters": len(result.chapters),
        "sections": len(result.sections),
        "toc_entries": len(result.toc),
        "source_normalized_chars": result.source_normalized_chars,
        "detected_total_chars": result.detected_total_chars,
        "findings": [
            {"level": f.level, "name": f.name, "msg": f.msg} for f in result.findings
        ],
    }
    print(json.dumps(payload, indent=2))


def render_llm_digest(result: ValidationResult) -> None:
    """Compact digest meant for an LLM reviewer (Claude) to read inline."""
    print()
    print("=" * 70)
    print("LLM DIGEST (read this and decide: pass / warn / fail)")
    print("=" * 70)
    if result.book:
        print(f"Title:  {result.book.get('title')}")
        print(f"Author: {result.book.get('author')}")
        print()

    if result.sections:
        print("SECTIONS (from DB):")
        for s in result.sections:
            print(f"  - #{s.get('section_number')} '{s.get('section_title')}'  (id={s.get('id')})")
        print()

    if result.toc:
        print("SOURCE TOC:")
        for i, (k, v) in enumerate(result.toc.items(), 1):
            print(f"  {i}. [{k}] {v}")
        print()
    else:
        print("SOURCE TOC: (none extracted)")
        print()

    chapters = result.chapters
    truncated = len(chapters) > MAX_CHAPTERS_IN_DIGEST
    if truncated:
        chapters = chapters[:MAX_CHAPTERS_IN_DIGEST]
    print(f"DETECTED CHAPTERS ({len(chapters)}{' (truncated)' if truncated else ''}):")
    for c in chapters:
        text = c.get("chapter_text") or ""
        wc = _word_count(text)
        first = text[:SNIPPET_LEN].strip().replace("\n", " ")
        last = text[-SNIPPET_LEN:].strip().replace("\n", " ")
        print(
            f"  CH {c['chapter_number']}: \"{c.get('chapter_title')}\""
            f"  | words={wc}  | section_id={c.get('section_id')}"
        )
        print(f"    FIRST_{SNIPPET_LEN}: {first}")
        print(f"    LAST_{SNIPPET_LEN}:  {last}")

    print()
    print("Reviewer: flag any of — missing chapter, mislabeled title,")
    print("  wrong boundary, text spilling between chapters, title that is")
    print("  actually a TOC entry, opening/closing not aligned with what a")
    print("  real chapter would start/end with. Render verdict + bullet issues.")
    print("=" * 70)


def main() -> int:
    p = argparse.ArgumentParser(description="Validate chapter splits for an ingested book.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--book-id", type=int, help="Validate book by DB id")
    g.add_argument("--file", type=Path, help="Validate against file (no DB row required)")
    p.add_argument("--char-tolerance", type=float, default=DEFAULT_CHAR_TOLERANCE,
                   help=f"Allowed char-count delta as fraction of source (default {DEFAULT_CHAR_TOLERANCE})")
    p.add_argument("--llm-digest", action="store_true", help="Also print compact digest for LLM review")
    p.add_argument("--json", action="store_true", help="Machine-readable findings JSON instead of report")
    args = p.parse_args()

    result = load_inputs(args.book_id, args.file)
    run_all_checks(result, args.char_tolerance)

    if args.json:
        render_json(result)
    else:
        render_report(result)

    if args.llm_digest:
        render_llm_digest(result)

    return 1 if result.has_fail() else 0


if __name__ == "__main__":
    sys.exit(main())
