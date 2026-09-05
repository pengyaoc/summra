#!/usr/bin/env python3
"""Check summaries for a specific book"""
import sys


from backend import models

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_book_summaries.py <book_id>")
        sys.exit(1)

    book_id = int(sys.argv[1])
    db = models.Database()

    book = db.get_book(book_id)
    if not book:
        print(f"Book ID {book_id} not found!")
        sys.exit(1)

    print(f"\nBook: {book['title']} by {book['author']}")
    print(f"Filename: {book['filename']}")
    print(f"Word count: {book.get('word_count', 'N/A')}")
    print("=" * 80)

    # Check summaries
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT summary_type, word_count FROM summaries WHERE book_id = ?', (book_id,))
    summaries = cursor.fetchall()

    cursor.execute('SELECT COUNT(*) FROM chapters WHERE book_id = ?', (book_id,))
    chapter_count = cursor.fetchone()[0]

    conn.close()

    print("\nSummaries:")
    if summaries:
        for summary in summaries:
            print(f"  ✓ {summary[0]}: {summary[1]} words")
    else:
        print("  ✗ No summaries found")

    print(f"\nChapters: {chapter_count}")

    if not summaries:
        print("\n⚠️  This book needs summaries to be generated!")
        print(f"Run: python scripts/content/generate_summaries.py data/books/{book['filename']}")
    else:
        print("\n✓ This book has summaries!")

if __name__ == '__main__':
    main()
