"""Tuning constants for generate_summaries.py, extracted so they can be
imported without pulling in the entire (multi-thousand-line) SummaryGenerator
class. See generate_summaries.py for how these are used.
"""
from pathlib import Path


class SummaryConstants:
    """Word count targets for summary generation"""
    CONCISE_TARGET_WORDS = 500
    MEDIUM_MIN_WORDS = 2000
    MEDIUM_MAX_WORDS = 3000
    ABOUT_MIN_WORDS = 75
    ABOUT_MAX_WORDS = 100
    RELEVANCE_MIN_WORDS = 75
    RELEVANCE_MAX_WORDS = 100
    MIN_WORDS_FOR_CHAPTER_SUMMARY = 500
    MIN_CHAPTER_SUMMARY_OUTPUT_WORDS = 200


class APIConstants:
    """Gemini API rate limiting and call size constants"""
    # API limits
    MAX_CHARS_PER_CALL = 750000  # ~187.5K tokens (free tier: 250K/min)
    CHARS_PER_TOKEN = 4  # Rough estimation
    MAX_TOKENS_PER_CALL = MAX_CHARS_PER_CALL // CHARS_PER_TOKEN  # ~187.5K tokens

    # Large call handling
    LARGE_CALL_THRESHOLD_TOKENS = 100000
    LARGE_CALL_WAIT_SECONDS = 60

    # Rate limiting windows
    RATE_LIMIT_WINDOW_SECONDS = 60

    # Retry configuration
    MAX_RETRIES = 2
    DEFAULT_RETRY_WAIT_SECONDS = 10
    RATE_LIMIT_RETRY_WAIT_SECONDS = 60

    # Batch processing
    MAX_BATCH_CHARS = 400000  # ~100K tokens for batch input
    MAX_CHAPTERS_PER_BATCH = 10
    MAX_MEDIUM_SUMMARY_CONTEXT_CHARS = 20000
    MAX_PREVIOUS_CHAPTER_CONTEXT_CHARS = 100000


class ContentThresholds:
    """Content size validation thresholds"""
    MIN_PREFACE_WORDS = 100
    MIN_PREFACE_CHARS = 100
    MIN_PREFACE_CONTENT_FOR_CREATION = 300
    MIN_SENTENCE_COUNT_FOR_PREFACE = 3

    MIN_CHAPTER_CHARS_V1 = 100  # Minimum chapter content for chapter detection
    MIN_AVG_CHAPTER_CHARS = 500

    # Coverage validation
    MIN_COVERAGE_PERCENT = 90
    MAX_COVERAGE_PERCENT = 110

    # Title validation
    MIN_TITLE_LENGTH = 5
    MAX_TITLE_LENGTH = 60
    MAX_CHAPTER_TITLE_LENGTH = 150


class ChapterDetectionConstants:
    """Chapter detection and validation thresholds"""
    MIN_CHAPTER_NUMBER = 1
    MAX_CHAPTER_NUMBER = 200  # Maximum expected chapter number

    # Content size thresholds for validation
    MIN_ACCUMULATED_CONTENT_FOR_TOC_END = 1000
    MIN_LOOKAHEAD_CONTENT_FOR_CHAPTER = 500

    # TOC detection
    MIN_PARAGRAPH_LENGTH = 40
    MIN_PARAGRAPH_LINES_FOR_CHAPTER = 3
    MIN_BLANK_LINES_BEFORE_STANDALONE_NUMBER = 2

    # Lookahead limits for validation
    LOOKAHEAD_CHAPTER_TITLE_LINES = 5
    LOOKAHEAD_CONTENT_VALIDATION_LINES = 5
    LOOKAHEAD_TOC_DETECTION_LINES = 15

    # Book marker context
    BOOK_MARKER_CONTEXT_RANGE = 3


class DisplayConstants:
    """Output formatting constants"""
    SEPARATOR_WIDTH = 60
    CHAPTER_BATCH_SEPARATOR_WIDTH = 80  # For batch processing separators
    MAX_PROMPT_PREVIEW_CHARS = 10000
    MAX_ERROR_MESSAGE_CHARS = 100


# Batch API configuration
BATCH_POLL_INTERVAL_SECONDS = 30  # How often to check batch job status
BATCH_MAX_WAIT_HOURS = 24  # Maximum time to wait for batch completion
BATCH_JOBS_DIR = Path(__file__).parent.parent.parent / "data" / "batch_jobs"  # Directory to store batch job state
