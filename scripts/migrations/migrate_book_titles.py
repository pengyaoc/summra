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

import os

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')

scripts_dir = os.path.dirname(os.path.abspath(__file__))

from backend import models
import argparse


def normalize_book_title(title):
    """
    Normalize book title to follow consistent formatting rules:
    1. Title Case (capitalize first letter of each word, except articles/prepositions)
    2. Truncate at first colon (:) or semicolon (;)

    Examples:
        "jane eyre: an autobiography" -> "Jane Eyre"
        "MOBY DICK; Or, The Whale" -> "Moby Dick"
        "the great gatsby" -> "The Great Gatsby"

    Args:
        title: Raw book title string

    Returns:
        Normalized title string
    """
    if not title or not title.strip():
        return title

    # Step 1: Truncate at first colon or semicolon
    # Find first occurrence of : or ;
    colon_pos = title.find(':')
    semicolon_pos = title.find(';')

    # Determine which comes first
    if colon_pos != -1 and semicolon_pos != -1:
        truncate_pos = min(colon_pos, semicolon_pos)
    elif colon_pos != -1:
        truncate_pos = colon_pos
    elif semicolon_pos != -1:
        truncate_pos = semicolon_pos
    else:
        truncate_pos = len(title)

    # Truncate title
    title = title[:truncate_pos].strip()

    # Step 2: Apply Title Case
    # Words that should remain lowercase (unless first word)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    words = title.split()
    result = []

    for i, word in enumerate(words):
        # Handle hyphenated words - capitalize each part
        if '-' in word:
            parts = word.split('-')
            capitalized_parts = []
            for j, part in enumerate(parts):
                # First part or parts that aren't lowercase words
                if j == 0 or part.lower() not in lowercase_words:
                    capitalized_parts.append(part.capitalize())
                else:
                    capitalized_parts.append(part.lower())
            result.append('-'.join(capitalized_parts))
        # Always capitalize first word
        elif i == 0:
            result.append(word.capitalize())
        # Keep lowercase words as lowercase (unless after colon/period)
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # Otherwise capitalize
        else:
            result.append(word.capitalize())

    return ' '.join(result)


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
