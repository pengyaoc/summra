#!/usr/bin/env python3
"""
Fetch missing Gutenberg books from Project Gutenberg using their IDs.
Downloads books that are missing from the local data/books/ directory.
"""

import sys
import os
import time
import urllib.request
import urllib.error
from pathlib import Path


from backend import models
from backend import config


class GutenbergFetcher:
    """Fetches missing books from Project Gutenberg"""

    def __init__(self):
        self.db = models.Database()
        self.books_dir = Path(config.BOOKS_DIR)
        self.gutenberg_base_url = "https://www.gutenberg.org/cache/epub"

    def get_missing_books(self):
        """
        Get list of books that have Gutenberg IDs but missing source files.

        Returns:
            List of (book_id, title, gutenberg_id, expected_filename) tuples
        """
        books = self.db.get_all_books()
        missing = []

        for book in books:
            gutenberg_id = book.get('gutenberg_id')
            if not gutenberg_id:
                continue

            # Check if source file exists
            filename = book.get('filename', f'pg{gutenberg_id}.txt')
            file_path = self.books_dir / filename

            # Also check for pg{ID}.txt format
            alt_path = self.books_dir / f'pg{gutenberg_id}.txt'

            if not file_path.exists() and not alt_path.exists():
                missing.append({
                    'book_id': book['id'],
                    'title': book['title'],
                    'author': book.get('author', 'Unknown'),
                    'gutenberg_id': gutenberg_id,
                    'filename': f'pg{gutenberg_id}.txt'
                })

        return missing

    def download_book(self, gutenberg_id, filename):
        """
        Download a book from Project Gutenberg.

        Args:
            gutenberg_id: Project Gutenberg book ID
            filename: Filename to save as (e.g., 'pg46.txt')

        Returns:
            True if successful, False otherwise
        """
        # Try UTF-8 text version first
        url = f"{self.gutenberg_base_url}/{gutenberg_id}/pg{gutenberg_id}.txt"
        output_path = self.books_dir / filename

        print(f"  Downloading from: {url}")

        try:
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            request = urllib.request.Request(url, headers=headers)

            # Download with timeout
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()

                # Save to file
                with open(output_path, 'wb') as f:
                    f.write(content)

                file_size = len(content)
                print(f"  ✓ Downloaded: {file_size:,} bytes")
                return True

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  ✗ Not found (404) - trying alternative URL")
                # Try alternative URL format (some books use different paths)
                return self._try_alternative_download(gutenberg_id, filename)
            else:
                print(f"  ✗ HTTP Error {e.code}: {e.reason}")
                return False

        except urllib.error.URLError as e:
            print(f"  ✗ URL Error: {e.reason}")
            return False

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            return False

    def _try_alternative_download(self, gutenberg_id, filename):
        """
        Try alternative download URLs for books not found at standard location.
        Some books use different directory structures.
        """
        # Try without /cache/epub/ path
        alt_url = f"https://www.gutenberg.org/files/{gutenberg_id}/pg{gutenberg_id}.txt"
        output_path = self.books_dir / filename

        print(f"  Trying alternative: {alt_url}")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            request = urllib.request.Request(alt_url, headers=headers)

            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()

                with open(output_path, 'wb') as f:
                    f.write(content)

                file_size = len(content)
                print(f"  ✓ Downloaded: {file_size:,} bytes")
                return True

        except Exception as e:
            print(f"  ✗ Alternative failed: {str(e)}")
            return False

    def fetch_all_missing(self, delay=2):
        """
        Fetch all missing books with Gutenberg IDs.

        Args:
            delay: Delay in seconds between downloads (to be respectful to servers)
        """
        missing = self.get_missing_books()

        if not missing:
            print("No missing books found! All books with Gutenberg IDs have source files.")
            return

        print(f"Found {len(missing)} missing books with Gutenberg IDs")
        print()

        successful = []
        failed = []

        for i, book in enumerate(missing, 1):
            print(f"[{i}/{len(missing)}] {book['title']} (ID: {book['gutenberg_id']})")
            print(f"  Author: {book['author']}")

            success = self.download_book(book['gutenberg_id'], book['filename'])

            if success:
                successful.append(book)
            else:
                failed.append(book)

            print()

            # Be respectful - wait between downloads
            if i < len(missing):
                time.sleep(delay)

        # Print summary
        print("=" * 80)
        print("DOWNLOAD SUMMARY")
        print("=" * 80)
        print(f"Total missing: {len(missing)}")
        print(f"Successfully downloaded: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print()

        if failed:
            print("Failed downloads:")
            for book in failed:
                print(f"  - {book['title']} (Gutenberg ID: {book['gutenberg_id']})")
            print()

        if successful:
            print("Successfully downloaded:")
            for book in successful:
                print(f"  ✓ {book['title']} → {book['filename']}")
            print()
            print(f"You can now re-run the audit script to verify these books:")
            print(f"  python scripts/audits/audit_chapter_text.py")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch missing books from Project Gutenberg'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=2,
        help='Delay in seconds between downloads (default: 2)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='List missing books without downloading'
    )

    args = parser.parse_args()

    fetcher = GutenbergFetcher()

    if args.dry_run:
        # Just list missing books
        missing = fetcher.get_missing_books()
        if not missing:
            print("No missing books found!")
        else:
            print(f"Found {len(missing)} missing books:")
            print()
            for book in missing:
                print(f"Book ID {book['book_id']}: {book['title']}")
                print(f"  Author: {book['author']}")
                print(f"  Gutenberg ID: {book['gutenberg_id']}")
                print(f"  Will download as: {book['filename']}")
                print()
    else:
        # Download missing books
        fetcher.fetch_all_missing(delay=args.delay)


if __name__ == '__main__':
    main()
