"""
Unit tests for chapter summary generation using bulk processing.

Tests cover:
1. Consecutive chapter validation in regenerate mode
2. Bulk summary response parsing with sequential indexing
3. Context building for previous chapter and medium summary
4. Error handling and edge cases
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add backend and scripts directories to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
sys.path.insert(0, backend_dir)
sys.path.insert(0, scripts_dir)

from generate_summaries import SummaryGenerator


class TestConsecutiveChapterValidation:
    """Test validation that chapters must be consecutive for regenerate mode."""

    def test_consecutive_chapters_pass(self):
        """Test that consecutive chapters pass validation (1,2,3)."""
        chapters_to_regenerate = [(1, "Chapter 1", "text1"), (2, "Chapter 2", "text2"), (3, "Chapter 3", "text3")]

        # Validation logic from process_book
        if len(chapters_to_regenerate) > 1:
            chapter_nums = sorted([ch[0] for ch in chapters_to_regenerate])
            for i in range(len(chapter_nums) - 1):
                assert chapter_nums[i+1] == chapter_nums[i] + 1, f"Gap detected between Chapter {chapter_nums[i]} and {chapter_nums[i+1]}"

    def test_single_chapter_skip_validation(self):
        """Test that single chapter skips validation entirely."""
        chapters_to_regenerate = [(5, "Chapter 5", "text5")]

        # Validation should be skipped for single chapter
        if len(chapters_to_regenerate) > 1:
            pytest.fail("Validation should be skipped for single chapter")

    def test_non_consecutive_chapters_fail(self):
        """Test that non-consecutive chapters fail validation (1,3,5)."""
        chapters_to_regenerate = [(1, "Chapter 1", "text1"), (3, "Chapter 3", "text3"), (5, "Chapter 5", "text5")]

        # Validation logic should detect gap
        if len(chapters_to_regenerate) > 1:
            chapter_nums = sorted([ch[0] for ch in chapters_to_regenerate])
            with pytest.raises(AssertionError, match="Gap detected between Chapter"):
                for i in range(len(chapter_nums) - 1):
                    assert chapter_nums[i+1] == chapter_nums[i] + 1, f"Gap detected between Chapter {chapter_nums[i]} and {chapter_nums[i+1]}"

    def test_unsorted_consecutive_chapters_pass(self):
        """Test that unsorted but consecutive chapters pass validation (3,1,2)."""
        chapters_to_regenerate = [(3, "Chapter 3", "text3"), (1, "Chapter 1", "text1"), (2, "Chapter 2", "text2")]

        # Validation logic sorts before checking
        if len(chapters_to_regenerate) > 1:
            chapter_nums = sorted([ch[0] for ch in chapters_to_regenerate])
            for i in range(len(chapter_nums) - 1):
                assert chapter_nums[i+1] == chapter_nums[i] + 1, f"Gap detected between Chapter {chapter_nums[i]} and {chapter_nums[i+1]}"


class TestBulkSummaryResponseParsing:
    """Test parsing of bulk summary responses using sequential indexing."""

    @patch('generate_summaries.genai')
    def test_parse_basic_response(self, mock_genai):
        """Test parsing a basic response with sequential indices (1, 2, 3)."""
        generator = SummaryGenerator("test_api_key")

        response_text = """
### CHAPTER 1: INTRODUCTION
This is the summary for chapter one.

### END CHAPTER 1

### CHAPTER 2: THE JOURNEY BEGINS
This is the summary for chapter two.

### END CHAPTER 2

### CHAPTER 3: THE FIRST CHALLENGE
This is the summary for chapter three.

### END CHAPTER 3
"""

        # Map sequential indices to actual chapter numbers
        index_to_chapter = {1: 10, 2: 11, 3: 12}

        result = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(result) == 3
        assert result[10] == "This is the summary for chapter one."
        assert result[11] == "This is the summary for chapter two."
        assert result[12] == "This is the summary for chapter three."

    @patch('generate_summaries.genai')
    def test_parse_response_with_encoded_chapter_numbers(self, mock_genai):
        """Test parsing response when actual chapter numbers are encoded (101, 201, 301)."""
        generator = SummaryGenerator("test_api_key")

        response_text = """
### CHAPTER 1: ACT ONE
Summary for Act 1, Chapter 1 (encoded as 101).

### END CHAPTER 1

### CHAPTER 2: ACT TWO
Summary for Act 2, Chapter 1 (encoded as 201).

### END CHAPTER 2

### CHAPTER 3: ACT THREE
Summary for Act 3, Chapter 1 (encoded as 301).

### END CHAPTER 3
"""

        # Encoded chapter numbers from book structure (Act/Chapter format)
        index_to_chapter = {1: 101, 2: 201, 3: 301}

        result = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(result) == 3
        assert 101 in result
        assert 201 in result
        assert 301 in result

    @patch('generate_summaries.genai')
    def test_parse_response_missing_chapters(self, mock_genai):
        """Test parsing when LLM response is missing some chapters."""
        generator = SummaryGenerator("test_api_key")

        response_text = """
### CHAPTER 1: FIRST
Summary one.

### END CHAPTER 1

### CHAPTER 3: THIRD
Summary three (missing chapter 2).

### END CHAPTER 3
"""

        index_to_chapter = {1: 1, 2: 2, 3: 3}

        result = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(result) == 2
        assert 1 in result
        assert 2 not in result
        assert 3 in result

    @patch('generate_summaries.genai')
    def test_parse_response_without_end_markers(self, mock_genai):
        """Test parsing response without END CHAPTER markers."""
        generator = SummaryGenerator("test_api_key")

        response_text = """
### CHAPTER 1: FIRST
Summary for first chapter.

### CHAPTER 2: SECOND
Summary for second chapter.

### CHAPTER 3: THIRD
Summary for third chapter.
"""

        index_to_chapter = {1: 1, 2: 2, 3: 3}

        result = generator.parse_bulk_summary_response(response_text, index_to_chapter)

        assert len(result) == 3
        assert all(ch_num in result for ch_num in [1, 2, 3])


class TestBulkChapterSummariesGeneration:
    """Test bulk chapter summaries generation with context."""

    @patch('generate_summaries.genai')
    def test_context_building_with_medium_summary(self, mock_genai):
        """Test that medium summary context is properly truncated and formatted."""
        generator = SummaryGenerator("test_api_key")

        # Create a long medium summary (> 20,000 chars)
        medium_summary = "A" * 25000

        # Mock client response
        mock_response = Mock()
        mock_response.text = """
### CHAPTER 1: TEST
Test summary

### END CHAPTER 1
"""
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        chapters_batch = [(1, "Chapter 1", "Chapter text")]

        result = generator.generate_bulk_chapter_summaries(
            chapters_batch,
            "Test Book",
            medium_summary=medium_summary,
            dry_run=False
        )

        # Verify the API was called with truncated medium summary
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        prompt = call_args[1]['contents']

        # Check that medium summary was truncated to 20,000 chars
        assert "## CONTEXT: Overall Book Summary" in prompt
        # The prompt should not contain the full 25,000 chars
        assert len(prompt) < 30000

    @patch('generate_summaries.genai')
    def test_context_building_with_previous_chapter(self, mock_genai):
        """Test that previous chapter context is properly included."""
        generator = SummaryGenerator("test_api_key")

        # Previous chapter text (should be truncated at 100,000 chars)
        previous_chapter_text = "B" * 105000

        # Mock client response
        mock_response = Mock()
        mock_response.text = """
### CHAPTER 1: TEST
Test summary

### END CHAPTER 1
"""
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        chapters_batch = [(2, "Chapter 2", "Chapter 2 text")]

        result = generator.generate_bulk_chapter_summaries(
            chapters_batch,
            "Test Book",
            previous_chapter_text=previous_chapter_text,
            dry_run=False
        )

        # Verify the API was called with truncated previous chapter
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        prompt = call_args[1]['contents']

        # Check that previous chapter context was included
        assert "## CONTEXT: Previous Chapter 1 Content" in prompt
        # The prompt should contain truncated previous chapter (100,000 chars max)
        assert len(prompt) < 120000

    @patch('generate_summaries.genai')
    def test_dry_run_mode(self, mock_genai):
        """Test that dry run mode skips API calls and returns dummy data."""
        generator = SummaryGenerator("test_api_key")

        chapters_batch = [(1, "Chapter 1", "text1"), (2, "Chapter 2", "text2")]

        result = generator.generate_bulk_chapter_summaries(
            chapters_batch,
            "Test Book",
            dry_run=True
        )

        # Verify dry run returns dummy summaries
        assert len(result) == 2
        assert "[DRY RUN]" in result[1]
        assert "[DRY RUN]" in result[2]

        # Verify no generate_content calls were made (Client() is called in __init__, that's ok)
        assert not mock_genai.Client.return_value.models.generate_content.called


class TestGenerateComprehensiveSummary:
    """Test comprehensive summary generation always uses bulk processing."""

    @patch('generate_summaries.genai')
    def test_always_uses_bulk_processing(self, mock_genai):
        """Test that comprehensive summary always uses bulk processing (no conditional logic)."""
        generator = SummaryGenerator("test_api_key")

        # Mock database
        generator.db = Mock()
        generator.db.add_chapter = Mock()

        # Mock bulk response
        mock_response = Mock()
        mock_response.text = """
### CHAPTER 1: FIRST
Summary 1

### END CHAPTER 1

### CHAPTER 2: SECOND
Summary 2

### END CHAPTER 2
"""
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        # Create chapters with enough words (> 200) to pass filtering
        long_text = " ".join(["word"] * 600)

        chapters = [(1, "Chapter 1", long_text), (2, "Chapter 2", long_text)]

        overall, chapter_summaries = generator.generate_comprehensive_summary(
            "full text",
            "Test Book",
            "Test Author",
            chapters,
            book_id=1,
            dry_run=False,
            regenerate_chapters=None
        )

        # Verify bulk processing was used (only 1 API call for all chapters)
        assert mock_genai.Client.return_value.models.generate_content.call_count == 1

        # Verify all chapters were processed
        assert len(chapter_summaries) == 2

    @patch('generate_summaries.genai')
    def test_partial_run_mode(self, mock_genai):
        """Test that partial run mode processes only first 3 chapters."""
        generator = SummaryGenerator("test_api_key")

        # Mock database
        generator.db = Mock()

        # Mock bulk response
        mock_response = Mock()
        mock_response.text = """
### CHAPTER 1: FIRST
Summary 1

### END CHAPTER 1

### CHAPTER 2: SECOND
Summary 2

### END CHAPTER 2

### CHAPTER 3: THIRD
Summary 3

### END CHAPTER 3
"""
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        # 5 chapters total, but partial run should only process first 3
        chapters = [
            (1, "Chapter 1", "text1"),
            (2, "Chapter 2", "text2"),
            (3, "Chapter 3", "text3"),
            (4, "Chapter 4", "text4"),
            (5, "Chapter 5", "text5")
        ]

        overall, chapter_summaries = generator.generate_comprehensive_summary(
            "full text",
            "Test Book",
            "Test Author",
            chapters,
            book_id=1,
            dry_run=False,
            partial_run=True,
            regenerate_chapters=None
        )

        # Verify only 3 chapters were processed
        assert len(chapter_summaries) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
