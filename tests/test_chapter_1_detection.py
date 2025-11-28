"""
Unit tests for Chapter 1 detection issue.

This test ensures that books with Chapter 1 as the first chapter
are correctly detected and not incorrectly labeled as "Preface".
"""

import unittest
import sys
import os

# Add parent directory to path to import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_summaries import SummaryGenerator


class TestChapter1Detection(unittest.TestCase):
    """Test that Chapter 1 is correctly detected and not labeled as Preface."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a dummy API key for testing (we won't make actual API calls)
        self.generator = SummaryGenerator(api_key="test-key-dummy")

    def test_enchanted_april_chapter_1(self):
        """Test that The Enchanted April correctly detects Chapter 1."""
        # Sample text from The Enchanted April with TOC and Chapter 1
        test_text = """The Project Gutenberg eBook of The Enchanted April

Title: The Enchanted April
Author: Elizabeth Von Arnim

*** START OF THE PROJECT GUTENBERG EBOOK THE ENCHANTED APRIL ***

The Enchanted April
by Elizabeth Von Arnim

Contents

 Chapter 1
 Chapter 2
 Chapter 3
 Chapter 4




Chapter 1


It began in a Woman's Club in London on a February afternoon—an
uncomfortable club, and a miserable afternoon—when Mrs. Wilkins, who
had come down from Hampstead to shop and had lunched at her club, took
up _The Times_ from the table in the smoking-room, and running her
listless eye down the Agony Column saw this:

  To Those who Appreciate Wistaria and Sunshine. Small mediaeval
    Italian Castle on the shores of the Mediterranean to be Let
    Furnished for the month of April. Necessary servants remain. Z,
    Box 1000, _The Times_.

That was its conception; yet, as in the case of many another, the
conceiver was unaware of it at the moment.

So entirely unaware was Mrs. Wilkins that her April for that year had
then and there been settled for her that she dropped the newspaper with
a gesture that was both irritated and resigned.


Chapter 2


The advertisement had been worded with care. It was simple but
effective. Mrs. Wilkins read it through twice, and the second time
she read it she felt something stir in her heart.

A small medieval castle on the shores of the Mediterranean. What could
be more romantic? She had always longed to go to Italy. The very word
Italy made her think of sunshine and beauty.


Chapter 3


Mrs. Arbuthnot was sitting in her drawing-room when Mrs. Wilkins
called on her. She was a woman of about forty, with a serious face
and kind eyes.

"I have something to show you," said Mrs. Wilkins, her eyes shining
with excitement as she handed over the newspaper.

Mrs. Arbuthnot read the advertisement carefully, and then looked up
at Mrs. Wilkins with a puzzled expression.

*** END OF THE PROJECT GUTENBERG EBOOK THE ENCHANTED APRIL ***
"""

        # Extract chapters using the generator's detect_chapters method
        chapters, _ = self.generator.detect_chapters(test_text)

        # Verify we detected 3 chapters
        self.assertEqual(len(chapters), 3, f"Expected 3 chapters, got {len(chapters)}")

        # Verify Chapter 1 is correctly numbered (not Chapter 0)
        chapter_numbers = [ch[0] for ch in chapters]
        self.assertIn(1, chapter_numbers, "Chapter 1 should be detected")
        self.assertIn(2, chapter_numbers, "Chapter 2 should be detected")
        self.assertIn(3, chapter_numbers, "Chapter 3 should be detected")

        # Verify no Chapter 0 (Preface) was created
        self.assertNotIn(0, chapter_numbers, "Chapter 0 (Preface) should not be created when Chapter 1 exists")

        # Verify Chapter 1 has the correct title
        chapter_1 = [ch for ch in chapters if ch[0] == 1][0]
        chapter_1_num, chapter_1_title, chapter_1_text = chapter_1

        self.assertEqual(chapter_1_num, 1, "First chapter should be numbered 1")
        self.assertEqual(chapter_1_title, "Chapter 1", "First chapter should be titled 'Chapter 1'")
        self.assertIn("Woman's Club in London", chapter_1_text, "Chapter 1 should contain correct content")

    def test_no_preface_when_chapter_1_exists(self):
        """Test that no Preface (Chapter 0) is created when Chapter 1 exists in TOC."""
        test_text = """
Contents

 Chapter 1
 Chapter 2


Chapter 1

This is the content of chapter 1. It should not be labeled as a preface.
This chapter has enough content to meet the minimum threshold for chapter detection
and ensure it is properly recognized as a numbered chapter rather than introductory
material that would be grouped into a preface section.


Chapter 2

This is the content of chapter 2. It also has sufficient content for proper detection.
This ensures both chapters are detected correctly without being filtered out due to
length restrictions. We need realistic chapter lengths to properly test the detection
logic and ensure the code works as expected in real-world scenarios.
"""

        chapters, _ = self.generator.detect_chapters(test_text)
        chapter_numbers = [ch[0] for ch in chapters]

        # Should have Chapter 1 and Chapter 2, but NOT Chapter 0
        self.assertEqual(len(chapters), 2, f"Expected 2 chapters, got {len(chapters)}")
        self.assertIn(1, chapter_numbers, "Should have Chapter 1")
        self.assertIn(2, chapter_numbers, "Should have Chapter 2")
        self.assertNotIn(0, chapter_numbers, "Should NOT have Chapter 0 when Chapter 1 exists")


if __name__ == '__main__':
    unittest.main()
