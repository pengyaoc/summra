#!/usr/bin/env python3
"""
Fix Huckleberry Finn chapter titles from table of contents.
No LLM calls - just parse TOC and update database.
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database


def roman_to_int(s: str) -> int:
    """Convert Roman numeral to integer"""
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


def parse_toc_from_book(book_path: str) -> dict:
    """Extract chapter titles from table of contents"""
    with open(book_path, 'r', encoding='utf-8') as f:
        text = f.read()

    toc_titles = {}
    lines = text.split('\n')
    in_toc = False
    current_chapter = None
    current_title_parts = []

    for line in lines:
        line_stripped = line.strip()

        # Start of TOC
        if re.match(r'^CONTENTS\.?\s*$', line_stripped, re.IGNORECASE):
            in_toc = True
            continue

        # End of TOC - when we hit ILLUSTRATIONS
        if in_toc and re.match(r'^ILLUSTRATIONS\.?\s*$', line_stripped, re.IGNORECASE):
            break

        if in_toc:
            # Match "CHAPTER I." or "CHAPTER THE LAST."
            chapter_match = re.match(r'^CHAPTER\s+([IVXLCDM]+|THE LAST)\.?\s*$', line_stripped)

            if chapter_match:
                # Save previous chapter if exists
                if current_chapter is not None and current_title_parts:
                    title = '.—'.join(current_title_parts)
                    toc_titles[current_chapter] = title

                # Start new chapter
                chapter_marker = chapter_match.group(1)
                if chapter_marker == "THE LAST":
                    current_chapter = 43  # Special case
                else:
                    current_chapter = roman_to_int(chapter_marker)
                current_title_parts = []

            # Collect title lines (non-empty lines after chapter marker)
            elif current_chapter is not None and line_stripped:
                # Split by .— or just . for subtitle parts
                parts = re.split(r'\.—', line_stripped)
                for part in parts:
                    part = part.strip()
                    if part and not part.endswith('.'):
                        current_title_parts.append(part)
                    elif part and part.endswith('.'):
                        current_title_parts.append(part[:-1])  # Remove trailing period

    # Save last chapter
    if current_chapter is not None and current_title_parts:
        title = '.—'.join(current_title_parts)
        toc_titles[current_chapter] = title

    return toc_titles


def main():
    # Initialize database
    db = Database()

    # Parse TOC
    book_path = "data/books/huckleberry_finn.txt"
    print(f"Parsing table of contents from {book_path}...")
    toc_titles = parse_toc_from_book(book_path)

    print(f"\nFound {len(toc_titles)} chapters in TOC")

    # Get book ID
    book = db.get_book_by_filename("huckleberry_finn.txt")
    if not book:
        print("ERROR: Book not found in database")
        return 1

    book_id = book['id']
    print(f"Book ID: {book_id}")

    # Get current chapters from database
    chapters = db.get_chapters(book_id)
    print(f"\nFound {len(chapters)} chapters in database")

    # Update chapter titles
    conn = db.get_connection()
    cursor = conn.cursor()

    updated_count = 0
    for chapter in chapters:
        chapter_num = chapter['chapter_number']
        current_title = chapter['chapter_title']

        # Get TOC title
        if chapter_num in toc_titles:
            toc_title = toc_titles[chapter_num]

            if current_title != toc_title:
                print(f"\nChapter {chapter_num}:")
                print(f"  Old: {current_title}")
                print(f"  New: {toc_title}")

                cursor.execute(
                    "UPDATE chapters SET chapter_title = ? WHERE book_id = ? AND chapter_number = ?",
                    (toc_title, book_id, chapter_num)
                )
                updated_count += 1
            else:
                print(f"Chapter {chapter_num}: Already correct")
        else:
            print(f"\nWARNING: Chapter {chapter_num} not found in TOC")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Updated {updated_count} chapter titles")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
