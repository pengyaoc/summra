"""Tests for scripts/audits/validate_chapter_split.py.

Validates the deterministic checks by constructing in-memory ValidationResult
objects and asserting each check produces the right Finding.
"""

import pytest

from scripts.audits.validate_chapter_split import (
    Finding,
    ValidationResult,
    check_count_matches_toc,
    check_first_chapter_opens_body,
    check_min_text_length,
    check_monotone_ordering,
    check_no_adjacent_overlap,
    check_no_duplicate_titles,
    check_section_subtitle_quality,
    check_total_chars,
    _strip_punct_lower,
)


def _make_result(chapters=None, toc=None, sections=None, body=""):
    r = ValidationResult(
        chapters=chapters or [],
        toc=toc or {},
        sections=sections or [],
    )
    r._source_body = body
    return r


def _ch(num, title="Title", text="Some body text " * 20, section_id=None):
    return {
        "chapter_number": num,
        "chapter_title": title,
        "chapter_text": text,
        "section_id": section_id,
    }


def _names(result):
    return {f.name: f for f in result.findings}


# ── count_matches_toc ────────────────────────────────────────────────────────

def test_count_matches_toc_pass():
    r = _make_result(chapters=[_ch(1), _ch(2)], toc={"I": "a", "II": "b"})
    check_count_matches_toc(r)
    assert _names(r)["count_matches_toc"].level == "info"


def test_count_matches_toc_two_level_pass():
    # 14 detected chapters across 2 sections, TOC reports 7 per section.
    chapters = [_ch(i) for i in range(1, 15)]
    sections = [
        {"section_number": 1, "section_title": "Part I"},
        {"section_number": 2, "section_title": "Part II"},
    ]
    r = _make_result(chapters=chapters, toc={str(i): f"t{i}" for i in range(1, 8)}, sections=sections)
    check_count_matches_toc(r)
    assert _names(r)["count_matches_toc"].level == "info"


def test_count_matches_toc_off_by_one_warns():
    r = _make_result(chapters=[_ch(1), _ch(2), _ch(3)], toc={"I": "a", "II": "b"})
    check_count_matches_toc(r)
    assert _names(r)["count_matches_toc"].level == "warn"


def test_count_matches_toc_mismatch_fails():
    r = _make_result(chapters=[_ch(1)], toc={"I": "a", "II": "b", "III": "c"})
    check_count_matches_toc(r)
    assert _names(r)["count_matches_toc"].level == "fail"


def test_count_matches_toc_empty_warns():
    r = _make_result(chapters=[_ch(1)])
    check_count_matches_toc(r)
    assert _names(r)["count_matches_toc"].level == "warn"


# ── monotone_ordering ────────────────────────────────────────────────────────

def test_monotone_ordering_flat_pass():
    r = _make_result(chapters=[_ch(1), _ch(2), _ch(3)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "info"


def test_monotone_ordering_two_level_pass():
    # 101..103 + 201..202
    chapters = [_ch(101), _ch(102), _ch(103), _ch(201), _ch(202)]
    r = _make_result(chapters=chapters)
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "info"


def test_monotone_ordering_duplicate_fails():
    r = _make_result(chapters=[_ch(1), _ch(1), _ch(2)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "fail"


def test_monotone_ordering_unsorted_fails():
    r = _make_result(chapters=[_ch(2), _ch(1), _ch(3)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "fail"


def test_monotone_ordering_two_level_gap_fails():
    # 101, 102, 104 (missing 103)
    r = _make_result(chapters=[_ch(101), _ch(102), _ch(104)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "fail"


def test_monotone_ordering_preface_zero_pass():
    # WORK_LOG convention: chapter 0 = preface, then 1..N
    r = _make_result(chapters=[_ch(0), _ch(1), _ch(2), _ch(3)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "info"


def test_monotone_ordering_starts_at_three_warns():
    # Suspicious: numbering starts at 3 — likely missing 1, 2
    r = _make_result(chapters=[_ch(3), _ch(4), _ch(5)])
    check_monotone_ordering(r)
    assert _names(r)["monotone_ordering"].level == "warn"


# ── no_duplicate_titles ──────────────────────────────────────────────────────

def test_no_duplicate_titles_pass():
    r = _make_result(chapters=[_ch(1, "Alpha"), _ch(2, "Beta")])
    check_no_duplicate_titles(r)
    assert _names(r)["no_duplicate_titles"].level == "info"


def test_no_duplicate_titles_within_section_fails():
    chapters = [
        _ch(1, "Alpha", section_id=10),
        _ch(2, "Alpha", section_id=10),
    ]
    r = _make_result(chapters=chapters)
    check_no_duplicate_titles(r)
    assert _names(r)["no_duplicate_titles"].level == "fail"


def test_no_duplicate_titles_across_sections_pass():
    # Same title in DIFFERENT sections is fine (e.g., "CHAPTER I" in PART I and PART II)
    chapters = [
        _ch(1, "Chapter One", section_id=10),
        _ch(8, "Chapter One", section_id=11),
    ]
    r = _make_result(chapters=chapters)
    check_no_duplicate_titles(r)
    assert _names(r)["no_duplicate_titles"].level == "info"


# ── min_text_length ──────────────────────────────────────────────────────────

def test_min_text_length_pass():
    r = _make_result(chapters=[_ch(1, text="x" * 200)])
    check_min_text_length(r)
    assert _names(r)["min_text_length"].level == "info"


def test_min_text_length_fails():
    r = _make_result(chapters=[_ch(1, text="tiny")])
    check_min_text_length(r)
    assert _names(r)["min_text_length"].level == "fail"


# ── total_chars ──────────────────────────────────────────────────────────────

def test_total_chars_within_tolerance_pass():
    body = "abc def " * 1000  # 8000 chars before normalize
    detected = "abc def " * 990  # ~99% of source
    r = _make_result(chapters=[_ch(1, text=detected)], body=body)
    check_total_chars(r, tolerance=0.05, is_poetry=False)
    assert _names(r)["total_chars"].level == "info"


def test_total_chars_under_fails():
    body = "abc def " * 1000
    detected = "abc def " * 500  # 50% — way under
    r = _make_result(chapters=[_ch(1, text=detected)], body=body)
    check_total_chars(r, tolerance=0.05, is_poetry=False)
    assert _names(r)["total_chars"].level == "fail"


def test_total_chars_over_warns():
    body = "abc def " * 1000
    # Duplicated content => detected ~2x source
    r = _make_result(
        chapters=[_ch(1, text="abc def " * 1000), _ch(2, text="abc def " * 1000)],
        body=body,
    )
    check_total_chars(r, tolerance=0.05, is_poetry=False)
    assert _names(r)["total_chars"].level == "warn"


# ── first_chapter_opens_body ────────────────────────────────────────────────

def test_first_chapter_opens_body_skips_preface():
    # Preface (ch 0) has different content; ch 1 has the body opener.
    # The check should target ch 1, not ch 0, and pass.
    body = (
        "CHAPTER I.\n"
        "MR. SHERLOCK HOLMES.\n\n"
        "In the year 1878 I took my degree of Doctor of Medicine "
        "of the University of London, and proceeded to Netley."
    )
    chapter_text = (
        "In the year 1878 I took my degree of Doctor of Medicine "
        "of the University of London, and proceeded to Netley."
    )
    r = _make_result(
        chapters=[
            _ch(0, text="Another preface " * 30),  # Preface — different content
            _ch(1, text=chapter_text),  # Real first chapter
        ],
        body=body,
    )
    check_first_chapter_opens_body(r)
    assert _names(r)["first_chapter_opens_body"].level == "info"


def test_first_chapter_opens_body_two_level_targets_101():
    # Two-level book: check should target chapter 101 (part 1, chapter 1)
    body = (
        "PART I.\n\nCHAPTER I.\n\nIn the central portion of the great North American "
        "Continent there lies an arid and repulsive desert, which for many a long year."
    )
    chapter_text = (
        "In the central portion of the great North American Continent there lies "
        "an arid and repulsive desert, which for many a long year."
    )
    r = _make_result(
        chapters=[_ch(101, text=chapter_text), _ch(102, text="Different content " * 30)],
        body=body,
    )
    check_first_chapter_opens_body(r)
    assert _names(r)["first_chapter_opens_body"].level == "info"


def test_first_chapter_opens_body_pass():
    body = (
        "CHAPTER I.\n"
        "MR. SHERLOCK HOLMES.\n\n"
        "In the year 1878 I took my degree of Doctor of Medicine "
        "of the University of London, and proceeded to Netley to go through the course."
    )
    chapter_text = (
        "In the year 1878 I took my degree of Doctor of Medicine "
        "of the University of London, and proceeded to Netley to go through the course."
    )
    r = _make_result(chapters=[_ch(1, text=chapter_text)], body=body)
    check_first_chapter_opens_body(r)
    assert _names(r)["first_chapter_opens_body"].level == "info"


def test_first_chapter_opens_body_misaligned_fails():
    # Chapter 1 contains text that does NOT appear in source body at all.
    # Real bug case: TOC contamination would mean chapter 1 starts with a TOC
    # entry like "CHAPTER I. Title page 5" which is in source, but here we
    # simulate a clean "totally foreign" failure.
    body = (
        "CHAPTER I.\n\n"
        "In the year 1878 I took my degree of Doctor of Medicine of the University of London."
    )
    r = _make_result(
        chapters=[_ch(1, text="The crystalline machinations of zlorgon empire " * 5)],
        body=body,
    )
    check_first_chapter_opens_body(r)
    assert _names(r)["first_chapter_opens_body"].level == "fail"


# ── no_adjacent_overlap ─────────────────────────────────────────────────────

def test_no_adjacent_overlap_pass():
    a = "alpha " * 200
    b = "bravo " * 200
    r = _make_result(chapters=[_ch(1, text=a), _ch(2, text=b)])
    check_no_adjacent_overlap(r)
    assert _names(r)["no_adjacent_overlap"].level == "info"


def test_no_adjacent_overlap_detects_overlap_fails():
    # Tail of chapter 1 appears verbatim at head of chapter 2.
    shared = "This is the shared overlapping sentence repeated many times. " * 10
    a = ("alpha words " * 100) + shared
    b = shared + ("bravo words " * 100)
    r = _make_result(chapters=[_ch(1, text=a), _ch(2, text=b)])
    check_no_adjacent_overlap(r)
    assert _names(r)["no_adjacent_overlap"].level == "fail"


# ── section_subtitle_quality ────────────────────────────────────────────────

def test_section_subtitle_quality_pass():
    r = _make_result(sections=[{"section_number": 1, "section_title": "Part One"}])
    check_section_subtitle_quality(r)
    assert _names(r)["section_subtitle_quality"].level == "info"


def test_section_subtitle_quality_empty_warns():
    # The exact bug we observed on pg244 PART I (title was just ".")
    r = _make_result(sections=[
        {"section_number": 1, "section_title": "."},
        {"section_number": 2, "section_title": "The Country of the Saints"},
    ])
    check_section_subtitle_quality(r)
    assert _names(r)["section_subtitle_quality"].level == "warn"


def test_section_subtitle_quality_empty_string_ok():
    # Empty subtitle is fine — some PARTs genuinely have no subtitle in source
    # (e.g. pg244 PART I after the parser bug-fix that strips bare '.').
    r = _make_result(sections=[
        {"section_number": 1, "section_title": ""},
        {"section_number": 2, "section_title": "The Country of the Saints"},
    ])
    check_section_subtitle_quality(r)
    assert _names(r)["section_subtitle_quality"].level == "info"


def test_section_subtitle_quality_ghost_filtered():
    # Ghost section (no number, no title) should be ignored, not flagged.
    r = _make_result(sections=[
        {"section_number": None, "section_title": None},
        {"section_number": 1, "section_title": "Part One"},
    ])
    check_section_subtitle_quality(r)
    # Only the real section is counted — info, not warn.
    assert _names(r)["section_subtitle_quality"].level == "info"


# ── helpers ─────────────────────────────────────────────────────────────────

def test_strip_punct_lower():
    assert _strip_punct_lower("Hello, World!") == "hello world"
    # Punctuation between letters becomes a space (so cross-line normalization works:
    # 'home is the resort\nOf love' must not become 'home is the resortof love').
    assert _strip_punct_lower("M.D.") == "m d"
    assert _strip_punct_lower("line1\nline2") == "line1 line2"
    # Collapsed whitespace runs
    assert _strip_punct_lower("foo   bar\n\n\nbaz") == "foo bar baz"
