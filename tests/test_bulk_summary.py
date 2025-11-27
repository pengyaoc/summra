#!/usr/bin/env python3
"""
Tests for bulk summary generation and parsing
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

# Add parent directory to path
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


def test_parse_bulk_summary_response():
    """Test parsing of bulk summary responses"""

    # Create mock API key (won't be used in this test)
    generator = SummaryGenerator(api_key="test_key")

    # Test case 1: Well-formatted response
    response_text = """### CHAPTER 1: The Three Metamorphoses
This is a summary of chapter 1. It contains important themes and character development.
### END CHAPTER 1

### CHAPTER 2: The Academic Chairs
This is a summary of chapter 2. It discusses various philosophical concepts.
### END CHAPTER 2

### CHAPTER 3: Backworldsmen
This is a summary of chapter 3 about backworldsmen and their beliefs.
### END CHAPTER 3"""

    # Create index-to-chapter mapping (for simple sequential chapters, it's {1: 1, 2: 2, 3: 3})
    index_to_chapter = {i: i for i in [1, 2, 3]}
    summaries = generator.parse_bulk_summary_response(response_text, index_to_chapter)

    # Verify all chapters parsed
    assert len(summaries) == 3, f"Expected 3 summaries, got {len(summaries)}"
    assert 1 in summaries, "Chapter 1 missing"
    assert 2 in summaries, "Chapter 2 missing"
    assert 3 in summaries, "Chapter 3 missing"

    # Verify content
    assert "summary of chapter 1" in summaries[1].lower()
    assert "summary of chapter 2" in summaries[2].lower()
    assert "summary of chapter 3" in summaries[3].lower()

    # Verify END markers are removed
    assert "### END CHAPTER" not in summaries[1]
    assert "### END CHAPTER" not in summaries[2]
    assert "### END CHAPTER" not in summaries[3]

    print("✓ Test case 1 passed: Well-formatted response")

    # Test case 2: Response without END markers
    # Note: LLM uses sequential indices (1, 2, 3) not actual chapter numbers (10, 11, 12)
    response_text_no_end = """### CHAPTER 1: War and Warriors
This chapter discusses the nature of war.

### CHAPTER 2: The New Idol
This chapter critiques the state.

### CHAPTER 3: The Flies in the Market-Place
This chapter warns against the masses."""

    index_to_chapter_2 = {i+1: ch for i, ch in enumerate([10, 11, 12])}  # {1: 10, 2: 11, 3: 12}
    summaries_2 = generator.parse_bulk_summary_response(response_text_no_end, index_to_chapter_2)

    assert len(summaries_2) == 3, f"Expected 3 summaries, got {len(summaries_2)}"
    assert 10 in summaries_2, "Chapter 10 missing"
    assert 11 in summaries_2, "Chapter 11 missing"
    assert 12 in summaries_2, "Chapter 12 missing"

    print("✓ Test case 2 passed: Response without END markers")

    # Test case 3: Case insensitive parsing
    # Note: LLM uses sequential indices (1, 2) not actual chapter numbers (20, 21)
    response_text_mixed_case = """### Chapter 1: Child and Marriage
This chapter discusses marriage and children.
### end chapter 1

### CHAPTER 2: Voluntary Death
This chapter examines death and when it's appropriate.
### End Chapter 2"""

    index_to_chapter_3 = {i+1: ch for i, ch in enumerate([20, 21])}  # {1: 20, 2: 21}
    summaries_3 = generator.parse_bulk_summary_response(response_text_mixed_case, index_to_chapter_3)

    assert len(summaries_3) == 2, f"Expected 2 summaries, got {len(summaries_3)}"
    assert 20 in summaries_3, "Chapter 20 missing"
    assert 21 in summaries_3, "Chapter 21 missing"

    print("✓ Test case 3 passed: Case insensitive parsing")

    # Test case 4: Missing chapter detection
    # Note: LLM uses sequential indices (1, 3) and skips index 2
    response_text_missing = """### CHAPTER 1: The Famous Wise Ones
This chapter critiques the wise.

### CHAPTER 3: The Dance-Song
This chapter contains a poetic dance."""

    index_to_chapter_4 = {i+1: ch for i, ch in enumerate([30, 31, 32])}  # {1: 30, 2: 31, 3: 32}, index 2 (ch 31) is missing
    summaries_4 = generator.parse_bulk_summary_response(response_text_missing, index_to_chapter_4)

    assert len(summaries_4) == 2, f"Expected 2 summaries (31 missing), got {len(summaries_4)}"
    assert 30 in summaries_4, "Chapter 30 missing"
    assert 31 not in summaries_4, "Chapter 31 should be missing"
    assert 32 in summaries_4, "Chapter 32 missing"

    print("✓ Test case 4 passed: Missing chapter detection")

    print("\n✅ All bulk summary parser tests passed!")


if __name__ == "__main__":
    print("Running bulk summary tests...\n")
    test_parse_bulk_summary_response()
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
