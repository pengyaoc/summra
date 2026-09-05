#!/usr/bin/env python3
"""
Update A Christmas Carol cover image in the database
"""

import os

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')

from backend import models

def main():
    db = models.Database()

    # Update A Christmas Carol (book ID 38) with new cover image
    new_cover_path = "covers/a_christmas_carol_custom.png"

    # Update the database directly
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE books SET cover_image_url = ? WHERE id = ?",
        (new_cover_path, 38)
    )
    conn.commit()

    print(f"✓ Updated A Christmas Carol cover image to: {new_cover_path}")

    # Verify the update
    cursor.execute("SELECT title, author, cover_image_url FROM books WHERE id = ?", (38,))
    result = cursor.fetchone()
    if result:
        print(f"  Book: {result[0]} by {result[1]}")
        print(f"  Cover: {result[2]}")

    conn.close()

if __name__ == '__main__':
    main()
