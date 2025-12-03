#!/usr/bin/env python3
"""
Tests for generate_combined_summaries() function.

Tests the new 7-field dictionary return format for enhanced book metadata:
1. about_text (150-200 words)
2. concise_summary (500 words)
3. medium_summary (2000-3000 words)
4. relevance_now (100-150 words)
5. author_country (country name)
6. similar_books (list of 5 dicts with title/author)
7. other_books_by_author (list of max 10 titles)
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from generate_summaries import SummaryGenerator


# Module-level fixtures to mock dependencies
@pytest.fixture(autouse=True)
def mock_database():
    """Mock the Database class to prevent production database access"""
    with patch('generate_summaries.models.Database') as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_genai_client():
    """Mock the Gemini AI client to prevent API initialization"""
    with patch('generate_summaries.genai.Client') as mock:
        yield mock


class TestGenerateCombinedSummariesDryRun:
    """Test dry-run mode returns proper dictionary format."""

    def test_dry_run_returns_dictionary(self):
        """Test that dry-run mode returns a dictionary with all 7 fields."""
        generator = SummaryGenerator(api_key="test_key")

        result = generator.generate_combined_summaries(
            text="Sample book text",
            title="Test Book",
            author="Test Author",
            dry_run=True
        )

        # Verify it's a dictionary
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Verify all 7 keys are present
        expected_keys = [
            'about_text',
            'concise_summary',
            'medium_summary',
            'relevance_now',
            'author_country',
            'similar_books',
            'other_books_by_author'
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

        # Verify data types
        assert isinstance(result['about_text'], str)
        assert isinstance(result['concise_summary'], str)
        assert isinstance(result['medium_summary'], str)
        assert isinstance(result['relevance_now'], str)
        assert isinstance(result['author_country'], str)
        assert isinstance(result['similar_books'], list)
        assert isinstance(result['other_books_by_author'], list)

        # Verify list contents
        assert len(result['similar_books']) == 5
        for book in result['similar_books']:
            assert isinstance(book, dict)
            assert 'title' in book
            assert 'author' in book

        assert len(result['other_books_by_author']) == 3
        for title in result['other_books_by_author']:
            assert isinstance(title, str)

        # Verify DRY RUN placeholders
        assert '[DRY RUN]' in result['about_text']
        assert '[DRY RUN]' in result['concise_summary']
        assert '[DRY RUN]' in result['medium_summary']
        assert '[DRY RUN]' in result['relevance_now']
        assert '[DRY RUN]' in result['author_country']

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
        """Test parsing of properly formatted LLM response."""
        generator = SummaryGenerator(api_key="test_key")

        # Mock LLM response with all sections
        mock_response = Mock()
        mock_response.text = """### ABOUT THE BOOK (150-200 words)
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

### RELEVANCE NOW (100-150 words)
This book remains relevant today because it addresses universal human experiences and
emotions that transcend time periods. The themes of identity, belonging, and moral
choice resonate with contemporary readers facing similar challenges in modern society.

### AUTHOR COUNTRY
England

### SIMILAR BOOKS
Pride and Prejudice|Jane Austen
Wuthering Heights|Emily Brontë
Jane Eyre|Charlotte Brontë
Middlemarch|George Eliot
Tess of the d'Urbervilles|Thomas Hardy

### OTHER BOOKS BY AUTHOR
Sense and Sensibility
Emma
Mansfield Park
Northanger Abbey
Persuasion
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
        assert len(result) == 7

        # Verify content (check for actual content, not template markers)
        assert "compelling story" in result['about_text']
        assert "central conflict" in result['concise_summary']  # Check actual content, not template text
        assert "comprehensive analysis" in result['medium_summary']
        assert "remains relevant" in result['relevance_now']
        assert result['author_country'] == 'England'

        # Verify similar books parsing
        assert len(result['similar_books']) == 5
        assert result['similar_books'][0]['title'] == 'Pride and Prejudice'
        assert result['similar_books'][0]['author'] == 'Jane Austen'
        assert result['similar_books'][4]['title'] == "Tess of the d'Urbervilles"

        # Verify other books parsing
        assert len(result['other_books_by_author']) == 5
        assert 'Sense and Sensibility' in result['other_books_by_author']
        assert 'Persuasion' in result['other_books_by_author']

    def test_parse_response_with_country_prefix(self, mock_genai_client):
        """Test that country prefixes are cleaned (e.g., 'Country: France' -> 'France')."""
        generator = SummaryGenerator(api_key="test_key")

        mock_response = Mock()
        mock_response.text = """### ABOUT THE BOOK (150-200 words)
Short about text.

### CONCISE SUMMARY (500 words)
Concise summary text.

### MEDIUM SUMMARY (2000-3000 words)
Medium summary text.

### RELEVANCE NOW (100-150 words)
Relevance text.

### AUTHOR COUNTRY
Country: France

### SIMILAR BOOKS
Book 1|Author 1
Book 2|Author 2
Book 3|Author 3
Book 4|Author 4
Book 5|Author 5

### OTHER BOOKS BY AUTHOR
Other Book 1
"""

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=False
        )

        # Verify country prefix was removed
        assert result['author_country'] == 'France'
        assert 'Country:' not in result['author_country']

    def test_parse_response_with_limited_similar_books(self, mock_genai_client):
        """Test that only first 5 similar books are returned even if more are provided."""
        generator = SummaryGenerator(api_key="test_key")

        mock_response = Mock()
        mock_response.text = """### ABOUT THE BOOK (150-200 words)
About text.

### CONCISE SUMMARY (500 words)
Concise text.

### MEDIUM SUMMARY (2000-3000 words)
Medium text.

### RELEVANCE NOW (100-150 words)
Relevance text.

### AUTHOR COUNTRY
USA

### SIMILAR BOOKS
Book 1|Author 1
Book 2|Author 2
Book 3|Author 3
Book 4|Author 4
Book 5|Author 5
Book 6|Author 6
Book 7|Author 7

### OTHER BOOKS BY AUTHOR
Other 1
"""

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=False
        )

        # Should only return first 5
        assert len(result['similar_books']) == 5
        assert result['similar_books'][0]['title'] == 'Book 1'
        assert result['similar_books'][4]['title'] == 'Book 5'

    def test_parse_response_with_limited_other_books(self, mock_genai_client):
        """Test that only first 10 other books are returned even if more are provided."""
        generator = SummaryGenerator(api_key="test_key")

        mock_response = Mock()
        mock_response.text = """### ABOUT THE BOOK (150-200 words)
About text.

### CONCISE SUMMARY (500 words)
Concise text.

### MEDIUM SUMMARY (2000-3000 words)
Medium text.

### RELEVANCE NOW (100-150 words)
Relevance text.

### AUTHOR COUNTRY
USA

### SIMILAR BOOKS
Book 1|Author 1
Book 2|Author 2
Book 3|Author 3
Book 4|Author 4
Book 5|Author 5

### OTHER BOOKS BY AUTHOR
Book 1
Book 2
Book 3
Book 4
Book 5
Book 6
Book 7
Book 8
Book 9
Book 10
Book 11
Book 12
"""

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        generator.client = mock_client

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=False
        )

        # Should only return first 10
        assert len(result['other_books_by_author']) == 10
        assert 'Book 1' in result['other_books_by_author']
        assert 'Book 10' in result['other_books_by_author']
        assert 'Book 11' not in result['other_books_by_author']


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
        """Test that all metadata fields can be accessed independently."""
        generator = SummaryGenerator(api_key="test_key")

        result = generator.generate_combined_summaries(
            text="Sample", title="Test", author="Author", dry_run=True
        )

        # Verify each field can be accessed
        about = result.get('about_text')
        relevance = result.get('relevance_now')
        country = result.get('author_country')
        similar = result.get('similar_books', [])
        other = result.get('other_books_by_author', [])

        assert about is not None
        assert relevance is not None
        assert country is not None
        assert isinstance(similar, list)
        assert isinstance(other, list)


if __name__ == "__main__":
    print("Running generate_combined_summaries tests...\n")
    pytest.main([__file__, "-v"])
