#!/usr/bin/env python3
"""
Generic script to update book cover images in the database

Usage:
    python scripts/images/update_book_cover.py --book-id 38 --source /path/to/cover.png
    python scripts/images/update_book_cover.py --title "A Christmas Carol" --source /path/to/cover.png
    python scripts/images/update_book_cover.py --list  # List all books
"""

import sys
import shutil
import argparse
from pathlib import Path


from backend import models

def list_books(db):
    """List all books in the database"""
    books = db.get_all_books()

    if not books:
        print("No books found in database.")
        return

    print(f"\n{'ID':<5} {'Title':<50} {'Author':<30} {'Cover':<30}")
    print("-" * 120)

    for book in books:
        book_id = book.get('id', 'N/A')
        title = book.get('title', 'N/A')[:48]
        author = book.get('author', 'N/A')[:28]
        cover = book.get('cover_image_url', 'None')[:28]
        print(f"{book_id:<5} {title:<50} {author:<30} {cover:<30}")

    print(f"\nTotal books: {len(books)}\n")

def find_book(db, book_id=None, title=None):
    """Find a book by ID or title"""
    if book_id:
        return db.get_book(book_id)

    if title:
        books = db.get_all_books()
        # Case-insensitive search
        title_lower = title.lower()
        for book in books:
            if title_lower in book['title'].lower():
                return book

    return None

def sanitize_filename(title):
    """Convert book title to a safe filename"""
    # Remove special characters and replace spaces with underscores
    safe_name = "".join(c if c.isalnum() or c in (' ', '-') else '' for c in title)
    safe_name = safe_name.replace(' ', '_').lower()
    return safe_name

def update_cover(db, book_id, source_path, output_filename=None):
    """Update book cover image"""

    # Verify source file exists
    source_path = Path(source_path)
    if not source_path.exists():
        print(f"Error: Source image file not found: {source_path}")
        return False

    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"Error: Book with ID {book_id} not found")
        return False

    # Generate output filename if not provided
    if not output_filename:
        safe_title = sanitize_filename(book['title'])
        ext = source_path.suffix
        output_filename = f"{safe_title}_custom{ext}"

    # Define target path
    script_dir = Path(__file__).parent.parent.parent
    covers_dir = script_dir / 'frontend' / 'static' / 'covers'
    target_path = covers_dir / output_filename

    # Create covers directory if it doesn't exist
    covers_dir.mkdir(parents=True, exist_ok=True)

    # Copy the image file
    try:
        shutil.copy2(source_path, target_path)
        print(f"✓ Copied cover image to: {target_path}")
    except Exception as e:
        print(f"Error copying file: {e}")
        return False

    # Update database
    relative_cover_path = f"covers/{output_filename}"

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE books SET cover_image_url = ? WHERE id = ?",
            (relative_cover_path, book_id)
        )
        conn.commit()

        print(f"✓ Updated database with cover path: {relative_cover_path}")

        # Verify the update
        cursor.execute("SELECT title, author, cover_image_url FROM books WHERE id = ?", (book_id,))
        result = cursor.fetchone()
        if result:
            print(f"\nBook Details:")
            print(f"  ID: {book_id}")
            print(f"  Title: {result[0]}")
            print(f"  Author: {result[1]}")
            print(f"  Cover: {result[2]}")

        return True

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Update book cover images in the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all books
  python scripts/images/update_book_cover.py --list

  # Update cover by book ID
  python scripts/images/update_book_cover.py --book-id 38 --source /path/to/cover.png

  # Update cover by book title
  python scripts/images/update_book_cover.py --title "A Christmas Carol" --source /path/to/cover.png

  # Update cover with custom filename
  python scripts/images/update_book_cover.py --book-id 38 --source /path/to/cover.png --output custom_cover.png
        """
    )

    parser.add_argument('--list', action='store_true', help='List all books in the database')
    parser.add_argument('--book-id', type=int, help='Book ID to update')
    parser.add_argument('--title', type=str, help='Book title to search for')
    parser.add_argument('--source', type=str, help='Path to source cover image file')
    parser.add_argument('--output', type=str, help='Output filename (optional, auto-generated if not provided)')

    args = parser.parse_args()

    # Initialize database
    db = models.Database()

    # Handle list command
    if args.list:
        list_books(db)
        return

    # Validate arguments for update
    if not args.source:
        print("Error: --source is required (unless using --list)")
        parser.print_help()
        sys.exit(1)

    if not args.book_id and not args.title:
        print("Error: Either --book-id or --title is required")
        parser.print_help()
        sys.exit(1)

    # Find the book
    book = find_book(db, book_id=args.book_id, title=args.title)

    if not book:
        if args.book_id:
            print(f"Error: No book found with ID {args.book_id}")
        else:
            print(f"Error: No book found matching title '{args.title}'")
        print("\nUse --list to see all available books")
        sys.exit(1)

    book_id = book['id']

    # If searching by title, confirm the book
    if args.title and not args.book_id:
        print(f"\nFound book:")
        print(f"  ID: {book_id}")
        print(f"  Title: {book['title']}")
        print(f"  Author: {book['author']}")
        print(f"  Current cover: {book.get('cover_image_url', 'None')}")
        print()

    # Update the cover
    success = update_cover(db, book_id, args.source, args.output)

    if success:
        print("\n✓ Cover update completed successfully!")
    else:
        print("\n✗ Cover update failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
