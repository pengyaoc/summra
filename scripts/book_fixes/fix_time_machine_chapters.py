#!/usr/bin/env python3
"""Fix chapter numbering for The Time Machine based on TOC"""


from backend import models

def main():
    db = models.Database()
    book_id = 28  # The Time Machine

    # Correct chapter mapping based on TOC
    # Current chapter_number -> (correct_number, correct_title)
    chapter_mapping = {
        0: (1, "Introduction"),
        2: (2, "The Machine"),
        3: (3, "The Time Traveller Returns"),
        4: (4, "Time Travelling"),
        5: (5, "In the Golden Age"),
        6: (6, "The Sunset of Mankind"),
        7: (7, "A Sudden Shock"),
        8: (8, "Explanation"),
        9: (9, "The Morlocks"),
        10: (10, "When Night Came"),
        11: (11, "The Palace of Green Porcelain"),
        12: (12, "In the Darkness"),
        13: (13, "The Trap of the White Sphinx"),
        14: (14, "The Further Vision"),
        15: (15, "The Time Traveller's Return"),
        16: (16, "After the Story"),
        999: (17, "Epilogue")
    }

    print("Fixing chapter numbering for The Time Machine...")
    print("=" * 80)

    # Get current chapters
    current_chapters = db.get_chapters(book_id)
    print(f"\nFound {len(current_chapters)} chapters")

    # Show current state
    print("\nCurrent chapters:")
    for ch in current_chapters:
        print(f"  Chapter {ch['chapter_number']}: {ch['chapter_title']}")

    # Update each chapter
    conn = db.get_connection()
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print("Updating chapters...")
    print(f"{'='*80}\n")

    updated_count = 0
    for old_num, (new_num, new_title) in chapter_mapping.items():
        # Find chapter with old number
        cursor.execute('SELECT id, chapter_title FROM chapters WHERE book_id = ? AND chapter_number = ?',
                      (book_id, old_num))
        result = cursor.fetchone()

        if result:
            chapter_id = result[0]
            old_title = result[1]

            print(f"Chapter {old_num} -> {new_num}")
            print(f"  Old title: {old_title}")
            print(f"  New title: {new_title}")

            # Update chapter
            cursor.execute('''
                UPDATE chapters
                SET chapter_number = ?, chapter_title = ?
                WHERE id = ?
            ''', (new_num, new_title, chapter_id))

            updated_count += 1
            print(f"  ✓ Updated\n")
        else:
            print(f"⚠️  Warning: Chapter {old_num} not found\n")

    conn.commit()
    conn.close()

    print(f"{'='*80}")
    print(f"✓ Updated {updated_count} chapters")
    print(f"{'='*80}\n")

    # Verify the updates
    print("Verifying updates...")
    updated_chapters = db.get_chapters(book_id)

    print("\nUpdated chapters (sorted by number):")
    for ch in sorted(updated_chapters, key=lambda x: x['chapter_number']):
        print(f"  Chapter {ch['chapter_number']}: {ch['chapter_title']}")

    print(f"\n{'='*80}")
    print("✓ All chapters updated successfully!")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
