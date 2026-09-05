#!/usr/bin/env python3
"""
Script to populate chapter_text field in database for existing books
without calling LLM. Uses existing chapter detection logic.
"""

import sys
from pathlib import Path

from backend import config
from backend import models

# Import chapter detection from generate_summaries

from scripts.content.generate_summaries import SummaryGenerator


def populate_chapter_text_for_book(book_id: int, book_file_path: Path):
    """Populate chapter_text for a specific book"""

    db = models.Database()

    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"Error: Book with ID {book_id} not found")
        return False

    print(f"Processing: {book['title']} by {book['author']}")

    # Read book text
    try:
        with open(book_file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(book_file_path, 'r', encoding='latin-1') as f:
            text = f.read()

    print(f"Book loaded: {len(text)} characters")

    # Use SummaryGenerator to extract Gutenberg content and detect chapters
    # We don't need API key since we're not calling LLM
    generator = SummaryGenerator(api_key="dummy")

    # Extract Project Gutenberg content
    text = generator.extract_gutenberg_content(text)
    print(f"Extracted content: {len(text)} characters")

    # Detect chapters using same logic as summary generation
    chapters = generator.detect_chapters(text)
    print(f"Detected {len(chapters)} chapters")

    # Get existing chapters from database
    existing_chapters = db.get_chapters(book_id)
    print(f"Found {len(existing_chapters)} existing chapters in database")

    # Update each chapter with its text
    updated_count = 0
    for chapter_num, chapter_title, chapter_text in chapters:
        # Find matching chapter in database
        db_chapter = next(
            (ch for ch in existing_chapters if ch['chapter_number'] == chapter_num),
            None
        )

        if db_chapter:
            # Update chapter with text
            db.add_chapter(
                book_id,
                chapter_num,
                db_chapter['chapter_title'],
                db_chapter['summary'],
                chapter_text  # Add the chapter text
            )
            print(f"✓ Updated Chapter {chapter_num}: {chapter_title[:50]}... ({len(chapter_text)} chars)")
            updated_count += 1
        else:
            print(f"⚠ Chapter {chapter_num} not found in database, skipping")

    print(f"\n✓ Successfully updated {updated_count} chapters with full text")
    return True


def main():
    """Main function to populate chapter text"""

    # For The Wealth of Nations
    book_id = 3
    book_file = Path("data/books/An_Inquiry_into_the_Nature_and_Causes_of_the_Wealth_of_Nations.txt")

    if not book_file.exists():
        print(f"Error: Book file not found at {book_file}")
        print("Please provide the correct path to the book file")
        sys.exit(1)

    print("=" * 60)
    print("Populating Chapter Text in Database")
    print("=" * 60)
    print()

    success = populate_chapter_text_for_book(book_id, book_file)

    if success:
        print("\n" + "=" * 60)
        print("✓ Complete! Chapter text has been added to the database")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ Failed to populate chapter text")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
