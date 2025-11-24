#!/usr/bin/env python3
"""List all books in the database"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import models

def main():
    db = models.Database()
    books = db.get_all_books()

    print(f"\nTotal books in database: {len(books)}\n")
    print("=" * 80)

    for book in books:
        print(f"ID: {book['id']} - {book['title']} by {book['author']}")
        print(f"  Filename: {book['filename']}")
        print()

if __name__ == '__main__':
    main()
