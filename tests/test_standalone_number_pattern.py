"""
Test cases for standalone number chapter pattern (e.g., A Little Princess format).

This pattern detects chapters formatted as:
  1

  Sara

  (content)

The pattern should only match when:
1. Past TOC section
2. Preceded by 2+ blank lines (chapter break context)
3. Number is reasonable (1-200)
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_summaries import SummaryGenerator


class TestStandaloneNumberPattern(unittest.TestCase):
    """Test standalone number pattern detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = SummaryGenerator(api_key="test-key-dummy")

    def test_a_little_princess_format(self):
        """Test A Little Princess format: standalone number followed by title."""
        test_text = """The Project Gutenberg eBook of A Little Princess

Title: A Little Princess
Author: Frances Hodgson Burnett

*** START OF THE PROJECT GUTENBERG EBOOK A LITTLE PRINCESS ***

CONTENTS

   Preface
 I Sara
II A French Lesson
III Ermengarde


Preface

This is the preface text with some introductory material.


1

Sara


Once on a dark winter's day, when the yellow fog hung so thick and heavy
in the streets of London that the lamps were lighted and the shop windows
blazed with gas as they do at night, an odd-looking little girl sat in a
cab with her father and was driven rather slowly through the big
thoroughfares.


2

A French Lesson


The first morning she sat at Miss Minchin's side and had her lessons, and
the classroom became a different place from what it had been in all the
years that it had been used.

*** END OF THE PROJECT GUTENBERG EBOOK A LITTLE PRINCESS ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect: Preface (Chapter 0) + 2 numbered chapters = 3 total
        self.assertEqual(len(chapters), 3, f"Expected 3 chapters, got {len(chapters)}")

        # Verify chapter 0 is preface
        self.assertEqual(chapters[0][0], 0, "First chapter should be Chapter 0 (Preface)")
        self.assertIn("Preface", chapters[0][1], "Chapter 0 title should contain 'Preface'")

        # Verify chapter 1 is "Sara"
        self.assertEqual(chapters[1][0], 1, "Second chapter should be Chapter 1")
        self.assertEqual(chapters[1][1], "Sara", f"Chapter 1 title should be 'Sara', got '{chapters[1][1]}'")
        self.assertIn("odd-looking little girl", chapters[1][2], "Chapter 1 should contain expected content")

        # Verify chapter 2 is "A French Lesson"
        self.assertEqual(chapters[2][0], 2, "Third chapter should be Chapter 2")
        self.assertEqual(chapters[2][1], "A French Lesson", f"Chapter 2 title should be 'A French Lesson', got '{chapters[2][1]}'")

    def test_no_false_positive_with_chapter_pattern(self):
        """Test that Chapter X pattern doesn't get confused with standalone numbers in prose."""
        test_text = """The Project Gutenberg eBook of Test Book

*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***

Chapter 1

The First Chapter


This is the first chapter. It contains a sentence that ends with the number
1
on its own line, but this should not be detected as a chapter marker.

The text continues here with more content. Another paragraph mentions that
there were exactly
2
people in the room at that time.


Chapter 2

The Second Chapter


This is the second chapter with proper formatting.

*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect 2 chapters: Chapter 1 + Chapter 2
        # The standalone 1 and 2 in prose should NOT be detected
        # No Chapter 0 is created because the Gutenberg header is too short (<300 chars) and has no narrative content
        self.assertEqual(len(chapters), 2, f"Expected 2 chapters (no preface for short metadata), got {len(chapters)}")
        self.assertEqual(chapters[0][1], "The First Chapter", "Chapter 1 title should be 'The First Chapter'")
        self.assertEqual(chapters[1][1], "The Second Chapter", "Chapter 2 title should be 'The Second Chapter'")

    def test_no_false_positive_with_standalone_pattern(self):
        """Test that standalone number pattern doesn't match numbers in prose."""
        test_text = """The Project Gutenberg eBook of Test Book

*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***


1

The First Chapter


This is the first chapter. It contains a sentence that ends with the number
1
on its own line, but this should not be detected as a chapter marker because
there's no blank line before it.

The text continues here. Another paragraph mentions that
there were exactly
2
people in the room at that time. Again, no blank line before the 2.


2

The Second Chapter


This is the second chapter with proper formatting.

*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect only 2 chapters (using standalone number pattern with proper blank lines)
        # The embedded 1 and 2 in prose should NOT be detected (no blank lines before them)
        self.assertEqual(len(chapters), 2, f"Expected 2 chapters, got {len(chapters)}")
        self.assertEqual(chapters[0][1], "The First Chapter")
        self.assertEqual(chapters[1][1], "The Second Chapter")

    def test_requires_blank_lines_before(self):
        """Test that standalone numbers require 2+ blank lines before them."""
        test_text = """The Project Gutenberg eBook of Test Book

*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***

CONTENTS
1. First Chapter
2. Second Chapter


1

First Chapter


This is the first chapter.
Just one blank line before this:

2
This should NOT be detected as chapter 2 because there's only 1 blank line.


3


Third Chapter


This SHOULD be detected because there are 2+ blank lines before it.

*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect chapters 1 and 3, but NOT 2
        chapter_nums = [ch[0] for ch in chapters]
        self.assertIn(1, chapter_nums, "Should detect chapter 1")
        self.assertIn(3, chapter_nums, "Should detect chapter 3")
        self.assertNotIn(2, chapter_nums, "Should NOT detect chapter 2 (only 1 blank line before)")

    def test_only_applies_after_toc(self):
        """Test that standalone number pattern only applies after TOC ends."""
        test_text = """The Project Gutenberg eBook of Test Book

CONTENTS

1
First Chapter

2
Second Chapter



1

First Chapter


This is the actual first chapter content.


2

Second Chapter


This is the actual second chapter content.

*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect 2 chapters from the body (after TOC), not from TOC
        self.assertEqual(len(chapters), 2, f"Expected 2 chapters, got {len(chapters)}")

        # Verify content is from body, not TOC
        self.assertIn("actual first chapter", chapters[0][2], "Chapter 1 should contain body content")
        self.assertIn("actual second chapter", chapters[1][2], "Chapter 2 should contain body content")

    def test_reasonable_number_range(self):
        """Test that only reasonable chapter numbers (1-200) are accepted."""
        test_text = """The Project Gutenberg eBook of Test Book

*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***


1

Chapter One


This is chapter 1.


999

Not A Chapter


This number is too large (>200) so should not be detected as a chapter.


50

Chapter Fifty


This is chapter 50, which is reasonable.

*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***
"""

        # Extract chapters
        chapters, _ = self.generator.detect_chapters(test_text)

        # Should detect chapters 1 and 50, but NOT 999
        chapter_nums = [ch[0] for ch in chapters]
        self.assertIn(1, chapter_nums, "Should detect chapter 1")
        self.assertIn(50, chapter_nums, "Should detect chapter 50")
        self.assertNotIn(999, chapter_nums, "Should NOT detect chapter 999 (too large)")


if __name__ == '__main__':
    unittest.main()
