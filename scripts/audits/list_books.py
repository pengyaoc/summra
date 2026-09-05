#!/usr/bin/env python3
"""List all books in the database"""


from backend import models

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
