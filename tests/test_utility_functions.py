#!/usr/bin/env python3
"""
Unit tests for utility functions in generate_summaries.py

Tests for:
- normalize_title() - title normalization and truncation
- fix_roman_numerals_in_text() - Roman numeral uppercase conversion
- word_to_int() - Word to number conversion
- get_gutenberg_cover_url() - Cover URL generation
- clean_page_numbers_from_title() - Page number removal
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_summaries import (
    normalize_book_title,
    fix_roman_numerals_in_text,
    SummaryGenerator
)
import pytest


class TestNormalizeBookTitle:
    """Test book title normalization function"""

    def test_simple_title(self):
        """Test basic title without colon or semicolon"""
        result = normalize_book_title("the great gatsby")
        assert result == "The Great Gatsby"

    def test_title_with_colon(self):
        """Test title truncation at colon"""
        result = normalize_book_title("Pride and Prejudice: A Novel")
        assert result == "Pride and Prejudice"

    def test_title_with_semicolon(self):
        """Test title truncation at semicolon"""
        result = normalize_book_title("War and Peace; A Historical Novel")
        assert result == "War and Peace"

    def test_title_with_both_colon_and_semicolon(self):
        """Test truncation uses first delimiter"""
        result = normalize_book_title("Title: Subtitle; Another Part")
        assert result == "Title"

    def test_lowercase_words_in_middle(self):
        """Test that articles/prepositions stay lowercase"""
        result = normalize_book_title("the lord of the rings")
        assert result == "The Lord of the Rings"

    def test_first_word_always_capitalized(self):
        """Test first word is capitalized even if it's an article"""
        result = normalize_book_title("a tale of two cities")
        assert result == "A Tale of Two Cities"

    def test_hyphenated_words(self):
        """Test hyphenated words are properly capitalized"""
        result = normalize_book_title("self-reliance and other essays")
        assert result == "Self-Reliance and Other Essays"

    def test_hyphenated_with_lowercase_word(self):
        """Test hyphenated words with articles"""
        result = normalize_book_title("state-of-the-art technology")
        assert result == "State-of-the-Art Technology"

    def test_empty_title(self):
        """Test empty title returns empty"""
        result = normalize_book_title("")
        assert result == ""

    def test_none_title(self):
        """Test None title returns None"""
        result = normalize_book_title(None)
        assert result is None

    def test_whitespace_only_title(self):
        """Test whitespace-only title"""
        result = normalize_book_title("   ")
        assert result == "   "


class TestFixRomanNumeralsInText:
    """Test Roman numeral uppercase conversion"""

    def test_single_roman_numeral(self):
        """Test converting single title-case Roman numeral"""
        result = fix_roman_numerals_in_text("Book Ii")
        assert result == "Book II"

    def test_multiple_roman_numerals(self):
        """Test converting multiple Roman numerals"""
        result = fix_roman_numerals_in_text("Book Ii, Part Iii, Chapter Iv")
        assert result == "Book II, Part III, Chapter IV"

    def test_high_roman_numerals(self):
        """Test high-value Roman numerals"""
        result = fix_roman_numerals_in_text("Book Xxiii")
        assert result == "Book XXIII"

    def test_mixed_case_preserved(self):
        """Test that already uppercase Roman numerals are preserved"""
        result = fix_roman_numerals_in_text("Book II and Part III")
        assert result == "Book II and Part III"

    def test_lowercase_roman_not_converted(self):
        """Test fully lowercase Roman numerals are NOT converted"""
        result = fix_roman_numerals_in_text("Book ii")
        assert result == "Book ii"  # Pattern only matches title-case (Ii, not ii)

    def test_empty_text(self):
        """Test empty text returns empty"""
        result = fix_roman_numerals_in_text("")
        assert result == ""

    def test_none_text(self):
        """Test None text returns None"""
        result = fix_roman_numerals_in_text(None)
        assert result is None

    def test_no_roman_numerals(self):
        """Test text without Roman numerals unchanged"""
        result = fix_roman_numerals_in_text("Book One, Chapter Two")
        assert result == "Book One, Chapter Two"


class TestWordToInt:
    """Test word to integer conversion"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance"""
        return SummaryGenerator('dummy_api_key')

    def test_one_to_ten(self, generator):
        """Test conversion of words one through ten"""
        assert generator.word_to_int("one") == 1
        assert generator.word_to_int("two") == 2
        assert generator.word_to_int("three") == 3
        assert generator.word_to_int("four") == 4
        assert generator.word_to_int("five") == 5
        assert generator.word_to_int("six") == 6
        assert generator.word_to_int("seven") == 7
        assert generator.word_to_int("eight") == 8
        assert generator.word_to_int("nine") == 9
        assert generator.word_to_int("ten") == 10

    def test_eleven_to_nineteen(self, generator):
        """Test conversion of eleven through nineteen"""
        assert generator.word_to_int("eleven") == 11
        assert generator.word_to_int("twelve") == 12
        assert generator.word_to_int("thirteen") == 13
        assert generator.word_to_int("fifteen") == 15
        assert generator.word_to_int("nineteen") == 19

    def test_tens(self, generator):
        """Test conversion of multiples of ten"""
        assert generator.word_to_int("twenty") == 20
        assert generator.word_to_int("thirty") == 30
        assert generator.word_to_int("fifty") == 50

    def test_invalid_word(self, generator):
        """Test invalid word returns 0"""
        assert generator.word_to_int("invalid") == 0
        assert generator.word_to_int("") == 0


class TestGetGutenbergCoverUrl:
    """Test Gutenberg cover URL generation"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance"""
        return SummaryGenerator('dummy_api_key')

    def test_single_digit_id(self, generator):
        """Test cover URL for single-digit Gutenberg ID"""
        url = generator.get_gutenberg_cover_url(5)
        assert url == "https://www.gutenberg.org/cache/epub/5/pg5.cover.medium.jpg"

    def test_two_digit_id(self, generator):
        """Test cover URL for two-digit Gutenberg ID"""
        url = generator.get_gutenberg_cover_url(42)
        assert url == "https://www.gutenberg.org/cache/epub/42/pg42.cover.medium.jpg"

    def test_large_id(self, generator):
        """Test cover URL for large Gutenberg ID"""
        url = generator.get_gutenberg_cover_url(12345)
        assert url == "https://www.gutenberg.org/cache/epub/12345/pg12345.cover.medium.jpg"


class TestCleanPageNumbersFromTitle:
    """Test page number removal from chapter titles"""

    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance"""
        return SummaryGenerator('dummy_api_key')

    def test_remove_page_numbers(self, generator):
        """Test removal of page numbers from title"""
        result = generator.clean_page_numbers_from_title("Chapter One 123")
        assert result == "Chapter One"

    def test_remove_multiple_page_numbers(self, generator):
        """Test removal of trailing numbers (removes last number only)"""
        result = generator.clean_page_numbers_from_title("The Adventure 42 123 456")
        # Function removes trailing numbers, not all numbers
        assert result == "The Adventure 42 123"

    def test_no_page_numbers(self, generator):
        """Test title without page numbers unchanged"""
        result = generator.clean_page_numbers_from_title("The Great Adventure")
        assert result == "The Great Adventure"

    def test_preserve_chapter_numbers(self, generator):
        """Test that chapter numbers at start are preserved"""
        # This function removes trailing numbers, not leading ones
        result = generator.clean_page_numbers_from_title("Chapter 5: The Beginning")
        assert result == "Chapter 5: The Beginning"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
