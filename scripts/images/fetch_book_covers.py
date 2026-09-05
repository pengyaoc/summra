#!/usr/bin/env python3
"""
Script to fetch book cover images from Project Gutenberg
and update the database for existing books.

This script searches Project Gutenberg by title and retrieves cover images.
"""

import os
import requests
from urllib.parse import quote
import time

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')

from backend import models


# Known Gutenberg IDs for common books (to speed up lookups)
KNOWN_GUTENBERG_IDS = {
    "Alice's Adventures in Wonderland": 11,
    "Through the Looking-Glass": 12,
    "The Origin of Species": 1228,
    "Pride and Prejudice": 1342,
    "Frankenstein": 84,
    "Dracula": 345,
    "A Tale of Two Cities": 98,
    "Great Expectations": 1400,
    "Jane Eyre": 1260,
    "Wuthering Heights": 768,
    "The Adventures of Sherlock Holmes": 1661,
    "Moby Dick": 2701,
    "War and Peace": 2600,
    "Crime and Punishment": 2554,
    "The Picture of Dorian Gray": 174,
    "The Odyssey": 1727,
    "The Iliad": 6130,
}


def search_gutenberg_book(title: str, author: str = None) -> int:
    """
    Search Project Gutenberg for a book and return its ID

    Args:
        title: Book title
        author: Book author (optional)

    Returns:
        Gutenberg book ID or None if not found
    """
    # Check known IDs first
    if title in KNOWN_GUTENBERG_IDS:
        print(f"  Using known Gutenberg ID: {KNOWN_GUTENBERG_IDS[title]}")
        return KNOWN_GUTENBERG_IDS[title]

    # Try to search using the Gutenberg search API
    # Format: https://www.gutenberg.org/ebooks/search/?query=title
    search_url = f"https://www.gutenberg.org/ebooks/search/?query={quote(title)}&submit_search=Go"

    try:
        response = requests.get(search_url, timeout=10)
        if response.status_code == 200:
            # Parse the HTML to find the first result
            # Look for patterns like /ebooks/11 in the response
            import re
            pattern = r'/ebooks/(\d+)'
            matches = re.findall(pattern, response.text)

            if matches:
                gutenberg_id = int(matches[0])
                print(f"  Found Gutenberg ID: {gutenberg_id}")
                return gutenberg_id
    except Exception as e:
        print(f"  Error searching Gutenberg: {e}")

    return None


def get_gutenberg_cover_url(gutenberg_id: int) -> str:
    """
    Get the cover image URL for a Project Gutenberg book

    Project Gutenberg cover images follow this pattern:
    https://www.gutenberg.org/cache/epub/{id}/pg{id}.cover.medium.jpg

    Args:
        gutenberg_id: Project Gutenberg book ID

    Returns:
        Cover image URL
    """
    # Try multiple cover image formats
    formats = [
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.medium.jpg",
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.small.jpg",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/images/cover.jpg",
    ]

    for url in formats:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                print(f"  Found cover image: {url}")
                return url
        except Exception as e:
            continue

    # Return a default placeholder or None
    print(f"  No cover image found for Gutenberg ID {gutenberg_id}")
    return None


def fetch_book_covers():
    """Fetch and update cover images for all books in the database"""
    db = models.Database()
    books = db.get_all_books()

    print(f"Found {len(books)} books in database")
    print("=" * 60)

    updated_count = 0
    failed_count = 0

    for book in books:
        print(f"\nProcessing: {book['title']}")

        # Skip if already has cover image
        if book.get('cover_image_url'):
            print(f"  ✓ Already has cover image: {book['cover_image_url']}")
            continue

        # Search for Gutenberg ID
        gutenberg_id = book.get('gutenberg_id')
        if not gutenberg_id:
            gutenberg_id = search_gutenberg_book(book['title'], book.get('author'))
            if not gutenberg_id:
                print(f"  ✗ Could not find Gutenberg ID")
                failed_count += 1
                continue

        # Get cover image URL
        cover_url = get_gutenberg_cover_url(gutenberg_id)
        if cover_url:
            # Update database
            db.update_book_cover(book['id'], gutenberg_id, cover_url)
            print(f"  ✓ Updated cover image")
            updated_count += 1
        else:
            print(f"  ✗ No cover image available")
            failed_count += 1

        # Be nice to Gutenberg servers
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"✓ Updated {updated_count} books")
    print(f"✗ Failed {failed_count} books")
    print("=" * 60)


if __name__ == '__main__':
    fetch_book_covers()
