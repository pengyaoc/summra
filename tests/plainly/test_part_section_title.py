"""Regression tests for two PART/CHAPTER parser bugs found via pg244 ingestion.

Bug 1 (PART subtitle): When source has bare 'PART I.' with no subtitle, the
parser captured the trailing '.' as the section_title instead of empty string.
Source: https://www.gutenberg.org/cache/epub/244/pg244.txt
"""

import pytest

from scripts.content.generate_summaries import SummaryGenerator


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


def _study_in_scarlet_minimal_body() -> str:
    """Hand-crafted pg244-shaped body with both bug cases.

    - PART I. has no subtitle (bug 1)
    - PART II. has a subtitle ('THE COUNTRY OF THE SAINTS') for control
    - 6 chapters per part (12 total) — extract_two_level_structure_from_body
      requires >=10 chapters and same-line CHAPTER+title format.
    """
    def _chapters_for_part(titles):
        # Substantial filler text per chapter so the parser treats them as real
        out = []
        roman = ['I', 'II', 'III', 'IV', 'V', 'VI']
        for r, t in zip(roman, titles):
            out.append(f"CHAPTER {r}. {t}\n\n\nFiller paragraph one. " * 1 + ("Sentence. " * 30))
        return "\n\n\n".join(out)

    part_i_titles = [
        "MR SHERLOCK HOLMES", "THE SCIENCE OF DEDUCTION",
        "THE LAURISTON GARDENS MYSTERY", "WHAT JOHN RANCE HAD TO TELL",
        "OUR ADVERTISEMENT BRINGS A VISITOR", "TOBIAS GREGSON SHOWS WHAT HE CAN DO",
    ]
    part_ii_titles = [
        "ON THE GREAT ALKALI PLAIN", "THE FLOWER OF UTAH",
        "JOHN FERRIER TALKS WITH THE PROPHET", "A FLIGHT FOR LIFE",
        "THE AVENGING ANGELS", "A CONTINUATION OF THE REMINISCENCES",
    ]

    return (
        "A STUDY IN SCARLET.\n\n\n\n"
        "PART I.\n\n\n"
        + _chapters_for_part(part_i_titles)
        + "\n\n\nPART II. THE COUNTRY OF THE SAINTS\n\n\n"
        + _chapters_for_part(part_ii_titles)
        + "\n"
    )


def test_bare_part_marker_yields_empty_title(generator):
    """PART I. (with trailing period and no subtitle) must not set title='.'."""
    text = _study_in_scarlet_minimal_body()
    structure = generator.extract_two_level_structure_from_body(text)

    assert structure, "Two-level structure should be detected for PART I/II body"
    assert len(structure) == 2, f"Expected 2 parts, got {len(structure)}"

    part_i, part_ii = structure
    assert part_i["type"] == "PART"
    assert part_i["number"] == 1
    # Bug 1 fix: bare 'PART I.' should yield empty title, never '.'
    assert part_i["title"] != ".", (
        f"PART I should have empty title for bare 'PART I.', got {part_i['title']!r}"
    )
    assert part_i["title"] in ("", None), (
        f"PART I should be empty/None for bare 'PART I.', got {part_i['title']!r}"
    )

    # Sanity check: PART II still captures its real subtitle
    assert part_ii["type"] == "PART"
    assert part_ii["number"] == 2
    assert "COUNTRY OF THE SAINTS" in (part_ii["title"] or "").upper()
