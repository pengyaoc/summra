#!/usr/bin/env python3
"""
Unit tests for bulk summary response parsing in generate_summaries.py

These tests validate the parsing of LLM responses in bulk chapter summary generation,
including support for both Arabic and Roman numerals.
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.content.generate_summaries import SummaryGenerator
import pytest


class TestBulkSummaryParser:
    """Test bulk summary response parsing"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_parse_sequential_indices(self, generator):
        """Test parsing with sequential indices (1, 2, 3...) - the new index-based approach"""
        response_text = """### CHAPTER 1: First Chapter
This is the summary for chapter 1 with substantial content about the first chapter.
It includes multiple sentences to make it realistic.

### END CHAPTER 1

### CHAPTER 2: Second Chapter
This is the summary for chapter 2 with details about what happens in the second chapter.
More content here to make it substantial.

### END CHAPTER 2"""

        # Test with simple sequential mapping (index 1 -> chapter 1, index 2 -> chapter 2)
        index_to_chapter = {1: 1, 2: 2}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 1 in summaries
        assert 2 in summaries
        assert "chapter 1" in summaries[1].lower()
        assert "chapter 2" in summaries[2].lower()

    def test_parse_encoded_chapter_mapping(self, generator):
        """Test parsing with index-to-chapter mapping for encoded chapters (e.g., 101, 102)"""
        response_text = """### CHAPTER 1: First Topic
This is the summary for the first chapter in Book 1.
It uses sequential index 1 in the response.

### END CHAPTER 1

### CHAPTER 2: Second Topic
This is the summary for the second chapter in Book 1.
It uses sequential index 2 in the response.

### END CHAPTER 2"""

        # Map sequential indices to encoded chapter numbers
        index_to_chapter = {1: 101, 2: 102}  # Index 1 -> Chapter 101, Index 2 -> Chapter 102
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 101 in summaries  # Actual chapter number
        assert 102 in summaries
        assert "first chapter" in summaries[101].lower()
        assert "second chapter" in summaries[102].lower()

    def test_parse_non_sequential_chapter_mapping(self, generator):
        """Test parsing with non-sequential chapter numbers (e.g., chapters 12, 13 mapped to indices 1, 2)"""
        response_text = """### CHAPTER 1: The Sirens
This is the summary for the first chapter in this batch.
The content describes Odysseus's journey past the Sirens.

### END CHAPTER 1

### CHAPTER 2: Return to Ithaca
This is the summary for the second chapter in this batch.
Odysseus finally arrives home after many years.

### END CHAPTER 2"""

        # Map sequential indices 1, 2 to actual chapters 12, 13
        index_to_chapter = {1: 12, 2: 13}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 12 in summaries  # Actual chapter numbers
        assert 13 in summaries
        assert "sirens" in summaries[12].lower()
        assert "arrives home" in summaries[13].lower()

    def test_parse_without_end_markers(self, generator):
        """Test parsing when END CHAPTER markers are missing"""
        response_text = """### CHAPTER 1: First Chapter
Summary of chapter 1 without explicit end marker.

### CHAPTER 2: Second Chapter
Summary of chapter 2, also without end marker."""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 1 in summaries
        assert 2 in summaries

    def test_parse_with_extra_whitespace(self, generator):
        """Test parsing with various whitespace patterns"""
        response_text = """###  CHAPTER 1:  First Chapter
Summary with extra spaces in header.

###  END CHAPTER 1

###CHAPTER 2: Second Chapter
Summary with minimal spacing.

###END CHAPTER 2"""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 1 in summaries
        assert 2 in summaries

    def test_parse_case_insensitive(self, generator):
        """Test that parsing is case-insensitive"""
        response_text = """### chapter 1: First Chapter
Summary with lowercase chapter marker.

### end chapter 1

### CHAPTER 2: Second Chapter
Summary with uppercase chapter marker.

### END CHAPTER 2"""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 1 in summaries
        assert 2 in summaries

    def test_missing_chapters_warning(self, generator, capsys):
        """Test that missing chapters trigger a warning"""
        response_text = """### CHAPTER 1: First Chapter
Only chapter 1 is present.

### END CHAPTER 1"""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2, 3])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        # Should only parse chapter 1
        assert len(summaries) == 1
        assert 1 in summaries

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Missing summaries for chapters: [2, 3]" in captured.out

    def test_encoded_chapter_numbers(self, generator):
        """Test parsing with encoded chapter numbers (e.g., 101, 201 for nested books)"""
        # Note: Response now uses sequential indices (1, 2), not encoded numbers
        response_text = """### CHAPTER 1: Book 1, Chapter 1
Summary for encoded chapter 101.

### END CHAPTER 1

### CHAPTER 2: Book 1, Chapter 2
Summary for encoded chapter 102.

### END CHAPTER 2"""

        # Map sequential indices to encoded chapter numbers
        index_to_chapter = {1: 101, 2: 102}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert 101 in summaries  # Actual encoded chapter numbers
        assert 102 in summaries

    def test_multiline_summary_content(self, generator):
        """Test parsing summaries with multiple paragraphs and newlines"""
        response_text = """### CHAPTER 1: First Chapter
This is the first paragraph of the summary.

This is the second paragraph with more detail.

And a third paragraph to ensure multiline content works.

### END CHAPTER 1

### CHAPTER 2: Second Chapter
Another multiline summary.

With multiple paragraphs.

### END CHAPTER 2"""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 2
        assert "first paragraph" in summaries[1].lower()
        assert "second paragraph" in summaries[1].lower()
        assert "third paragraph" in summaries[1].lower()
        assert "\n\n" in summaries[1]  # Verify paragraph breaks are preserved

    def test_summary_with_colons_in_title(self, generator):
        """Test parsing when chapter titles contain colons"""
        response_text = """### CHAPTER 1: Title: With Multiple: Colons
Summary for chapter with colons in title.

### END CHAPTER 1"""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 1
        assert 1 in summaries

    def test_empty_response(self, generator):
        """Test handling of empty response"""
        response_text = ""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 0

    def test_malformed_response(self, generator):
        """Test handling of completely malformed response"""
        response_text = """This is just random text without any chapter markers.
It doesn't follow the expected format at all.
Should return empty dict."""

        index_to_chapter = {i+1: ch for i, ch in enumerate([1, 2])}
        summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(summaries) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
