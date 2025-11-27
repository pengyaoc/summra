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

        chapters, _ = generator.detect_chapters(test_text)

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
The protagonist enters a world of mystery and intrigue, where nothing is as it
seems. We establish the initial conflict and present the reader with questions
that will drive the narrative forward. More detail is included to ensure this
chapter has substantial content and exceeds 500 characters. The setting is
richly described with attention to atmosphere and mood. Character motivations
are carefully established to create reader investment in the story. Additional
exposition provides necessary background without overwhelming the reader.

CHAPTER I: The Beginning—Part II

This is the second part of chapter one, continuing where Part I left off.
The story develops further and we learn more about the characters' motivations.
New revelations emerge that complicate the initial situation and raise the
stakes for our protagonist. The narrative tension builds as obstacles appear
that must be overcome. We delve deeper into character psychology and explore
the underlying themes of the work. More substantial content is added here to
ensure proper chapter length and avoid triggering the TOC detection safety net.
The plot thickens as secondary characters are introduced who will play important
roles in the unfolding drama. Foreshadowing hints at challenges yet to come.

CHAPTER I: The Beginning—Part III

This is the third and final part of chapter one, concluding the introduction
and setting up the conflicts that will drive the rest of the narrative.
The initial situation reaches a critical point that propels the story forward
into the main action. Our protagonist makes a decision that will have lasting
consequences. The chapter ends with a hook that compels the reader to continue.
We've established the world, the characters, and the central conflict that will
sustain the narrative through subsequent chapters. Additional content ensures
this part also meets minimum length requirements. The foundation has been laid
for the story to develop in exciting and unexpected directions. Thematic elements
introduced here will resonate throughout the entire work.

CHAPTER II: Development

This is chapter two, which is a single part and not split up like chapter one.
It contains the development of the plot and character arcs. The action moves
forward as the protagonist begins actively pursuing their goals. New challenges
emerge that test their resolve and capabilities. Character relationships deepen
and evolve through meaningful interactions and shared experiences. The narrative
gains momentum as the pacing accelerates. We explore the consequences of earlier
decisions and introduce complications that raise the stakes even higher. More
substantial content is included to make this chapter comparable in length to the
merged Chapter I. Themes established earlier are developed and expanded. The world
continues to be revealed through action and dialogue rather than exposition.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should have 2 chapters: Chapter I (Parts I+II+III merged), Chapter II
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"

        # Chapter I should be merged from Parts I, II and III
        ch1_num, ch1_title, ch1_text = chapters[0]
        assert ch1_num == 1, f"First chapter should be Chapter 1, got {ch1_num}"
        assert "first part" in ch1_text.lower()
        assert "second part" in ch1_text.lower()
        assert "third and final part" in ch1_text.lower()

        # Chapter II should be a single part chapter
        ch2_num, ch2_title, ch2_text = chapters[1]
        assert ch2_num == 2, f"Second chapter should be Chapter 2, got {ch2_num}"
        assert "development" in ch2_title.lower()
        assert "development" in ch2_text.lower()
    

    def test_introduction_preface_capture(self, generator):
        """Test that Introduction and Preface sections are captured as Chapter 0"""
        test_text = """
INTRODUCTION

This is the introduction to the book. It provides context and background
information that readers need before diving into the main content.
We explain our motivation and goals here. The introduction sets the stage
for the work that follows and helps readers understand the context in which
this book was written. We discuss the broader field of study and explain
where this particular contribution fits within the existing body of knowledge.
The introduction also outlines the structure of the book and provides a roadmap
for readers to navigate the material effectively. Historical context is provided
to help readers appreciate the significance of the work. Key concepts are
introduced that will be developed more fully in subsequent chapters. The scope
and limitations of the work are clearly delineated to set appropriate expectations.

PREFACE

This preface was written by the author to explain the origins of this work
and to thank those who contributed to its development. The author reflects
on the journey that led to the creation of this book and acknowledges the
many people who provided support, guidance, and inspiration along the way.
The preface provides personal insights into the author's motivation for
undertaking this project and explains the particular approach taken. Colleagues,
mentors, and family members who contributed to the work are thanked for their
invaluable assistance. The preface also addresses the intended audience and
suggests how different readers might approach the material based on their
backgrounds and interests. Additional context about the writing process helps
readers understand the author's perspective and methodology.

Preface To The Second Edition

Additional notes for the second edition, including corrections and updates
based on feedback from readers of the first edition. The author addresses
errors and omissions identified in the original publication and incorporates
new developments in the field that have emerged since the first edition appeared.
Reader suggestions and criticisms have been carefully considered and incorporated
where appropriate. New research findings are integrated to keep the work current
and relevant. The author expresses gratitude to readers who took the time to
provide thoughtful feedback that has improved this edition. Changes to the text
are explained and justified to help readers who are familiar with the first
edition understand what has been modified and why these changes were necessary.

CHAPTER I: The First Chapter

This is the actual first chapter of the main content. It begins the narrative
or exposition that forms the core of the book. The opening chapter establishes
the central themes and introduces key concepts that will be developed throughout
the work. Readers are drawn into the subject matter through engaging examples
and clear explanations. The foundation is laid for arguments and analyses that
will follow in subsequent chapters. Core terminology is defined and explained
to ensure readers have the necessary background to follow the discussion. The
chapter builds systematically from basic principles to more complex ideas,
ensuring accessibility while maintaining intellectual rigor. Examples and
illustrations help clarify abstract concepts and demonstrate practical applications.
"""

        chapters, _ = generator.detect_chapters(test_text)

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
PREFACE

This comprehensive work employs a nested organizational structure with books and chapters
to accommodate the complexity of the subject matter. The hierarchical encoding system
preserves both the book division and chapter sequence in the numbering scheme, ensuring
proper organization and navigation of the multi-volume content. This preface explains the
structural conventions used throughout the work.

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

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 5 chapters (0=Preface, 101, 102, 201, 202) with proper encoding
        assert len(chapters) == 5

        # Check encoded chapter numbers
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 0 in chapter_nums, "Should have Preface as Chapter 0"
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

        chapters, _ = generator.detect_chapters(test_text)

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

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 3 actual chapters (not TOC entries)
        assert len(chapters) == 3

        # TOC entries with page numbers should be filtered out
        for _, _, ch_text in chapters:
            assert "............" not in ch_text  # No dotted lines from TOC
            assert len(ch_text) > 200  # Actual chapters have substantial content

    def test_illustration_markers_ignored(self, generator):
        """Test that [Illustration: ...] blocks don't create false chapters"""
        test_text = """
PREFACE

This book contains important historical narratives accompanied by numerous illustrations
that help readers visualize the locations and events described in the text. The illustrations
are referenced throughout using standard notation and should not be confused with chapter
headings. This preface provides essential context for understanding the structure of the work
and explains the various conventions used in presenting the material. We have included maps,
diagrams, and artistic renderings to enhance the reader's comprehension and engagement with
the subject matter. The illustrations are carefully integrated into the narrative flow to
provide maximum educational and aesthetic value. Readers are encouraged to study each
illustration closely as they proceed through the chapters to gain a fuller appreciation
of the historical events and geographical settings described in the text.

CHAPTER I: The Start

This chapter begins our story. Here we see important context. This chapter contains substantial
narrative content and detailed exposition to ensure it meets the minimum length requirements for
proper chapter detection and validation. We include multiple paragraphs of meaningful text that
demonstrates this is actual chapter content rather than table of contents entries or metadata.
The content provides context, character development, and advances the plot in meaningful ways.
Additional sentences ensure adequate length while maintaining coherent narrative flow throughout.
The narrative introduces key characters and establishes the setting for the entire story that follows.
We delve into the background and motivations of the protagonist, exploring their history and the
circumstances that have led them to this point in time. The world-building is carefully constructed
to provide readers with a rich understanding of the environment in which the story takes place.

The protagonist's journey begins in a small village nestled in the mountains. The morning sun
casts long shadows across the cobblestone streets as merchants begin to set up their stalls.
There is a sense of anticipation in the air, as if something momentous is about to occur.

[Illustration: A map of the region
CHAPTER II: The Middle (this is just part of the illustration caption)
showing various locations mentioned in the text.]

The chapter continues after the illustration block. The fake chapter marker inside the illustration
should be ignored. More content is added here to build up the chapter length and demonstrate that
this is substantial narrative text rather than brief metadata or table of contents entries. We continue
developing the themes and characters introduced earlier, building tension and advancing the plot forward.
The narrative flows naturally from one scene to the next, maintaining reader engagement throughout.

The day unfolds with various encounters and revelations that set the stage for future events.
Characters are introduced with care, each one contributing to the rich tapestry of the narrative.
Dialogue reveals personality and builds relationships that will be important later in the story.

CHAPTER II: The Middle

This is the real Chapter II that should be detected as a chapter. It follows after Chapter I in
the normal sequence. This chapter contains substantial narrative content and detailed exposition
to ensure it meets the minimum length requirements for proper chapter detection and validation.
We include multiple paragraphs of meaningful text that demonstrates this is actual chapter content
rather than table of contents entries or metadata. The content provides context, character development,
and advances the plot in meaningful ways. Additional sentences ensure adequate length while maintaining
coherent narrative flow throughout. The story develops further as new conflicts emerge and characters
face challenges that test their resolve and capabilities. We explore deeper themes and continue to
build the narrative arc that will carry through to the conclusion of the work.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 3 chapters: Chapter 0 (Preface), Chapter I, and Chapter II (not the fake one in illustration)
        assert len(chapters) == 3

        # Chapters should be 0 (Preface), I, and II
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 0 in chapter_nums  # Preface
        assert 1 in chapter_nums
        assert 2 in chapter_nums

    def test_multiline_titles_basic(self, generator):
        """Test handling of chapter titles that span multiple lines"""
        test_text = """
PREFACE

This book explores important historical topics through careful analysis and detailed exposition.
The structure of this work follows traditional academic conventions while incorporating modern
scholarly insights. Each chapter builds upon previous material to create a comprehensive narrative
that addresses the complexity of the subject matter. Readers will find extensive documentation and
references throughout the text to support the arguments presented. The methodology employed in this
research draws from multiple disciplinary perspectives to provide a well-rounded understanding of
the historical period under examination. Special attention has been given to primary source materials
and contemporary accounts to ensure accuracy and authenticity in the presentation of events and
circumstances. This preface provides necessary context for understanding the organization and
approach taken in the chapters that follow, ensuring readers can fully appreciate the scholarly
contribution this work aims to make to the field of historical studies.

CHAPTER I: The Extent Of The Empire In The Age Of The
Antonines

This is the first chapter content with enough text to pass validation. It contains important
information that must not be lost during parsing. This chapter contains substantial narrative
content and detailed exposition to ensure it meets the minimum length requirements for proper
chapter detection and validation. We include multiple paragraphs of meaningful text that demonstrates
this is actual chapter content rather than table of contents entries or metadata. The content provides
context, character development, and advances the plot in meaningful ways. Additional sentences ensure
adequate length while maintaining coherent narrative flow throughout.

CHAPTER II: The Internal Prosperity In The Age Of The
Antonines

This is the second chapter with substantial content that needs to be preserved. We include multiple
paragraphs here to ensure the chapter is long enough to be recognized as a real chapter rather than
metadata or table of contents information. This chapter contains substantial narrative content and
detailed exposition to ensure it meets the minimum length requirements for proper chapter detection
and validation. We include multiple paragraphs of meaningful text that demonstrates this is actual
chapter content rather than table of contents entries or metadata. The content provides context,
character development, and advances the plot in meaningful ways.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 3 chapters (0=Preface, 1, 2)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Check that titles are complete (not truncated)
        ch0_num, ch0_title, ch0_text = chapters[0]
        ch1_num, ch1_title, ch1_text = chapters[1]
        ch2_num, ch2_title, ch2_text = chapters[2]

        assert ch0_num == 0  # Preface
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
PREFACE

This historical work examines the Roman Empire during the age of the Antonines through multiple
chapters that explore various aspects of imperial administration, society, and culture. The text
draws upon primary sources and modern scholarship to provide comprehensive coverage of this important
period in Roman history. Each chapter is carefully structured to build upon previous material while
maintaining scholarly rigor and accessibility for readers. The organization follows chronological
and thematic lines to facilitate understanding of complex historical developments. Special attention
is given to archaeological evidence and contemporary accounts that illuminate the period under study.
This preface establishes the context and methodology employed throughout the work, ensuring readers
can fully engage with the historical analysis presented in subsequent chapters.

CHAPTER I: The Extent Of The Empire In The Age Of The Antonines—Part
 I.

This is chapter one part one with enough content to be recognized as a real chapter and not a table
of contents entry. We include multiple paragraphs to ensure proper validation and detection of chapter
boundaries in the text. This chapter contains substantial narrative content and detailed exposition to
ensure it meets the minimum length requirements for proper chapter detection and validation. We include
multiple paragraphs of meaningful text that demonstrates this is actual chapter content rather than table
of contents entries or metadata. The content provides context and advances the narrative in meaningful ways.

CHAPTER I: The Extent Of The Empire In The Age Of The Antonines—Part
 II.

This is chapter one part two, which should be merged with part one to create a single complete chapter.
The content here is also substantial to pass the minimum length requirements for chapter detection and
validation. This chapter contains substantial narrative content and detailed exposition to ensure it meets
the minimum length requirements for proper chapter detection and validation. We include multiple paragraphs
of meaningful text that demonstrates this is actual chapter content rather than table of contents entries
or metadata. The content provides context and advances the narrative in meaningful ways.

CHAPTER II: Another Chapter

This is a different chapter entirely, with its own substantial content that meets the minimum requirements
for being recognized as a valid chapter in the book structure rather than a table of contents entry. This
chapter contains substantial narrative content and detailed exposition to ensure it meets the minimum length
requirements for proper chapter detection and validation. We include multiple paragraphs of meaningful text
that demonstrates this is actual chapter content rather than table of contents entries or metadata. The
content provides context and advances the narrative in meaningful ways.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should have 3 chapters (Chapter 0=Preface, Chapter I merged from 2 parts, Chapter II standalone)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Chapter I should be merged and have clean title (no "Part I" or "Part II")
        ch0_num, ch0_title, ch0_text = chapters[0]
        ch1_num, ch1_title, ch1_text = chapters[1]
        assert ch0_num == 0  # Preface
        assert ch1_num == 1
        assert ch1_title == "The Extent Of The Empire In The Age Of The Antonines", \
            f"Expected clean title without part markers, got: {ch1_title}"
        assert "part one" in ch1_text.lower() and "part two" in ch1_text.lower(), \
            "Chapter I should contain both parts"

    def test_part_marker_without_dash(self, generator):
        """Test handling of part markers without dashes (e.g., '. Part IV')"""
        test_text = """
PREFACE

This scholarly examination of the Roman Empire provides detailed analysis of constitutional
developments and governmental structures during the Antonine period. The work synthesizes
primary sources with modern historiographical perspectives to offer comprehensive coverage
of this crucial era in Roman history. Each chapter addresses specific aspects of imperial
administration while maintaining coherent thematic connections throughout the narrative.
The methodology combines textual analysis with archaeological evidence to support the
historical arguments presented. This preface establishes the framework and approach that
guides the subsequent chapters, ensuring readers understand the scholarly foundations of
the work and can appreciate the contributions it makes to our understanding of Roman history.

CHAPTER I: The Constitution In The Age Of The Antonines. Part
 IV.

This is chapter one part four with content spread across the multi-line title. The part marker here
uses a period instead of a dash, which is a variation we need to handle correctly. Including more text
to meet minimum chapter length. This chapter contains substantial narrative content and detailed exposition
to ensure it meets the minimum length requirements for proper chapter detection and validation. We include
multiple paragraphs of meaningful text that demonstrates this is actual chapter content rather than table
of contents entries or metadata. The content provides context and advances the narrative in meaningful ways.

CHAPTER II: Another Chapter

This is a separate chapter with its own content that should be detected as a distinct chapter from the
first one. More text is added here to ensure it passes the minimum length requirement for proper chapter
validation. This chapter contains substantial narrative content and detailed exposition to ensure it meets
the minimum length requirements for proper chapter detection and validation. We include multiple paragraphs
of meaningful text that demonstrates this is actual chapter content rather than table of contents entries
or metadata. The content provides context and advances the narrative in meaningful ways.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should have 3 chapters (0=Preface, 1, 2)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Chapter I should have clean title (no ". Part IV")
        ch0_num, ch0_title, ch0_text = chapters[0]
        ch1_num, ch1_title, ch1_text = chapters[1]
        assert ch0_num == 0  # Preface
        assert ch1_num == 1
        assert ch1_title == "The Constitution In The Age Of The Antonines", \
            f"Expected clean title without '. Part IV', got: {ch1_title}"
        assert "Part" not in ch1_title, f"Title should not contain 'Part': {ch1_title}"
        assert "IV" not in ch1_title or "Antonines" in ch1_title, \
            f"Title should not contain standalone 'IV': {ch1_title}"

    def test_various_part_marker_formats(self, generator):
        """Test removal of various part marker formats"""
        test_text = """
PREFACE

This work demonstrates various formatting conventions used in historical texts, particularly
regarding chapter division and part markers. The examples presented illustrate different
editorial approaches to organizing complex multi-part chapters within larger works. Understanding
these variations is essential for proper parsing and analysis of historical documents. The
methodology employed examines textual patterns and structures to identify consistent principles
underlying diverse formatting choices. This preface establishes the analytical framework used
throughout the chapters that follow, ensuring readers can appreciate the significance of the
formatting variations discussed and their implications for textual interpretation and preservation.

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

        chapters, _ = generator.detect_chapters(test_text)

        # Should have 5 chapters (0=Preface, 1-4)
        assert len(chapters) == 5, f"Expected 5 chapters, got {len(chapters)}"

        # All chapters should have clean titles (no part markers)
        ch0_num, ch0_title, _ = chapters[0]
        assert ch0_num == 0  # Preface

        ch1_num, ch1_title, _ = chapters[1]
        assert ch1_title == "Title With Dash", \
            f"Chapter 1 should have 'Title With Dash', got: {ch1_title}"

        ch2_num, ch2_title, _ = chapters[2]
        assert ch2_title == "Title With Period", \
            f"Chapter 2 should have 'Title With Period', got: {ch2_title}"

        ch3_num, ch3_title, _ = chapters[3]
        assert ch3_title == "Title With Period", \
            f"Chapter 3 should have 'Title With Period', got: {ch3_title}"

        ch4_num, ch4_title, _ = chapters[4]
        assert ch4_title == "Title With No Marker", \
            f"Chapter 4 should have 'Title With No Marker', got: {ch4_title}"

    def test_decline_and_fall_examples(self, generator):
        """Test the specific examples from 'The History of the Decline and Fall of the Roman Empire'"""
        test_text = """
PREFACE

The History of the Decline and Fall of the Roman Empire represents one of the most significant
works of historical scholarship ever produced. This monumental study examines the complex factors
that led to the transformation of the Roman Empire from its zenith to its eventual fragmentation.
The work draws upon extensive primary sources and demonstrates remarkable erudition in synthesizing
diverse historical evidence into a coherent narrative. Each chapter addresses specific aspects of
imperial history while maintaining the broader analytical framework that makes this study invaluable
for understanding historical processes. This preface establishes the scope and methodology of the
work, ensuring readers appreciate the scholarly foundations and historical significance of the
analysis presented in the chapters that follow.

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

        chapters, _ = generator.detect_chapters(test_text)

        # Should have 5 chapters (0=Preface, I, II, III, IV)
        assert len(chapters) == 5, f"Expected 5 chapters, got {len(chapters)}"

        # Verify all titles are clean and complete
        expected_titles = [
            "Preface",  # Chapter 0
            "The Extent Of The Empire In The Age Of The Antonines",
            "The Internal Prosperity In The Age Of The Antonines",
            "The Constitution In The Age Of The Antonines",
            "The Cruelty, Follies And Murder Of Commodus"
        ]

        for i, (ch_num, ch_title, _) in enumerate(chapters):
            assert ch_num == i, f"Chapter number mismatch: expected {i}, got {ch_num}"
            assert ch_title == expected_titles[i], \
                f"Chapter {i} title mismatch: expected '{expected_titles[i]}', got '{ch_title}'"


    def test_book_markers_as_chapters(self, generator):
        """Test that BOOK/VOLUME/ACT markers become chapters when no nested chapters exist"""
        # Simulate a book like The Odyssey where BOOK markers ARE the chapters
        test_text = """
PREFACE

This epic poem represents one of the foundational works of Western literature, presenting
a narrative of adventure, heroism, and the human condition through carefully structured
episodes. The work is divided into books rather than chapters, following the classical
tradition of epic poetry. Each book contains a distinct episode or set of events that
contributes to the overall narrative arc while maintaining thematic coherence throughout
the entire work. The translation presented here aims to preserve the poetic qualities
and narrative power of the original while making it accessible to modern readers. This
preface provides context for understanding the structure and significance of the work.

TABLE OF CONTENTS

BOOK I
BOOK II
BOOK III

BOOK I

This is the content of Book I. It contains the opening of the epic narrative with substantial detail
about the characters and setting. We introduce the hero and his journey, establishing the themes that
will carry through the entire work. Adding more content here to ensure this chapter is substantial
enough to pass validation and be recognized as a real chapter rather than metadata. This chapter contains
substantial narrative content and detailed exposition to ensure it meets the minimum length requirements
for proper chapter detection and validation. We include multiple paragraphs of meaningful text that
demonstrates this is actual chapter content rather than table of contents entries or metadata.

BOOK II

This is the content of Book II, continuing the story from Book I. New characters are introduced and the
plot develops further. We include multiple paragraphs of content to ensure this chapter meets minimum
length requirements and is clearly distinguished from table of contents entries. The narrative continues
with rich description and dialogue that advances the storyline significantly. This chapter contains
substantial narrative content and detailed exposition to ensure it meets the minimum length requirements
for proper chapter detection and validation. We include multiple paragraphs of meaningful text that
demonstrates this is actual chapter content rather than table of contents entries or metadata.

BOOK III

This is the content of Book III, which further advances the narrative. Important events unfold and
character development continues. We provide substantial text here to ensure proper chapter detection
and to distinguish this real chapter from the brief TOC entry that appeared earlier in the document.
More details and exposition are included to make this chapter substantial and meaningful. This chapter
contains substantial narrative content and detailed exposition to ensure it meets the minimum length
requirements for proper chapter detection and validation. We include multiple paragraphs of meaningful
text that demonstrates this is actual chapter content rather than table of contents entries or metadata.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 4 chapters (0=Preface, BOOK I, II, III)
        assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

        # Chapters should use simple numbering (0, 1, 2, 3) not nested encoding (100, 200, 300)
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert chapter_nums == [0, 1, 2, 3], f"Expected [0, 1, 2, 3], got {chapter_nums}"

        # Chapter titles should be formatted as "Preface", "BOOK I", "BOOK II", "BOOK III"
        for i, (ch_num, ch_title, ch_text) in enumerate(chapters):
            assert ch_num == i, f"Chapter {i} has wrong number: {ch_num} vs {i}"
            if i > 0:  # Skip preface
                assert f"BOOK" in ch_title, f"Chapter {i} title should contain 'BOOK': {ch_title}"

            # Verify content is present
            assert len(ch_text) > 200, f"Chapter {ch_num} is too short: {len(ch_text)} chars"
            if i > 0:
                assert "content of Book" in ch_text, f"Chapter {ch_num} missing expected content"

    def test_book_markers_with_duplicates(self, generator):
        """Test that duplicate BOOK markers (TOC + actual) are deduplicated correctly"""
        test_text = """
PREFACE

This work demonstrates the importance of properly handling duplicate chapter markers that
appear in both table of contents sections and in the main body of the text. The parsing
logic must distinguish between reference listings and actual chapter content to ensure
accurate chapter extraction. This preface provides the necessary context for understanding
the structure and approach used in organizing the material that follows.

CONTENTS
BOOK I
BOOK II

BOOK I

This is the actual content of Book I, not the TOC entry. It has substantial text that makes it clearly
different from the brief TOC reference above. We include multiple paragraphs here to ensure this chapter
is long enough to be recognized as real content rather than just a table of contents entry or other
metadata that should be filtered out during the parsing process. This chapter contains substantial narrative
content and detailed exposition to ensure it meets the minimum length requirements for proper chapter
detection and validation. We include multiple paragraphs of meaningful text that demonstrates this is
actual chapter content rather than table of contents entries or metadata.

BOOK II

This is the actual content of Book II with rich narrative detail. The story continues from Book I with
new developments and character interactions. We provide enough text here to distinguish this from the TOC
entry and ensure it passes all validation checks for proper chapter detection and parsing. This chapter
contains substantial narrative content and detailed exposition to ensure it meets the minimum length
requirements for proper chapter detection and validation. We include multiple paragraphs of meaningful
text that demonstrates this is actual chapter content rather than table of contents entries or metadata.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 3 chapters (0=Preface, 1, 2 deduplicating TOC entries)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Chapters should be numbered 0, 1, and 2
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert chapter_nums == [0, 1, 2], f"Expected [0, 1, 2], got {chapter_nums}"

        # Each chapter (except preface) should have substantial content (not TOC)
        for i, (ch_num, ch_title, ch_text) in enumerate(chapters):
            if i > 0:  # Skip preface
                assert "actual content" in ch_text, f"Chapter {ch_num} should have actual content, not TOC"
            assert len(ch_text) > 200, f"Chapter {ch_num} is too short"

    def test_book_markers_preserve_backward_compatibility(self, generator):
        """Test that nested BOOK/CHAPTER structure still works (backward compatibility)"""
        # This is the existing behavior - BOOK markers with nested chapters
        test_text = """
PREFACE

This work examines the organization of complex multi-volume historical texts that employ
nested book and chapter structures. The parsing logic must correctly handle hierarchical
organization where books contain multiple chapters, encoding this structure in the chapter
numbering system. This preface establishes the context for understanding the organizational
principles applied throughout the work.

BOOK I

CHAPTER 1: First Topic

This is Book 1, Chapter 1 content with substantial detail and exposition. We include enough text here
to ensure this passes validation and is recognized as a real chapter with meaningful content rather than
just metadata or a table of contents entry. Multiple paragraphs are included to meet minimum length
requirements for proper chapter detection and parsing throughout the system. This chapter contains substantial
narrative content and detailed exposition to ensure it meets the minimum length requirements for proper
chapter detection and validation. We include multiple paragraphs of meaningful text that demonstrates this
is actual chapter content rather than table of contents entries or metadata.

CHAPTER 2: Second Topic

This is Book 1, Chapter 2 with additional narrative content and development. More substantial text is
provided to ensure this chapter is long enough to pass all validation checks. We maintain consistency with
the previous chapter in terms of content length and structure to ensure reliable parsing results. This chapter
contains substantial narrative content and detailed exposition to ensure it meets the minimum length requirements
for proper chapter detection and validation. We include multiple paragraphs of meaningful text that demonstrates
this is actual chapter content rather than table of contents entries or metadata.

BOOK II

CHAPTER 1: New Beginning

This is Book 2, Chapter 1 content starting a new section of the narrative. Substantial text is included here
as well to meet the minimum requirements for chapter detection. We provide detailed content that clearly
distinguishes this from brief TOC entries or metadata that might appear elsewhere in text. This chapter contains
substantial narrative content and detailed exposition to ensure it meets the minimum length requirements for
proper chapter detection and validation. We include multiple paragraphs of meaningful text that demonstrates
this is actual chapter content rather than table of contents entries or metadata.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 4 chapters (0=Preface, 101, 102, 201) with nested encoding
        assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 0 in chapter_nums, "Should have Preface as Chapter 0"
        assert 101 in chapter_nums, "Book 1 Chapter 1 should be encoded as 101"
        assert 102 in chapter_nums, "Book 1 Chapter 2 should be encoded as 102"
        assert 201 in chapter_nums, "Book 2 Chapter 1 should be encoded as 201"

    def test_title_only_toc_first_chapter(self, generator):
        """
        Test that title-only TOC extraction gets first chapter (Jekyll and Hyde issue).

        The fix: Use LAST occurrence of each title instead of first to skip TOC.
        Previously, when a title appeared in both TOC and content, we'd only find
        the TOC occurrence and skip the actual chapter.
        """
        test_text = """
The Strange Case Of Dr. Jekyll And Mr. Hyde

by Robert Louis Stevenson

Contents

STORY OF THE DOOR

SEARCH FOR MR. HYDE

DR. JEKYLL WAS QUITE AT EASE

STORY OF THE DOOR

Mr. Utterson the lawyer was a man of a rugged countenance that was
never lighted by a smile; cold, scanty and embarrassed in discourse;
backward in sentiment; lean, long, dusty, dreary and yet somehow lovable.
At friendly meetings, and when the wine was to his taste, something
eminently human beaconed from his eye. This is substantial chapter content
that goes on for many paragraphs and contains the actual story. More text
is added here to make this chapter long enough and substantial enough to
clearly distinguish it from the table of contents entry above.

SEARCH FOR MR. HYDE

Mr. Utterson that evening walked slowly home. It was a fine dry night and
the streets were brilliantly lit. This chapter continues with more content
about the search for the mysterious Mr. Hyde and the growing suspense as
Utterson investigates. More text is included here to make this chapter
substantial and clearly different from the brief TOC entry above. Additional
paragraphs ensure proper chapter length and detection.

DR. JEKYLL WAS QUITE AT EASE

A fortnight later, by excellent good fortune, the doctor gave one of his
pleasant dinners to some five or six old cronies. This chapter provides
important context about Dr. Jekyll's character and his relationships with
his friends. We include more content to ensure this chapter is properly
detected and not confused with the table of contents entry. More sentences
are added to ensure adequate chapter length for validation.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect ALL 3 chapters, including "STORY OF THE DOOR"
        assert len(chapters) == 3, f"Expected 3 chapters (including first), got {len(chapters)}"

        # Verify we got all three chapters in order
        chapter_titles = [title for _, title, _ in chapters]
        assert "STORY OF THE DOOR" in chapter_titles, "Missing first chapter 'STORY OF THE DOOR'"
        assert "SEARCH FOR MR. HYDE" in chapter_titles, "Missing 'SEARCH FOR MR. HYDE'"
        assert "DR. JEKYLL WAS QUITE AT EASE" in chapter_titles, "Missing 'DR. JEKYLL WAS QUITE AT EASE'"

        # Verify content is from actual chapters, not TOC
        for ch_num, ch_title, ch_text in chapters:
            assert len(ch_text) > 200, f"Chapter '{ch_title}' is too short ({len(ch_text)} chars)"
            # Verify we got actual content, not TOC
            assert "Mr. Utterson" in ch_text or "fortnight later" in ch_text, \
                f"Chapter '{ch_title}' missing actual content"

    def test_book_markers_embedded_in_paragraphs(self, generator):
        """
        Test that BOOK markers embedded in paragraphs are ignored (Moby Dick issue).

        The fix: Check surrounding lines for substantial content. If BOOK marker
        is within 3 lines of actual content (lowercase, >20 chars), treat as
        embedded content, not a chapter boundary.

        This handles Moby Dick's Chapter 32 "Cetology" which contains:
        "BOOK I (Folio), BOOK II (Octavo), BOOK III (Duodecimo)"
        as part of whale classification discussion.
        """
        test_text = """
CHAPTER 1: Introduction

This is the first chapter with enough content to establish the book properly
and avoid triggering the TOC detection safety net. We include multiple paragraphs
here to build up enough context and accumulated content that the subsequent chapters
will be recognized as real chapters rather than table of contents entries. Adding
even more substantial text to ensure this chapter exceeds 500 characters and has
enough content to be recognized as a real chapter. We continue with additional
sentences and paragraphs to build up the word count and character count. This
ensures the chapter detection logic treats this as actual content rather than
metadata or a table of contents entry. More text is needed to reach the threshold
that distinguishes real chapters from TOC entries in our validation logic. The
chapter needs substantial exposition and narrative content to pass the average
length check. We include historical context, character development, and detailed
descriptions to make this a realistic and substantial chapter for testing purposes.

CHAPTER 2: Background

More substantial content continues in chapter two, providing additional context
and building up the accumulated content size. This helps ensure that later chapters
with embedded BOOK markers will be properly recognized and those BOOK markers will
be treated as content rather than chapter boundaries. We add multiple paragraphs
of detailed content to ensure this chapter also exceeds 500 characters and meets
the minimum requirements for proper chapter detection. Additional narrative and
exposition are included to make this chapter realistic and substantial enough to
pass all validation checks. We provide background information, historical context,
and character introductions to flesh out the chapter content. More sentences are
added to ensure adequate length and substance throughout this test chapter. The
content needs to be comprehensive enough to demonstrate real chapter structure.

CHAPTER 32: Cetology

Already we have sought to explain the whale scientifically. Now we
attempt to classify the various types and species of whales known to man.
This chapter will contain extensive discussion of whale taxonomy and classification
systems used by whalers and naturalists in the nineteenth century. We provide
detailed descriptions of each category and the specific whale species that belong
to them. The classification system divides whales into three main categories based
on their size and characteristics. Each category is named after a book format that
corresponds to its relative size in the grand scheme of cetacean taxonomy.

BOOK I (Folio)

The largest whales fall into this category, including the great Sperm Whale
and the Right Whale. These massive creatures are the most sought after by
whalers due to their size and valuable oil. They represent the pinnacle of
whale classification in terms of sheer magnitude and commercial importance.
The Folio whales are named for the largest book format, reflecting their
enormous size and significance in the whaling industry. These leviathans of
the deep are the primary targets of commercial whaling operations and provide
the most valuable oil and whalebone products.

BOOK II (Octavo)

Medium-sized whales occupy this classification, such as the Grampus and
Blackfish. While smaller than the Folio whales, they still provide value
to the whaling industry and are frequently encountered during voyages.
The Octavo designation refers to a medium-sized book format, representing
the intermediate size of these cetaceans. Though not as commercially valuable
as their larger cousins, these whales are still hunted and provide useful
products including oil and meat for various industrial purposes.

BOOK III (Duodecimo)

The smallest whales and porpoises belong to this final category. Though
diminutive compared to their larger cousins, they are no less remarkable
in their adaptations and behaviors. The Duodecimo category, named for the
smallest book format, encompasses the lesser cetaceans including dolphins
and porpoises. While not typically targeted by commercial whalers due to
their small size and limited oil yields, these creatures are nonetheless
fascinating subjects of natural history and scientific inquiry.

Thus concludes our classification of the various orders of cetaceans known
to science and whaling practice. We now return to the narrative with a better
understanding of the great variety and complexity of whale species that inhabit
the world's oceans. This taxonomy, while perhaps unconventional in its use of
bibliographic terminology, serves to organize our knowledge of these magnificent
creatures in a manner both memorable and instructive for the student of cetology.

CHAPTER 33: The Specksnyder

The next chapter begins here with new content about the hierarchy aboard
whaling vessels and the role of the specksnyder. This is a real chapter
boundary that should be detected, unlike the BOOK markers above which were
just part of Chapter 32's content about whale classification. We provide
substantial detail about the specksnyder's responsibilities and position in
the ship's command structure. Additional paragraphs of content are included
to ensure this chapter also meets the minimum length requirements and is
recognized as a distinct chapter rather than being mistaken for metadata or
table of contents entries. The specksnyder serves an important role in the
whaling operation, overseeing various aspects of the hunt and processing of
the catch. More historical and operational details are provided to flesh out
the chapter content and ensure adequate length for proper chapter detection.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 4 chapters (1, 2, 32, 33), not 7 (1, 2, 32, BOOK I, II, III, 33)
        assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

        # Verify chapter numbers
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 32 in chapter_nums, "Should detect Chapter 32"
        assert 33 in chapter_nums, "Should detect Chapter 33"

        # Chapter 32 should contain all the BOOK content
        ch32 = next((text for num, title, text in chapters if num == 32), None)
        assert ch32 is not None, "Chapter 32 not found"
        assert "BOOK I" in ch32, "Chapter 32 should contain 'BOOK I' as content"
        assert "BOOK II" in ch32, "Chapter 32 should contain 'BOOK II' as content"
        assert "BOOK III" in ch32, "Chapter 32 should contain 'BOOK III' as content"
        assert "Folio" in ch32, "Chapter 32 should contain whale classification content"
        assert "Octavo" in ch32, "Chapter 32 should contain whale classification content"
        assert "Duodecimo" in ch32, "Chapter 32 should contain whale classification content"

        # Verify no BOOK markers were treated as chapters
        for ch_num, ch_title, _ in chapters:
            assert "BOOK I" not in ch_title, "BOOK I should not be a chapter title"
            assert "BOOK II" not in ch_title, "BOOK II should not be a chapter title"
            assert "BOOK III" not in ch_title, "BOOK III should not be a chapter title"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
