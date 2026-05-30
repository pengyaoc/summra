#!/usr/bin/env python3
"""
Update The Odyssey cover image in the database
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

import models

def main():
    db = models.Database()

    # Update The Odyssey (book ID 11) with new cover image
    new_cover_path = "covers/odyssey_custom.png"

    # Update the database directly
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE books SET cover_image_url = ? WHERE id = ?",
        (new_cover_path, 11)
    )
    conn.commit()

    print(f"✓ Updated The Odyssey cover image to: {new_cover_path}")

    # Verify the update
    cursor.execute("SELECT title, author, cover_image_url FROM books WHERE id = ?", (11,))
    result = cursor.fetchone()
    if result:
        print(f"  Book: {result[0]} by {result[1]}")
        print(f"  Cover: {result[2]}")

    conn.close()

if __name__ == '__main__':
    main()
