#!/usr/bin/env python3
"""Delete test books from the database"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import models

def main():
    db = models.Database()

    # Get all books
    all_books = db.get_all_books()

    # Define test book patterns
    test_patterns = ["Book 1", "Book 2", "Book 3", "Test Book"]

    # Find test books
    test_books = []
    for book in all_books:
        if book['title'] in test_patterns:
            test_books.append(book)

    if not test_books:
        print("\n✓ No test books found in database!")
        return

    print(f"\nDeleting {len(test_books)} test books...")
    print("=" * 80)

    deleted_count = 0
    conn = db.get_connection()
    cursor = conn.cursor()

    for book in test_books:
        # Count related data before deletion
        cursor.execute('SELECT COUNT(*) FROM summaries WHERE book_id = ?', (book['id'],))
        summary_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM chapters WHERE book_id = ?', (book['id'],))
        chapter_count = cursor.fetchone()[0]

        print(f"\nDeleting ID {book['id']}: {book['title']} by {book['author']}")
        print(f"  Filename: {book['filename']}")
        print(f"  Removing {summary_count} summaries and {chapter_count} chapters...")

        # Delete the book (CASCADE will delete summaries and chapters)
        cursor.execute('DELETE FROM books WHERE id = ?', (book['id'],))
        deleted_count += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 80)
    print(f"\n✓ Successfully deleted {deleted_count} test books and their related data!")
    print("\nVerifying deletion...")

    # Verify
    remaining_books = db.get_all_books()
    remaining_test = [b for b in remaining_books if b['title'] in test_patterns]

    if remaining_test:
        print(f"⚠️  Warning: {len(remaining_test)} test books still remain!")
    else:
        print(f"✓ All test books removed. Database now has {len(remaining_books)} books.\n")

if __name__ == '__main__':
    main()
