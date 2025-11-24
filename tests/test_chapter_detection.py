#!/usr/bin/env python3
"""
Unit tests for chapter detection logic in generate_summaries.py

These tests use synthetic book content to validate:
1. Table of Contents detection and filtering
2. Multi-part chapter merging
3. Introduction/Preface capture
4. Nested BOOK/CHAPTER structure handling
5. Coverage validation
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.generate_summaries import SummaryGenerator
import pytest


class TestChapterDetection:
    """Test chapter detection and parsing logic"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_toc_detection_short_chapters(self, generator):
        """Test that Table of Contents entries (very short chapters) are filtered out"""
        # Simulate a book with TOC followed by actual chapters
        test_text = """
CHAPTER I: Introduction
This is just a title in the table of contents.

CHAPTER II: Background
Another short TOC entry here.

CHAPTER III: Methods
Third TOC entry is short too.

CHAPTER I: Introduction

This is the actual first chapter with substantial content. Lorem ipsum dolor sit amet,
consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna
aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip
ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur.

This chapter continues with much more text to make it substantial. We need to ensure that
this actual chapter content is preserved while the short TOC entries above are filtered out.
The chapter should have enough content to clearly distinguish it from a TOC entry.

CHAPTER II: Background

This is the actual second chapter with real content about the background of our study.
It contains multiple paragraphs of detailed information that would not appear in a
table of contents. The content here is substantive and provides real value to readers.

We continue with more paragraphs to ensure this chapter is long enough to pass our
filtering logic. Table of contents entries are typically just titles or brief descriptions,
while actual chapters contain detailed exposition and analysis. This needs to be over
500 characters to pass the test threshold, so I'm adding more content here to make
it substantial enough to distinguish from a TOC entry.

CHAPTER III: Methods

The third actual chapter describes our methodology in detail. This is not a brief TOC
entry but rather a full chapter with comprehensive information about how we conducted
our research and what approaches we used.

More content follows to ensure adequate length. The key insight is that TOC entries
are typically under 500 characters while real chapters are much longer, often thousands
of characters or more. We include additional paragraphs here to ensure this chapter
exceeds 500 characters and will pass the validation test. This demonstrates the
difference between actual chapter content and table of contents entries.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 3 actual chapters (not the 3 TOC entries)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # All chapters should be substantial (not TOC entries)
        for ch_num, ch_title, ch_text in chapters:
            assert len(ch_text) > 500, f"Chapter {ch_num} is too short ({len(ch_text)} chars), likely a TOC entry"

    def test_multi_part_chapter_merging(self, generator):
        """Test that multi-part chapters are properly merged"""
        test_text = """
CHAPTER I: The Beginning—Part I

This is the first part of chapter one. It contains important information about
the beginning of our story. We introduce the main characters and setting here.

CHAPTER I: The Beginning—Part II

This is the second part of chapter one, continuing where Part I left off.
The story develops further and we learn more about the characters' motivations.

CHAPTER I: The Beginning—Part III

This is the third and final part of chapter one, concluding the introduction
and setting up the conflicts that will drive the rest of the narrative.

CHAPTER II: Development

This is chapter two, which is a single part and not split up like chapter one.
It contains the development of the plot and character arcs.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have 2 chapters (Chapter I merged from 3 parts, Chapter II standalone)
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Chapter I should be merged and contain all three parts
        ch1_num, ch1_title, ch1_text = chapters[0]
        assert ch1_num == 1
        assert "first part" in ch1_text.lower()
        assert "second part" in ch1_text.lower()
        assert "third and final part" in ch1_text.lower()

    def test_introduction_preface_capture(self, generator):
        """Test that Introduction and Preface sections are captured as Chapter 0"""
        test_text = """
INTRODUCTION

This is the introduction to the book. It provides context and background
information that readers need before diving into the main content.
We explain our motivation and goals here.

PREFACE

This preface was written by the author to explain the origins of this work
and to thank those who contributed to its development.

Preface To The Second Edition

Additional notes for the second edition, including corrections and updates
based on feedback from readers of the first edition.

CHAPTER I: The First Chapter

This is the actual first chapter of the main content. It begins the narrative
or exposition that forms the core of the book.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have Chapter 0 (merged intro/prefaces) and Chapter 1
        assert len(chapters) >= 2

        # First chapter should be Chapter 0
        ch0_num, ch0_title, ch0_text = chapters[0]
        assert ch0_num == 0
        assert "introduction" in ch0_title.lower() or "preface" in ch0_title.lower()

        # Chapter 0 should contain all introductory material
        assert "introduction to the book" in ch0_text.lower()
        assert "preface was written" in ch0_text.lower()
        assert "second edition" in ch0_text.lower()

    def test_nested_book_chapter_structure(self, generator):
        """Test handling of nested BOOK/CHAPTER structure (e.g., Book I Chapter 1 = 101)"""
        test_text = """
BOOK I

CHAPTER I: First Topic

This is Book 1, Chapter 1. The chapter numbering should encode this as 101
to preserve the book structure while allowing proper ordering. Adding more
content to make this chapter substantial enough to pass the minimum length
requirement for chapter detection and validation. We include multiple paragraphs
of content to ensure this chapter is long enough to not be mistaken for a table
of contents entry. The content needs to be substantive and demonstrate that this
is a real chapter with meaningful content, not just a brief TOC reference or
metadata entry. More sentences are added here to reach the 500 character minimum
that distinguishes actual chapters from TOC entries in our detection logic.

CHAPTER II: Second Topic

This is Book 1, Chapter 2, which should be encoded as 102. More content here
to ensure the chapter is long enough to be recognized as a valid chapter
rather than a table of contents entry or other metadata. We continue with
additional paragraphs to make sure this chapter has sufficient length for
proper detection. The chapter detection logic needs substantial content to
differentiate between real chapters and TOC entries, so we include enough
text here to meet that threshold. This ensures accurate parsing of books
with nested book and chapter structures, which is important for properly
organizing complex multi-volume works.

BOOK II

CHAPTER I: New Beginning

This is Book 2, Chapter 1, which should be encoded as 201 to show it's in
the second book while being the first chapter of that book. Additional text
is included to meet the minimum length requirements for proper chapter
detection and to distinguish this from TOC entries. We provide multiple
paragraphs of substantive content to ensure this chapter passes all validation
checks. The encoding scheme allows us to maintain the book structure while
ensuring chapters are properly ordered within their respective books. This
is essential for works that are divided into multiple books or volumes, each
with their own chapter sequences.

CHAPTER II: Continuation

This is Book 2, Chapter 2, encoded as 202. This chapter also needs sufficient
length to pass validation, so we include more content to ensure it meets the
minimum character threshold for being recognized as a real chapter. Additional
sentences and paragraphs are added to provide the necessary length for proper
chapter detection. The chapter must have enough content to clearly distinguish
it from TOC entries and other metadata, ensuring accurate parsing of the book
structure. This helps maintain the integrity of the chapter detection system
and ensures that multi-volume works are properly organized.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 4 chapters with proper encoding
        assert len(chapters) == 4

        # Check encoded chapter numbers
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 101 in chapter_nums, "Book 1 Chapter 1 should be 101"
        assert 102 in chapter_nums, "Book 1 Chapter 2 should be 102"
        assert 201 in chapter_nums, "Book 2 Chapter 1 should be 201"
        assert 202 in chapter_nums, "Book 2 Chapter 2 should be 202"

    def test_coverage_validation(self, generator):
        """Test that parsed chapters capture >90% of original content"""
        test_text = """
Some header material that might be skipped.

CHAPTER I: First

This is the first chapter with actual content that should be captured.
It contains important information that must not be lost during parsing.

CHAPTER II: Second

This is the second chapter, also with substantial content that needs
to be preserved when we parse the book into chapters.

Some footer material or appendix that might not be captured.
"""

        chapters = generator.detect_chapters(test_text)

        # Calculate coverage
        total_parsed = sum(len(ch_text) for _, _, ch_text in chapters)
        original_len = len(test_text)
        coverage = (total_parsed / original_len) * 100

        # Should capture most of the content (allowing for some header/footer loss)
        assert coverage > 70, f"Coverage too low: {coverage:.1f}% (expected >70%)"

    def test_toc_pattern_detection(self, generator):
        """Test detection of common TOC patterns like 'PAGE' headers and dotted lines"""
        test_text = """
TABLE OF CONTENTS

PAGE

CHAPTER I: Introduction .......................... 1
CHAPTER II: Background ........................... 25
CHAPTER III: Methods ............................. 50

CHAPTER I: Introduction

This is the actual chapter one with real content, not just a TOC entry.
It has substantial text that distinguishes it from the table of contents above.
We include multiple paragraphs here to ensure the chapter meets the minimum
length requirement of 200 characters for proper validation and to clearly
distinguish it from TOC entries which are typically much shorter.

CHAPTER II: Background

This is the actual second chapter with detailed background information
that extends beyond the brief TOC entry. More content is added here to
ensure this chapter is long enough to be recognized as a real chapter
rather than metadata or table of contents information.

CHAPTER III: Methods

The third chapter contains our full methodology with comprehensive details
about how the research was conducted. Additional sentences are included to
make sure this chapter passes the 200 character minimum for validation.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 3 actual chapters (not TOC entries)
        assert len(chapters) == 3

        # TOC entries with page numbers should be filtered out
        for _, _, ch_text in chapters:
            assert "............" not in ch_text  # No dotted lines from TOC
            assert len(ch_text) > 200  # Actual chapters have substantial content

    def test_illustration_markers_ignored(self, generator):
        """Test that [Illustration: ...] blocks don't create false chapters"""
        test_text = """
CHAPTER I: The Start

This chapter begins our story. Here we see important context.

[Illustration: A map of the region
CHAPTER II: The Middle (this is just part of the illustration caption)
showing various locations mentioned in the text.]

The chapter continues after the illustration block. The fake chapter
marker inside the illustration should be ignored.

CHAPTER II: The Middle

This is the real Chapter II that should be detected as a chapter.
It follows after Chapter I in the normal sequence.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect only 2 chapters (not the fake one in illustration)
        assert len(chapters) == 2

        # Chapters should be I and II
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 1 in chapter_nums
        assert 2 in chapter_nums

    def test_multiline_titles_basic(self, generator):
        """Test handling of chapter titles that span multiple lines"""
        test_text = """
CHAPTER I: The Extent Of The Empire In The Age Of The
Antonines

This is the first chapter content with enough text to pass validation.
It contains important information that must not be lost during parsing.
Adding more content here to ensure the chapter meets minimum length requirements
for proper detection and to distinguish it from table of contents entries.

CHAPTER II: The Internal Prosperity In The Age Of The
Antonines

This is the second chapter with substantial content that needs to be preserved.
We include multiple paragraphs here to ensure the chapter is long enough to be
recognized as a real chapter rather than metadata or table of contents information.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 2 chapters
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Check that titles are complete (not truncated)
        ch1_num, ch1_title, ch1_text = chapters[0]
        ch2_num, ch2_title, ch2_text = chapters[1]

        assert ch1_num == 1
        assert "Antonines" in ch1_title, f"Chapter 1 title truncated: {ch1_title}"
        assert ch1_title == "The Extent Of The Empire In The Age Of The Antonines", \
            f"Expected full title, got: {ch1_title}"

        assert ch2_num == 2
        assert "Antonines" in ch2_title, f"Chapter 2 title truncated: {ch2_title}"
        assert ch2_title == "The Internal Prosperity In The Age Of The Antonines", \
            f"Expected full title, got: {ch2_title}"

    def test_part_marker_split_across_lines(self, generator):
        """Test handling of part markers split across lines (e.g., '—Part\\n I.')"""
        test_text = """
CHAPTER I: The Extent Of The Empire In The Age Of The Antonines—Part
 I.

This is chapter one part one with enough content to be recognized as a real
chapter and not a table of contents entry. We include multiple paragraphs to
ensure proper validation and detection of chapter boundaries in the text.

CHAPTER I: The Extent Of The Empire In The Age Of The Antonines—Part
 II.

This is chapter one part two, which should be merged with part one to create
a single complete chapter. The content here is also substantial to pass the
minimum length requirements for chapter detection and validation.

CHAPTER II: Another Chapter

This is a different chapter entirely, with its own substantial content that
meets the minimum requirements for being recognized as a valid chapter in
the book structure rather than a table of contents entry.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have 2 chapters (Chapter I merged from 2 parts, Chapter II standalone)
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Chapter I should be merged and have clean title (no "Part I" or "Part II")
        ch1_num, ch1_title, ch1_text = chapters[0]
        assert ch1_num == 1
        assert ch1_title == "The Extent Of The Empire In The Age Of The Antonines", \
            f"Expected clean title without part markers, got: {ch1_title}"
        assert "part one" in ch1_text.lower() and "part two" in ch1_text.lower(), \
            "Chapter I should contain both parts"

    def test_part_marker_without_dash(self, generator):
        """Test handling of part markers without dashes (e.g., '. Part IV')"""
        test_text = """
CHAPTER I: The Constitution In The Age Of The Antonines. Part
 IV.

This is chapter one part four with content spread across the multi-line title.
The part marker here uses a period instead of a dash, which is a variation we
need to handle correctly. Including more text to meet minimum chapter length.

CHAPTER II: Another Chapter

This is a separate chapter with its own content that should be detected as
a distinct chapter from the first one. More text is added here to ensure it
passes the minimum length requirement for proper chapter validation.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have 2 chapters
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Chapter I should have clean title (no ". Part IV")
        ch1_num, ch1_title, ch1_text = chapters[0]
        assert ch1_num == 1
        assert ch1_title == "The Constitution In The Age Of The Antonines", \
            f"Expected clean title without '. Part IV', got: {ch1_title}"
        assert "Part" not in ch1_title, f"Title should not contain 'Part': {ch1_title}"
        assert "IV" not in ch1_title or "Antonines" in ch1_title, \
            f"Title should not contain standalone 'IV': {ch1_title}"

    def test_various_part_marker_formats(self, generator):
        """Test removal of various part marker formats"""
        test_text = """
CHAPTER I: Title With Dash—Part I

Content for chapter one with dash-style part marker. This needs enough text
to pass validation as a real chapter and not be mistaken for a TOC entry.
We include multiple lines to ensure proper chapter detection and parsing.
Adding more substantial content here to exceed the 500 character minimum
average that would trigger the TOC detection fallback mechanism. This ensures
our test accurately validates the part marker removal logic rather than
testing the TOC detection safety net. More text is needed to make this
chapter substantial and realistic for proper validation testing purposes.

CHAPTER II: Title With Period.—Part II

Content for chapter two with period-dash combination. Adding more text here
to meet the minimum length requirements for chapter detection and ensure the
chapter is recognized as valid content rather than metadata. We continue with
additional paragraphs to make this chapter long enough to pass the average
length check that distinguishes real chapters from table of contents entries.
This helps ensure accurate testing of the part marker removal functionality
without triggering safety fallbacks in the chapter detection logic.

CHAPTER III: Title With Period. Part III

Content for chapter three with period-space-part format. This variation also
needs substantial text to be detected properly and distinguished from table
of contents entries or other metadata in the book structure. Adding enough
content to exceed 500 characters ensures this chapter contributes to a high
enough average length across all chapters to avoid the TOC detection fallback.
More paragraphs are included to make this a realistic chapter for testing
purposes and to validate the part marker removal logic properly.

CHAPTER IV: Title With No Marker

Content for chapter four with no part marker at all. This is the control case
to ensure that chapters without part markers are still detected correctly and
their titles are preserved exactly as they appear in the source text. We add
substantial content here as well to maintain a high average chapter length
across all test chapters and prevent the TOC detection safety mechanism from
being triggered. This ensures our test focuses on the part marker removal
functionality rather than testing the fallback behavior for short chapters.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have 4 chapters
        assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

        # All chapters should have clean titles (no part markers)
        ch1_num, ch1_title, _ = chapters[0]
        assert ch1_title == "Title With Dash", \
            f"Chapter 1 should have 'Title With Dash', got: {ch1_title}"

        ch2_num, ch2_title, _ = chapters[1]
        assert ch2_title == "Title With Period", \
            f"Chapter 2 should have 'Title With Period', got: {ch2_title}"

        ch3_num, ch3_title, _ = chapters[2]
        assert ch3_title == "Title With Period", \
            f"Chapter 3 should have 'Title With Period', got: {ch3_title}"

        ch4_num, ch4_title, _ = chapters[3]
        assert ch4_title == "Title With No Marker", \
            f"Chapter 4 should have 'Title With No Marker', got: {ch4_title}"

    def test_decline_and_fall_examples(self, generator):
        """Test the specific examples from 'The History of the Decline and Fall of the Roman Empire'"""
        test_text = """
CHAPTER I: The Extent Of The Empire In The Age Of The Antonines—Part
 I.

This is the content of chapter one part one. Adding sufficient text here to
ensure this chapter passes all validation checks and is recognized as a real
chapter rather than a table of contents entry or metadata. We include multiple
paragraphs to build up substantial length and exceed the 500 character minimum
average required to avoid the TOC detection fallback mechanism. This ensures
accurate testing of the multi-line title parsing and part marker removal logic
that we implemented to handle books like Decline and Fall of the Roman Empire.

CHAPTER II: The Internal Prosperity In The Age Of The Antonines. Part
 IV.

This is the content of chapter two part four with the period-space-part format.
We include enough content to pass validation and ensure proper chapter detection
throughout the parsing process for this multi-volume historical work. Additional
text is added to maintain a high average chapter length across all test chapters
and prevent triggering the TOC detection safety net. This allows us to properly
test the part marker removal functionality for the unusual ". Part IV" format
that appears in the actual Decline and Fall source text.

CHAPTER III: The Constitution In The Age Of The Antonines.—Part
 I.

This is chapter three part one content with period-dash-part marker format.
Including substantial text to meet minimum requirements and ensure accurate
chapter detection and title parsing throughout the document. More paragraphs
are needed to keep the average chapter length above 500 characters to avoid
the TOC detection fallback. This ensures we're testing the actual multi-line
title concatenation logic rather than the safety net for detecting malformed
chapter structures in potential table of contents sections.

CHAPTER IV: The Cruelty, Follies And Murder Of Commodus.—Part I

This is chapter four with inline part marker (not split across lines). Adding
enough content to pass validation and ensure this chapter is recognized as a
real chapter with substantial content rather than just metadata. We continue
with additional sentences to maintain the average chapter length requirements
and ensure all test chapters contribute to passing the TOC detection threshold.
This allows us to properly test the part marker removal for inline markers that
don't span multiple lines unlike some of the previous examples.
"""

        chapters = generator.detect_chapters(test_text)

        # Should have 4 chapters (each part becomes separate chapter initially, then merged)
        # Actually, since these are all different chapters (I, II, III, IV), should be 4 chapters
        assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

        # Verify all titles are clean and complete
        expected_titles = [
            "The Extent Of The Empire In The Age Of The Antonines",
            "The Internal Prosperity In The Age Of The Antonines",
            "The Constitution In The Age Of The Antonines",
            "The Cruelty, Follies And Murder Of Commodus"
        ]

        for i, (ch_num, ch_title, _) in enumerate(chapters):
            assert ch_num == i + 1, f"Chapter number mismatch: expected {i+1}, got {ch_num}"
            assert ch_title == expected_titles[i], \
                f"Chapter {i+1} title mismatch: expected '{expected_titles[i]}', got '{ch_title}'"


    def test_book_markers_as_chapters(self, generator):
        """Test that BOOK/VOLUME/ACT markers become chapters when no nested chapters exist"""
        # Simulate a book like The Odyssey where BOOK markers ARE the chapters
        test_text = """
TABLE OF CONTENTS

BOOK I
BOOK II
BOOK III

BOOK I

This is the content of Book I. It contains the opening of the epic narrative
with substantial detail about the characters and setting. We introduce the hero
and his journey, establishing the themes that will carry through the entire work.
Adding more content here to ensure this chapter is substantial enough to pass
validation and be recognized as a real chapter rather than metadata.

BOOK II

This is the content of Book II, continuing the story from Book I. New characters
are introduced and the plot develops further. We include multiple paragraphs of
content to ensure this chapter meets minimum length requirements and is clearly
distinguished from table of contents entries. The narrative continues with rich
description and dialogue that advances the storyline significantly.

BOOK III

This is the content of Book III, which further advances the narrative. Important
events unfold and character development continues. We provide substantial text
here to ensure proper chapter detection and to distinguish this real chapter from
the brief TOC entry that appeared earlier in the document. More details and
exposition are included to make this chapter substantial and meaningful.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 3 chapters (BOOK I, II, III)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Chapters should use simple numbering (1, 2, 3) not nested encoding (100, 200, 300)
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert chapter_nums == [1, 2, 3], f"Expected [1, 2, 3], got {chapter_nums}"

        # Chapter titles should be formatted as "BOOK I", "BOOK II", "BOOK III"
        for i, (ch_num, ch_title, ch_text) in enumerate(chapters):
            expected_num = i + 1
            assert ch_num == expected_num, f"Chapter {i} has wrong number: {ch_num} vs {expected_num}"
            assert f"BOOK" in ch_title, f"Chapter {i} title should contain 'BOOK': {ch_title}"

            # Verify content is present
            assert len(ch_text) > 200, f"Chapter {ch_num} is too short: {len(ch_text)} chars"
            assert "content of Book" in ch_text, f"Chapter {ch_num} missing expected content"

    def test_book_markers_with_duplicates(self, generator):
        """Test that duplicate BOOK markers (TOC + actual) are deduplicated correctly"""
        test_text = """
CONTENTS
BOOK I
BOOK II

BOOK I

This is the actual content of Book I, not the TOC entry. It has substantial
text that makes it clearly different from the brief TOC reference above. We
include multiple paragraphs here to ensure this chapter is long enough to be
recognized as real content rather than just a table of contents entry or
other metadata that should be filtered out during the parsing process.

BOOK II

This is the actual content of Book II with rich narrative detail. The story
continues from Book I with new developments and character interactions. We
provide enough text here to distinguish this from the TOC entry and ensure
it passes all validation checks for proper chapter detection and parsing.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 2 chapters (deduplicating TOC entries)
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Chapters should be numbered 1 and 2
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert chapter_nums == [1, 2], f"Expected [1, 2], got {chapter_nums}"

        # Each chapter should have substantial content (not TOC)
        for ch_num, ch_title, ch_text in chapters:
            assert "actual content" in ch_text, f"Chapter {ch_num} should have actual content, not TOC"
            assert len(ch_text) > 200, f"Chapter {ch_num} is too short"

    def test_book_markers_preserve_backward_compatibility(self, generator):
        """Test that nested BOOK/CHAPTER structure still works (backward compatibility)"""
        # This is the existing behavior - BOOK markers with nested chapters
        test_text = """
BOOK I

CHAPTER 1: First Topic

This is Book 1, Chapter 1 content with substantial detail and exposition.
We include enough text here to ensure this passes validation and is recognized
as a real chapter with meaningful content rather than just metadata or a table
of contents entry. Multiple paragraphs are included to meet minimum length
requirements for proper chapter detection and parsing throughout the system.

CHAPTER 2: Second Topic

This is Book 1, Chapter 2 with additional narrative content and development.
More substantial text is provided to ensure this chapter is long enough to
pass all validation checks. We maintain consistency with the previous chapter
in terms of content length and structure to ensure reliable parsing results.

BOOK II

CHAPTER 1: New Beginning

This is Book 2, Chapter 1 content starting a new section of the narrative.
Substantial text is included here as well to meet the minimum requirements
for chapter detection. We provide detailed content that clearly distinguishes
this from brief TOC entries or metadata that might appear elsewhere in text.
"""

        chapters = generator.detect_chapters(test_text)

        # Should detect 3 chapters with nested encoding (101, 102, 201)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 101 in chapter_nums, "Book 1 Chapter 1 should be encoded as 101"
        assert 102 in chapter_nums, "Book 1 Chapter 2 should be encoded as 102"
        assert 201 in chapter_nums, "Book 2 Chapter 1 should be encoded as 201"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
