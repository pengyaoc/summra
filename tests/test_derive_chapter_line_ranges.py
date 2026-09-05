"""Tests for the line-range helper used by --dry-run.

derive_chapter_line_ranges(raw_text, chapters) takes the raw source file
text and the (chapter_number, chapter_title, chapter_text) tuples produced
by SummaryGenerator.detect_chapters(), and returns a list of
(chapter_number, start_line, end_line) — 1-indexed, inclusive.

Used by --dry-run to print line ranges so an LLM reviewer can verify
boundaries against the source.
"""

import pytest

# Import will fail until the helper exists — that's the red phase.
from scripts.content.generate_summaries import SummaryGenerator, derive_chapter_line_ranges


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


def test_derive_line_ranges_simple():
    """Two chapters, easy boundaries. start = first line where chapter prose
    begins (after any leading header/blank lines); end = line just before the
    next chapter's prose starts (or EOF for the last chapter)."""
    raw = "\n".join([
        "BOILERPLATE",                          # line 1
        "",                                      # 2
        "CHAPTER I",                             # 3
        "",                                      # 4
        "Once upon a time there was a fox.",     # 5
        "He ran through the forest quickly.",    # 6
        "",                                      # 7
        "CHAPTER II",                            # 8
        "",                                      # 9
        "Then a wolf appeared.",                 # 10
        "It growled loudly at him.",             # 11
    ])
    chapters = [
        (1, "Chapter I",
         "Once upon a time there was a fox.\nHe ran through the forest quickly."),
        (2, "Chapter II",
         "Then a wolf appeared.\nIt growled loudly at him."),
    ]
    ranges = derive_chapter_line_ranges(raw, chapters)
    # Ch1 prose at line 5; ends at line 9 (one before Ch2 prose at line 10).
    # Ch2 prose at line 10; ends at EOF (line 11).
    assert ranges == [(1, 5, 9), (2, 10, 11)]


def test_derive_line_ranges_handles_punctuation_drift():
    """Normalized chapter_text often differs from raw in punctuation/whitespace.

    Helper must match on a punctuation-stripped, lowercased prefix.
    """
    raw = "\n".join([
        "CHAPTER I.",                            # 1
        "MR. SHERLOCK HOLMES.",                  # 2
        "",                                      # 3
        "In the year 1878, I took my degree.",   # 4
        "Sentence two.",                          # 5
        "",                                      # 6
        "CHAPTER II.",                            # 7
        "",                                      # 8
        "We met next day, as arranged.",          # 9
    ])
    chapters = [
        # Chapter text often has smart quotes / normalized whitespace
        (1, "Mr. Sherlock Holmes",
         "MR SHERLOCK HOLMES In the year 1878 I took my degree Sentence two"),
        (2, "We Met",
         "We met next day as arranged"),
    ]
    ranges = derive_chapter_line_ranges(raw, chapters)
    # Ch1 anchor 'in the year 1878 i took' matches at line 4 (first prose);
    # ends at line 8 (one before Ch2 prose at line 9). Ch2 ends at EOF.
    assert ranges == [(1, 4, 8), (2, 9, 9)]


def test_derive_line_ranges_two_level_part_chapters():
    """Two-level book — chapter prose can start either on the header line
    (joined-window match) or the next prose line, depending on layout."""
    raw = "\n".join([
        "PART I",                                # 1
        "",                                      # 2
        "CHAPTER I",                             # 3
        "First content here, more than fifty chars to anchor on.",  # 4
        "",                                      # 5
        "CHAPTER II",                            # 6
        "Second content here, more than fifty chars to anchor on.", # 7
        "",                                      # 8
        "PART II",                               # 9
        "",                                      # 10
        "CHAPTER I",                             # 11
        "Third content here, more than fifty chars to anchor on.",  # 12
    ])
    chapters = [
        (1, "Chapter I", "First content here more than fifty chars to anchor on"),
        (2, "Chapter II", "Second content here more than fifty chars to anchor on"),
        (3, "Chapter I", "Third content here more than fifty chars to anchor on"),
    ]
    ranges = derive_chapter_line_ranges(raw, chapters)
    # Ch1 matches in joined (line 3 + line 4) → anchored at line 3 (header).
    # Ch2 at line 6 (header line joined with prose). Ch3 at line 11.
    assert ranges == [(1, 3, 5), (2, 6, 10), (3, 11, 12)]


def test_derive_line_ranges_empty_chapters():
    """No chapters → empty result."""
    assert derive_chapter_line_ranges("anything", []) == []


def test_derive_line_ranges_handles_unfindable_gracefully():
    """If a chapter's opening can't be found in raw, return (-1, -1) for it.

    Should NOT crash. The reviewer can spot the failure in the report.
    """
    raw = "Some unrelated content\nthat does not contain the chapter text."
    chapters = [
        (1, "Ghost", "totally absent content here to anchor on"),
    ]
    ranges = derive_chapter_line_ranges(raw, chapters)
    assert ranges == [(1, -1, -1)]
