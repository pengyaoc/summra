"""Regression tests for TOC vs body numeral mismatch (e.g. Roman TOC + Arabic body).

Bug case from pg245.txt (Twain, Life on the Mississippi):
  TOC lists 'CHAPTER I. ...', 'CHAPTER II. ...', etc. (Roman),
  but the body uses 'CHAPTER 1', 'CHAPTER 2', etc. (Arabic).
  The TOC-validation check rejected every body chapter as "not in TOC"
  because string equality between 'I' and '1' fails. Result: 0 chapters
  detected, parser fell back to single 'Full Text' chapter.

Fix: when checking if a body chapter_marker is in the TOC, also try
matching by integer value (roman_to_int / int) — so '1' matches 'I'.
"""

import pytest

from generate_summaries import SummaryGenerator


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


def _twain_minimal_with_arabic_body() -> str:
    """Hand-crafted minimal text: Roman TOC, Arabic body."""
    return """LIFE ON THE MISSISSIPPI

By Mark Twain




TABLE OF CONTENTS

CHAPTER I. The Mississippi is Well worth Reading about

CHAPTER II. La Salle again Appears

CHAPTER III. A little History




CHAPTER 1

The River and Its History

The Mississippi is well worth reading about. Considering the
Missouri its main branch, it is the longest river in the world.
This is the first body chapter and it needs to be long enough to
actually be detected as a real chapter and not as TOC noise.
""" + ("\n\nThis is a filler paragraph. " * 30) + """




CHAPTER 2

The River and Its Explorers

LA SALLE himself sued for certain high privileges, and they were
graciously accorded him by Louis XIV. This is the second body chapter
with substantial content so the parser sees it as legitimate.
""" + ("\n\nMore filler text to bulk out chapter two. " * 30) + """




CHAPTER 3

Frescoes from the Past

This third body chapter also needs substantial content to be detected.
""" + ("\n\nFiller paragraph three. " * 30) + "\n"


def test_arabic_body_chapters_match_roman_toc(generator):
    """Body 'CHAPTER 1/2/3' must validate against TOC 'CHAPTER I/II/III'.

    Before the fix, this returned 0 body chapters (entire book became one
    'Full Text' fallback chapter). With numeric equivalence, all 3 are
    detected and pick up the Roman TOC titles.
    """
    text = _twain_minimal_with_arabic_body()
    chapters, _ = generator.detect_chapters(text)
    # Filter out preface (chapter_number == 0)
    body = [c for c in chapters if c[0] != 0]
    assert len(body) >= 3, (
        f"Expected >=3 body chapters from Arabic body matching Roman TOC, "
        f"got {len(body)}: {[(c[0], c[1]) for c in body]}"
    )
    # The titles should come from the TOC (Roman side) since it was the authoritative source
    nums = [c[0] for c in body]
    assert nums[:3] == [1, 2, 3], f"Expected chapters 1,2,3 in body, got {nums}"


def test_extract_two_level_toc_dedupes_roman_vs_arabic_volumes():
    """When the TOC lists 'VOLUME I/II/III/IV' (Roman) and the body restarts
    with 'VOLUME 1/2/3/4' (Arabic), extract_two_level_toc must recognize them
    as the same volumes and stop at the second occurrence, returning 4 sections
    (not 8).

    Bug case: pg3268 (Radcliffe, Mysteries of Udolpho).
    """
    from generate_summaries import SummaryGenerator
    g = SummaryGenerator(api_key="dummy")
    # Minimal text mimicking pg3268: TOC with Roman VOLUMEs followed by body Arabic VOLUMEs
    chapters_per_vol_toc = "\n".join(f" CHAPTER {n}" for n in ["I", "II", "III"])
    chapters_per_vol_body = "\n".join(f"CHAPTER {n}\n\nProse content for chapter {n} " * 1 + ("blah " * 60) for n in ["I", "II", "III"])
    text = (
        "MYSTERIES OF UDOLPHO\n\n By Ann Radcliffe\n\n\nContents\n\n\n"
        + " VOLUME I\n" + chapters_per_vol_toc + "\n\n"
        + " VOLUME II\n" + chapters_per_vol_toc + "\n\n"
        + " VOLUME III\n" + chapters_per_vol_toc + "\n\n"
        + " VOLUME IV\n" + chapters_per_vol_toc + "\n\n\n"
        # Body
        + "VOLUME 1\n\n" + chapters_per_vol_body + "\n\n"
        + "VOLUME 2\n\n" + chapters_per_vol_body + "\n\n"
        + "VOLUME 3\n\n" + chapters_per_vol_body + "\n\n"
        + "VOLUME 4\n\n" + chapters_per_vol_body + "\n"
    )
    sections = g.extract_two_level_toc(text)
    assert sections is not None, "Should detect two-level structure"
    # Critical: only 4 volumes (TOC + body collapse), not 8
    assert len(sections) == 4, (
        f"Expected 4 sections (Roman TOC dedupes against Arabic body), "
        f"got {len(sections)}: {[(s['type'], s['numeral']) for s in sections]}"
    )
