#!/usr/bin/env python3
"""
Tests for generate_combined_summaries() function.

Tests the 4-field dictionary return format:
1. about_text (75-100 words, no spoilers)
2. concise_summary (500 words)
3. medium_summary (2000-3000 words)
4. relevance_now (75-100 words)
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock



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


class TestGenerateCombinedSummariesDryRun:
    """Test dry-run mode returns proper dictionary format."""

    def test_dry_run_returns_dictionary(self):
        """Test that dry-run mode returns a dictionary with all 4 fields."""
        generator = SummaryGenerator(api_key="test_key")

        result = generator.generate_combined_summaries(
            text="Sample book text",
            title="Test Book",
            author="Test Author",
            dry_run=True
        )

        # Verify it's a dictionary
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Verify all 4 keys are present
        expected_keys = [
            'about_text',
            'concise_summary',
            'medium_summary',
            'relevance_now'
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

        # Verify data types
        assert isinstance(result['about_text'], str)
        assert isinstance(result['concise_summary'], str)
        assert isinstance(result['medium_summary'], str)
        assert isinstance(result['relevance_now'], str)

        # Verify DRY RUN placeholders
        assert '[DRY RUN]' in result['about_text']
        assert '[DRY RUN]' in result['concise_summary']
        assert '[DRY RUN]' in result['medium_summary']
        assert '[DRY RUN]' in result['relevance_now']

    def test_dry_run_no_api_calls(self):
        """Test that dry-run mode makes no API calls."""
        generator = SummaryGenerator(api_key="test_key")

        # Mock the client to track calls
        with patch.object(generator, 'client') as mock_client:
            result = generator.generate_combined_summaries(
                text="Sample text",
                title="Test",
                author="Author",
                dry_run=True
            )

            # Verify no API calls were made
            mock_client.models.generate_content.assert_not_called()


class TestGenerateCombinedSummariesParsing:
    """Test parsing of LLM response into dictionary format."""

    def test_parse_well_formatted_response(self, mock_genai_client):
        """Test parsing of properly formatted LLM response with 4 sections."""
        generator = SummaryGenerator(api_key="test_key")

        # Mock LLM response with all 4 sections
        mock_response = Mock()
        mock_response.text = """### ABOUT THE BOOK (75-100 words, no spoilers)
This is a compelling story about adventure and discovery. The protagonist embarks on a journey
that transforms their understanding of the world. Written with elegant prose and deep insight,
this classic work explores timeless themes of human nature, morality, and the search for meaning.
The narrative weaves together complex characters and intricate plot developments.

### CONCISE SUMMARY (500 words)
This is the concise summary of the book. It provides an overview of the main themes,
central conflict, and key characters without revealing spoilers. The setting is established
early, and the narrative arc follows a traditional structure with rising action, climax,
and resolution. The author's writing style is characterized by vivid descriptions.

### MEDIUM SUMMARY (2000-3000 words)
This is a comprehensive analysis of the book. It covers all major plot points, character
developments, and thematic elements in great detail. The summary explores the author's
techniques, narrative structure, and the historical context of the work. It examines
how the various storylines interconnect and build toward the conclusion.

### RELEVANCE NOW (75-100 words)
This book remains relevant today because it addresses universal human experiences and
emotions that transcend time periods. The themes of identity, belonging, and moral
choice resonate with contemporary readers facing similar challenges in modern society.
"""

        # Mock the API client
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client

        result = generator.generate_combined_summaries(
            text="Sample text",
            title="Test Book",
            author="Test Author",
            dry_run=False
        )

        # Verify dictionary structure
        assert isinstance(result, dict)
        assert len(result) == 4

        # Verify content (check for actual content, not template markers)
        assert "compelling story" in result['about_text']
        assert "central conflict" in result['concise_summary']
        assert "comprehensive analysis" in result['medium_summary']
        assert "remains relevant" in result['relevance_now']


class TestGenerateCombinedSummariesIntegration:
    """Integration tests for generate_combined_summaries usage in process flow."""

    def test_backward_compatibility_with_dictionary_extraction(self):
        """Test that dictionary return works with concise/medium extraction."""
        generator = SummaryGenerator(api_key="test_key")

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=True
        )

        # Verify we can extract the traditional fields
        concise = result['concise_summary']
        medium = result['medium_summary']

        assert isinstance(concise, str)
        assert isinstance(medium, str)
        assert len(concise) > 0
        assert len(medium) > 0

    def test_all_metadata_fields_accessible(self):
        """Test that all 4 fields can be accessed independently."""
        generator = SummaryGenerator(api_key="test_key")

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=True
        )

        # Verify each field can be accessed
        about = result.get('about_text')
        concise = result.get('concise_summary')
        medium = result.get('medium_summary')
        relevance = result.get('relevance_now')

        assert about is not None
        assert concise is not None
        assert medium is not None
        assert relevance is not None

        assert isinstance(about, str)
        assert isinstance(concise, str)
        assert isinstance(medium, str)
        assert isinstance(relevance, str)


if __name__ == "__main__":
    print("Running generate_combined_summaries tests...\n")
    pytest.main([__file__, "-v"])
