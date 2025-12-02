#!/usr/bin/env python3
"""
Script to bulk import chapter illustration images and update database.

The script:
1. Automatically resizes images >1.5MB to ~1MB before copying (configurable)
2. Copies image files to the covers directory
3. Updates the database chapters table with illustration URLs
4. Supports flexible naming patterns

Usage:
    # Import files (auto-resizes images >1.5MB)
    python scripts/import_chapter_illustrations.py --book-id 1 /Users/pengyao/Downloads/1_*.png

    # Custom resize thresholds
    python scripts/import_chapter_illustrations.py --book-id 1 --max-size 2.0 --target-size 1.5 /path/to/images/*.png

    # Dry run (show what would be done without making changes)
    python scripts/import_chapter_illustrations.py --book-id 1 --dry-run /Users/pengyao/Downloads/1_*.png
"""

import sys
import os
import shutil
import re
import glob
from pathlib import Path
from PIL import Image

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from backend.models import Database
import backend.config as config


def get_file_size_mb(filepath):
    """Get file size in MB."""
    return os.path.getsize(filepath) / (1024 * 1024)


def resize_image_to_target_size(input_path, output_path, target_mb=1.0, tolerance_mb=0.1):
    """
    Resize a PNG image to approximately target_mb file size.

    Args:
        input_path: Path to input image file
        output_path: Path to output image file
        target_mb: Target file size in MB (default: 1.0)
        tolerance_mb: Acceptable tolerance in MB (default: 0.1)

    Returns:
        dict: Result info with keys 'success', 'original_size_mb', 'final_size_mb', 'dimensions'
    """
    try:
        # Open the image
        img = Image.open(input_path)
        original_width, original_height = img.size
        original_size_mb = get_file_size_mb(input_path)

        print(f"  📏 Original: {original_width}x{original_height}, {original_size_mb:.2f} MB")

        # Check if input is already small enough
        if original_size_mb <= target_mb:
            print(f"  ✓ Already ≤{target_mb} MB, no resize needed")
            img.save(output_path, img.format or 'PNG', optimize=True)
            final_size_mb = get_file_size_mb(output_path)
            return {
                'success': True,
                'original_size_mb': original_size_mb,
                'final_size_mb': final_size_mb,
                'dimensions': f"{original_width}x{original_height}",
                'resized': False
            }

        # Start with a scale factor
        scale = 1.0
        min_scale = 0.1
        max_scale = 1.0

        print(f"  🔄 Resizing to ~{target_mb} MB...")

        # Binary search for the right scale
        for iteration in range(15):  # Max 15 iterations
            # Calculate new dimensions
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

            # Resize image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save temporarily to check size
            resized_img.save(output_path, img.format or 'PNG', optimize=True)
            current_size_mb = get_file_size_mb(output_path)

            # Check if we're within tolerance
            if abs(current_size_mb - target_mb) <= tolerance_mb:
                print(f"  ✓ Resized to {new_width}x{new_height}, {current_size_mb:.2f} MB")
                return {
                    'success': True,
                    'original_size_mb': original_size_mb,
                    'final_size_mb': current_size_mb,
                    'dimensions': f"{new_width}x{new_height}",
                    'resized': True
                }

            # Adjust scale using binary search
            if current_size_mb > target_mb:
                max_scale = scale
                scale = (min_scale + scale) / 2
            else:
                min_scale = scale
                scale = (scale + max_scale) / 2

        # If we exit the loop, we're as close as we can get
        final_size_mb = get_file_size_mb(output_path)
        final_img = Image.open(output_path)
        print(f"  ✓ Resized to {final_img.size[0]}x{final_img.size[1]}, {final_size_mb:.2f} MB")

        return {
            'success': True,
            'original_size_mb': original_size_mb,
            'final_size_mb': final_size_mb,
            'dimensions': f"{final_img.size[0]}x{final_img.size[1]}",
            'resized': True
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'original_size_mb': 0,
            'final_size_mb': 0,
            'dimensions': 'N/A',
            'resized': False
        }


def parse_filename(filename, book_id):
    """
    Parse filename to extract chapter number.
    Supports patterns like:
    - {book_id}_{chapter_id}_resized.png
    - {book_id}_{chapter_id}.png
    - {chapter_id}_resized.png
    - {chapter_id}.png

    Returns chapter_id as integer or None if parsing fails
    """
    basename = os.path.basename(filename)
    name_without_ext = os.path.splitext(basename)[0]

    # Try pattern: {book_id}_{chapter_id}_resized or {book_id}_{chapter_id}
    pattern1 = rf'^{book_id}_(\d+)(?:_resized)?$'
    match = re.match(pattern1, name_without_ext)
    if match:
        return int(match.group(1))

    # Try pattern: {chapter_id}_resized or {chapter_id}
    pattern2 = r'^(\d+)(?:_resized)?$'
    match = re.match(pattern2, name_without_ext)
    if match:
        return int(match.group(1))

    return None


def import_illustrations(book_id, image_files, dry_run=False, max_size_mb=1.5, target_size_mb=1.0):
    """
    Import chapter illustrations for a book.
    Automatically resizes images larger than max_size_mb to target_size_mb before importing.

    Args:
        book_id: Book ID in database
        image_files: List of image file paths
        dry_run: If True, show what would be done without making changes
        max_size_mb: Maximum file size before auto-resize (default: 1.5 MB)
        target_size_mb: Target size for resized images (default: 1.0 MB)
    """
    # Initialize database
    db = Database()

    # Verify book exists
    book = db.get_book(book_id)
    if not book:
        print(f"Error: Book ID {book_id} not found in database")
        return False

    print(f"Book: {book['title']} by {book['author']}")
    print(f"Book ID: {book_id}")
    print()

    # Get existing chapters
    chapters = db.get_chapters(book_id)
    if not chapters:
        print(f"Warning: No chapters found for book ID {book_id}")
        return False

    chapter_map = {ch['chapter_number']: ch for ch in chapters}
    print(f"Found {len(chapters)} chapters in database (chapters {min(chapter_map.keys())} - {max(chapter_map.keys())})")
    print()

    # Ensure illustrations directory exists
    illustrations_dir = config.ILLUSTRATIONS_DIR
    book_illustrations_dir = illustrations_dir / str(book_id)
    if not dry_run:
        book_illustrations_dir.mkdir(parents=True, exist_ok=True)

    # Process each image file
    results = {
        'success': [],
        'resized': [],
        'skipped': [],
        'errors': []
    }

    print(f"Processing {len(image_files)} image file(s)...")
    print(f"Auto-resize threshold: {max_size_mb} MB (target: {target_size_mb} MB)")
    print("=" * 80)

    for image_path in sorted(image_files):
        print(f"\nProcessing: {image_path}")

        # Check if file exists
        if not os.path.exists(image_path):
            error_msg = "File not found"
            print(f"  ❌ Error: {error_msg}")
            results['errors'].append({'file': image_path, 'error': error_msg})
            continue

        # Parse filename to get chapter number
        chapter_number = parse_filename(image_path, book_id)
        if chapter_number is None:
            error_msg = f"Could not parse chapter number from filename"
            print(f"  ❌ Error: {error_msg}")
            results['errors'].append({'file': image_path, 'error': error_msg})
            continue

        print(f"  Detected chapter number: {chapter_number}")

        # Check if chapter exists
        if chapter_number not in chapter_map:
            error_msg = f"Chapter {chapter_number} not found in database"
            print(f"  ⚠️  Warning: {error_msg}")
            results['skipped'].append({'file': image_path, 'reason': error_msg})
            continue

        chapter = chapter_map[chapter_number]

        # Generate destination filename (just chapter number, not book_id prefix)
        file_ext = os.path.splitext(image_path)[1]
        dest_filename = f"{chapter_number}{file_ext}"
        dest_path = book_illustrations_dir / dest_filename

        # URL path for database (relative to static folder)
        illustration_url = f"illustrations/{book_id}/{dest_filename}"

        print(f"  Chapter: {chapter['chapter_title']}")
        print(f"  Destination: {dest_path}")
        print(f"  URL: {illustration_url}")

        if dry_run:
            # Check if resize would be needed
            file_size_mb = get_file_size_mb(image_path)
            if file_size_mb > max_size_mb:
                print(f"  🔍 DRY RUN - Would resize from {file_size_mb:.2f} MB to ~{target_size_mb} MB")
            print(f"  🔍 DRY RUN - Would copy file and update database")
            results['success'].append({
                'file': image_path,
                'chapter_number': chapter_number,
                'chapter_title': chapter['chapter_title'],
                'dest_path': str(dest_path),
                'url': illustration_url
            })
        else:
            try:
                # Check if we need to resize
                file_size_mb = get_file_size_mb(image_path)
                was_resized = False

                if file_size_mb > max_size_mb:
                    print(f"  ⚠️  File size {file_size_mb:.2f} MB exceeds {max_size_mb} MB threshold")
                    # Resize directly to destination
                    resize_result = resize_image_to_target_size(image_path, dest_path, target_size_mb)
                    if not resize_result['success']:
                        error_msg = resize_result.get('error', 'Resize failed')
                        print(f"  ❌ Resize error: {error_msg}")
                        results['errors'].append({'file': image_path, 'error': error_msg})
                        continue
                    was_resized = resize_result['resized']
                else:
                    # Just copy file to covers directory
                    shutil.copy2(image_path, dest_path)
                    print(f"  ✅ Copied to: {dest_path}")

                # Update database with illustration URL
                db.add_chapter(
                    book_id=book_id,
                    chapter_number=chapter_number,
                    chapter_title=chapter['chapter_title'],
                    summary=chapter['summary'],
                    chapter_text=chapter.get('chapter_text'),
                    section_id=chapter.get('section_id'),
                    illustration_url=illustration_url
                )
                print(f"  ✅ Updated database with illustration URL")

                result_item = {
                    'file': image_path,
                    'chapter_number': chapter_number,
                    'chapter_title': chapter['chapter_title'],
                    'dest_path': str(dest_path),
                    'url': illustration_url,
                    'resized': was_resized
                }
                results['success'].append(result_item)
                if was_resized:
                    results['resized'].append(result_item)

            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ Error: {error_msg}")
                results['errors'].append({'file': image_path, 'error': error_msg})

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if dry_run:
        print("DRY RUN MODE - No changes were made")
        print()

    print(f"Total files processed: {len(image_files)}")
    print(f"Successfully imported: {len(results['success'])}")
    if results['resized']:
        print(f"  - Auto-resized: {len(results['resized'])}")
        print(f"  - Copied as-is: {len(results['success']) - len(results['resized'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print(f"Errors: {len(results['errors'])}")

    if results['success']:
        print(f"\n✅ Successfully imported {len(results['success'])} illustration(s):")
        for item in results['success']:
            resize_tag = " (resized)" if item.get('resized') else ""
            print(f"   Chapter {item['chapter_number']}: {item['chapter_title']}{resize_tag}")

    if results['skipped']:
        print(f"\n⚠️  Skipped {len(results['skipped'])} file(s):")
        for item in results['skipped']:
            print(f"   {os.path.basename(item['file'])}: {item['reason']}")

    if results['errors']:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for item in results['errors']:
            print(f"   {os.path.basename(item['file'])}: {item['error']}")

    print()
    return len(results['errors']) == 0


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python scripts/import_chapter_illustrations.py --book-id BOOK_ID [OPTIONS] IMAGE_FILES...")
        print("\nOptions:")
        print("  --dry-run              Preview changes without making them")
        print("  --max-size MB          Max file size before auto-resize (default: 1.5)")
        print("  --target-size MB       Target size for resized images (default: 1.0)")
        print("\nExamples:")
        print("  python scripts/import_chapter_illustrations.py --book-id 1 /Users/pengyao/Downloads/1_*.png")
        print("  python scripts/import_chapter_illustrations.py --book-id 1 --dry-run /path/to/images/*.png")
        print("  python scripts/import_chapter_illustrations.py --book-id 1 --max-size 2.0 --target-size 1.5 *.png")
        print("\nNaming convention:")
        print("  Files should be named: {book_id}_{chapter_id}_resized.png or {book_id}_{chapter_id}.png")
        print("  Examples: 1_1_resized.png, 1_2_resized.png, 1_3.png")
        print("\nAuto-resize:")
        print("  Images larger than --max-size are automatically resized to --target-size before importing")
        sys.exit(1)

    # Parse arguments
    args = sys.argv[1:]
    book_id = None
    dry_run = False
    max_size_mb = 1.5
    target_size_mb = 1.0
    image_files = []

    i = 0
    while i < len(args):
        if args[i] == '--book-id' and i + 1 < len(args):
            try:
                book_id = int(args[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid book ID '{args[i + 1]}'")
                sys.exit(1)
        elif args[i] == '--dry-run':
            dry_run = True
            i += 1
        elif args[i] == '--max-size' and i + 1 < len(args):
            try:
                max_size_mb = float(args[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid max size '{args[i + 1]}'")
                sys.exit(1)
        elif args[i] == '--target-size' and i + 1 < len(args):
            try:
                target_size_mb = float(args[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid target size '{args[i + 1]}'")
                sys.exit(1)
        else:
            # Expand glob patterns
            expanded = glob.glob(args[i])
            if expanded:
                # Filter for image files only
                for f in expanded:
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_files.append(f)
            else:
                # Add as-is if no glob expansion
                if args[i].lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_files.append(args[i])
            i += 1

    # Validate arguments
    if book_id is None:
        print("Error: --book-id is required")
        sys.exit(1)

    if not image_files:
        print("Error: No image files specified")
        sys.exit(1)

    # Remove duplicates and sort
    image_files = sorted(list(set(image_files)))

    # Run import
    success = import_illustrations(book_id, image_files, dry_run, max_size_mb, target_size_mb)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
