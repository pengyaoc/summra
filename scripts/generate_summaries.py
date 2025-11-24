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
            # Look for patterns like "Release Date: ... [EBook #11]" or "eBook #11"
            # Case-insensitive search for both "EBook" and "eBook"
            if 'ebook' in line.lower() and '#' in line:
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

    def extract_toc(self, text: str) -> Dict[str, str]:
        """
        Extract table of contents from the text.
        Returns dict mapping roman numerals to expected chapter titles.
        """
        toc = {}
        lines = text.split('\n')

        # Look for CONTENTS section
        in_toc = False
        toc_end_markers = ['INTRODUCTION BY', 'ZARATHUSTRA\'S PROLOGUE', 'FIRST PART', 'CHAPTER I']

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Start of TOC
            if re.match(r'^\s*CONTENTS\.?\s*$', line_stripped, re.IGNORECASE):
                in_toc = True
                continue

            # End of TOC - when we hit the actual content
            if in_toc and any(marker in line_stripped for marker in toc_end_markers):
                if i > 100:  # Make sure we're past the TOC, not just seeing these in TOC
                    break

            # Parse TOC entries
            if in_toc and line_stripped:
                # Match patterns like "LVI. Old and New Tables" or "LVII.  The Convalescent."
                match = re.match(r'^([IVXLCDM]+)\.\s+(.+?)\.?\s*$', line_stripped)
                if match:
                    roman_num = match.group(1)
                    title = match.group(2).strip('. ')
                    toc[roman_num] = title

        return toc

    def detect_chapters(self, text: str) -> List[Tuple[int, str, str]]:
        """
        Detect chapters in the book text, skipping table of contents
        Supports nested book/chapter structure (e.g., "BOOK I", "BOOK II" with chapters)
        Returns list of (chapter_number, chapter_title, chapter_text)
        Chapter numbers are encoded as: book_num * 100 + chapter_num (e.g., 101, 205, 312)
        """
        # Extract TOC for validation
        toc = self.extract_toc(text)
        if toc:
            print(f"Found TOC with {len(toc)} chapters")

        chapters = []

        # Pattern for BOOK/VOLUME/ACT markers (e.g., "BOOK I", "BOOK II", "VOLUME I", "VOLUME II", "ACT I", "ACT II")
        volume_book_pattern = r'(BOOK|VOLUME|ACT)\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$'

        # Common chapter patterns - must start new line
        chapter_patterns = [
            r'CHAPTER\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # CHAPTER I: Title or CHAPTER 1
            r'Chapter\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',
            r'SCENE\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # SCENE I. A public place (for plays)
            r'Scene\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # Scene I. or Scene 1. (for plays)
            r'^([IVXLCDM]+)\.\s+(.+)$',  # Roman numeral only format: "I. TITLE" (must have title after period)
            # Introductory material patterns (all become Chapter 0)
            r'^(INTRODUCTION)$',  # Standalone "INTRODUCTION"
            r'^(Introduction)$',  # Standalone "Introduction"
            r'^(PREFACE)(?:\s+.*)?$',  # "PREFACE" or "PREFACE By The Editor" etc.
            r'^(Preface)(?:\s+.*)?$',  # "Preface" or "Preface Of The Author" etc.
        ]

        lines = text.split('\n')
        current_chapter = None
        current_text = []
        current_book_num = 1  # Track current book number for nested structure
        has_book_markers = False  # Track if we found any BOOK markers

        # Track chapter headings to detect TOC (table of contents)
        # If we see many chapter headings close together with little content, it's likely a TOC
        potential_chapters = []

        # Track BOOK/VOLUME/ACT markers for books where these ARE the chapters (not nested)
        book_markers = []

        # Track illustration blocks to skip chapter markers inside them
        in_illustration = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Track illustration blocks (update state before processing)
            if line_stripped.startswith('[Illustration'):
                in_illustration = True

            # Check if this closes an illustration block
            closes_illustration = in_illustration and line_stripped.endswith(']')

            # Check if line contains a chapter marker (before we skip it)
            has_chapter_marker = any(re.match(pattern, line_stripped) for pattern in chapter_patterns)

            if closes_illustration:
                in_illustration = False
                # Skip this closing line ONLY if it doesn't have a chapter marker
                if not has_chapter_marker:
                    continue

            # Skip empty lines initially
            if not line_stripped:
                if current_chapter is not None and not in_illustration:
                    current_text.append(line)
                continue

            # Check if this line is a BOOK/VOLUME marker (e.g., "BOOK I", "VOLUME II")
            # Case-sensitive to avoid false positives
            volume_book_match = re.match(volume_book_pattern, line_stripped)
            if volume_book_match:
                has_book_markers = True  # Mark that we found BOOK/VOLUME markers
                marker_type = volume_book_match.group(1)  # "BOOK" or "VOLUME"
                marker_numeral = volume_book_match.group(2)  # Roman/Arabic numeral
                marker_title = volume_book_match.group(3).strip() if volume_book_match.group(3) else ""  # Optional title

                # Determine book/volume number from marker
                if marker_numeral.isdigit():
                    current_book_num = int(marker_numeral)
                else:
                    # Convert Roman numeral
                    current_book_num = self.roman_to_int(marker_numeral)

                # Store this BOOK marker for potential conversion to chapter later
                book_markers.append({
                    'line_index': i,
                    'marker_type': marker_type,
                    'number': current_book_num,
                    'numeral': marker_numeral,
                    'title': marker_title,
                    'line': line_stripped
                })

                print(f"Detected {marker_type} {current_book_num}")
                # Don't add BOOK/VOLUME markers to text, just update tracking
                continue

            # Explicitly ignore PART markers (e.g., "PART I", "PART II", "PART III")
            # These are section markers within chapters, not chapter boundaries
            # Case-sensitive to avoid false positives
            part_pattern = r'^PART\s+([IVXLCDM]+|[0-9]+)'
            if re.match(part_pattern, line_stripped):
                # This is a section marker within a chapter, include it in current chapter
                if current_chapter is not None and not in_illustration:
                    current_text.append(line)
                continue

            # Skip chapter detection if inside an illustration block
            if in_illustration:
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
                    # For Roman numeral-only pattern, verify original line only has whitespace before it
                    # This prevents false positives like "Frederick II. But Fate..." where II. starts the line
                    # but is part of a sentence, not a chapter marker
                    if pattern == r'^([IVXLCDM]+)\.\s+(.+)$':
                        # Check if original line (before strip) only has whitespace before the Roman numeral
                        if not line.lstrip() == line_stripped:
                            # Original line had non-whitespace content before the Roman numeral
                            continue
                        # Additionally, require that the title portion is in ALL CAPS or starts with a capital
                        # Real chapters in this format have ALL CAPS titles like "I. THE THREE METAMORPHOSES"
                        # False positives have sentence case like "II. But Fate lay behind it all"
                        title_part = match.group(2).strip()
                        # Get first word of title
                        first_word = title_part.split()[0] if title_part else ""
                        # Skip if first word is not all caps (allows for titles like "THE TITLE" but not "But fate")
                        if first_word and not first_word.isupper():
                            continue

                    is_chapter = True
                    # Convert Roman numerals to numbers or use number directly
                    chapter_marker = match.group(1)
                    # Handle both single-group (PREFACE/INTRODUCTION) and two-group (CHAPTER) patterns
                    try:
                        chapter_title = match.group(2).strip() if match.group(2) else ""
                    except IndexError:
                        # Single-group pattern (PREFACE/INTRODUCTION)
                        chapter_title = ""

                    # Clean up title: remove trailing periods, brackets, and other punctuation
                    chapter_title = re.sub(r'[.\]\[]+$', '', chapter_title).strip()

                    # Check if next line is a continuation of the title (for multi-line titles)
                    # Do this BEFORE removing part markers so we can check if continuation is part of the marker
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()

                        # Check if next line is just a part marker continuation (e.g., " I.", "II.", etc.)
                        # These should be removed, not appended to title
                        is_part_marker_continuation = re.match(r'^[IVXLCDM]+\.$', next_line)

                        # Check if next line looks like a title continuation:
                        # - Not a part marker continuation
                        # - Not another chapter marker
                        # - Not illustration or footnote markers
                        # - Relatively short (< 100 chars)
                        # - Either starts with lowercase or looks like a title word
                        is_continuation = (
                            next_line and
                            not is_part_marker_continuation and
                            not re.match(r'(CHAPTER|Chapter|SCENE|Scene|PREFACE|Preface|INTRODUCTION|Introduction|BOOK|VOLUME|ACT|PART)\s+', next_line) and
                            not re.match(r'^[IVXLCDM]+\.\s+', next_line) and  # Not Roman numeral-only chapter format
                            not next_line.startswith('[Illustration') and
                            not next_line.startswith('By ') and
                            len(next_line) < 100 and
                            len(next_line) > 1 and
                            (next_line[0].islower() or next_line[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or next_line.startswith('Æ'))
                        )

                        # If title is empty OR looks like continuation, use next line
                        if not chapter_title:
                            # Title is empty - use next line as title
                            if is_continuation and len(next_line) > 3:
                                chapter_title = next_line
                        elif is_continuation:
                            # Title exists but next line is likely a continuation - append it
                            chapter_title = chapter_title + ' ' + next_line

                    # Remove part markers from titles (e.g., "—Part I", ".—Part II", ". Part IV", etc.)
                    # Do this AFTER concatenation so we handle multi-line part markers
                    # Handle various formats: "—Part I", "—Part", ".—Part II.", ". Part IV", etc.
                    # The dash is optional (?) to handle cases like ". Part IV" without a dash
                    chapter_title = re.sub(r'[.\s]*[—–-]?\s*Part\s+[IVXLCDM]+[.\s]*$', '', chapter_title, flags=re.IGNORECASE).strip()
                    chapter_title = re.sub(r'[.\s]*[—–-]?\s*Part[.\s]*$', '', chapter_title, flags=re.IGNORECASE).strip()

                    # Determine base chapter number from marker
                    base_chapter_num = None
                    # Special handling for PREFACE and INTRODUCTION (no number)
                    if chapter_marker.upper() in ['PREFACE', 'INTRODUCTION']:
                        base_chapter_num = 0  # Preface/Introduction comes before chapter 1
                        if not chapter_title:
                            chapter_title = "Introduction & Prefaces"  # Generic title for merged introductory content
                    elif chapter_marker.isdigit():
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

                    # TOC-based validation (if TOC exists)
                    if toc:
                        # Check if this chapter marker is in the TOC
                        if chapter_marker not in toc:
                            # Chapter marker not in TOC - skip this false positive
                            is_chapter = False
                            continue

                        # Use the TOC title as the authoritative title
                        toc_title = toc[chapter_marker]
                        # Only replace if the detected title is significantly different
                        # Allow for minor differences (case, punctuation)
                        detected_normalized = chapter_title.upper().strip('. ')
                        toc_normalized = toc_title.upper().strip('. ')
                        if detected_normalized != toc_normalized:
                            # Titles don't match - use TOC title
                            print(f"Chapter {chapter_marker}: Using TOC title '{toc_title}' instead of detected '{chapter_title}'")
                            chapter_title = toc_title

                    # Record potential chapter
                    potential_chapters.append({
                        'line_index': i,
                        'marker': chapter_marker,
                        'number': chapter_num,
                        'title': chapter_title,
                        'line': line_stripped
                    })
                    break

            if is_chapter and chapter_num is not None:
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
                # Skip table of contents entries
                # Pattern 1: Lines starting with "Heading to"
                # Pattern 2: Common TOC headers
                # Pattern 3: Lines with lots of whitespace followed by page numbers (e.g., "Title    123" or "Title    vii")
                is_toc_entry = (
                    line_stripped.startswith('Heading to') or
                    line_stripped.startswith('Dedication') or
                    line_stripped in ['PAGE', 'CONTENTS', 'TABLE OF CONTENTS', 'LIST OF ILLUSTRATIONS', 'Frontispiece', 'Title-page'] or
                    re.match(r'.+\s{10,}[ivxlcdm\d]+\s*$', line_stripped, re.IGNORECASE)  # Text followed by 10+ spaces and page number
                )
                if is_toc_entry:
                    continue

                # Add to current chapter (skip illustration content)
                if not in_illustration:
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

        # Filter out duplicate chapter numbers and merge multi-part chapters
        # For chapters split into parts (e.g., "Chapter X Part I", "Chapter X Part II"),
        # concatenate all parts together into one chapter
        if chapters:
            chapter_dict = {}
            for chapter_num, chapter_title, chapter_text in chapters:
                if chapter_num in chapter_dict:
                    # Already have this chapter number - merge the parts
                    existing_title, existing_text = chapter_dict[chapter_num]
                    existing_length = len(existing_text)
                    new_length = len(chapter_text)

                    # Concatenate the texts with a separator
                    merged_text = existing_text + "\n\n" + chapter_text

                    # Keep the LONGEST title (most complete version)
                    # This handles cases where TOC entries are shorter than actual chapter titles
                    better_title = existing_title

                    # Special handling for Chapter 0 (Introduction/Preface)
                    # Always prefer "Introduction & Prefaces" over specific footnote titles
                    if chapter_num == 0:
                        if "Introduction" in existing_title or "Preface" in existing_title:
                            better_title = existing_title  # Keep the generic intro title
                        elif "Introduction" in chapter_title or "Preface" in chapter_title:
                            better_title = chapter_title  # Use the new intro title
                        # Otherwise keep existing_title (first encountered)
                    else:
                        # Always prefer the longer title (more complete)
                        if len(chapter_title) > len(existing_title):
                            better_title = chapter_title

                    print(f"Merged Chapter {chapter_num} parts: {existing_length} + {new_length} = {len(merged_text)} chars (title: {better_title})")
                    chapter_dict[chapter_num] = (better_title, merged_text)
                else:
                    chapter_dict[chapter_num] = (chapter_title, chapter_text)

            # Rebuild chapters list from dict, sorted by chapter number
            chapters = [(num, title, text) for num, (title, text) in sorted(chapter_dict.items())]

        # Improved TOC detection: filter out short chapter instances that are likely TOC entries
        # If we detect duplicate chapter numbers where some are very short (TOC) and some are longer (actual),
        # keep only the longer versions
        if chapters and len(chapters) > 3:
            # Group chapters by chapter number to find duplicates
            chapter_groups = {}
            for ch_num, ch_title, ch_text in chapters:
                if ch_num not in chapter_groups:
                    chapter_groups[ch_num] = []
                chapter_groups[ch_num].append((ch_num, ch_title, ch_text, len(ch_text)))

            # If we have multiple instances of the same chapter number,
            # keep only instances that are > 500 chars (likely actual chapters, not TOC)
            filtered_chapters = []
            for ch_num in sorted(chapter_groups.keys()):
                instances = chapter_groups[ch_num]
                if len(instances) > 1:
                    # Multiple instances - filter by length
                    # Keep only those > 500 chars (the longer, actual chapters)
                    long_instances = [inst for inst in instances if inst[3] > 500]
                    if long_instances:
                        # Add the longest instance (should be just one after merging was already done)
                        longest = max(long_instances, key=lambda x: x[3])
                        filtered_chapters.append((longest[0], longest[1], longest[2]))
                    else:
                        # All instances are short - keep the longest one
                        longest = max(instances, key=lambda x: x[3])
                        filtered_chapters.append((longest[0], longest[1], longest[2]))
                else:
                    # Only one instance - keep it if it's substantial enough
                    ch_num, ch_title, ch_text, ch_len = instances[0]
                    filtered_chapters.append((ch_num, ch_title, ch_text))

            # If we filtered out any chapters, update the list
            if len(filtered_chapters) != len(chapters):
                print(f"Filtered out {len(chapters) - len(filtered_chapters)} TOC entries, keeping {len(filtered_chapters)} actual chapters")
                chapters = filtered_chapters

            # Final sanity check: if ALL remaining chapters are tiny (< 500 chars average),
            # likely the entire detection failed and we should treat as single text
            if chapters:
                avg_length = sum(len(ch[2]) for ch in chapters) / len(chapters)
                if avg_length < 500:
                    print("Warning: Detected potential table of contents. Treating book as single text.")
                    chapters = [(1, "Full Text", text)]

        # Special handling: If we found BOOK/VOLUME/ACT markers but no nested chapters,
        # treat the BOOK markers themselves as chapters
        # This handles cases where BOOK/VOLUME/ACT are the actual chapters (e.g., The Odyssey)
        # Condition: We have BOOK markers AND either:
        #   1. No chapters at all
        #   2. Only a few chapters (like just intro/preface) compared to many BOOK markers
        should_convert_books = False
        if book_markers and len(book_markers) > 3:
            # Count chapters that aren't just intro/preface (chapter 0 or X00 encoded)
            # Also exclude very large chapter numbers like 2400 which suggest merged content
            non_intro_chapters = [ch for ch in chapters if ch[0] != 0 and ch[0] % 100 != 0]

            # If we have way fewer actual chapters than BOOK markers, convert the BOOK markers
            if len(non_intro_chapters) < len(book_markers) * 0.3:  # Less than 30% of expected
                should_convert_books = True
                print(f"Detected {len(book_markers)} {book_markers[0]['marker_type']} markers but only {len(non_intro_chapters)} nested chapters")
                print(f"Converting {book_markers[0]['marker_type']} markers to chapters with simple numbering")

        if should_convert_books:
            # Clear existing chapters (they're just merged preface/intro content)
            chapters = []

            # Deduplicate book_markers - keep only LAST occurrence of each book number
            # (BOOK markers often appear twice: once in TOC, once in actual content)
            # We want the actual content occurrence, not the TOC occurrence
            seen_numbers = {}
            for marker in book_markers:
                # Always update - this keeps the last occurrence
                seen_numbers[marker['number']] = marker

            # Convert back to list, sorted by book number
            unique_book_markers = [seen_numbers[num] for num in sorted(seen_numbers.keys())]

            print(f"Deduplicated to {len(unique_book_markers)} unique {unique_book_markers[0]['marker_type']} markers")

            # Extract content for each BOOK marker
            book_markers = unique_book_markers
            for idx, marker_info in enumerate(book_markers):
                book_num = marker_info['number']
                marker_type = marker_info['marker_type']
                marker_title = marker_info['title']
                start_line = marker_info['line_index']

                # Determine end line (next BOOK marker or end of text)
                if idx + 1 < len(book_markers):
                    end_line = book_markers[idx + 1]['line_index']
                else:
                    end_line = len(lines)

                # Extract content between this BOOK marker and the next
                book_content_lines = lines[start_line + 1:end_line]
                book_content = '\n'.join(book_content_lines)

                # Normalize the content
                book_content = self.normalize_chapter_text(book_content)

                # Create a descriptive title
                if marker_title:
                    chapter_title = f"{marker_type} {marker_info['numeral']}: {marker_title}"
                else:
                    chapter_title = f"{marker_type} {marker_info['numeral']}"

                # Use simple sequential numbering (1, 2, 3...) instead of nested encoding
                chapter_num = book_num

                if len(book_content) > 100:  # Only add if substantial content
                    chapters.append((chapter_num, chapter_title, book_content))

            print(f"Created {len(chapters)} chapters from {book_markers[0]['marker_type']} markers")

        # If no chapters detected, treat the whole book as one chapter
        if not chapters:
            chapters = [(1, "Full Text", text)]

        return chapters

    def generate_concise_summary(self, text: str, title: str, author: str, dry_run: bool = False) -> str:
        """Generate concise 500-word summary without spoilers for fiction"""
        model_name = config.SUMMARY_CONFIGS['concise']['model']

        # Estimate tokens (rough estimate: 1 token ≈ 4 characters)
        # Cap at 1 million characters to avoid exceeding token limit
        estimated_tokens = min(len(text), 1000000) // 4 + 500

        prompt = f"""Generate a concise 500-word summary of "{title}" by {author}.

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers (no plot twists, endings, or major reveals). For non-fiction, cover main arguments and key takeaways. Write in an engaging, accessible style.

{text[:1000000]}"""

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

        # Estimate tokens (rough estimate: 1 token ≈ 4 characters)
        # Cap at 1 million characters to avoid exceeding token limit
        estimated_tokens = min(len(text), 1000000) // 4 + 3000

        prompt = f"""Generate a comprehensive 2000-3000 word summary of "{title}" by {author}.

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions.

{text[:1000000]}"""

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

    def batch_chapters(self, chapters: List[Tuple]) -> List[List[Tuple]]:
        """
        Batch chapters together for bulk processing.
        Returns list of batches, where each batch is a list of (chapter_num, chapter_title, chapter_text) tuples.
        """
        if not config.BULK_SUMMARY_CONFIG['enabled']:
            # If bulk processing disabled, return each chapter as its own batch
            return [[ch] for ch in chapters]

        max_batch_words = config.BULK_SUMMARY_CONFIG['max_batch_words']
        max_chapters_per_batch = config.BULK_SUMMARY_CONFIG['max_chapters_per_batch']

        batches = []
        current_batch = []
        current_batch_words = 0

        for chapter_num, chapter_title, chapter_text in chapters:
            chapter_words = len(chapter_text.split())

            # Check if adding this chapter would exceed limits
            would_exceed_words = current_batch_words + chapter_words > max_batch_words
            would_exceed_count = len(current_batch) >= max_chapters_per_batch

            if current_batch and (would_exceed_words or would_exceed_count):
                # Start new batch
                batches.append(current_batch)
                current_batch = []
                current_batch_words = 0

            # Add chapter to current batch
            current_batch.append((chapter_num, chapter_title, chapter_text))
            current_batch_words += chapter_words

        # Add final batch if not empty
        if current_batch:
            batches.append(current_batch)

        return batches

    def parse_bulk_summary_response(self, response_text: str, chapter_numbers: List[int]) -> Dict[int, str]:
        """
        Parse bulk summary response to extract individual chapter summaries.
        Returns dict mapping chapter_number -> summary_text
        """
        summaries = {}

        # Split by chapter markers
        # Expected format: ### CHAPTER N: TITLE\n[content]\n### END CHAPTER N
        pattern = r'###\s*CHAPTER\s+(\d+):\s*[^\n]*\n(.*?)(?=###\s*(?:CHAPTER\s+\d+:|END\s+CHAPTER\s+\d+)|$)'

        matches = re.finditer(pattern, response_text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            chapter_num = int(match.group(1))
            summary_text = match.group(2).strip()

            # Remove the END CHAPTER marker if present
            summary_text = re.sub(r'###\s*END\s+CHAPTER\s+\d+\s*$', '', summary_text, flags=re.IGNORECASE).strip()

            summaries[chapter_num] = summary_text

        # Verify we got all expected chapters
        missing = set(chapter_numbers) - set(summaries.keys())
        if missing:
            print(f"  ⚠️  Warning: Missing summaries for chapters: {sorted(missing)}")

        return summaries

    def generate_bulk_chapter_summaries(self, chapters_batch: List[Tuple], book_title: str,
                                       medium_summary: str = None, dry_run: bool = False,
                                       partial_run: bool = False) -> Dict[int, str]:
        """
        Generate summaries for multiple chapters in a single API call.
        Returns dict mapping chapter_number -> summary_text
        """
        model_name = config.SUMMARY_CONFIGS['comprehensive']['model']
        max_words = config.SUMMARY_CONFIGS['comprehensive']['words_per_chapter']

        # Build the prompt with all chapters
        # Calculate dynamic target words for each chapter (same as regular mode)
        chapters_text = []
        chapter_numbers = []
        chapter_targets = {}  # Map chapter_num -> target_words
        total_words = 0
        total_target_words = 0

        for chapter_num, chapter_title, chapter_text in chapters_batch:
            chapter_numbers.append(chapter_num)
            chapter_word_count = len(chapter_text.split())
            total_words += chapter_word_count

            # Calculate dynamic target: min(chapter_words / 4, max_words)
            # Ensure a minimum of 200 words for very short chapters
            target_words = min(chapter_word_count // 4, max_words)
            target_words = max(target_words, 200)
            chapter_targets[chapter_num] = target_words
            total_target_words += target_words

            # Format: CHAPTER N: TITLE\n[content]\n\n
            chapter_section = f"CHAPTER {chapter_num}: {chapter_title}\n\n{chapter_text}"
            chapters_text.append(chapter_section)

        # Build context section
        context = ""
        if medium_summary:
            context = f"""## CONTEXT: Overall Book Summary (for reference)\n\n{medium_summary[:5000]}\n\n"""

        # Build chapter-specific word count instructions
        chapter_instructions = []
        for chapter_num, chapter_title, _ in chapters_batch:
            target = chapter_targets[chapter_num]
            chapter_instructions.append(f"  - Chapter {chapter_num}: {chapter_title} (~{target} words)")

        # Build structured prompt
        prompt = f"""Summarize the following {len(chapters_batch)} chapters from "{book_title}".

IMPORTANT: Format your response EXACTLY as shown below. Use the exact chapter numbers provided. Follow the word count targets for each chapter:

{chr(10).join(chapter_instructions)}

FORMAT:
### CHAPTER N: TITLE
[Your summary here following the word count target above]
Cover important events, dialogues, and developments. Analyze character development and relationships. Identify key themes and symbols. Note important quotes. Explain how this chapter advances the overall narrative.

### END CHAPTER N

{context}## CHAPTERS TO SUMMARIZE:

{"=" * 80}
{chr(10).join(chapters_text)}
{"=" * 80}

Now provide summaries for all {len(chapters_batch)} chapters above, following the exact format and word count targets specified."""

        if dry_run:
            print(f"\n[DRY RUN] Would generate bulk summary for {len(chapters_batch)} chapters")
            print(f"[DRY RUN] Chapters: {chapter_numbers}")
            print(f"[DRY RUN] Total input: {total_words:,} words")
            print(f"[DRY RUN] Expected output: ~{total_target_words:,} words")
            return {ch_num: f"[DRY RUN] Summary for chapter {ch_num}" for ch_num in chapter_numbers}

        # Estimate tokens
        estimated_tokens = len(prompt) // 4 + total_target_words
        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input
        print(f"Generating bulk summary for {len(chapters_batch)} chapters: {chapter_numbers}")
        print(f"  → Input: {total_words:,} words (~{len(prompt):,} chars)")

        # Make API call
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        response_text = response.text
        output_words = len(response_text.split())
        print(f"  ← Output: {output_words:,} words")

        # Display output in partial-run mode
        if partial_run:
            print(f"\n{'='*60}")
            print(f"BULK SUMMARY OUTPUT (Chapters {chapter_numbers[0]}-{chapter_numbers[-1]}):")
            print(f"{'='*60}")
            print(response_text)
            print(f"{'='*60}\n")

        # Parse response
        summaries = self.parse_bulk_summary_response(response_text, chapter_numbers)

        # Verify we got all summaries
        if len(summaries) == len(chapter_numbers):
            print(f"  ✓ Successfully parsed all {len(summaries)} chapter summaries")
        else:
            print(f"  ⚠️  Parsed {len(summaries)}/{len(chapter_numbers)} summaries")

        return summaries

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

{chapter_text}

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
                                      book_id: int = None,
                                      medium_summary: str = None,
                                      dry_run: bool = False,
                                      partial_run: bool = False) -> Tuple[str, List[Dict]]:
        """
        Generate comprehensive summary with chapter breakdowns
        Returns (overall_summary, chapter_summaries)
        """
        chapter_summaries = []

        # Limit to first 3 chapters in partial run mode
        chapters_to_process = chapters[:3] if partial_run else chapters

        if partial_run and len(chapters) > 3:
            print(f"PARTIAL RUN: Processing first 3 of {len(chapters)} chapters\n")

        # Check if bulk processing is enabled
        use_bulk = config.BULK_SUMMARY_CONFIG['enabled'] and not partial_run

        if use_bulk:
            # Batch chapters for bulk processing
            batches = self.batch_chapters(chapters_to_process)
            print(f"\n--- Using Bulk Chapter Summaries ({len(batches)} batches for {len(chapters_to_process)} chapters) ---")

            batch_num = 0
            for batch in batches:
                batch_num += 1
                batch_chapter_nums = [ch[0] for ch in batch]
                print(f"\nBatch {batch_num}/{len(batches)}: Chapters {batch_chapter_nums[0]}-{batch_chapter_nums[-1]} ({len(batch)} chapters)")

                # Generate bulk summaries
                bulk_summaries = self.generate_bulk_chapter_summaries(
                    batch,
                    title,
                    medium_summary=medium_summary,
                    dry_run=dry_run,
                    partial_run=partial_run
                )

                # Process results and save to database
                for chapter_num, chapter_title, chapter_text in batch:
                    summary = bulk_summaries.get(chapter_num, f"ERROR: Summary not generated for chapter {chapter_num}")

                    chapter_summaries.append({
                        'chapter_number': chapter_num,
                        'chapter_title': chapter_title,
                        'summary': summary,
                        'word_count': len(summary.split())
                    })

                    # Commit chapter to database immediately after generation
                    if not dry_run and not partial_run and book_id is not None:
                        self.db.add_chapter(
                            book_id,
                            chapter_num,
                            chapter_title,
                            summary,
                            chapter_text  # Full chapter text
                        )
                        print(f"  ✓ Saved chapter {chapter_num} to database")

            print(f"\n✓ Completed all {len(batches)} batches")

        else:
            # Use single-chapter processing (original method)
            print(f"\n--- Using Single Chapter Summaries ({len(chapters_to_process)} API calls) ---")
            previous_chapter_text = None

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

                # Commit chapter to database immediately after generation
                if not dry_run and not partial_run and book_id is not None:
                    self.db.add_chapter(
                        book_id,
                        chapter_num,
                        chapter_title,
                        summary,
                        chapter_text  # Full chapter text
                    )
                    print(f"✓ Saved chapter {chapter_num} to database")
                elif partial_run:
                    print(f"Chapter {chapter_num} complete (not saved in partial run)")

                # Update previous chapter text for next iteration
                previous_chapter_text = chapter_text

        # Show skipped chapters in partial run
        if partial_run and len(chapters) > 3:
            print(f"\n[PARTIAL RUN] Skipped remaining {len(chapters) - 3} chapters:")
            for ch_num, ch_title, _ in chapters[3:]:
                print(f"  - Chapter {ch_num}: {ch_title}")

        # Skip overall analysis - no longer generating comprehensive overall summaries
        if partial_run:
            print(f"\n[PARTIAL RUN] Skipping overall comprehensive analysis")
            if use_bulk:
                print(f"[PARTIAL RUN] Total API calls made: 2+ (concise + medium + bulk batches)")
            else:
                print(f"[PARTIAL RUN] Total API calls made: 5 (concise + medium + 3 chapters)")
        else:
            print(f"\nSkipping overall comprehensive analysis (disabled)")

        overall_summary = ""  # No overall summary generated

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

            # Generate summaries for specified chapters using bulk mode if enabled
            chapter_summaries = []

            # Check if bulk processing is enabled
            use_bulk = config.BULK_SUMMARY_CONFIG['enabled']

            if use_bulk:
                # Batch chapters for bulk processing
                batches = self.batch_chapters(chapters_to_regenerate)
                print(f"\n--- Using Bulk Chapter Summaries ({len(batches)} batches for {len(chapters_to_regenerate)} chapters) ---\n")

                batch_num = 0
                for batch in batches:
                    batch_num += 1
                    batch_chapter_nums = [ch[0] for ch in batch]
                    print(f"Batch {batch_num}/{len(batches)}: Chapters {batch_chapter_nums[0]}-{batch_chapter_nums[-1]} ({len(batch)} chapters)")

                    # Generate bulk summaries
                    bulk_summaries = self.generate_bulk_chapter_summaries(
                        batch,
                        title,
                        medium_summary=medium,
                        dry_run=dry_run
                    )

                    # Process results and update database
                    for chapter_num, chapter_title, chapter_text in batch:
                        summary = bulk_summaries.get(chapter_num, f"ERROR: Summary not generated for chapter {chapter_num}")

                        chapter_summaries.append({
                            'chapter_number': chapter_num,
                            'chapter_title': chapter_title,
                            'summary': summary,
                            'word_count': len(summary.split())
                        })

                        # Add/update chapter in database (INSERT OR REPLACE)
                        if not dry_run:
                            self.db.add_chapter(
                                book_id,
                                chapter_num,
                                chapter_title,
                                summary,
                                chapter_text  # Full chapter text
                            )
                            print(f"  ✓ Saved chapter {chapter_num} to database")

                print(f"\n✓ Completed all {len(batches)} batches")
            else:
                # Use single-chapter processing (original method)
                print(f"\n--- Using Single Chapter Summaries ({len(chapters_to_regenerate)} API calls) ---\n")
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

                    # Add/update chapter in database (INSERT OR REPLACE)
                    if not dry_run:
                        self.db.add_chapter(
                            book_id,
                            chapter_num,
                            chapter_title,
                            summary,
                            chapter_text  # Full chapter text
                        )
                        print(f"✓ Saved Chapter {chapter_num} to database")

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

        # Calculate total parsed content
        total_parsed_chars = sum(len(ch_text) for _, _, ch_text in chapters)
        original_chars = len(text)
        coverage_percent = (total_parsed_chars / original_chars * 100) if original_chars > 0 else 0

        print(f"\nContent Coverage:")
        print(f"  Original text: {original_chars:,} chars")
        print(f"  Parsed chapters: {total_parsed_chars:,} chars")
        print(f"  Coverage: {coverage_percent:.1f}%")

        if coverage_percent < 90:
            print(f"  ⚠️  WARNING: Only {coverage_percent:.1f}% of content captured - may be losing content!")
        elif coverage_percent > 110:
            print(f"  ⚠️  WARNING: Parsed content is {coverage_percent:.1f}% - may have duplicates!")
        else:
            print(f"  ✓ Good coverage - parsing looks correct")

        if dry_run:
            print("\n[DRY RUN] Chapter breakdown:")
            for ch_num, ch_title, ch_text in chapters:
                print(f"  Chapter {ch_num}: {ch_title}")
                print(f"    Length: {len(ch_text)} chars (~{len(ch_text.split())} words)")
            print()

        # Generate comprehensive summary
        print("\n--- Generating Comprehensive Summary ---")
        overall, chapter_summaries = self.generate_comprehensive_summary(
            text, title, author, chapters,
            book_id=book_id,
            medium_summary=medium,
            dry_run=dry_run, partial_run=partial_run
        )

        # Save comprehensive summary (only if not empty)
        if not dry_run and not partial_run and overall:
            self.db.add_summary(book_id, 'comprehensive', overall)
        results['summaries']['comprehensive'] = {
            'overall': overall,
            'overall_word_count': len(overall.split()) if overall else 0,
            'chapters': chapter_summaries
        }

        # Note: Chapters are now saved immediately after generation (see generate_comprehensive_summary)

        if overall:
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
