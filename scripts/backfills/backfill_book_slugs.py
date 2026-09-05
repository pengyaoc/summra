#!/usr/bin/env python3
"""
Backfill missing slugs for all books in the database.

This script generates URL-friendly slugs for all books that don't have one yet.
"""

import sys


from backend.models import Database, slugify


def backfill_slugs(dry_run=True):
    """Backfill missing slugs for all books.

    Args:
        dry_run: If True, only print what would be updated without making changes
    """
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get all books without slugs or with empty slugs
    cursor.execute("""
        SELECT id, title
        FROM books
        WHERE slug IS NULL OR slug = ''
        ORDER BY id
    """)

    books_to_update = cursor.fetchall()

    if not books_to_update:
        print("All books already have slugs!")
        conn.close()
        return

    print(f"Found {len(books_to_update)} books without slugs\n")

    for book in books_to_update:
        book_id = book['id']
        title = book['title']
        new_slug = slugify(title)

        if dry_run:
            print(f"[DRY RUN] Book {book_id}: '{title}' -> slug: '{new_slug}'")
        else:
            cursor.execute("UPDATE books SET slug = ? WHERE id = ?", (new_slug, book_id))
            print(f"Updated book {book_id}: '{title}' -> slug: '{new_slug}'")

    if not dry_run:
        conn.commit()
        print(f"\nSuccessfully updated {len(books_to_update)} book slugs!")
    else:
        print(f"\n[DRY RUN] Would update {len(books_to_update)} book slugs. Run with --commit to apply changes.")

    conn.close()


if __name__ == '__main__':
    # Check for --commit flag
    dry_run = '--commit' not in sys.argv

    if dry_run:
        print("Running in DRY RUN mode. Use --commit to actually update the database.\n")
    else:
        print("Running in COMMIT mode. Changes will be saved to the database.\n")

    backfill_slugs(dry_run=dry_run)
