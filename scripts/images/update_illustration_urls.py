#!/usr/bin/env python3
"""
Quick script to populate illustration_url in database for existing illustration files.
"""

import sys
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

from backend.models import Database
import backend.config as config


def update_illustration_urls(book_id=None):
    """Update illustration_url in database for existing files"""
    db = Database()
    illustrations_dir = config.ILLUSTRATIONS_DIR

    # Get all books or specific book
    if book_id:
        books = [db.get_book(book_id)]
        if not books[0]:
            print(f"Book {book_id} not found")
            return
    else:
        books = db.get_all_books()

    total_updated = 0

    for book in books:
        book_id = book['id']
        book_illustrations_dir = illustrations_dir / str(book_id)

        if not book_illustrations_dir.exists():
            continue

        print(f"\nProcessing book {book_id}: {book['title']}")

        # Get all chapters for this book
        chapters = db.get_chapters(book_id)
        chapter_map = {ch['chapter_number']: ch for ch in chapters}

        updated_count = 0

        # Build a map of chapter numbers to their best illustration file
        # Priority: .png > .jpg > .webp
        chapter_illustrations = {}
        for img_file in book_illustrations_dir.glob("*"):
            if img_file.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                continue

            # Extract chapter number from filename
            try:
                chapter_num = int(img_file.stem)
            except ValueError:
                continue

            if chapter_num not in chapter_map:
                continue

            # Determine priority (lower is better)
            priority = {'.png': 0, '.jpg': 1, '.jpeg': 1, '.webp': 2}
            ext_priority = priority.get(img_file.suffix.lower(), 999)

            # Keep this file if it's the first or has better priority
            if chapter_num not in chapter_illustrations or ext_priority < chapter_illustrations[chapter_num][1]:
                chapter_illustrations[chapter_num] = (img_file, ext_priority)

        # Now update database with the best illustration for each chapter
        for chapter_num, (img_file, _) in chapter_illustrations.items():
            chapter = chapter_map[chapter_num]
            illustration_url = f"illustrations/{book_id}/{img_file.name}"

            # Only update if URL is different
            if chapter.get('illustration_url') != illustration_url:
                print(f"  Updating chapter {chapter_num}: {illustration_url}")
                db.add_chapter(
                    book_id=book_id,
                    chapter_number=chapter_num,
                    chapter_title=chapter['chapter_title'],
                    summary=chapter['summary'],
                    chapter_text=chapter.get('chapter_text'),
                    section_id=chapter.get('section_id'),
                    illustration_url=illustration_url
                )
                updated_count += 1

        if updated_count > 0:
            print(f"  Updated {updated_count} chapters")
            total_updated += updated_count

    print(f"\nTotal chapters updated: {total_updated}")


if __name__ == "__main__":
    book_id = None
    if len(sys.argv) > 1:
        try:
            book_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid book ID: {sys.argv[1]}")
            sys.exit(1)

    update_illustration_urls(book_id)
