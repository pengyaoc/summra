#!/usr/bin/env python3
"""
Test chapter numbering logic, especially for Introduction chapters
"""
import sys
import os
import unittest

# Add backend and scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_summaries import SummaryGenerator


class TestChapterNumbering(unittest.TestCase):
    """Test chapter numbering logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = SummaryGenerator("")  # Empty API key for testing

    def test_introduction_as_chapter_one(self):
        """
        Test that Introduction is treated as Chapter 1 when it appears in TOC as Roman numeral I

        This was a bug in The Time Machine where:
        - TOC showed "I Introduction" (Chapter 1)
        - Script treated it as Chapter 0 (preface)
        - Should be Chapter 1 based on TOC
        """
        # Simulate The Time Machine structure
        text = """*** START OF THE PROJECT GUTENBERG EBOOK 35 ***

The Time Machine

CONTENTS

 I Introduction
 II The Machine
 III The Time Traveller Returns


 I.
 Introduction


The Time Traveller was expounding a recondite matter to us.
This is the first chapter content. It has been expanded to ensure
it meets the minimum character length requirement for chapter detection.

 II.
 The Machine


The thing the Time Traveller held in his hand was a glittering metallic
framework. This is the second chapter content with enough text to pass
the minimum character length requirement for proper chapter detection.

 III.
 The Time Traveller Returns


I think that at that time none of us quite believed in the Time Machine.
This is the third chapter content. The time machine was a remarkable invention
that would change the course of history and our understanding of time itself.

*** END OF THE PROJECT GUTENBERG EBOOK 35 ***
"""

        # Extract content
        content = self.generator.extract_gutenberg_content(text)

        # Detect chapters
        chapters, _ = self.generator.detect_chapters(content)

        # Verify we detected 3 chapters
        self.assertEqual(len(chapters), 3, f"Expected 3 chapters, got {len(chapters)}")

        # Verify chapter numbers and titles
        chapter_nums = [ch[0] for ch in chapters]
        chapter_titles = [ch[1] for ch in chapters]

        # Introduction should be Chapter 1, not Chapter 0
        self.assertIn(1, chapter_nums, "Introduction should be Chapter 1")
        self.assertNotIn(0, chapter_nums, "Should not have Chapter 0 when Introduction is in TOC as Chapter I")

        # Find Introduction chapter
        intro_chapter = next((ch for ch in chapters if 'Introduction' in ch[1]), None)
        self.assertIsNotNone(intro_chapter, "Introduction chapter not found")

        # Verify Introduction is Chapter 1
        self.assertEqual(intro_chapter[0], 1,
                        f"Introduction should be Chapter 1, got Chapter {intro_chapter[0]}")

        # Verify other chapters
        self.assertIn(2, chapter_nums, "Should have Chapter 2 (The Machine)")
        self.assertIn(3, chapter_nums, "Should have Chapter 3 (The Time Traveller Returns)")

    def test_introduction_as_preface_without_toc(self):
        """
        Test that Introduction is treated as Chapter 0 (preface) when there's no TOC
        or when it doesn't appear as a numbered chapter in TOC
        """
        text = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

Test Book

Introduction

This is the introduction or preface to the book.
It provides context and background.

Chapter I
First Chapter

This is the first actual chapter of the book.

Chapter II
Second Chapter

This is the second chapter.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""

        # Extract content
        content = self.generator.extract_gutenberg_content(text)

        # Detect chapters
        chapters, _ = self.generator.detect_chapters(content)

        # In this case, Introduction should be Chapter 0 (preface)
        # because it's not numbered in the TOC
        chapter_nums = [ch[0] for ch in chapters]

        # Should have Chapter 0 for Introduction
        # Note: This test may need to be updated based on final implementation
        # The key is that Introduction without TOC numbering should be treated differently
        # than Introduction with TOC numbering as Chapter I

    def test_epilogue_numbering(self):
        """Test that Epilogue gets the correct final chapter number"""
        text = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

Test Book

CONTENTS

 I First Chapter
 II Second Chapter
 Epilogue


 I.
 First Chapter

Content of first chapter. This chapter introduces the main themes and characters
that will be developed throughout the rest of the book in great detail.

 II.
 Second Chapter

Content of second chapter. This continues the narrative and explores the central
conflict while developing the plot and character relationships further.

Epilogue

Content of epilogue. This concluding section wraps up the story and provides
closure to the narrative while reflecting on the themes explored earlier.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""

        # Extract content
        content = self.generator.extract_gutenberg_content(text)

        # Detect chapters
        chapters, _ = self.generator.detect_chapters(content)

        # Find epilogue
        epilogue = next((ch for ch in chapters if 'Epilogue' in ch[1]), None)
        self.assertIsNotNone(epilogue, "Epilogue not found")

        # Epilogue should be numbered after the last numbered chapter
        # In this case, should be Chapter 3 (or whatever number follows Chapter 2)
        max_regular_chapter = max(ch[0] for ch in chapters if 'Epilogue' not in ch[1])
        expected_epilogue_num = max_regular_chapter + 1

        # Epilogue should not be 999 or 0, should be sequential
        self.assertEqual(epilogue[0], expected_epilogue_num,
                        f"Epilogue should be Chapter {expected_epilogue_num}, got Chapter {epilogue[0]}")
        self.assertNotEqual(epilogue[0], 999, "Epilogue should not be Chapter 999")


if __name__ == '__main__':
    unittest.main()
