#!/usr/bin/env python3
"""
Bulk backfill script to categorize all existing books.

Uses the shared categorization module to assign categories to books
that don't have any categories yet. Processes books in batches to
optimize API usage.

Usage:
    # Categorize all books without categories
    python categorize_books_bulk_backfill.py

    # Re-categorize ALL books (even those with existing categories)
    python categorize_books_bulk_backfill.py --force

    # Categorize a specific book
    python categorize_books_bulk_backfill.py --book-id 5

    # Use smaller batch size for more careful processing
    python categorize_books_bulk_backfill.py --batch-size 5
"""

import os
import sys
import argparse

from google import genai
from dotenv import load_dotenv
from backend import config
from backend import models
from scripts.categorization import categorization


def main():
    parser = argparse.ArgumentParser(description='Bulk backfill categories for existing books')
    parser.add_argument('--book-id', type=int, help='Categorize a specific book by ID')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of books per API call (default: 10)')
    parser.add_argument('--force', action='store_true', help='Re-categorize all books, even if they already have categories')
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
        # Bulk mode: get all books
        all_books = db.get_all_books()

        # Filter based on --force flag
        books_to_categorize = []
        for book in all_books:
            medium_summary = db.get_summary(book['id'], 'medium')

            # Skip books without medium summaries
            if not medium_summary:
                continue

            if args.force:
                # Force mode: include all books with medium summaries
                books_to_categorize.append(book)
            else:
                # Normal mode: only books without categories
                existing_categories = db.get_book_categories(book['id'])
                if not existing_categories:
                    books_to_categorize.append(book)

        if not books_to_categorize:
            if args.force:
                print("\nNo books found with medium summaries to categorize")
            else:
                print("\nNo books found that need categorization")
                print("(All books either have categories or don't have medium summaries)")
                print("Use --force to re-categorize all books")
            sys.exit(0)

        books = books_to_categorize
        if args.force:
            print(f"\nFound {len(books)} books to re-categorize (force mode)")
        else:
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
