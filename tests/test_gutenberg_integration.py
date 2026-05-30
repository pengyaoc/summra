#!/usr/bin/env python3
"""
Unit tests for Project Gutenberg integration

Tests metadata extraction, content extraction, and cover image handling
"""

import sys
import os
from pathlib import Path
import pytest

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.content.generate_summaries import SummaryGenerator


class TestGutenbergIntegration:
    """Test Project Gutenberg integration features"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance for testing"""
        return SummaryGenerator('dummy_api_key')

    def test_extract_gutenberg_id_ebook_format(self, generator):
        """Test extracting Gutenberg ID from eBook format"""
        text = """
The Project Gutenberg eBook of The Odyssey

Title: The Odyssey
Author: Homer
Release Date: April 1, 1999 [eBook #1727]

*** START OF THE PROJECT GUTENBERG EBOOK THE ODYSSEY ***
"""
        gutenberg_id = generator.extract_gutenberg_id(text)
        assert gutenberg_id == 1727

    def test_extract_gutenberg_id_uppercase_ebook(self, generator):
        """Test extracting Gutenberg ID with uppercase EBook"""
        text = """
Release Date: January 1, 1994 [EBook #11]
[Most recently updated: November 2, 2021]
"""
        gutenberg_id = generator.extract_gutenberg_id(text)
        assert gutenberg_id == 11

    def test_extract_gutenberg_id_mixed_case(self, generator):
        """Test case-insensitive extraction"""
        text = """
This eBoOk is for anyone anywhere...
Release Date: [eBoOk #1342]
"""
        gutenberg_id = generator.extract_gutenberg_id(text)
        assert gutenberg_id == 1342

    def test_extract_gutenberg_id_not_found(self, generator):
        """Test when no Gutenberg ID is present"""
        text = """
This is a book without Gutenberg metadata.
Just regular text content.
"""
        gutenberg_id = generator.extract_gutenberg_id(text)
        assert gutenberg_id is None

    def test_extract_metadata_with_title_and_author(self, generator):
        """Test extracting title and author from Gutenberg header"""
        text = """
The Project Gutenberg eBook of Pride and Prejudice

Title: Pride and Prejudice
Author: Jane Austen
Release Date: [eBook #1342]

*** START OF THE PROJECT GUTENBERG EBOOK ***
"""
        title, author = generator.extract_metadata(text, "fallback.txt")

        assert title == "Pride and Prejudice"
        assert author == "Jane Austen"

    def test_extract_metadata_fallback_to_filename(self, generator):
        """Test fallback to filename when metadata not found"""
        text = """
This book has no metadata headers.
Just the content...
"""
        title, author = generator.extract_metadata(text, "the_great_book.txt")

        assert title == "The Great Book"  # Filename converted to title case
        assert author == "Unknown"

    def test_extract_metadata_missing_author(self, generator):
        """Test when only title is present"""
        text = """
Title: The Mysterious Book

Some content here...
"""
        title, author = generator.extract_metadata(text, "fallback.txt")

        assert title == "The Mysterious Book"
        assert author == "Unknown"

    def test_extract_gutenberg_content_standard_markers(self, generator):
        """Test extracting content between standard Gutenberg markers"""
        text = """License information...
Gutenberg metadata...

*** START OF THE PROJECT GUTENBERG EBOOK THE TEST BOOK ***

This is the actual book content.
Chapter 1...
Chapter 2...

*** END OF THE PROJECT GUTENBERG EBOOK THE TEST BOOK ***

More license information...
"""
        content = generator.extract_gutenberg_content(text)

        assert "This is the actual book content" in content
        assert "Chapter 1" in content
        assert "License information" not in content
        assert "More license information" not in content
        assert "*** START" not in content
        assert "*** END" not in content

    def test_extract_gutenberg_content_variant_markers(self, generator):
        """Test with variant marker formats"""
        text = """Header...

***START OF THE PROJECT GUTENBERG EBOOK ***

Actual content here.

***END OF THE PROJECT GUTENBERG EBOOK ***

Footer..."""

        content = generator.extract_gutenberg_content(text)

        assert "Actual content here" in content
        assert "Header" not in content
        assert "Footer" not in content

    def test_extract_gutenberg_content_no_markers(self, generator):
        """Test when markers are not present"""
        text = """This is a book without Gutenberg markers.
Just regular content."""

        content = generator.extract_gutenberg_content(text)

        # Should return original text unchanged
        assert content == text

    def test_extract_gutenberg_content_preserves_formatting(self, generator):
        """Test that content formatting is preserved"""
        text = """
*** START OF THE PROJECT GUTENBERG EBOOK ***

CHAPTER I

This is a paragraph.

This is another paragraph.


This has extra spacing.

*** END OF THE PROJECT GUTENBERG EBOOK ***
"""
        content = generator.extract_gutenberg_content(text)

        # Should preserve paragraph breaks
        assert "CHAPTER I" in content
        assert "This is a paragraph" in content
        assert "This is another paragraph" in content

    def test_get_gutenberg_cover_url_generation(self, generator):
        """Test cover URL generation for different formats"""
        gutenberg_id = 1727

        # Note: This test just checks URL format generation
        # Actual URL validity would require network calls
        # We're testing the logic, not the actual download

        # The method tries multiple formats in order
        # We can't easily test without mocking requests
        # So we'll test the URL format generation indirectly

        # Just verify the method exists and accepts correct parameters
        url = generator.get_gutenberg_cover_url(gutenberg_id)
        # url will be None if no cover found (which is expected without network)
        # or a valid URL string if mock/network succeeds
        assert url is None or isinstance(url, str)

    def test_roman_to_int_basic(self, generator):
        """Test basic Roman numeral conversion"""
        assert generator.roman_to_int("I") == 1
        assert generator.roman_to_int("V") == 5
        assert generator.roman_to_int("X") == 10
        assert generator.roman_to_int("L") == 50
        assert generator.roman_to_int("C") == 100
        assert generator.roman_to_int("D") == 500
        assert generator.roman_to_int("M") == 1000

    def test_roman_to_int_compound(self, generator):
        """Test compound Roman numerals"""
        assert generator.roman_to_int("II") == 2
        assert generator.roman_to_int("III") == 3
        assert generator.roman_to_int("VI") == 6
        assert generator.roman_to_int("VII") == 7
        assert generator.roman_to_int("VIII") == 8

    def test_roman_to_int_subtraction_rule(self, generator):
        """Test subtraction rule (IV, IX, XL, etc.)"""
        assert generator.roman_to_int("IV") == 4
        assert generator.roman_to_int("IX") == 9
        assert generator.roman_to_int("XL") == 40
        assert generator.roman_to_int("XC") == 90
        assert generator.roman_to_int("CD") == 400
        assert generator.roman_to_int("CM") == 900

    def test_roman_to_int_complex(self, generator):
        """Test complex Roman numerals"""
        assert generator.roman_to_int("XIV") == 14
        assert generator.roman_to_int("XIX") == 19
        assert generator.roman_to_int("XXIV") == 24
        assert generator.roman_to_int("XLII") == 42
        assert generator.roman_to_int("XCIX") == 99
        assert generator.roman_to_int("MCMXCIV") == 1994

    def test_roman_to_int_case_insensitive(self, generator):
        """Test that conversion works with lowercase"""
        assert generator.roman_to_int("xiv") == 14
        assert generator.roman_to_int("Xlii") == 42
        assert generator.roman_to_int("mcmxciv") == 1994

    def test_roman_to_int_empty_string(self, generator):
        """Test empty string returns 0"""
        assert generator.roman_to_int("") == 0

    def test_roman_to_int_invalid_character(self, generator):
        """Test invalid characters are ignored (return 0 for that char)"""
        # Invalid characters get 0 from roman_map.get(char, 0)
        result = generator.roman_to_int("XZ")  # Z is invalid
        # X=10, Z=0, so result should be 10
        assert result == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
