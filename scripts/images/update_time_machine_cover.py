#!/usr/bin/env python3
"""Update The Time Machine cover image"""

import sys
import shutil
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database

def main():
    # Paths
    source_image = Path("/Users/pengyao/Downloads/9EDF63EA-B2FB-4B48-91AC-E55312121C63.png")
    covers_dir = Path(__file__).parent.parent.parent / "frontend" / "static" / "covers"
    dest_image = covers_dir / "time_machine_custom.png"

    # Copy the new cover image
    print(f"Copying {source_image} to {dest_image}...")
    shutil.copy2(source_image, dest_image)
    print(f"✓ Cover image copied successfully")

    # Update database
    db = Database()

    # Find The Time Machine book
    books = db.get_all_books()
    time_machine_book = None

    for book in books:
        if "Time Machine" in book['title']:
            time_machine_book = book
            break

    if not time_machine_book:
        print("ERROR: Could not find The Time Machine in database")
        return 1

    print(f"\nFound book: {time_machine_book['title']} by {time_machine_book['author']}")
    print(f"Current cover: {time_machine_book.get('cover_image_url', 'None')}")

    # Update the cover image URL (without /static/ prefix, just relative to static dir)
    new_cover_url = "covers/time_machine_custom.png"
    db.update_book_cover(
        book_id=time_machine_book['id'],
        gutenberg_id=time_machine_book.get('gutenberg_id', 35),
        cover_image_url=new_cover_url
    )

    print(f"✓ Database updated with new cover: {new_cover_url}")
    print("\nDone!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
