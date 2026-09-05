"""Regression tests for parse_combined_summaries_response().

Found 2026-05-30: the medium summary section in Gemini responses for newly
ingested books was being parsed as empty (word_count=0 in DB), even though the
model emitted ~2,500 words. Root cause: the lookahead in the section regex
terminated at any `###`, including the `####` (h4) subheadings the model uses
inside the medium summary (e.g. "#### Part I: The Reminiscences of John H.
Watson, M.D.").

Captured raw response: tests/fixtures/combined_response_pg244.txt
(4,455 words, originally written to /tmp/summra_combined_raw.json by a
debug write in scripts/content/generate_summaries.py).
"""

from pathlib import Path

import pytest

from scripts.content.generate_summaries import SummaryGenerator


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


@pytest.fixture
def pg244_raw_response():
    return (FIXTURE_DIR / "combined_response_pg244.txt").read_text()


def _count_words(s: str) -> int:
    return len(s.split())


# --- Test 1: regression against the actual failing response -----------------

def test_pg244_medium_summary_is_extracted(generator, pg244_raw_response):
    """The captured pg244 response contains a ~2,500-word medium summary that
    the buggy parser drops. The fixed parser must extract it intact."""
    parsed = generator.parse_combined_summaries_response(
        pg244_raw_response, "A Study in Scarlet", "Arthur Conan Doyle"
    )

    medium = parsed["medium_summary"]
    assert _count_words(medium) > 1500, (
        f"medium summary should be the full ~2500-word block, got "
        f"{_count_words(medium)} words: {medium[:200]!r}..."
    )
    assert "Part I: The Reminiscences" in medium
    assert "Part II: The Country of the Saints" in medium


def test_pg244_concise_summary_is_extracted(generator, pg244_raw_response):
    """Concise must still parse correctly (it works today; guard against
    regression from the fix)."""
    parsed = generator.parse_combined_summaries_response(
        pg244_raw_response, "A Study in Scarlet", "Arthur Conan Doyle"
    )
    concise = parsed["concise_summary"]
    assert 300 < _count_words(concise) < 700, (
        f"concise should be ~500 words, got {_count_words(concise)}"
    )
    assert "Sherlock Holmes" in concise


def test_pg244_about_summary_is_extracted(generator, pg244_raw_response):
    parsed = generator.parse_combined_summaries_response(
        pg244_raw_response, "A Study in Scarlet", "Arthur Conan Doyle"
    )
    about = parsed["about_text"]
    assert 50 < _count_words(about) < 150, (
        f"about should be ~75-100 words, got {_count_words(about)}"
    )
    assert "Sherlock Holmes" in about


def test_pg244_relevance_now_is_extracted(generator, pg244_raw_response):
    parsed = generator.parse_combined_summaries_response(
        pg244_raw_response, "A Study in Scarlet", "Arthur Conan Doyle"
    )
    relevance = parsed["relevance_now"]
    assert 50 < _count_words(relevance) < 150, (
        f"relevance should be ~75-100 words, got {_count_words(relevance)}"
    )


# --- Test 2: clean response with only ### headings (no subheadings) ---------

CLEAN_RESPONSE = """\
### ABOUT THE BOOK (75-100 words)

A short about block. It has no subheadings at all. Just plain text.

### CONCISE SUMMARY (500 words)

A concise summary with no subheadings. Plain paragraphs.

### MEDIUM SUMMARY (2000-3000 words)

A medium summary with no subheadings. Just paragraphs of prose, all flowing
together without any markdown structure.

### RELEVANCE NOW (75-100 words)

Why it matters today. Plain text.
"""


def test_clean_response_parses_all_four_sections(generator):
    parsed = generator.parse_combined_summaries_response(
        CLEAN_RESPONSE, "T", "A"
    )
    assert "short about block" in parsed["about_text"]
    assert "concise summary with no subheadings" in parsed["concise_summary"]
    assert "medium summary with no subheadings" in parsed["medium_summary"]
    assert "matters today" in parsed["relevance_now"]


# --- Test 3: #### subheadings inside concise too ----------------------------

CONCISE_WITH_SUBHEADINGS = """\
### ABOUT THE BOOK (75-100 words)

About text here.

### CONCISE SUMMARY (500 words)

Intro paragraph.

#### Subsection A

Body of A.

#### Subsection B

Body of B.

### MEDIUM SUMMARY (2000-3000 words)

#### Part I

Body of part I.

#### Part II

Body of part II.

### RELEVANCE NOW (75-100 words)

Relevance text here.
"""


def test_subheadings_inside_concise_dont_truncate(generator):
    parsed = generator.parse_combined_summaries_response(
        CONCISE_WITH_SUBHEADINGS, "T", "A"
    )
    concise = parsed["concise_summary"]
    medium = parsed["medium_summary"]

    assert "Intro paragraph" in concise
    assert "Subsection A" in concise
    assert "Subsection B" in concise
    assert "Body of A" in concise
    assert "Body of B" in concise
    # Concise must NOT bleed into medium
    assert "Part I" not in concise
    assert "Body of part I" not in concise

    assert "Part I" in medium
    assert "Part II" in medium
    assert "Body of part I" in medium
    assert "Body of part II" in medium
    # Medium must NOT bleed into relevance
    assert "Relevance text" not in medium


# --- Test 4: bonus ### sections after RELEVANCE NOW -------------------------

WITH_BONUS_SECTIONS = """\
### ABOUT THE BOOK (75-100 words)

About text.

### CONCISE SUMMARY (500 words)

Concise text.

### MEDIUM SUMMARY (2000-3000 words)

#### Part I

Medium body of part I.

#### Part II

Medium body of part II.

### RELEVANCE NOW (75-100 words)

Relevance text.

### LITERARY STYLE AND NARRATIVE STRUCTURE ANALYSIS

Bonus section the model sometimes adds.

### THEMATIC EXPLORATION

Another bonus section.
"""


def test_medium_terminates_before_relevance_not_at_bonus_section(generator):
    parsed = generator.parse_combined_summaries_response(
        WITH_BONUS_SECTIONS, "T", "A"
    )
    medium = parsed["medium_summary"]
    relevance = parsed["relevance_now"]

    assert "Medium body of part I" in medium
    assert "Medium body of part II" in medium
    # Medium must terminate at ### RELEVANCE NOW, NOT include relevance or bonuses
    assert "Relevance text" not in medium
    assert "Bonus section" not in medium
    assert "Another bonus" not in medium

    assert "Relevance text" in relevance
    # Relevance must terminate at the next ### bonus section
    assert "Bonus section" not in relevance
    assert "Another bonus" not in relevance


# --- Test 5: *** horizontal rules between sections (the real model emits these) ----

WITH_HORIZONTAL_RULES = """\
### ABOUT THE BOOK (75-100 words)

About text here with content.

***

### CONCISE SUMMARY (500 words)

Concise text here with content.

***

### MEDIUM SUMMARY (2000-3000 words)

#### Part I

Medium body part I.

***

#### Part II

Medium body part II.

***

### RELEVANCE NOW (75-100 words)

Relevance text here.
"""


def test_horizontal_rules_dont_break_parsing(generator):
    parsed = generator.parse_combined_summaries_response(
        WITH_HORIZONTAL_RULES, "T", "A"
    )
    assert "About text here" in parsed["about_text"]
    assert "Concise text here" in parsed["concise_summary"]
    medium = parsed["medium_summary"]
    assert "Part I" in medium
    assert "Medium body part I" in medium
    assert "Part II" in medium
    assert "Medium body part II" in medium
    assert "Relevance text here" in parsed["relevance_now"]
