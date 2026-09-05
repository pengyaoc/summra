#!/usr/bin/env python3
"""
Backfill script to normalize all chapter titles to title case.

This script updates existing chapter titles in the database to use consistent
title case formatting.
"""

from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent / 'backend'

import sqlite3


def normalize_chapter_title(title: str) -> str:
    """
    Normalize chapter title to use consistent title case.
    Converts to title case while preserving certain words in lowercase.
    Handles special cases:
    - Words inside quotes are always capitalized (including first word)
    - Words after em-dashes (—) are capitalized
    - Words after colons (:) are capitalized
    - Words after periods (.) are capitalized

    This is a copy of the function from generate_summaries.py to ensure
    consistency between backfill and future generation.
    """
    import re

    if not title or not title.strip():
        return title

    # Words that should remain lowercase in titles (unless first word, after punctuation, or in quotes)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    # First, handle em-dashes by adding spaces around them
    # This ensures "Huck.—miss" becomes "Huck.— miss" so we can capitalize properly
    title = title.replace('—', ' — ')
    # Also handle colons followed directly by letters
    title = re.sub(r':(\S)', r': \1', title)
    # Collapse multiple spaces into one
    title = re.sub(r'\s+', ' ', title).strip()

    # Track whether we're inside quotes and if we need to capitalize next word
    in_quotes = False
    capitalize_next = True  # Always capitalize first word
    result = []

    # Split on whitespace while preserving spaces
    words = title.split()

    for i, word in enumerate(words):
        # Check if word contains quotes (opening or closing)
        # Handle both straight quotes and curly quotes (U+201C LEFT, U+201D RIGHT)
        has_quote = '"' in word or '\u201c' in word or '\u201d' in word
        starts_with_quote = word.startswith('"') or word.startswith('\u201c') or word.startswith('\u201d')

        if has_quote:
            in_quotes = not in_quotes

        # Handle standalone em-dash
        if word == '—':
            result.append(word)
            capitalize_next = True
            continue

        # Handle hyphenated words - capitalize each part appropriately
        if '-' in word and not starts_with_quote:
            parts = word.split('-')
            capitalized_parts = []
            for j, part in enumerate(parts):
                # First part or parts that aren't lowercase words
                # Also capitalize if we need to capitalize next word (after colon/period)
                if j == 0:
                    # First part: capitalize if capitalize_next is True, otherwise apply normal rules
                    if capitalize_next or in_quotes:
                        capitalized_parts.append(part.capitalize())
                        capitalize_next = False
                    elif part.lower() in lowercase_words and i > 0:
                        capitalized_parts.append(part.lower())
                    else:
                        capitalized_parts.append(part.capitalize())
                elif part.lower() not in lowercase_words:
                    # Non-lowercase words: always capitalize
                    capitalized_parts.append(part.capitalize())
                else:
                    # Lowercase words in non-first position: keep lowercase
                    capitalized_parts.append(part.lower())
            result.append('-'.join(capitalized_parts))
            continue

        if starts_with_quote:
            # Word starts with quote - capitalize first letter after quote
            # e.g., "it -> "It
            if len(word) > 1:
                # Get the quote character and rest of word
                quote_char = word[0]
                rest = word[1:]
                # Capitalize using the same logic as normal words
                if capitalize_next:
                    result.append(quote_char + rest.capitalize())
                else:
                    # First letter after quote should be capitalized
                    result.append(quote_char + rest[0].upper() + rest[1:].lower() if len(rest) > 1 else quote_char + rest.upper())
            else:
                result.append(word)
            capitalize_next = False
            in_quotes = True  # We're now inside quotes
        elif capitalize_next or in_quotes:
            # Capitalize this word
            result.append(word.capitalize())
            capitalize_next = False
        elif word.lower() in lowercase_words:
            # Keep as lowercase
            result.append(word.lower())
        else:
            # Default: capitalize
            result.append(word.capitalize())

        # Check if we should capitalize the NEXT word
        # This happens after colon (:) or period (.)
        if result[-1].endswith(':') or result[-1].endswith('.'):
            capitalize_next = True

    # Clean up: remove spaces before em-dashes and after em-dashes when followed by punctuation
    result_str = ' '.join(result)
    result_str = result_str.replace(' — ', '—')

    return result_str


def backfill_chapter_titles(dry_run=False):
    """
    Update all chapter titles in the database to use title case.

    Args:
        dry_run: If True, only show what would be changed without updating
    """
    # Connect to database
    db_path = Path(__file__).parent.parent.parent / 'data' / 'database.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all chapters
    cursor.execute("""
        SELECT id, book_id, chapter_number, chapter_title
        FROM chapters
        ORDER BY book_id, chapter_number
    """)

    chapters = cursor.fetchall()
    print(f"Found {len(chapters)} chapters in database\n")

    # Track statistics
    total_chapters = len(chapters)
    changed_chapters = 0
    unchanged_chapters = 0

    # Process each chapter
    for chapter_id, book_id, chapter_number, chapter_title in chapters:
        # Normalize the title
        normalized_title = normalize_chapter_title(chapter_title)

        # Check if title changed
        if normalized_title != chapter_title:
            changed_chapters += 1
            print(f"Chapter {chapter_number} (ID: {chapter_id}):")
            print(f"  OLD: {chapter_title}")
            print(f"  NEW: {normalized_title}")
            print()

            # Update in database (unless dry run)
            if not dry_run:
                cursor.execute("""
                    UPDATE chapters
                    SET chapter_title = ?
                    WHERE id = ?
                """, (normalized_title, chapter_id))
        else:
            unchanged_chapters += 1

    # Commit changes
    if not dry_run:
        conn.commit()
        print(f"\n✓ Updated {changed_chapters} chapter titles in database")
    else:
        print(f"\n[DRY RUN] Would update {changed_chapters} chapter titles")

    print(f"  {unchanged_chapters} chapters already had correct title case")
    print(f"  Total: {total_chapters} chapters")

    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Backfill chapter titles to use title case'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    args = parser.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made to database")
        print("=" * 60)
        print()

    backfill_chapter_titles(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
