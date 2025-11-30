#!/usr/bin/env python3
"""
Fix chapter title capitalization for The Invisible Man (book_id 71)
"""

import sqlite3
import re

def normalize_chapter_title(title: str) -> str:
    """
    Normalize chapter title to use consistent title case.
    Converts to title case while preserving certain words in lowercase.
    Handles quoted text specially - words inside quotes are always capitalized.
    """
    if not title or not title.strip():
        return title

    # Words that should remain lowercase in titles (unless first word or in quotes)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    # Track whether we're inside quotes
    in_quotes = False
    result = []

    # Split on whitespace while preserving spaces
    words = title.split()

    for i, word in enumerate(words):
        # Check if word contains quotes
        if '"' in word or '"' in word or '"' in word:
            in_quotes = not in_quotes
            # Words with quotes should be capitalized
            result.append(word.capitalize())
        # First word always capitalized
        elif i == 0:
            result.append(word.capitalize())
        # Words inside quotes are always capitalized
        elif in_quotes:
            result.append(word.capitalize())
        # Check if word should be lowercase
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # Otherwise capitalize
        else:
            result.append(word.capitalize())

    return ' '.join(result)

def main():
    db_path = 'data/database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all chapters for book 71 (The Invisible Man)
    cursor.execute("SELECT id, chapter_number, chapter_title FROM chapters WHERE book_id = 71 ORDER BY chapter_number")
    chapters = cursor.fetchall()

    print(f"Found {len(chapters)} chapters for The Invisible Man (book_id 71)\n")
    print("=" * 80)
    print("BEFORE -> AFTER")
    print("=" * 80)

    updates = []
    for chapter_id, chapter_num, old_title in chapters:
        new_title = normalize_chapter_title(old_title)
        if old_title != new_title:
            print(f"Chapter {chapter_num}:")
            print(f"  BEFORE: {old_title}")
            print(f"  AFTER:  {new_title}")
            print()
            updates.append((new_title, chapter_id))
        else:
            print(f"Chapter {chapter_num}: {old_title} (no change)")

    print("=" * 80)
    print(f"\nTotal changes: {len(updates)} out of {len(chapters)} chapters\n")

    # Apply updates
    if updates:
        response = input("Apply these changes to the database? (yes/no): ")
        if response.lower() == 'yes':
            cursor.executemany("UPDATE chapters SET chapter_title = ? WHERE id = ?", updates)
            conn.commit()
            print(f"\n✓ Updated {len(updates)} chapter titles successfully!")
        else:
            print("\n✗ Changes not applied")
    else:
        print("No changes needed")

    conn.close()

if __name__ == '__main__':
    main()
