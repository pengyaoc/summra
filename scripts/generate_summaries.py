#!/usr/bin/env python3
"""
Summra - Book Summary Generation Script

This script processes book text files and generates three types of summaries
using Google's Gemini API:
1. Concise (500 words, no spoilers for fiction)
2. Medium (2000-3000 words)
3. Comprehensive (chapter-by-chapter with overall summary)

Usage:
    python generate_summaries.py <book_file.txt> [--title "Book Title"] [--author "Author Name"]
    python generate_summaries.py <book_file.txt> --dry-run  # Preview without API calls
    python generate_summaries.py --batch <directory>
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import re
import requests
from urllib.parse import quote

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

from google import genai
from dotenv import load_dotenv

import config
import models


class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.request_times = []
        self.token_counts = []

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Wait if we're approaching rate limits"""
        current_time = time.time()

        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        self.token_counts = [
            (t, count) for t, count in self.token_counts if current_time - t < 60
        ]

        # Check request limit
        if len(self.request_times) >= self.max_requests:
            sleep_time = 60 - (current_time - self.request_times[0]) + 1
            print(f"Rate limit: Waiting {sleep_time:.1f}s for request quota...")
            time.sleep(sleep_time)
            self.request_times = []

        # Check token limit
        total_tokens = sum(count for _, count in self.token_counts)
        if total_tokens + estimated_tokens > self.max_tokens:
            if self.token_counts:
                sleep_time = 60 - (current_time - self.token_counts[0][0]) + 1
                print(f"Rate limit: Waiting {sleep_time:.1f}s for token quota...")
                time.sleep(sleep_time)
            self.token_counts = []

        # Record this request
        self.request_times.append(current_time)
        if estimated_tokens > 0:
            self.token_counts.append((current_time, estimated_tokens))


class SummaryGenerator:
    """Generate book summaries using Gemini API"""

    def __init__(self, api_key: str):
        # Initialize Gemini client with API key
        self.client = genai.Client(api_key=api_key)
        self.db = models.Database()
        self.rate_limiter = RateLimiter(
            config.MAX_REQUESTS_PER_MINUTE,
            config.MAX_TOKENS_PER_MINUTE
        )

    def clean_llm_response(self, text: str) -> str:
        """
        Remove common LLM preamble phrases and clean up the response.
        Removes phrases like "Of course. Here is..." and leading whitespace.
        """
        # Common preamble patterns to remove
        preamble_patterns = [
            r'^Of course[.!]?\s*',
            r'^Certainly[.!]?\s*',
            r'^Sure[.!]?\s*',
            r'^Here is\s+',
            r'^Here\'s\s+',
            r"^Here is a.*?summary.*?[:\n]",
            r"^Here's a.*?summary.*?[:\n]",
            r"^I'll provide.*?[:\n]",
            r"^I will provide.*?[:\n]",
            r"^This is.*?summary.*?[:\n]",
            r"^a\s+(comprehensive|detailed|complete|thorough)\s+summary\s+and\s+analysis\s+of.*?[:\n]",
        ]

        cleaned = text
        for pattern in preamble_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

        # Strip leading/trailing whitespace and newlines
        cleaned = cleaned.strip()

        # Remove leading asterisks and separator lines
        cleaned = re.sub(r'^\*+\s*\n*', '', cleaned)

        # Remove excessive leading newlines (keep max 1)
        cleaned = re.sub(r'^\n+', '', cleaned)

        return cleaned

    def read_book(self, file_path: Path) -> str:
        """Read book text from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

    def extract_metadata(self, text: str, filename: str) -> Tuple[str, str]:
        """
        Extract title and author from book text (common in Project Gutenberg books)
        Returns (title, author)
        """
        lines = text.split('\n')[:50]  # Check first 50 lines

        title = None
        author = None

        for line in lines:
            line = line.strip()
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Author:'):
                author = line.replace('Author:', '').strip()

        # Fallback to filename if not found
        if not title:
            title = filename.replace('.txt', '').replace('_', ' ').title()
        if not author:
            author = "Unknown"

        return title, author

    def extract_gutenberg_id(self, text: str) -> int:
        """
        Extract Project Gutenberg ID from the book text header
        Returns Gutenberg ID or None
        """
        lines = text.split('\n')[:100]  # Check first 100 lines

        for line in lines:
            line = line.strip()
            # Look for patterns like "Release Date: ... [EBook #11]" or "EBook #11"
            if 'EBook' in line and '#' in line:
                match = re.search(r'#(\d+)', line)
                if match:
                    return int(match.group(1))

        return None

    def get_gutenberg_cover_url(self, gutenberg_id: int) -> str:
        """
        Get the cover image URL for a Project Gutenberg book
        Returns cover image URL or None
        """
        # Try multiple cover image formats
        formats = [
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.medium.jpg",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.small.jpg",
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/images/cover.jpg",
        ]

        for url in formats:
            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    print(f"Found cover image: {url}")
                    return url
            except Exception:
                continue

        return None

    def download_gutenberg_cover(self, gutenberg_id: int, dry_run: bool = False) -> str:
        """
        Download and save the cover image for a Project Gutenberg book
        Returns local file path relative to static directory, or None if download fails

        Example return: 'covers/pg11.jpg' (relative to frontend/static/)
        """
        # Get the cover image URL
        cover_url = self.get_gutenberg_cover_url(gutenberg_id)

        if not cover_url:
            print(f"No cover image found for Gutenberg ID {gutenberg_id}")
            return None

        if dry_run:
            print(f"[DRY RUN] Would download cover image from: {cover_url}")
            return f"covers/pg{gutenberg_id}.jpg"

        try:
            # Create covers directory if it doesn't exist
            config.COVERS_DIR.mkdir(parents=True, exist_ok=True)

            # Determine file extension from URL
            file_ext = '.jpg'  # Default to jpg
            if cover_url.endswith('.png'):
                file_ext = '.png'
            elif cover_url.endswith('.gif'):
                file_ext = '.gif'

            # Create local filename
            local_filename = f"pg{gutenberg_id}{file_ext}"
            local_path = config.COVERS_DIR / local_filename

            # Check if image already exists
            if local_path.exists():
                print(f"Cover image already exists: {local_path}")
                # Return path relative to static directory
                return f"covers/{local_filename}"

            # Download the image
            print(f"Downloading cover image from: {cover_url}")
            response = requests.get(cover_url, timeout=10)
            response.raise_for_status()

            # Save the image
            with open(local_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ Saved cover image to: {local_path}")

            # Return path relative to static directory (for serving via web)
            return f"covers/{local_filename}"

        except Exception as e:
            print(f"Error downloading cover image: {e}")
            return None

    def roman_to_int(self, s: str) -> int:
        """Convert Roman numeral to integer"""
        if not s:
            return 0

        roman_map = {
            'I': 1, 'V': 5, 'X': 10, 'L': 50,
            'C': 100, 'D': 500, 'M': 1000
        }

        s = s.upper()
        result = 0
        prev_value = 0

        for char in reversed(s):
            value = roman_map.get(char, 0)
            if value < prev_value:
                result -= value
            else:
                result += value
            prev_value = value

        return result

    def extract_gutenberg_content(self, text: str) -> str:
        """
        Extract the actual book content from Project Gutenberg ebooks.
        Removes headers, footers, and license information.
        """
        # Look for standard Project Gutenberg markers
        start_markers = [
            '*** START OF THE PROJECT GUTENBERG EBOOK',
            '*** START OF THIS PROJECT GUTENBERG EBOOK',
            '***START OF THE PROJECT GUTENBERG EBOOK'
        ]

        end_markers = [
            '*** END OF THE PROJECT GUTENBERG EBOOK',
            '*** END OF THIS PROJECT GUTENBERG EBOOK',
            '***END OF THE PROJECT GUTENBERG EBOOK'
        ]

        # Find start position
        start_pos = 0
        for marker in start_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                # Find the end of the line after the marker
                start_pos = text.find('\n', pos) + 1
                break

        # Find end position
        end_pos = len(text)
        for marker in end_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                end_pos = pos
                break

        # Extract content
        if start_pos > 0 or end_pos < len(text):
            content = text[start_pos:end_pos]
            # Only remove excessive leading/trailing newlines, preserve paragraph spacing
            while content.startswith('\n'):
                content = content[1:]
            while content.endswith('\n'):
                content = content[:-1]
            print(f"Extracted Project Gutenberg content: {len(content)} characters (original: {len(text)})")
            return content

        return text

    def normalize_chapter_text(self, text: str) -> str:
        """
        Normalize chapter text by removing single newlines but keeping paragraph breaks
        Also removes leading/trailing spaces from each line
        Uses single newline between paragraphs
        """
        import re

        # Replace any Windows-style line endings with Unix-style
        text = text.replace('\r\n', '\n')

        # Replace multiple consecutive newlines (3+) with exactly 2 newlines (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Split into paragraphs (separated by double newlines)
        paragraphs = text.split('\n\n')

        # For each paragraph: split lines, trim each line, join with space
        normalized_paragraphs = []
        for paragraph in paragraphs:
            # Split on single newlines
            lines = paragraph.split('\n')
            # Trim each line and filter out empty lines
            trimmed_lines = [line.strip() for line in lines if line.strip()]
            # Join lines within paragraph with space
            normalized_paragraph = ' '.join(trimmed_lines)
            if normalized_paragraph:
                normalized_paragraphs.append(normalized_paragraph)

        # Join paragraphs with single newline
        result = '\n'.join(normalized_paragraphs)

        # Clean up multiple spaces (in case any slipped through)
        result = re.sub(r' {2,}', ' ', result)

        return result

    def detect_chapters(self, text: str) -> List[Tuple[int, str, str]]:
        """
        Detect chapters in the book text, skipping table of contents
        Supports nested book/chapter structure (e.g., "BOOK I", "BOOK II" with chapters)
        Returns list of (chapter_number, chapter_title, chapter_text)
        Chapter numbers are encoded as: book_num * 100 + chapter_num (e.g., 101, 205, 312)
        """
        chapters = []

        # Pattern for BOOK markers (e.g., "BOOK I", "BOOK II")
        book_pattern = r'BOOK\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$'

        # Common chapter patterns - must start new line
        chapter_patterns = [
            r'CHAPTER\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # CHAPTER I: Title or CHAPTER 1
            r'Chapter\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',
        ]

        lines = text.split('\n')
        current_chapter = None
        current_text = []
        current_book_num = 1  # Track current book number for nested structure
        has_book_markers = False  # Track if we found any BOOK markers

        # Track chapter headings to detect TOC (table of contents)
        # If we see many chapter headings close together with little content, it's likely a TOC
        potential_chapters = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines initially
            if not line_stripped:
                if current_chapter is not None:
                    current_text.append(line)
                continue

            # Check if this line is a BOOK marker (e.g., "BOOK I", "BOOK II")
            # Case-sensitive to avoid false positives
            book_match = re.match(book_pattern, line_stripped)
            if book_match:
                has_book_markers = True  # Mark that we found BOOK markers
                book_marker = book_match.group(1)
                # Determine book number from marker
                if book_marker.isdigit():
                    current_book_num = int(book_marker)
                else:
                    # Convert Roman numeral
                    current_book_num = self.roman_to_int(book_marker)
                print(f"Detected Book {current_book_num}")
                # Don't add BOOK markers to text, just update tracking
                continue

            # Explicitly ignore PART markers (e.g., "PART I", "PART II", "PART III")
            # These are section markers within chapters, not chapter boundaries
            # Case-sensitive to avoid false positives
            part_pattern = r'^PART\s+([IVXLCDM]+|[0-9]+)'
            if re.match(part_pattern, line_stripped):
                # This is a section marker within a chapter, include it in current chapter
                if current_chapter is not None:
                    current_text.append(line)
                continue

            # Check if this line is a chapter heading
            is_chapter = False
            chapter_title = None
            chapter_num = None

            for pattern in chapter_patterns:
                # Don't use IGNORECASE - chapter markers should be uppercase to avoid false positives
                # (e.g., "chapter into three parts" should not match)
                match = re.match(pattern, line_stripped)
                if match:
                    is_chapter = True
                    # Convert Roman numerals to numbers or use number directly
                    chapter_marker = match.group(1)
                    chapter_title = match.group(2).strip() if match.group(2) else ""

                    # If title is empty and there's a next line, check if it's the title
                    if not chapter_title and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # If next line is not empty and doesn't look like another chapter header
                        # Case-sensitive to avoid false positives
                        if next_line and not re.match(r'CHAPTER\s+', next_line):
                            chapter_title = next_line

                    # Determine base chapter number from marker
                    base_chapter_num = None
                    if chapter_marker.isdigit():
                        base_chapter_num = int(chapter_marker)
                    else:
                        # Try to convert Roman numeral
                        base_chapter_num = self.roman_to_int(chapter_marker)

                    # Encode as book_num * 100 + chapter_num (e.g., Book 1 Chapter 5 = 105)
                    # For regular books without BOOK markers, use simple encoding (1, 2, 3...)
                    if has_book_markers:
                        chapter_num = current_book_num * 100 + base_chapter_num
                        # Keep original chapter title WITHOUT "Book X, Chapter Y:" prefix
                        # Just store the actual chapter title
                        if not chapter_title:
                            chapter_title = f"Chapter {base_chapter_num}"
                    else:
                        # Regular book - use simple chapter numbering
                        chapter_num = base_chapter_num
                        # Keep original chapter title
                        if not chapter_title:
                            chapter_title = f"Chapter {base_chapter_num}"

                    # Record potential chapter
                    potential_chapters.append({
                        'line_index': i,
                        'marker': chapter_marker,
                        'number': chapter_num,
                        'title': chapter_title,
                        'line': line_stripped
                    })
                    break

            if is_chapter and chapter_num:
                # Save previous chapter (only if it has substantial content)
                if current_chapter is not None and current_text:
                    # Preserve original formatting including paragraph breaks and spacing
                    content = '\n'.join(current_text)
                    # Only remove excessive leading/trailing blank lines
                    while content.startswith('\n'):
                        content = content[1:]
                    while content.endswith('\n'):
                        content = content[:-1]
                    # Normalize newlines: remove single newlines, keep paragraph breaks
                    content = self.normalize_chapter_text(content)
                    # Only save if chapter has more than 100 characters (avoid TOC entries)
                    if len(content) > 100:
                        chapters.append((current_chapter[0], current_chapter[1], content))

                # Start new chapter
                current_chapter = (chapter_num, chapter_title)
                current_text = []
            elif current_chapter is not None:
                # Add to current chapter
                current_text.append(line)

        # Add last chapter
        if current_chapter is not None and current_text:
            # Preserve original formatting including paragraph breaks and spacing
            content = '\n'.join(current_text)
            # Only remove excessive leading/trailing blank lines
            while content.startswith('\n'):
                content = content[1:]
            while content.endswith('\n'):
                content = content[:-1]
            # Normalize newlines: remove single newlines, keep paragraph breaks
            content = self.normalize_chapter_text(content)
            if len(content) > 100:  # Only save if substantial content
                chapters.append((current_chapter[0], current_chapter[1], content))

        # Filter out duplicate chapter numbers (TOC vs actual content)
        # Keep the text from the longest version but preserve title from first occurrence (TOC)
        if chapters:
            chapter_dict = {}
            for chapter_num, chapter_title, chapter_text in chapters:
                if chapter_num in chapter_dict:
                    # Already have this chapter number
                    existing_title, existing_text = chapter_dict[chapter_num]
                    existing_length = len(existing_text)
                    new_length = len(chapter_text)

                    if new_length > existing_length:
                        # Keep longer text, but preserve the FIRST title (from TOC, more complete)
                        # unless the first title is clearly incomplete and the new one is better
                        better_title = existing_title
                        if len(existing_title) < 10 or (len(chapter_title) > len(existing_title) * 1.5):
                            better_title = chapter_title
                        print(f"Found duplicate Chapter {chapter_num}, keeping longer text ({new_length} chars vs {existing_length} chars) with title: {better_title}")
                        chapter_dict[chapter_num] = (better_title, chapter_text)
                else:
                    chapter_dict[chapter_num] = (chapter_title, chapter_text)

            # Rebuild chapters list from dict, sorted by chapter number
            chapters = [(num, title, text) for num, (title, text) in sorted(chapter_dict.items())]

        # Filter out likely TOC: if we have many chapters detected but they're all tiny,
        # we probably hit a table of contents
        if chapters and len(chapters) > 3:
            avg_length = sum(len(ch[2]) for ch in chapters) / len(chapters)
            # If average chapter is less than 500 characters, likely hit TOC, return whole book
            if avg_length < 500:
                print("Warning: Detected potential table of contents. Treating book as single text.")
                chapters = [(1, "Full Text", text)]

        # If no chapters detected, treat the whole book as one chapter
        if not chapters:
            chapters = [(1, "Full Text", text)]

        return chapters

    def generate_concise_summary(self, text: str, title: str, author: str, dry_run: bool = False) -> str:
        """Generate concise 500-word summary without spoilers for fiction"""
        model_name = config.SUMMARY_CONFIGS['concise']['model']

        # Estimate tokens (rough estimate: 1 token ≈ 4 characters)
        estimated_tokens = len(text) // 4 + 500

        prompt = f"""Generate a concise 500-word summary of "{title}" by {author}.

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers (no plot twists, endings, or major reveals). For non-fiction, cover main arguments and key takeaways. Write in an engaging, accessible style.

{text[:50000]}"""

        if dry_run:
            print(f"\n[DRY RUN] Would generate concise summary using {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * 60)
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            print("-" * 60)
            return "[DRY RUN] Summary would be generated here"

        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"Generating concise summary using {model_name}...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        result = self.clean_llm_response(response.text)
        output_words = len(result.split())
        print(f"  ← Output: {output_words:,} words")

        return result

    def generate_medium_summary(self, text: str, title: str, author: str, dry_run: bool = False) -> str:
        """Generate medium-length 2000-3000 word summary"""
        model_name = config.SUMMARY_CONFIGS['medium']['model']

        estimated_tokens = len(text) // 4 + 3000

        prompt = f"""Generate a comprehensive 2000-3000 word summary of "{title}" by {author}.

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions.

{text[:100000]}"""

        if dry_run:
            print(f"\n[DRY RUN] Would generate medium summary using {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * 60)
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            print("-" * 60)
            return "[DRY RUN] Summary would be generated here"

        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"Generating medium summary using {model_name}...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        result = self.clean_llm_response(response.text)
        output_words = len(result.split())
        print(f"  ← Output: {output_words:,} words")

        return result

    def generate_chapter_summary(self, chapter_text: str, chapter_num: int,
                                chapter_title: str, book_title: str,
                                medium_summary: str = None, previous_chapter_text: str = None,
                                dry_run: bool = False, partial_run: bool = False) -> str:
        """Generate summary for a single chapter"""
        model_name = config.SUMMARY_CONFIGS['comprehensive']['model']
        max_words = config.SUMMARY_CONFIGS['comprehensive']['words_per_chapter']

        # Calculate dynamic target: min(chapter_words / 4, max_words)
        chapter_word_count = len(chapter_text.split())
        target_words = min(chapter_word_count // 4, max_words)

        # Ensure a minimum of 200 words for very short chapters
        target_words = max(target_words, 200)

        # Build context sections
        context_sections = []

        if medium_summary:
            context_sections.append(f"""## CONTEXT: Overall Book Summary (for reference only - do not summarize this)

{medium_summary[:10000]}""")

        if previous_chapter_text:
            prev_chapter_num = chapter_num - 1
            context_sections.append(f"""## CONTEXT: Previous Chapter {prev_chapter_num} Content (for reference only - do not summarize this)

{previous_chapter_text[:20000]}""")

        context = "\n\n".join(context_sections) if context_sections else ""

        # Estimate tokens including context
        estimated_tokens = (len(chapter_text) + len(context)) // 4 + target_words

        prompt = f"""Summarize Chapter {chapter_num} of "{book_title}" in approximately {target_words} words.

Chapter title: {chapter_title}

{context}

## CHAPTER {chapter_num} TO SUMMARIZE:

{chapter_text[:80000]}

Cover important events, dialogues, and developments. Analyze character development and relationships. Identify key themes and symbols. Note important quotes. Explain how this chapter advances the overall narrative."""

        if dry_run:
            print(f"\n[DRY RUN] Would generate summary for Chapter {chapter_num}: {chapter_title}")
            print(f"[DRY RUN] Chapter: {chapter_word_count} words → Summary target: {target_words} words (min(words/4, {max_words}))")
            print(f"[DRY RUN] Using model: {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * 60)
            print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
            print("-" * 60)
            return "[DRY RUN] Chapter summary would be generated here"

        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"Generating summary for Chapter {chapter_num}: {chapter_title}...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        summary_text = response.text

        output_words = len(summary_text.split())
        print(f"  ← Output: {output_words:,} words")

        # Display output in partial-run mode
        if partial_run:
            print(f"\n{'='*60}")
            print(f"CHAPTER {chapter_num} SUMMARY OUTPUT:")
            print(f"{'='*60}")
            print(summary_text)
            print(f"{'='*60}\n")

        return summary_text

    def generate_comprehensive_summary(self, text: str, title: str,
                                      author: str, chapters: List[Tuple],
                                      medium_summary: str = None,
                                      dry_run: bool = False,
                                      partial_run: bool = False) -> Tuple[str, List[Dict]]:
        """
        Generate comprehensive summary with chapter breakdowns
        Returns (overall_summary, chapter_summaries)
        """
        chapter_summaries = []
        previous_chapter_text = None

        # Limit to first 3 chapters in partial run mode
        chapters_to_process = chapters[:3] if partial_run else chapters

        if partial_run and len(chapters) > 3:
            print(f"PARTIAL RUN: Processing first 3 of {len(chapters)} chapters\n")

        # Generate summary for each chapter
        for chapter_num, chapter_title, chapter_text in chapters_to_process:
            summary = self.generate_chapter_summary(
                chapter_text, chapter_num, chapter_title, title,
                medium_summary=medium_summary,
                previous_chapter_text=previous_chapter_text,
                dry_run=dry_run,
                partial_run=partial_run
            )
            chapter_summaries.append({
                'chapter_number': chapter_num,
                'chapter_title': chapter_title,
                'summary': summary,
                'word_count': len(summary.split())
            })

            if not dry_run and not partial_run:
                print(f"Saving chapter {chapter_num} to database...")
            elif partial_run:
                print(f"Chapter {chapter_num} complete (not saved in partial run)")

            # Update previous chapter text for next iteration
            previous_chapter_text = chapter_text

        # Show skipped chapters in partial run
        if partial_run and len(chapters) > 3:
            print(f"\n[PARTIAL RUN] Skipped remaining {len(chapters) - 3} chapters:")
            for ch_num, ch_title, _ in chapters[3:]:
                print(f"  - Chapter {ch_num}: {ch_title}")

        # Skip overall analysis in partial run mode
        if partial_run:
            print(f"\n[PARTIAL RUN] Skipping overall comprehensive analysis")
            print(f"[PARTIAL RUN] Total API calls made: 5 (concise + medium + 3 chapters)")
            overall_summary = "[PARTIAL RUN] Overall analysis skipped"
        else:
            # Generate overall literary analysis
            model_name = config.SUMMARY_CONFIGS['comprehensive']['model']
            target_words = config.SUMMARY_CONFIGS['comprehensive']['overall_summary_words']

            # Use full book text for overall analysis, not just chapter summaries
            estimated_tokens = len(text) // 4 + target_words

            prompt = f"""Write a {target_words}-word literary analysis of "{title}" by {author}.

Analyze the relationships between chapters and how they build the narrative arc. Examine the book's structure, pacing, and literary techniques. Discuss recurring themes, motifs, and symbols across the work. Place the book in its historical and cultural context. Explain why this work is considered significant or classic literature. Discuss the author's broader intent, style, and contribution to literature. Go beyond plot summary to provide deep literary analysis.

{text[:150000]}"""

            if dry_run:
                print(f"\n[DRY RUN] Would generate overall analysis using {model_name}")
                print(f"[DRY RUN] Target words: {target_words}")
                print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
                print("-" * 60)
                print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
                print("-" * 60)
                overall_summary = "[DRY RUN] Overall analysis would be generated here"
            else:
                self.rate_limiter.wait_if_needed(estimated_tokens)

                # Log input word count
                input_words = len(prompt.split())
                print(f"Generating comprehensive overall summary using {model_name}...")
                print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                overall_summary = self.clean_llm_response(response.text)

                output_words = len(overall_summary.split())
                print(f"  ← Output: {output_words:,} words")

        return overall_summary, chapter_summaries

    def process_book(self, file_path: Path, title: str = None, author: str = None,
                    dry_run: bool = False, partial_run: bool = False, regenerate_chapters: List[int] = None) -> Dict:
        """Process a single book and generate all summaries"""
        print(f"\n{'='*60}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*60}\n")

        # Read book
        text = self.read_book(file_path)
        print(f"Book loaded: {len(text)} characters, ~{len(text.split())} words")

        # Extract metadata if not provided
        if not title or not author:
            extracted_title, extracted_author = self.extract_metadata(text, file_path.stem)
            title = title or extracted_title
            author = author or extracted_author

        print(f"Title: {title}")
        print(f"Author: {author}\n")

        # Extract Gutenberg ID from header (before content extraction removes it)
        gutenberg_id = self.extract_gutenberg_id(text)
        cover_image_path = None

        if gutenberg_id:
            print(f"Found Gutenberg ID: {gutenberg_id}")
            # Download and save cover image locally
            cover_image_path = self.download_gutenberg_cover(gutenberg_id, dry_run)
            if cover_image_path:
                print(f"Cover image: {cover_image_path}\n")
            else:
                print(f"No cover image found for Gutenberg ID {gutenberg_id}\n")
        else:
            print("No Gutenberg ID found in text\n")

        # Extract Project Gutenberg content (removes headers/footers)
        text = self.extract_gutenberg_content(text)
        print(f"Extracted content: {len(text)} characters, ~{len(text.split())} words\n")

        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN MODE - No API calls will be made")
            print("=" * 60 + "\n")
        elif partial_run:
            print("\n" + "=" * 60)
            print("PARTIAL RUN MODE - Making up to 5 API calls for testing")
            print("Will generate: Concise + Medium + First 3 Chapters")
            print("Note: Reusing existing summaries from DB when available")
            print("API outputs will be displayed to stdout")
            print("=" * 60 + "\n")
        elif regenerate_chapters:
            print("\n" + "=" * 60)
            print(f"REGENERATE CHAPTERS MODE - Regenerating {len(regenerate_chapters)} chapter(s)")
            print(f"Chapters to regenerate: {regenerate_chapters}")
            print("Will skip concise/medium/comprehensive overall summaries")
            print("=" * 60 + "\n")

        # Check if book already exists
        existing_book = self.db.get_book_by_filename(file_path.name)
        if existing_book:
            print(f"Book already exists in database (ID: {existing_book['id']})")
            book_id = existing_book['id']
        else:
            # Add book to database with local cover image path
            book_id = self.db.add_book(title, author, file_path.name, text, gutenberg_id, cover_image_path)
            print(f"Book added to database (ID: {book_id})\n")

        results = {
            'book_id': book_id,
            'title': title,
            'author': author,
            'filename': file_path.name,
            'summaries': {}
        }

        # Detect chapters early if in regenerate mode
        if regenerate_chapters:
            print("\n--- Detecting Chapters ---")
            chapters = self.detect_chapters(text)
            print(f"Detected {len(chapters)} chapter(s)\n")

            # Get medium summary from database for context
            medium_summary_record = self.db.get_summary(book_id, 'medium')
            medium = medium_summary_record['content'] if medium_summary_record else None

            # Filter chapters to only those we want to regenerate
            chapters_to_regenerate = [(num, title, text) for num, title, text in chapters if num in regenerate_chapters]

            if not chapters_to_regenerate:
                print(f"ERROR: None of the requested chapters {regenerate_chapters} were found in the book")
                print(f"Available chapters: {[num for num, _, _ in chapters]}")
                return results

            print(f"Found {len(chapters_to_regenerate)} chapter(s) to regenerate:")
            for ch_num, ch_title, _ in chapters_to_regenerate:
                print(f"  - Chapter {ch_num}: {ch_title}")
            print()

            # Generate summaries for specified chapters
            chapter_summaries = []
            for chapter_num, chapter_title, chapter_text in chapters_to_regenerate:
                print(f"\n--- Regenerating Chapter {chapter_num}: {chapter_title} ---")
                summary = self.generate_chapter_summary(
                    chapter_text, chapter_num, chapter_title, title,
                    medium_summary=medium,
                    dry_run=dry_run
                )

                chapter_summaries.append({
                    'chapter_number': chapter_num,
                    'chapter_title': chapter_title,
                    'summary': summary,
                    'word_count': len(summary.split())
                })

                # Update database
                if not dry_run:
                    # Update chapter summary in database
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE chapters
                        SET summary = ?
                        WHERE book_id = ? AND chapter_number = ?
                    """, (summary, book_id, chapter_num))
                    conn.commit()
                    conn.close()
                    print(f"✓ Updated Chapter {chapter_num} summary in database")

            print(f"\n{'='*60}")
            print(f"✓ Regenerated {len(chapter_summaries)} chapter summaries!")
            print(f"{'='*60}\n")

            return results

        # Generate concise summary
        print("\n--- Generating Concise Summary ---")

        # In partial-run mode, check if we already have this summary
        if partial_run:
            existing_concise = self.db.get_summary(book_id, 'concise')
            if existing_concise:
                concise = existing_concise['content']
                print(f"[PARTIAL RUN] Reusing existing concise summary from database")
            else:
                concise = self.generate_concise_summary(text, title, author, dry_run)
                if not dry_run:
                    self.db.add_summary(book_id, 'concise', concise)
        else:
            concise = self.generate_concise_summary(text, title, author, dry_run)
            if not dry_run:
                self.db.add_summary(book_id, 'concise', concise)

        results['summaries']['concise'] = {
            'text': concise,
            'word_count': len(concise.split())
        }
        print(f"✓ Concise summary: {results['summaries']['concise']['word_count']} words")

        if partial_run and not dry_run:
            print(f"\n{'='*60}")
            print("CONCISE SUMMARY OUTPUT:")
            print(f"{'='*60}")
            print(concise)
            print(f"{'='*60}\n")

        # Generate medium summary
        print("\n--- Generating Medium Summary ---")

        # In partial-run mode, check if we already have this summary
        if partial_run:
            existing_medium = self.db.get_summary(book_id, 'medium')
            if existing_medium:
                medium = existing_medium['content']
                print(f"[PARTIAL RUN] Reusing existing medium summary from database")
            else:
                medium = self.generate_medium_summary(text, title, author, dry_run)
                if not dry_run:
                    self.db.add_summary(book_id, 'medium', medium)
        else:
            medium = self.generate_medium_summary(text, title, author, dry_run)
            if not dry_run:
                self.db.add_summary(book_id, 'medium', medium)

        results['summaries']['medium'] = {
            'text': medium,
            'word_count': len(medium.split())
        }
        print(f"✓ Medium summary: {results['summaries']['medium']['word_count']} words")

        if partial_run and not dry_run:
            print(f"\n{'='*60}")
            print("MEDIUM SUMMARY OUTPUT:")
            print(f"{'='*60}")
            print(medium)
            print(f"{'='*60}\n")

        # Detect chapters
        print("\n--- Detecting Chapters ---")
        chapters = self.detect_chapters(text)
        print(f"Detected {len(chapters)} chapter(s)")

        if dry_run:
            print("\n[DRY RUN] Chapter breakdown:")
            for ch_num, ch_title, ch_text in chapters:
                print(f"  Chapter {ch_num}: {ch_title}")
                print(f"    Length: {len(ch_text)} chars (~{len(ch_text.split())} words)")
            print()

        # Generate comprehensive summary
        print("\n--- Generating Comprehensive Summary ---")
        overall, chapter_summaries = self.generate_comprehensive_summary(
            text, title, author, chapters, medium_summary=medium,
            dry_run=dry_run, partial_run=partial_run
        )

        # Save comprehensive summary
        if not dry_run and not partial_run:
            self.db.add_summary(book_id, 'comprehensive', overall)
        results['summaries']['comprehensive'] = {
            'overall': overall,
            'overall_word_count': len(overall.split()),
            'chapters': chapter_summaries
        }

        # Save chapter summaries with full chapter text
        if not dry_run and not partial_run:
            for ch in chapter_summaries:
                # Find the corresponding chapter text from the original chapters list
                chapter_text = next(
                    (text for num, _, text in chapters if num == ch['chapter_number']),
                    None
                )
                self.db.add_chapter(
                    book_id,
                    ch['chapter_number'],
                    ch['chapter_title'],
                    ch['summary'],
                    chapter_text  # Add the full chapter text
                )

        print(f"✓ Comprehensive summary: {len(overall.split())} words")
        print(f"✓ Chapter summaries: {len(chapter_summaries)} chapters")

        # Save results to JSON file
        if not dry_run and not partial_run:
            output_file = config.SUMMARIES_DIR / f"{file_path.stem}_summaries.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Results saved to: {output_file}")
        elif dry_run:
            print(f"\n[DRY RUN] Results would be saved to: {config.SUMMARIES_DIR / f'{file_path.stem}_summaries.json'}")
        elif partial_run:
            print(f"\n[PARTIAL RUN] Results NOT saved (test mode only)")

        print(f"\n{'='*60}")
        if partial_run:
            print(f"✓ Partial run complete! (5 API calls made)")
            print(f"   Run without --partial-run to generate all summaries")
        else:
            print(f"✓ Book processing complete!")
        print(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(description='Generate book summaries using Gemini API')
    parser.add_argument('input', help='Book file (.txt) or directory for batch processing')
    parser.add_argument('--title', help='Book title (optional, will try to extract from text)')
    parser.add_argument('--author', help='Author name (optional, will try to extract from text)')
    parser.add_argument('--batch', action='store_true', help='Process all .txt files in directory')
    parser.add_argument('--dry-run', action='store_true', help='Preview chapter detection and prompts without making API calls')
    parser.add_argument('--partial-run', action='store_true', help='Test mode: Make only 5 LLM calls (concise + medium + first 3 chapters)')
    parser.add_argument('--regenerate-chapters', help='Regenerate specific chapters only (comma-separated, e.g., "101,111")')

    args = parser.parse_args()

    # Parse regenerate_chapters argument
    regenerate_chapters = None
    if args.regenerate_chapters:
        try:
            regenerate_chapters = [int(ch.strip()) for ch in args.regenerate_chapters.split(',')]
            print(f"Regenerate mode: Will regenerate chapters {regenerate_chapters}")
        except ValueError:
            print("Error: --regenerate-chapters must be comma-separated integers (e.g., '101,111')")
            sys.exit(1)

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        print("Please set it in a .env file or export it")
        sys.exit(1)

    # Initialize generator
    generator = SummaryGenerator(api_key)

    # Process books
    if args.batch:
        # Batch mode: process all .txt files in directory
        input_path = Path(args.input)
        if not input_path.is_dir():
            print(f"Error: {input_path} is not a directory")
            sys.exit(1)

        txt_files = list(input_path.glob('*.txt'))
        if not txt_files:
            print(f"No .txt files found in {input_path}")
            sys.exit(1)

        print(f"Found {len(txt_files)} book(s) to process\n")

        for book_file in txt_files:
            try:
                generator.process_book(book_file, dry_run=args.dry_run, partial_run=args.partial_run, regenerate_chapters=regenerate_chapters)
            except Exception as e:
                print(f"Error processing {book_file.name}: {e}")
                continue

    else:
        # Single file mode
        book_file = Path(args.input)
        if not book_file.exists():
            print(f"Error: File not found: {book_file}")
            sys.exit(1)

        generator.process_book(book_file, args.title, args.author, args.dry_run, args.partial_run, regenerate_chapters)


if __name__ == '__main__':
    main()
