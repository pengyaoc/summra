#!/usr/bin/env python3
"""
Bulk backfill script to categorize all existing books.

Uses the shared categorization module to assign categories to books
that don't have any categories yet. Processes books in batches to
optimize API usage.

Usage:
    # Categorize all books without categories
    python categorize_books_bulk_backfill.py

    # Categorize a specific book
    python categorize_books_bulk_backfill.py --book-id 5

    # Use smaller batch size for more careful processing
    python categorize_books_bulk_backfill.py --batch-size 5
"""

import os
import sys
import argparse
from pathlib import Path

# Add backend and scripts directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

from google import genai
from dotenv import load_dotenv
import config
import models
import categorization


def main():
    parser = argparse.ArgumentParser(description='Bulk backfill categories for existing books')
    parser.add_argument('--book-id', type=int, help='Categorize a specific book by ID')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of books per API call (default: 10)')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        sys.exit(1)

    # Initialize client and database
    client = genai.Client(api_key=api_key)
    db = models.Database()

    # Get all categories from database
    categories = db.get_all_categories()
    if not categories:
        print("Error: No categories found in database")
        print("Please run generate_master_categories.py first")
        sys.exit(1)

    print(f"Found {len(categories)} categories in database")

    # Get books to categorize
    if args.book_id:
        # Single book mode
        book = db.get_book(args.book_id)
        if not book:
            print(f"Error: Book {args.book_id} not found")
            sys.exit(1)

        # Check if book already has categories
        existing_categories = db.get_book_categories(args.book_id)
        if existing_categories:
            print(f"\nBook {args.book_id} ({book['title']}) already has {len(existing_categories)} categories:")
            for cat in existing_categories:
                print(f"  - {cat['name']}")
            print("\nClearing existing categories and re-categorizing...")

        books = [book]
        print(f"\nCategorizing single book: {book['title']} by {book['author']}")

    else:
        # Bulk mode: get all books without categories
        all_books = db.get_all_books()

        # Filter to books that don't have categories AND have a medium summary
        books_to_categorize = []
        for book in all_books:
            existing_categories = db.get_book_categories(book['id'])
            medium_summary = db.get_summary(book['id'], 'medium')

            if not existing_categories and medium_summary:
                books_to_categorize.append(book)

        if not books_to_categorize:
            print("\nNo books found that need categorization")
            print("(All books either have categories or don't have medium summaries)")
            sys.exit(0)

        books = books_to_categorize
        print(f"\nFound {len(books)} books to categorize (have medium summaries, no categories)")

    # Categorize books using bulk processing
    print(f"\nStarting bulk categorization (batch size: {args.batch_size})...")
    print(f"This will make approximately {(len(books) + args.batch_size - 1) // args.batch_size} API calls\n")

    results = categorization.categorize_books_bulk(
        client,
        db,
        books,
        categories,
        batch_size=args.batch_size
    )

    # Save results to database
    print("\n\nSaving results to database...")
    success_count = 0
    failed_count = 0

    for book_id, category_names in results.items():
        if category_names:
            categorization.save_book_categories(db, book_id, category_names)
            book = next(b for b in books if b['id'] == book_id)
            print(f"  ✓ Book {book_id} ({book['title']}): {len(category_names)} categories")
            for cat_name in category_names:
                print(f"      - {cat_name}")
            success_count += 1
        else:
            book = next(b for b in books if b['id'] == book_id)
            print(f"  ❌ Book {book_id} ({book['title']}): Failed to categorize")
            failed_count += 1

    print(f"\n{'='*60}")
    print(f"Categorization Complete!")
    print(f"{'='*60}")
    print(f"Successfully categorized: {success_count} books")
    print(f"Failed: {failed_count} books")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
