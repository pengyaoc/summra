"""Regression tests for TOC detection on books with non-standard TOC headers.

Bug case from pg245.txt (Twain's Life on the Mississippi):
  The TOC starts with the line "TABLE OF CONTENTS", but extract_toc only
  recognized a standalone "CONTENTS" or "CHAPTER" line. Result: no TOC was
  detected, so the parser then matched the first TOC entry ("CHAPTER I.
  The Mississippi is Well worth...") as the first body chapter, and every
  subsequent TOC entry as another chapter — corrupting all 60 chapters.

Same fix benefits any book that uses "TABLE OF CONTENTS" or "LIST OF CHAPTERS".
"""

import pytest

from scripts.content.generate_summaries import SummaryGenerator


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


def _twain_minimal_text() -> str:
    """Hand-crafted minimal text mimicking pg245's TOC + body structure.

    - TOC header is "TABLE OF CONTENTS" (not the standalone "CONTENTS"
      that the original regex recognized).
    - TOC uses Roman numerals: CHAPTER I, CHAPTER II, ...
    - Body uses Arabic: CHAPTER 1, CHAPTER 2, ... (Twain's pg245 quirk).
    """
    return """LIFE ON THE MISSISSIPPI

By Mark Twain




TABLE OF CONTENTS

CHAPTER I. The Mississippi is Well worth Reading about.--It is
Remarkable.--Instead of Widening towards its Mouth, it grows Narrower.

CHAPTER II. La Salle again Appears, and so does a Cat-fish.--Buffaloes
also.

CHAPTER III. A little History.--Early Commerce.--Coal Fleets.




CHAPTER 1

The River and Its History

THE Mississippi is well worth reading about. It is not a commonplace
river, but on the contrary is in all ways remarkable. Considering the
Missouri its main branch, it is the longest river in the world.




CHAPTER 2

The body content of chapter two begins here.
It runs for several lines of text to make sure the parser sees it
as a substantial body chapter, not a TOC fragment.




CHAPTER 3

The body content of chapter three. Another substantial paragraph
to ensure we have enough content for detection. The previous chapter
ended just above; this one begins fresh.
"""


def test_extract_toc_recognizes_table_of_contents_header(generator):
    """extract_toc must recognize 'TABLE OF CONTENTS' as the TOC start marker."""
    text = _twain_minimal_text()
    toc, toc_end = generator.extract_toc(text)
    # We should detect a non-empty TOC and an end-of-toc line > 0
    assert len(toc) >= 3, f"Expected at least 3 TOC entries (Roman I/II/III), got {len(toc)}: {toc}"
    assert toc_end > 0, f"toc_end_line should be > 0, got {toc_end}"
    # The Roman-numeral keys should be present
    assert "I" in toc and "II" in toc and "III" in toc, f"Missing Roman keys in {toc}"


def test_extract_toc_recognizes_list_of_chapters_header(generator):
    """Less common but valid TOC header variant."""
    text = _twain_minimal_text().replace("TABLE OF CONTENTS", "LIST OF CHAPTERS")
    toc, toc_end = generator.extract_toc(text)
    assert len(toc) >= 3, f"Expected at least 3 TOC entries, got {len(toc)}"
    assert toc_end > 0
