#!/usr/bin/env python3
"""
Script to reorganize chapter illustrations into book-specific folders.

Changes:
- FROM: illustrations/1_1.png, illustrations/1_2.png
- TO:   illustrations/1/1.png, illustrations/1/2.png
"""

import os
import sys
import shutil
from pathlib import Path

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

import models
import config


def reorganize_illustrations(dry_run=False):
    """Reorganize illustrations into book-specific subdirectories"""

    db = models.Database()
    illustrations_dir = config.ILLUSTRATIONS_DIR

    print("=" * 80)
    print("ILLUSTRATIONS REORGANIZATION SCRIPT")
    print("=" * 80)
    print(f"Illustrations directory: {illustrations_dir}")
    print(f"Dry run: {dry_run}")
    print("=" * 80)
    print()

    stats = {
        'total': 0,
        'moved': 0,
        'updated_db': 0,
        'errors': 0
    }

    # Get all illustration files (matching pattern: {book_id}_{chapter_num}.{ext})
    for file_path in illustrations_dir.glob("*_*.*"):
        if file_path.is_file():
            stats['total'] += 1

            filename = file_path.name
            name_without_ext = file_path.stem
            ext = file_path.suffix

            # Parse book_id and chapter_num from filename
            try:
                parts = name_without_ext.split('_')
                if len(parts) != 2:
                    print(f"⚠ Skipping {filename}: unexpected format")
                    continue

                book_id = int(parts[0])
                chapter_num = int(parts[1])

                # Create book-specific subdirectory
                book_dir = illustrations_dir / str(book_id)
                new_filename = f"{chapter_num}{ext}"
                new_path = book_dir / new_filename
                new_url = f"illustrations/{book_id}/{new_filename}"

                print(f"\n[Book {book_id}, Chapter {chapter_num}]")
                print(f"  Old: {filename}")
                print(f"  New: {book_id}/{new_filename}")

                if not dry_run:
                    # Create book directory if it doesn't exist
                    book_dir.mkdir(parents=True, exist_ok=True)

                    # Move file
                    shutil.move(str(file_path), str(new_path))
                    stats['moved'] += 1
                    print(f"  ✓ Moved to {new_path}")

                    # Update database
                    chapter = db.get_chapter(book_id, chapter_num)
                    if chapter:
                        db.add_chapter(
                            book_id=book_id,
                            chapter_number=chapter_num,
                            chapter_title=chapter['chapter_title'],
                            summary=chapter['summary'],
                            chapter_text=chapter.get('chapter_text'),
                            section_id=chapter.get('section_id'),
                            illustration_url=new_url
                        )
                        stats['updated_db'] += 1
                        print(f"  ✓ Updated DB: {new_url}")
                    else:
                        print(f"  ⚠ Chapter not found in DB")
                else:
                    print(f"  [DRY RUN] Would move and update DB")

            except (ValueError, IndexError) as e:
                print(f"✗ Error processing {filename}: {e}")
                stats['errors'] += 1
                continue

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files: {stats['total']}")
    print(f"Moved: {stats['moved']}")
    print(f"DB updated: {stats['updated_db']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 80)

    if dry_run:
        print("\n⚠ DRY RUN - No changes were made!")
        print("Run without --dry-run to apply changes.")
    else:
        print("\n✓ Reorganization complete!")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Reorganize chapter illustrations into book-specific folders'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without making them'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("This will reorganize illustration files into book-specific subdirectories.")
        print("It's recommended to run with --dry-run first to preview changes.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

    reorganize_illustrations(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
