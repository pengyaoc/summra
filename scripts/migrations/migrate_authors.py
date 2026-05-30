#!/usr/bin/env python3
"""
Migration script to populate the authors table from existing book.author strings
and link books to their authors via author_id foreign key.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / 'backend'))

from backend.models import Database


def migrate_authors():
    """Extract unique authors from books and populate authors table"""
    db = Database()

    print("Starting author migration...")

    # Get all books
    books = db.get_all_books()
    print(f"Found {len(books)} books")

    # Track statistics
    authors_created = 0
    books_updated = 0

    for book in books:
        author_name = book.get('author')
        if not author_name:
            print(f"Warning: Book '{book['title']}' has no author")
            continue

        # Add or get author
        author_id = db.add_author(author_name)

        # Check if this was a new author
        if author_id:
            author = db.get_author(author_id)
            if author:
                # Check if this is the first book for this author
                existing_books = db.get_books_by_author_id(author_id)
                if len(existing_books) == 0:
                    authors_created += 1
                    print(f"Created author: {author_name}")

        # Update book's author_id
        if author_id:
            db.update_book_author_id(book['id'], author_id)
            books_updated += 1
            print(f"  Linked '{book['title']}' to author ID {author_id}")

    print("\nMigration complete!")
    print(f"Authors created: {authors_created}")
    print(f"Books updated: {books_updated}")

    # Display summary
    print("\nAuthor summary:")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, a.name, COUNT(b.id) as book_count
        FROM authors a
        LEFT JOIN books b ON a.id = b.author_id
        GROUP BY a.id
        ORDER BY book_count DESC, a.name
    ''')

    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row['name']}: {row['book_count']} book(s)")

    conn.close()


if __name__ == '__main__':
    migrate_authors()
