#!/usr/bin/env python3
"""Check for test books in the database"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import models

def main():
    db = models.Database()

    # Get all books
    all_books = db.get_all_books()

    print(f"\nTotal books in database: {len(all_books)}")
    print("=" * 80)

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

    print(f"\n⚠️  Found {len(test_books)} test books:\n")

    for book in test_books:
        print(f"ID: {book['id']}")
        print(f"  Title: {book['title']}")
        print(f"  Author: {book['author']}")
        print(f"  Filename: {book['filename']}")
        print(f"  Word Count: {book.get('word_count', 'N/A')}")
        print(f"  Created: {book.get('created_at', 'N/A')}")

        # Check for related data
        conn = db.get_connection()
        cursor = conn.cursor()

        # Count summaries
        cursor.execute('SELECT COUNT(*) FROM summaries WHERE book_id = ?', (book['id'],))
        summary_count = cursor.fetchone()[0]

        # Count chapters
        cursor.execute('SELECT COUNT(*) FROM chapters WHERE book_id = ?', (book['id'],))
        chapter_count = cursor.fetchone()[0]

        conn.close()

        print(f"  Summaries: {summary_count}")
        print(f"  Chapters: {chapter_count}")
        print()

    print("=" * 80)
    print(f"\nThese {len(test_books)} books will be deleted (along with their summaries and chapters)")
    print("when you run the delete script.\n")

if __name__ == '__main__':
    main()
