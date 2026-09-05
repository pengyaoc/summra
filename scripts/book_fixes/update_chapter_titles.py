#!/usr/bin/env python3
"""
Update chapter titles in database without regenerating summaries.

This script re-parses chapter titles using the latest parsing logic
and updates the chapter_title field in the database for existing chapters.
"""

import os
import sys
from pathlib import Path

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')

from scripts.content.generate_summaries import SummaryGenerator
from backend import models

def update_chapter_titles(book_id: int, book_file: Path):
    """
    Update chapter titles for a book without regenerating summaries.

    Args:
        book_id: Database ID of the book
        book_file: Path to the book text file
    """
    # Initialize generator (dummy API key since we won't call LLM)
    generator = SummaryGenerator('dummy_key')
    db = models.Database()

    # Read and parse the book
    print(f"Reading book from: {book_file}")
    text = generator.read_book(book_file)

    # Extract Gutenberg content
    text = generator.extract_gutenberg_content(text)

    # Detect chapters with corrected parsing
    print("Detecting chapters with corrected parsing logic...")
    chapters = generator.detect_chapters(text)

    print(f"Found {len(chapters)} chapters")

    # Get existing chapters from database
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT chapter_number, chapter_title
        FROM chapters
        WHERE book_id = ?
        ORDER BY chapter_number
    """, (book_id,))

    existing_chapters = cursor.fetchall()
    print(f"Found {len(existing_chapters)} existing chapters in database")

    # Create mapping of chapter numbers to new titles
    new_titles = {ch_num: ch_title for ch_num, ch_title, _ in chapters}

    # Update each chapter title
    updates = 0
    for db_chapter_num, old_title in existing_chapters:
        if db_chapter_num in new_titles:
            new_title = new_titles[db_chapter_num]
            if old_title != new_title:
                print(f"\nChapter {db_chapter_num}:")
                print(f"  Old: {old_title}")
                print(f"  New: {new_title}")

                cursor.execute("""
                    UPDATE chapters
                    SET chapter_title = ?
                    WHERE book_id = ? AND chapter_number = ?
                """, (new_title, book_id, db_chapter_num))
                updates += 1
            else:
                print(f"Chapter {db_chapter_num}: No change needed")
        else:
            print(f"WARNING: Chapter {db_chapter_num} not found in parsed chapters")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Updated {updates} chapter titles")
    print(f"{'='*60}")

if __name__ == '__main__':
    # Database and file paths
    db = models.Database()

    # Get book ID for Winnie-the-Pooh
    book = db.get_book_by_filename("pg67098.txt")

    if not book:
        print("ERROR: Book not found in database")
        print("Looking for: pg67098.txt")
        sys.exit(1)

    book_id = book['id']
    book_title = book['title']

    print(f"Found book: {book_title} (ID: {book_id})")

    # Path to book file
    book_file = Path("data/books/pg67098.txt")

    if not book_file.exists():
        print(f"ERROR: Book file not found: {book_file}")
        sys.exit(1)

    # Update chapter titles
    update_chapter_titles(book_id, book_file)
