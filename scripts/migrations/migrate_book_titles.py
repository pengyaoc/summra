#!/usr/bin/env python3
"""
Migration script to normalize existing book titles in database.

This script:
1. Reads all books from the database
2. Normalizes each title (Title Case + truncate at : or ;)
3. Updates the database with normalized titles

Usage:
    python scripts/migrations/migrate_book_titles.py [--dry-run]
"""



from backend import models
from scripts.lib.text import normalize_book_title as _normalize_book_title
import argparse


def normalize_book_title(title):
    """Normalize book title to follow consistent formatting rules.

    Delegates to scripts.lib.text — see there for the full docstring.
    """
    return _normalize_book_title(title)


def main():
    parser = argparse.ArgumentParser(description='Migrate book titles to normalized format')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without modifying database')
    args = parser.parse_args()

    # Initialize database
    db = models.Database()

    # Get all books
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM books ORDER BY id")
    books = cursor.fetchall()

    print(f"\n{'='*60}")
    print(f"Book Title Normalization Migration")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")

    print(f"Found {len(books)} book(s) in database\n")

    updated_count = 0
    unchanged_count = 0

    for book in books:
        book_id = book['id']
        old_title = book['title']
        new_title = normalize_book_title(old_title)

        if old_title != new_title:
            updated_count += 1
            print(f"Book {book_id}:")
            print(f"  Old: {old_title}")
            print(f"  New: {new_title}")

            if not args.dry_run:
                cursor.execute("UPDATE books SET title = ? WHERE id = ?", (new_title, book_id))
                print(f"  ✓ Updated")
            else:
                print(f"  [DRY RUN] Would update")
            print()
        else:
            unchanged_count += 1

    if not args.dry_run:
        conn.commit()

    print(f"{'='*60}")
    print(f"Summary:")
    print(f"  Total books: {len(books)}")
    print(f"  Updated: {updated_count}")
    print(f"  Unchanged: {unchanged_count}")
    print(f"{'='*60}\n")

    if args.dry_run and updated_count > 0:
        print("Run without --dry-run to apply these changes")

    conn.close()


if __name__ == '__main__':
    main()
