#!/usr/bin/env python3
"""
Script to standardize book cover filenames and process large files.

This script:
1. Renames all book covers to {book_id}.{ext} format
2. Moves files >1.5MB to data/cover_originals/
3. Resizes large files to ~1MB for web use
4. Updates database with new paths and cover_source metadata
"""

import os
import sys
import shutil
from pathlib import Path
from PIL import Image

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

import models
import config

# Import resize function from existing script
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from resize_image import resize_image_to_target_size, get_file_size_mb


def get_file_extension(filepath):
    """Get file extension in lowercase"""
    return os.path.splitext(filepath)[1].lower()


def determine_cover_source(current_path):
    """Determine if cover is from custom upload or gutenberg"""
    filename = os.path.basename(current_path)

    # Check if it's a Gutenberg cover (pg*.jpg pattern)
    if filename.startswith('pg') and filename.endswith('.jpg'):
        return 'gutenberg'

    # Check if it has _custom in the name
    if '_custom' in filename:
        return 'custom'

    # Check if it's a numbered pattern (e.g., 1_1.png)
    if filename.split('_')[0].isdigit():
        return 'custom'

    # Default to unknown
    return 'unknown'


def is_chapter_illustration(filename, book_id):
    """Check if filename matches chapter illustration pattern: {book_id}_{chapter_num}.{ext}"""
    basename = os.path.basename(filename)
    name_without_ext = os.path.splitext(basename)[0]

    # Pattern: {book_id}_{chapter_num}
    import re
    pattern = rf'^{book_id}_(\d+)$'
    match = re.match(pattern, name_without_ext)

    if match:
        chapter_num = int(match.group(1))
        # Chapter illustrations are typically numbered  1-999
        # Book covers would be just {book_id}.{ext}
        return chapter_num > 0

    return False


def migrate_chapter_illustrations(dry_run=False):
    """
    Migrate chapter illustration files to illustrations directory.

    Args:
        dry_run: If True, only print what would be done without making changes
    """
    db = models.Database()
    books = db.get_all_books()

    covers_dir = config.COVERS_DIR
    illustrations_dir = config.ILLUSTRATIONS_DIR

    if not dry_run:
        illustrations_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("CHAPTER ILLUSTRATIONS MIGRATION")
    print("=" * 80)

    illustration_stats = {
        'total': 0,
        'moved': 0,
        'updated_db': 0,
        'errors': 0
    }

    for book in books:
        book_id = book['id']
        chapters = db.get_chapters(book_id)

        if not chapters:
            continue

        # Find all files matching {book_id}_{num}.{ext} pattern in covers directory
        for file_path in covers_dir.glob(f"{book_id}_*.*"):
            if is_chapter_illustration(file_path.name, book_id):
                illustration_stats['total'] += 1

                # Extract chapter number
                basename = file_path.stem
                chapter_num = int(basename.split('_')[1])

                # Find matching chapter
                chapter = next((ch for ch in chapters if ch['chapter_number'] == chapter_num), None)

                if not chapter:
                    print(f"  ⚠ Chapter {chapter_num} not found for book {book_id}, skipping {file_path.name}")
                    continue

                # New path in illustrations directory
                new_path = illustrations_dir / file_path.name
                new_url = f"illustrations/{file_path.name}"

                print(f"\n  {book['title'][:50]} - Chapter {chapter_num}")
                print(f"    Moving: {file_path.name}")
                print(f"    To: {new_path}")

                if not dry_run:
                    try:
                        # Move file
                        shutil.move(str(file_path), str(new_path))
                        illustration_stats['moved'] += 1

                        # Update database
                        db.add_chapter(
                            book_id=book_id,
                            chapter_number=chapter_num,
                            chapter_title=chapter['chapter_title'],
                            summary=chapter['summary'],
                            chapter_text=chapter.get('chapter_text'),
                            section_id=chapter.get('section_id'),
                            illustration_url=new_url
                        )
                        illustration_stats['updated_db'] += 1
                        print(f"    ✓ Moved and updated DB")

                    except Exception as e:
                        print(f"    ✗ Error: {e}")
                        illustration_stats['errors'] += 1
                else:
                    print(f"    [DRY RUN] Would move and update DB")

    print("\n" + "-" * 80)
    print("Chapter Illustrations Summary:")
    print(f"  Total found: {illustration_stats['total']}")
    print(f"  Moved: {illustration_stats['moved']}")
    print(f"  DB updated: {illustration_stats['updated_db']}")
    print(f"  Errors: {illustration_stats['errors']}")
    print("=" * 80)

    return illustration_stats


def migrate_book_covers(dry_run=False):
    """
    Migrate all book covers to new standardized naming scheme.

    Args:
        dry_run: If True, only print what would be done without making changes
    """
    db = models.Database()
    books = db.get_all_books()

    covers_dir = config.COVERS_DIR
    originals_dir = Path(config.BASE_DIR) / 'data' / 'cover_originals'

    # Ensure originals directory exists
    if not dry_run:
        originals_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("BOOK COVER MIGRATION SCRIPT")
    print("=" * 80)
    print(f"Covers directory: {covers_dir}")
    print(f"Originals directory: {originals_dir}")
    print(f"Illustrations directory: {config.ILLUSTRATIONS_DIR}")
    print(f"Total books: {len(books)}")
    print(f"Dry run: {dry_run}")
    print("=" * 80)
    print()

    # First, migrate chapter illustrations out of covers directory
    migrate_chapter_illustrations(dry_run)

    stats = {
        'total': len(books),
        'renamed': 0,
        'resized': 0,
        'moved_to_originals': 0,
        'no_cover': 0,
        'errors': 0,
        'skipped': 0
    }

    for book in books:
        book_id = book['id']
        title = book['title']
        current_cover_url = book.get('cover_image_url')

        print(f"\n[Book {book_id}] {title}")
        print("-" * 80)

        if not current_cover_url:
            print("  ⊘ No cover image in database")
            stats['no_cover'] += 1
            continue

        # Get current file path
        current_path = covers_dir / current_cover_url.replace('covers/', '')

        if not current_path.exists():
            print(f"  ✗ Cover file not found: {current_path}")
            stats['errors'] += 1
            continue

        # Skip chapter illustrations (they were already migrated)
        if is_chapter_illustration(str(current_path), book_id):
            print(f"  → Skipping chapter illustration: {current_path.name}")
            stats['skipped'] += 1
            continue

        # Determine cover source
        cover_source = determine_cover_source(str(current_path))
        print(f"  Source: {cover_source}")

        # Get file info
        file_ext = get_file_extension(str(current_path))
        file_size_mb = get_file_size_mb(str(current_path))
        print(f"  Current: {current_path.name} ({file_size_mb:.2f} MB)")

        # Determine new filename
        new_filename = f"{book_id}{file_ext}"
        new_path = covers_dir / new_filename

        # Check if file is already in correct format
        if current_path == new_path:
            print(f"  ✓ Already using correct filename: {new_filename}")

            # Still update database if cover_source is unknown
            if book.get('cover_source') == 'unknown' or not book.get('cover_source'):
                if not dry_run:
                    db.update_book_cover(
                        book_id,
                        book.get('gutenberg_id'),
                        f"covers/{new_filename}",
                        cover_source
                    )
                    print(f"  → Updated cover_source to: {cover_source}")

            stats['skipped'] += 1

            # Still check if needs resizing
            if file_size_mb > 1.5:
                print(f"  ⚠ File is large ({file_size_mb:.2f} MB), needs processing")

                original_filename = f"{book_id}_original{file_ext}"
                original_path = originals_dir / original_filename

                if not dry_run:
                    # Move original to originals directory
                    print(f"  → Moving to: {original_path}")
                    shutil.move(str(current_path), str(original_path))
                    stats['moved_to_originals'] += 1

                    # Resize for web
                    print(f"  → Resizing to ~1MB: {new_path}")
                    result = resize_image_to_target_size(
                        str(original_path),
                        str(new_path),
                        target_mb=1.0,
                        verbose=False
                    )

                    if result['success']:
                        print(f"  ✓ Resized to {result['final_size_mb']:.2f} MB ({result['dimensions']})")
                        stats['resized'] += 1
                    else:
                        print(f"  ✗ Resize failed: {result.get('error', 'Unknown error')}")
                        stats['errors'] += 1
                else:
                    print(f"  [DRY RUN] Would move to: {original_path}")
                    print(f"  [DRY RUN] Would resize to: {new_path}")

            continue

        # Rename/move file
        print(f"  → New name: {new_filename}")

        # Check if file >1.5MB
        needs_resize = file_size_mb > 1.5

        if needs_resize:
            print(f"  ⚠ Large file ({file_size_mb:.2f} MB), will resize")

            original_filename = f"{book_id}_original{file_ext}"
            original_path = originals_dir / original_filename

            if not dry_run:
                # Move original to originals directory
                print(f"  → Moving original to: {original_path}")
                shutil.move(str(current_path), str(original_path))
                stats['moved_to_originals'] += 1

                # Resize for web
                print(f"  → Resizing for web: {new_path}")
                result = resize_image_to_target_size(
                    str(original_path),
                    str(new_path),
                    target_mb=1.0,
                    verbose=False
                )

                if result['success']:
                    print(f"  ✓ Resized to {result['final_size_mb']:.2f} MB ({result['dimensions']})")
                    stats['resized'] += 1
                    stats['renamed'] += 1
                else:
                    print(f"  ✗ Resize failed: {result.get('error', 'Unknown error')}")
                    stats['errors'] += 1
                    continue
            else:
                print(f"  [DRY RUN] Would move to: {original_path}")
                print(f"  [DRY RUN] Would resize to: {new_path}")
        else:
            # Just rename
            if not dry_run:
                print(f"  → Renaming to: {new_path}")
                shutil.move(str(current_path), str(new_path))
                stats['renamed'] += 1
            else:
                print(f"  [DRY RUN] Would rename to: {new_path}")

        # Update database
        new_cover_url = f"covers/{new_filename}"
        if not dry_run:
            db.update_book_cover(
                book_id,
                book.get('gutenberg_id'),
                new_cover_url,
                cover_source
            )
            print(f"  ✓ Updated database: {new_cover_url} (source: {cover_source})")
        else:
            print(f"  [DRY RUN] Would update DB: {new_cover_url} (source: {cover_source})")

    # Print summary
    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total books:            {stats['total']}")
    print(f"Renamed:                {stats['renamed']}")
    print(f"Resized:                {stats['resized']}")
    print(f"Moved to originals:     {stats['moved_to_originals']}")
    print(f"Already correct:        {stats['skipped']}")
    print(f"No cover:               {stats['no_cover']}")
    print(f"Errors:                 {stats['errors']}")
    print("=" * 80)

    if dry_run:
        print("\n⚠ DRY RUN - No changes were made!")
        print("Run without --dry-run to apply changes.")
    else:
        print("\n✓ Migration complete!")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Migrate book covers to standardized naming scheme'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making changes (preview mode)'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("This will rename and potentially resize book cover files.")
        print("It's recommended to run with --dry-run first to preview changes.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

    migrate_book_covers(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
