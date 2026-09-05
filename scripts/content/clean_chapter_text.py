#!/usr/bin/env python3
"""
Clean up chapter text by removing image references and "Full Size" text.

This script removes:
1. Image filenames like "p01a.jpg (156K)"
2. "Full Size" text that appears within 2 lines of an image reference
3. Excessive blank lines

Usage:
    python scripts/content/clean_chapter_text.py --book-id 98
    python scripts/content/clean_chapter_text.py --book-id 98 --dry-run
    python scripts/content/clean_chapter_text.py --all
"""

import argparse
import re

from scripts.lib.db import get_connection


def clean_text(text: str) -> str:
    """
    Clean chapter text by removing image references and "Full Size" markers.

    Args:
        text: Raw chapter text

    Returns:
        Cleaned chapter text
    """
    if not text:
        return text

    lines = text.split('\n')
    cleaned_lines = []
    skip_next_full_size = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this line is an image reference (e.g., "p01a.jpg (156K)")
        # Pattern: filename.ext (size)
        if re.match(r'^[a-zA-Z0-9_-]+\.(jpg|jpeg|png|gif|bmp|svg|webp)\s*\(\d+[KMG]?\)$', stripped, re.IGNORECASE):
            # Skip this line and mark to skip "Full Size" in next 2 lines
            skip_next_full_size = True
            continue

        # Check if this line is just "Full Size" and we recently saw an image
        if skip_next_full_size and stripped == "Full Size":
            # Skip this line
            continue

        # Reset the skip flag after checking 2 lines
        if skip_next_full_size and i > 0:
            # Check if we're more than 2 lines away from the image reference
            # by looking back to see if we've added 2+ non-empty lines
            non_empty_count = sum(1 for l in cleaned_lines[-2:] if l.strip())
            if non_empty_count >= 2:
                skip_next_full_size = False

        # Keep this line
        cleaned_lines.append(line)

    # Join lines back together
    cleaned_text = '\n'.join(cleaned_lines)

    # Remove excessive blank lines (more than 2 consecutive)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)

    # Trim leading/trailing whitespace
    cleaned_text = cleaned_text.strip()

    return cleaned_text


def clean_chapter_in_db(cursor, book_id: int, chapter_number: int, dry_run: bool = False) -> tuple[bool, int]:
    """
    Clean a single chapter's text in the database.

    Args:
        cursor: SQLite cursor
        book_id: Book ID
        chapter_number: Chapter number
        dry_run: If True, don't actually update the database

    Returns:
        Tuple of (was_modified, chars_removed)
    """
    # Get chapter text
    cursor.execute("""
        SELECT chapter_text, modern_english_text
        FROM chapters
        WHERE book_id = ? AND chapter_number = ?
    """, (book_id, chapter_number))

    row = cursor.fetchone()
    if not row:
        return False, 0

    original_text, modern_text = row

    # Clean both texts
    cleaned_text = clean_text(original_text) if original_text else None
    cleaned_modern = clean_text(modern_text) if modern_text else None

    # Check if anything changed
    text_changed = original_text != cleaned_text
    modern_changed = modern_text != cleaned_modern

    if not text_changed and not modern_changed:
        return False, 0

    # Calculate characters removed
    original_len = len(original_text or '') + len(modern_text or '')
    cleaned_len = len(cleaned_text or '') + len(cleaned_modern or '')
    chars_removed = original_len - cleaned_len

    if not dry_run:
        # Update database
        cursor.execute("""
            UPDATE chapters
            SET chapter_text = ?, modern_english_text = ?
            WHERE book_id = ? AND chapter_number = ?
        """, (cleaned_text, cleaned_modern, book_id, chapter_number))

    return True, chars_removed


def main():
    parser = argparse.ArgumentParser(description='Clean up chapter text by removing image references')
    parser.add_argument('--book-id', type=int, help='Book ID to clean')
    parser.add_argument('--all', action='store_true', help='Clean all books')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without modifying')

    args = parser.parse_args()

    if not args.book_id and not args.all:
        parser.error('Must specify either --book-id or --all')

    # Connect to database
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get list of books to process
        if args.all:
            cursor.execute("SELECT DISTINCT book_id FROM chapters ORDER BY book_id")
            book_ids = [row[0] for row in cursor.fetchall()]
        else:
            book_ids = [args.book_id]

        print(f"{'DRY RUN: ' if args.dry_run else ''}Cleaning chapter text for {len(book_ids)} book(s)...\n")

        total_chapters_modified = 0
        total_chars_removed = 0

        for book_id in book_ids:
            # Get book title
            cursor.execute("SELECT title FROM books WHERE id = ?", (book_id,))
            book_row = cursor.fetchone()
            book_title = book_row[0] if book_row else f"Book {book_id}"

            # Get all chapters for this book
            cursor.execute("""
                SELECT chapter_number
                FROM chapters
                WHERE book_id = ?
                ORDER BY chapter_number
            """, (book_id,))

            chapter_numbers = [row[0] for row in cursor.fetchall()]

            print(f"Processing: {book_title} ({len(chapter_numbers)} chapters)")

            book_chapters_modified = 0
            book_chars_removed = 0

            for chapter_num in chapter_numbers:
                was_modified, chars_removed = clean_chapter_in_db(
                    cursor, book_id, chapter_num, args.dry_run
                )

                if was_modified:
                    book_chapters_modified += 1
                    book_chars_removed += chars_removed
                    print(f"  ✓ Chapter {chapter_num}: removed {chars_removed} characters")

            if book_chapters_modified > 0:
                print(f"  Modified {book_chapters_modified} chapters, removed {book_chars_removed} total characters\n")
            else:
                print(f"  No changes needed\n")

            total_chapters_modified += book_chapters_modified
            total_chars_removed += book_chars_removed

        # Commit changes if not dry run
        if not args.dry_run:
            conn.commit()
            print(f"✓ Committed changes to database")
        else:
            print(f"✓ Dry run complete (no changes made)")

        print(f"\nSummary:")
        print(f"  Books processed: {len(book_ids)}")
        print(f"  Chapters modified: {total_chapters_modified}")
        print(f"  Characters removed: {total_chars_removed}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
