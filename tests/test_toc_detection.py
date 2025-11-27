"""
Unit tests for TOC (Table of Contents) detection in chapter parsing.

These tests ensure that the chapter detection logic correctly distinguishes between:
1. TOC entries (which should be skipped)
2. Actual chapter markers (which should be parsed)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_summaries import SummaryGenerator


def test_dracula_chapter_detection():
    """
    Test that Dracula's chapters are detected correctly.

    Dracula has:
    - TOC at the beginning with format: "CHAPTER I. Jonathan Harker's Journal"
    - Actual chapters with format: "CHAPTER I" (line), blank line, "JONATHAN HARKER'S JOURNAL"

    Chapter 1 should NOT be skipped as a TOC entry.
    """
    # Read Dracula text
    dracula_path = Path("/private/tmp/pg345.txt")

    if not dracula_path.exists():
        print("Skipping Dracula test - file not found")
        return

    with open(dracula_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Create generator instance
    generator = SummaryGenerator(api_key="dummy")

    # Extract Gutenberg content (removes headers/footers)
    text = generator.extract_gutenberg_content(text)

    # Detect chapters
    chapters, _ = generator.detect_chapters(text)

    # Verify we have chapters
    assert len(chapters) > 0, "Should detect chapters in Dracula"

    # Check that Chapter 1 exists
    chapter_numbers = [ch[0] for ch in chapters]
    assert 1 in chapter_numbers, "Chapter 1 should be detected, not skipped as TOC"

    # Get Chapter 1
    chapter_1 = next(ch for ch in chapters if ch[0] == 1)
    chapter_num, chapter_title, chapter_text = chapter_1

    # Verify Chapter 1 has the correct title
    assert "Jonathan Harker" in chapter_title, \
        f"Chapter 1 should have 'Jonathan Harker' in title, got: {chapter_title}"

    # Verify Chapter 1 has substantial content
    assert len(chapter_text) > 1000, \
        f"Chapter 1 should have substantial content, got {len(chapter_text)} chars"

    print(f"✓ Dracula: Detected {len(chapters)} chapters")
    print(f"✓ Chapter 1: {chapter_title} ({len(chapter_text)} chars)")


def test_war_and_peace_chapter_detection():
    """
    Test that War and Peace chapters are detected correctly.

    War and Peace has:
    - Nested BOOK/CHAPTER structure
    - 15 Books + 2 Epilogues
    - ~349 total chapters
    """
    # Read War and Peace text
    war_peace_path = Path("/private/tmp/pg2600.txt")

    if not war_peace_path.exists():
        print("Skipping War and Peace test - file not found")
        return

    with open(war_peace_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Create generator instance
    generator = SummaryGenerator(api_key="dummy")

    # Extract Gutenberg content
    text = generator.extract_gutenberg_content(text)

    # Detect chapters
    chapters, _ = generator.detect_chapters(text)

    # Verify we have many chapters (should be ~349)
    assert len(chapters) >= 300, \
        f"War and Peace should have ~349 chapters, got {len(chapters)}"

    # Check that we have chapters from different books
    chapter_numbers = [ch[0] for ch in chapters]

    # Should have chapters from Book 1 (100-199)
    book_1_chapters = [n for n in chapter_numbers if 100 <= n < 200]
    assert len(book_1_chapters) > 0, "Should have chapters from Book 1"

    # Should have chapters from Book 15 (1500-1599)
    book_15_chapters = [n for n in chapter_numbers if 1500 <= n < 1600]
    assert len(book_15_chapters) > 0, "Should have chapters from Book 15"

    # Should have Epilogue chapters (1600+, 1700+)
    epilogue_chapters = [n for n in chapter_numbers if n >= 1600]
    assert len(epilogue_chapters) > 0, "Should have Epilogue chapters"

    print(f"✓ War and Peace: Detected {len(chapters)} chapters")
    print(f"✓ Book 1 chapters: {len(book_1_chapters)}")
    print(f"✓ Book 15 chapters: {len(book_15_chapters)}")
    print(f"✓ Epilogue chapters: {len(epilogue_chapters)}")


def test_toc_vs_actual_chapter_distinction():
    """
    Test that we can distinguish between TOC entries and actual chapters.

    Key differences:
    - TOC: "CHAPTER I. Title" (title on same line with period)
    - Actual: "CHAPTER I" (standalone), then "TITLE" on next line
    """
    # Create sample text with both TOC and actual chapters
    sample_text = """
CONTENTS

CHAPTER I. The Beginning
CHAPTER II. The Middle
CHAPTER III. The End

""" + "\n".join(["Some substantial introduction text to separate TOC from content and pass the threshold requirements."] * 100) + """

CHAPTER I

The Beginning Story Title

""" + " ".join(["This is the actual content of chapter 1."] * 50) + """

CHAPTER II

The Middle Story Title

""" + " ".join(["This is the actual content of chapter 2."] * 50)

    # Create generator instance
    generator = SummaryGenerator(api_key="dummy")

    # Detect chapters
    chapters, _ = generator.detect_chapters(sample_text)

    # Should detect 2 actual chapters (not the TOC entries)
    assert len(chapters) >= 2, \
        f"Should detect at least 2 actual chapters, got {len(chapters)}"

    # Get chapter numbers
    chapter_numbers = [ch[0] for ch in chapters]

    # Should have Chapter 1 and 2
    assert 1 in chapter_numbers, "Should detect Chapter 1"
    assert 2 in chapter_numbers, "Should detect Chapter 2"

    # Chapter 1 should have substantial content
    chapter_1 = next(ch for ch in chapters if ch[0] == 1)
    assert len(chapter_1[2]) > 50, \
        f"Chapter 1 should have substantial content, got {len(chapter_1[2])} chars"

    print(f"✓ TOC distinction: Detected {len(chapters)} actual chapters (not TOC entries)")


if __name__ == "__main__":
    print("Running TOC Detection Tests...")
    print("=" * 60)

    try:
        test_dracula_chapter_detection()
    except AssertionError as e:
        print(f"✗ Dracula test failed: {e}")

    print()

    try:
        test_war_and_peace_chapter_detection()
    except AssertionError as e:
        print(f"✗ War and Peace test failed: {e}")

    print()

    try:
        test_toc_vs_actual_chapter_distinction()
    except AssertionError as e:
        print(f"✗ TOC distinction test failed: {e}")

    print("=" * 60)
    print("Tests complete!")
