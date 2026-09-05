#!/usr/bin/env python3
"""
Backfill chapter title normalization for recent books.

This script updates chapter titles in the database to apply the new title
normalization (title casing) that was recently added to generate_summaries.py.
"""

import sqlite3


from scripts.content.generate_summaries import SummaryGenerator, fix_roman_numerals_in_text

def normalize_chapter_titles_for_book(book_id: int, db_path: str = 'data/database.db'):
    """
    Update chapter titles for a specific book to apply title normalization.

    Args:
        book_id: The ID of the book to update
        db_path: Path to the database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get book info
    cursor.execute('SELECT title, gutenberg_id FROM books WHERE id = ?', (book_id,))
    book_row = cursor.fetchone()
    if not book_row:
        print(f"Book ID {book_id} not found")
        conn.close()
        return

    book_title, gutenberg_id = book_row
    print(f"\nProcessing Book {book_id}: {book_title} (pg{gutenberg_id})")

    # Get all chapters for this book
    cursor.execute('''
        SELECT id, chapter_number, chapter_title
        FROM chapters
        WHERE book_id = ?
        ORDER BY chapter_number
    ''', (book_id,))

    chapters = cursor.fetchall()
    print(f"  Found {len(chapters)} chapters")

    # Create a generator instance to use the normalize_chapter_title method
    generator = SummaryGenerator('dummy_api_key')

    updated_count = 0
    for chapter_id, chapter_num, old_title in chapters:
        # Apply normalization
        normalized_title = generator.normalize_chapter_title(old_title)
        normalized_title = fix_roman_numerals_in_text(normalized_title)

        # Only update if the title changed
        if normalized_title != old_title:
            cursor.execute('''
                UPDATE chapters
                SET chapter_title = ?
                WHERE id = ?
            ''', (normalized_title, chapter_id))
            updated_count += 1
            print(f"  Chapter {chapter_num}: '{old_title}' -> '{normalized_title}'")

    conn.commit()
    conn.close()

    print(f"  Updated {updated_count} out of {len(chapters)} chapter titles")


def main():
    """Main entry point for the script."""
    # Last 6 books based on the database query
    book_ids = [79, 80, 81, 82, 83, 84]

    print("Backfilling chapter title normalization for recent books...")
    print("=" * 70)

    for book_id in book_ids:
        normalize_chapter_titles_for_book(book_id)

    print("\n" + "=" * 70)
    print("Backfill complete!")


if __name__ == '__main__':
    main()
