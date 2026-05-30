#!/usr/bin/env python3
"""
Unit tests for LLM helper functions

Tests response cleaning, batching, and text normalization
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.content.generate_summaries import SummaryGenerator


# Module-level fixtures to mock dependencies
@pytest.fixture(autouse=True)
def mock_database():
    """Mock the Database class to prevent production database access"""
    with patch('scripts.content.generate_summaries.models.Database') as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_genai_client():
    """Mock the Gemini AI client to prevent API initialization"""
    with patch('scripts.content.generate_summaries.genai.Client') as mock:
        yield mock


class TestLLMResponseCleaning:
    """Test LLM response cleaning functionality"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_clean_of_course_preamble(self, generator):
        """Test removal of 'Of course' preamble"""
        response = "Of course. Here is the summary: The book is about..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Of course")
        assert "The book is about" in cleaned

    def test_clean_certainly_preamble(self, generator):
        """Test removal of 'Certainly' preamble"""
        response = "Certainly! Here's a detailed summary:\n\nThe story begins..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Certainly")
        assert "The story begins" in cleaned

    def test_clean_sure_preamble(self, generator):
        """Test removal of 'Sure' preamble"""
        response = "Sure. The Odyssey is an epic poem..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Sure")
        assert "The Odyssey is an epic poem" in cleaned

    def test_clean_here_is_preamble(self, generator):
        """Test removal of 'Here is' preamble"""
        response = "Here is a comprehensive summary:\n\nOdysseus embarks..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Here is")
        assert "Odysseus embarks" in cleaned

    def test_clean_here_is_a_summary_preamble(self, generator):
        """Test removal of 'Here is a...summary' pattern"""
        response = "Here is a comprehensive summary of the book:\n\nThe protagonist..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Here is")
        assert "The protagonist" in cleaned

    def test_clean_ill_provide_preamble(self, generator):
        """Test removal of 'I'll provide' preamble"""
        response = "I'll provide a detailed summary:\n\nIn Chapter 1..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("I'll provide")
        assert "In Chapter 1" in cleaned

    def test_clean_leading_asterisks(self, generator):
        """Test removal of leading asterisks"""
        response = "***\n\nThe summary begins here..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("*")
        assert "The summary begins here" in cleaned

    def test_clean_excessive_newlines(self, generator):
        """Test removal of excessive leading newlines"""
        response = "\n\n\n\nThe summary starts here..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("\n")
        assert cleaned.startswith("The summary")

    def test_clean_combined_preambles(self, generator):
        """Test removal when multiple patterns present"""
        response = "Of course. Here is a comprehensive summary:\n\n**Summary**\n\nThe book discusses..."
        cleaned = generator.clean_llm_response(response)

        assert not cleaned.startswith("Of course")
        assert not cleaned.startswith("Here is")
        assert "The book discusses" in cleaned

    def test_clean_no_preamble(self, generator):
        """Test that clean text without preamble is unchanged"""
        response = "The Odyssey is an ancient Greek epic poem..."
        cleaned = generator.clean_llm_response(response)

        assert cleaned == "The Odyssey is an ancient Greek epic poem..."

    def test_clean_case_insensitive(self, generator):
        """Test that cleaning is case-insensitive"""
        response = "of COURSE. here is the summary: Text begins..."
        cleaned = generator.clean_llm_response(response)

        assert "Text begins" in cleaned


class TestTextNormalization:
    """Test text normalization for chapters"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_normalize_single_newlines(self, generator):
        """Test that single newlines within paragraphs are removed"""
        text = """This is a paragraph
that spans multiple
lines but should be
one paragraph."""

        normalized = generator.normalize_chapter_text(text)

        assert "\n" not in normalized or normalized.count("\n") == 0
        assert "This is a paragraph that spans multiple lines but should be one paragraph." == normalized

    def test_normalize_paragraph_breaks(self, generator):
        """Test that paragraph breaks (double newlines) are preserved"""
        text = """First paragraph.

Second paragraph.

Third paragraph."""

        normalized = generator.normalize_chapter_text(text)

        # Should have single newlines between paragraphs
        paragraphs = normalized.split("\n")
        assert len(paragraphs) == 3
        assert "First paragraph." in paragraphs[0]
        assert "Second paragraph." in paragraphs[1]
        assert "Third paragraph." in paragraphs[2]

    def test_normalize_excessive_newlines(self, generator):
        """Test that 3+ newlines are reduced to single paragraph break"""
        text = """Paragraph 1.



Paragraph 2."""

        normalized = generator.normalize_chapter_text(text)

        # Should be single newline between paragraphs
        paragraphs = normalized.split("\n")
        assert len(paragraphs) == 2

    def test_normalize_trim_whitespace(self, generator):
        """Test that whitespace is trimmed from each line"""
        text = """  This line has leading spaces
    This has more spaces
This is normal"""

        normalized = generator.normalize_chapter_text(text)

        # Each line should be trimmed and joined with space
        assert "  " not in normalized  # No double spaces from trimming

    def test_normalize_windows_line_endings(self, generator):
        """Test conversion of Windows line endings"""
        text = "Line 1\r\nLine 2\r\nLine 3"

        normalized = generator.normalize_chapter_text(text)

        assert "\r" not in normalized
        # Should be joined as one paragraph
        assert "Line 1 Line 2 Line 3" == normalized

    def test_normalize_multiple_spaces(self, generator):
        """Test that multiple spaces are reduced to single space"""
        text = "This  has    multiple     spaces."

        normalized = generator.normalize_chapter_text(text)

        assert "  " not in normalized
        assert "This has multiple spaces." == normalized

    def test_normalize_empty_lines_removed(self, generator):
        """Test that empty lines within paragraphs are removed"""
        text = """Paragraph start

Line 2
Line 3"""

        normalized = generator.normalize_chapter_text(text)

        # Should have two paragraphs
        paragraphs = normalized.split("\n")
        assert len(paragraphs) == 2

    def test_normalize_preserves_single_spaces(self, generator):
        """Test that single spaces between words are preserved"""
        text = "The quick brown fox jumps over the lazy dog."

        normalized = generator.normalize_chapter_text(text)

        assert normalized == "The quick brown fox jumps over the lazy dog."


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
