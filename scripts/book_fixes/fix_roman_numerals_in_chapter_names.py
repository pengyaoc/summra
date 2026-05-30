#!/usr/bin/env python3
"""
Script to fix Roman numerals in chapter names from title case to all caps.

This script detects chapter names like "Book Ii" and converts them to "Book II".
"""

import re
import sys
from pathlib import Path

# Add parent directory to path to import config and models
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'backend'))

import config
from models import Database


def contains_title_case_roman_numeral(text):
    """
    Check if text contains a title-cased Roman numeral.

    Examples:
        "Book Ii" -> True
        "Book II" -> False
        "Part Xiv" -> True
        "Part XIV" -> False
    """
    # Pattern matches: word boundary, then title-case Roman numerals
    # Examples: Ii, Iii, Iv, Vi, Vii, Viii, Ix, Xi, Xii, etc.
    pattern = r'\b(Ii|Iii|Iv|Vi|Vii|Viii|Ix|Xi|Xii|Xiii|Xiv|Xv|Xvi|Xvii|Xviii|Xix|Xx|Xxi|Xxii|Xxiii|Xxiv|Xxv|Xxvi|Xxvii|Xxviii|Xxix|Xxx)\b'
    return bool(re.search(pattern, text))


def fix_roman_numerals(text):
    """
    Convert all title-cased Roman numerals in text to uppercase.

    Examples:
        "Book Ii" -> "Book II"
        "Part Xiv" -> "Part XIV"
        "Book Xxiii" -> "Book XXIII"
    """
    # Pattern matches title-case Roman numerals
    pattern = r'\b(Ii|Iii|Iv|Vi|Vii|Viii|Ix|Xi|Xii|Xiii|Xiv|Xv|Xvi|Xvii|Xviii|Xix|Xx|Xxi|Xxii|Xxiii|Xxiv|Xxv|Xxvi|Xxvii|Xxviii|Xxix|Xxx)\b'

    def replace_with_uppercase(match):
        return match.group(1).upper()

    return re.sub(pattern, replace_with_uppercase, text)


def main():
    """Main function to fix Roman numerals in all chapter names."""
    db = Database(config.DATABASE_PATH)
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get all chapters with title-cased Roman numerals
    cursor.execute('SELECT id, book_id, chapter_number, chapter_title FROM chapters')
    all_chapters = cursor.fetchall()

    affected_chapters = []
    for chapter in all_chapters:
        if chapter['chapter_title'] and contains_title_case_roman_numeral(chapter['chapter_title']):
            affected_chapters.append(chapter)

    if not affected_chapters:
        print("No chapters with title-cased Roman numerals found.")
        conn.close()
        return

    print(f"Found {len(affected_chapters)} chapters with title-cased Roman numerals.")
    print("\nExamples:")
    for i, chapter in enumerate(affected_chapters[:5]):
        old_title = chapter['chapter_title']
        new_title = fix_roman_numerals(old_title)
        print(f"  {i+1}. '{old_title}' -> '{new_title}'")

    if len(affected_chapters) > 5:
        print(f"  ... and {len(affected_chapters) - 5} more")

    # Ask for confirmation
    print(f"\nThis will update {len(affected_chapters)} chapter names.")
    response = input("Continue? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("Aborted.")
        conn.close()
        return

    # Update chapters
    updated_count = 0
    for chapter in affected_chapters:
        old_title = chapter['chapter_title']
        new_title = fix_roman_numerals(old_title)

        cursor.execute('''
            UPDATE chapters
            SET chapter_title = ?
            WHERE id = ?
        ''', (new_title, chapter['id']))

        updated_count += 1
        if updated_count % 10 == 0:
            print(f"Updated {updated_count}/{len(affected_chapters)} chapters...")

    conn.commit()
    conn.close()

    print(f"\nSuccessfully updated {updated_count} chapter names.")
    print("\nSample of updated chapters:")

    # Verify the updates
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chapter_title FROM chapters WHERE id IN ({})'.format(
        ','.join('?' * min(5, len(affected_chapters)))
    ), [ch['id'] for ch in affected_chapters[:5]])

    for row in cursor.fetchall():
        print(f"  - {row['chapter_title']}")

    conn.close()


if __name__ == '__main__':
    main()
