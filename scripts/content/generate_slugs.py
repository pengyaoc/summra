#!/usr/bin/env python3
"""
Generate and backfill SEO-friendly slugs for all books.

Usage:
    python scripts/content/generate_slugs.py
"""

import sys
import os
import re

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import models


def slugify(text):
    """
    Convert text to SEO-friendly slug.

    Examples:
        "Alice's Adventures in Wonderland" -> "alices-adventures-in-wonderland"
        "Pride and Prejudice" -> "pride-and-prejudice"
        "The Great Gatsby" -> "the-great-gatsby"
    """
    # Convert to lowercase
    text = text.lower()

    # Remove apostrophes and quotes
    text = text.replace("'", "").replace('"', '')

    # Replace any non-alphanumeric character (except hyphens) with hyphens
    text = re.sub(r'[^a-z0-9-]+', '-', text)

    # Remove leading/trailing hyphens and collapse multiple hyphens
    text = re.sub(r'-+', '-', text).strip('-')

    return text


def generate_slugs():
    """Generate and update slugs for all books in the database"""
    db = models.Database()

    books = db.get_all_books()

    print(f"Found {len(books)} books in the database")
    print("Generating slugs...\n")

    updated_count = 0
    skipped_count = 0

    for book in books:
        book_id = book['id']
        title = book['title']
        existing_slug = book.get('slug')

        # Generate slug from title
        new_slug = slugify(title)

        # Check if slug already exists and is correct
        if existing_slug == new_slug:
            print(f"✓ Skipping '{title}' - slug already set: {existing_slug}")
            skipped_count += 1
            continue

        # Update the slug
        try:
            db.update_book_slug(book_id, new_slug)
            print(f"✓ Updated '{title}' -> {new_slug}")
            updated_count += 1
        except Exception as e:
            print(f"✗ Error updating '{title}': {e}")

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total books: {len(books)}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped (already set): {skipped_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    generate_slugs()
