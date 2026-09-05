#!/usr/bin/env python3
"""
Unit tests for EPILOGUE frontmatter detection fix.

Tests the fix for https://github.com/anthropics/claude-code/issues/XXX
where EPILOGUE markers appearing in TOC/frontmatter were incorrectly
treated as chapter boundaries, causing content duplication.

The fix ensures that EPILOGUE, PREFACE, INTRODUCTION, and AUTHOR'S PREFACE
patterns appearing before first_chapter_line are skipped and not treated
as separate chapters.
"""

import sys
import os
from pathlib import Path


from scripts.content.generate_summaries import SummaryGenerator
import pytest


class TestEpilogueFrontmatterDetection:
    """Test EPILOGUE frontmatter detection and deduplication"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_epilogue_in_toc_not_duplicated(self, generator):
        """
        Test that EPILOGUE appearing in TOC is not treated as a chapter.

        This tests the fix for The Three Musketeers where:
        - EPILOGUE appears in TOC (line 102) without chapter number
        - AUTHOR'S PREFACE follows (line 107)
        - Both were being detected as chapters and merged
        - Result: AUTHOR'S PREFACE content duplicated in Chapter 0 and Chapter 68

        Expected behavior after fix:
        - TOC EPILOGUE is skipped
        - AUTHOR'S PREFACE goes to Chapter 0 (Preface)
        - Only actual EPILOGUE at end is detected as final chapter
        """
        test_text = """
CONTENTS
 AUTHOR'S PREFACE
 CHAPTER I. THE THREE PRESENTS
 CHAPTER II. THE ANTECHAMBER
 CHAPTER III. THE AUDIENCE
 EPILOGUE

EPILOGUE

AUTHOR'S PREFACE

This is the author's preface with substantial content explaining the origins
of the story and providing context for readers. The preface discusses the
historical background and the inspiration for writing this adventure tale.
Multiple paragraphs ensure this content is substantive enough to be recognized
as real frontmatter that should be part of Chapter 0 rather than being treated
as a separate chapter or merged into the epilogue. The author reflects on the
research conducted and acknowledges sources consulted during the writing process.
Additional context helps readers understand the historical period in which the
story is set and the creative choices made in adapting historical events into
a compelling narrative that captures the spirit of adventure and intrigue.

CHAPTER I. THE THREE PRESENTS

On the first Monday of the month of April, 1625, the market town of Meung
appeared to be in as perfect a state of revolution as if the Huguenots had
just made a second La Rochelle of it. This is the actual first chapter content
with substantial narrative detail that introduces our protagonist and sets the
stage for the adventures to come. We include multiple paragraphs of detailed
exposition to ensure this chapter is long enough to be recognized as actual
content rather than a table of contents entry or metadata. The young Gascon
d'Artagnan arrives in Paris with dreams of becoming a musketeer and serving
the king. His journey begins with a series of misadventures that test his
courage and resourcefulness. More content is added to build up the chapter
length and provide the narrative substance expected in a real chapter.

CHAPTER II. THE ANTECHAMBER

D'Artagnan finds himself in the antechamber of Monsieur de Tréville, captain
of the King's Musketeers. This chapter continues the narrative with more
adventures and character development. We include substantial content here to
ensure proper chapter detection and to distinguish this from brief TOC entries.
The protagonist observes the musketeers and learns about the hierarchy and
customs of this elite military company. Multiple encounters and conversations
reveal both the opportunities and challenges that await our young hero. Additional
paragraphs of exposition and dialogue ensure this chapter has adequate length
and substance for proper validation and chapter boundary detection throughout.

CHAPTER III. THE AUDIENCE

D'Artagnan finally meets Monsieur de Tréville and seeks to join the musketeers.
This pivotal chapter includes important dialogue and character interactions that
advance the plot significantly. We provide substantial narrative content with
multiple paragraphs to ensure this chapter passes all validation checks and is
recognized as a distinct chapter in the story structure. The audience with
Tréville proves both challenging and enlightening for the young Gascon, who
must navigate courtly protocol while demonstrating his worth and potential.
More content is included to build character relationships and establish the
foundations for future conflicts and alliances that will shape the narrative.

EPILOGUE

Twenty years have passed since the events chronicled in this tale. Our heroes
have gone their separate ways, each following their own path to glory or
obscurity. This epilogue provides closure to the narrative by revealing the
fates of the main characters and reflecting on the adventures they shared.
D'Artagnan has achieved his dream of becoming a musketeer and has risen through
the ranks through courage and loyal service. The bonds of friendship forged
during those early adventures have endured despite the passage of time and the
challenges of life. This brief epilogue wraps up the story with appropriate
finality while leaving room for readers' imaginations about future adventures.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 5 chapters (0=Preface, 1, 2, 3, and EPILOGUE)
        # NOT 6 chapters (which would indicate the TOC EPILOGUE was detected)
        assert len(chapters) == 5, f"Expected 5 chapters, got {len(chapters)}"

        # Verify chapter structure
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 0 in chapter_nums, "Should have Chapter 0 (Preface)"
        assert 1 in chapter_nums, "Should have Chapter 1"
        assert 2 in chapter_nums, "Should have Chapter 2"
        assert 3 in chapter_nums, "Should have Chapter 3"

        # Verify chapter titles are title cased (not ALL CAPS)
        for num, title, text in chapters:
            # Titles should not be all uppercase (except for Roman numerals and acronyms)
            # Remove Roman numerals and common patterns to check if the rest is title cased
            title_words = title.replace('I.', '').replace('II.', '').replace('III.', '').split()
            for word in title_words:
                if len(word) > 2:  # Skip short words like "of", "a", etc.
                    # Word should not be all caps (unless it's an acronym)
                    is_all_caps = word.isupper() and len(word) > 3
                    assert not is_all_caps, f"Chapter title '{title}' contains all-caps word '{word}' - should be title cased"

        # Find the preface and epilogue chapters
        preface = next((text for num, title, text in chapters if num == 0), None)
        epilogue_chapters = [(num, title, text) for num, title, text in chapters
                            if 'epilogue' in title.lower()]

        # Verify preface contains AUTHOR'S PREFACE content
        assert preface is not None, "Chapter 0 (Preface) not found"
        assert "author's preface" in preface.lower(), \
            "Chapter 0 should contain AUTHOR'S PREFACE content"
        assert "origins of the story" in preface.lower(), \
            "Chapter 0 should have the actual preface content"

        # Should only have ONE epilogue (not merged from two parts)
        assert len(epilogue_chapters) == 1, \
            f"Expected 1 epilogue, got {len(epilogue_chapters)} (TOC EPILOGUE was not skipped)"

        # Epilogue should NOT contain AUTHOR'S PREFACE content
        epilogue_num, epilogue_title, epilogue_text = epilogue_chapters[0]
        assert "author's preface" not in epilogue_text.lower(), \
            "EPILOGUE should not contain AUTHOR'S PREFACE content (duplication issue)"
        assert "twenty years have passed" in epilogue_text.lower(), \
            "EPILOGUE should contain actual epilogue content"


    def test_epilogue_without_chapter_number(self, generator):
        """
        Test that EPILOGUE can be a valid chapter without a chapter number,
        but only when it appears after the last numbered chapter.
        """
        test_text = """
CHAPTER 1: First

This is the first chapter with substantial narrative content. We include
multiple paragraphs to ensure proper chapter detection and validation. The
story begins with an introduction to the main character and the setting where
events will unfold. Additional content builds the foundation for the narrative
that will develop through subsequent chapters.

CHAPTER 2: Second

This is the second chapter continuing the narrative. More plot development
and character interactions occur here. We provide substantial content to ensure
this chapter passes validation and is recognized as distinct from table of
contents entries or metadata. The story progresses with new challenges and
revelations that drive the plot forward.

EPILOGUE

This epilogue wraps up the story after all numbered chapters conclude. It should
be detected as a valid chapter even though it doesn't have a chapter number,
because EPILOGUE is a special chapter marker that can stand alone when it appears
after the last numbered chapter. This epilogue provides closure by revealing the
fates of characters and reflecting on the events that transpired. Multiple paragraphs
ensure this has sufficient content to be recognized as a legitimate chapter that
completes the narrative arc.
"""

        chapters, _ = generator.detect_chapters(test_text)

        # Should detect 3 chapters (1, 2, and EPILOGUE)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

        # Verify chapter numbers
        chapter_nums = [ch_num for ch_num, _, _ in chapters]
        assert 1 in chapter_nums, "Should have Chapter 1"
        assert 2 in chapter_nums, "Should have Chapter 2"

        # Verify EPILOGUE exists
        epilogue_chapters = [(num, title, text) for num, title, text in chapters
                            if 'epilogue' in title.lower()]
        assert len(epilogue_chapters) == 1, "Should have exactly 1 EPILOGUE chapter"

        epilogue_num, epilogue_title, epilogue_text = epilogue_chapters[0]
        assert "wraps up the story" in epilogue_text.lower(), \
            "EPILOGUE should contain the actual epilogue content"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
