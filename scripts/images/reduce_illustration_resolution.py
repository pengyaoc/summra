#!/usr/bin/env python3
"""
Optimize images with WebP + JPG fallback and backup originals

This script:
1. Moves original high-resolution images to data/image_originals/
2. Creates optimized WebP and JPG versions in the original location
3. Supports both illustrations and book covers
4. Can batch process all books or individual book/covers

Usage:
    # Process illustrations for a book
    python scripts/images/reduce_illustration_resolution.py --book-id 47
    python scripts/images/reduce_illustration_resolution.py --book-id 47 --max-width 1024

    # Process book covers (all or specific)
    python scripts/images/reduce_illustration_resolution.py --covers --all
    python scripts/images/reduce_illustration_resolution.py --covers --book-id 47

    # Dry run to see what would be processed
    python scripts/images/reduce_illustration_resolution.py --covers --all --dry-run
"""

import sys
import shutil
import argparse
from pathlib import Path
from PIL import Image

# Add parent directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

import config
from models import Database

# Default maximum width for reduced images
DEFAULT_MAX_WIDTH = 1024
DEFAULT_COVER_WIDTH = 400  # Reasonable size for book covers


def optimize_image(input_path: Path, output_base_path: Path, max_width: int = DEFAULT_MAX_WIDTH,
                   create_webp: bool = True) -> bool:
    """Optimize image by creating WebP and JPG versions

    Args:
        input_path: Path to original image
        output_base_path: Base path for output (without extension)
        max_width: Maximum width in pixels (height scaled proportionally)
        create_webp: If True, create WebP version; if False, only JPG

    Returns:
        True if successful, False otherwise
    """
    try:
        # Open image
        img = Image.open(input_path)
        original_size = img.size

        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if width > max_width:
            new_width = max_width
            new_height = int((max_width / width) * height)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"  Resized: {original_size} -> {img.size}")
        else:
            print(f"  No resize needed (width {width} <= {max_width})")

        # Ensure output directory exists
        output_base_path.parent.mkdir(parents=True, exist_ok=True)

        original_size_mb = input_path.stat().st_size / (1024 * 1024)
        total_output_size = 0

        # Save WebP version (best compression)
        if create_webp:
            webp_path = output_base_path.with_suffix('.webp')
            img.save(webp_path, 'WEBP', quality=85, method=6)
            webp_size_mb = webp_path.stat().st_size / (1024 * 1024)
            total_output_size += webp_path.stat().st_size
            print(f"  ✅ WebP: {webp_path.name} ({webp_size_mb:.2f} MB)")

        # Save JPG version (fallback for older browsers)
        jpg_path = output_base_path.with_suffix('.jpg')
        img.save(jpg_path, 'JPEG', quality=85, optimize=True)
        jpg_size_mb = jpg_path.stat().st_size / (1024 * 1024)
        total_output_size += jpg_path.stat().st_size
        print(f"  ✅ JPG:  {jpg_path.name} ({jpg_size_mb:.2f} MB)")

        # Calculate total reduction
        avg_output_mb = (total_output_size / (2 if create_webp else 1)) / (1024 * 1024)
        reduction = ((original_size_mb - avg_output_mb) / original_size_mb) * 100 if original_size_mb > 0 else 0
        print(f"  📊 Original: {original_size_mb:.2f} MB -> Avg output: {avg_output_mb:.2f} MB ({reduction:.1f}% reduction)")

        return True

    except Exception as e:
        print(f"  ❌ Error processing {input_path}: {e}")
        return False


def process_book_illustrations(book_id: int, max_width: int = DEFAULT_MAX_WIDTH,
                               dry_run: bool = False, chapter_numbers: list = None,
                               update_db: bool = False) -> bool:
    """Process all illustrations for a book

    Args:
        book_id: Book ID
        max_width: Maximum width for optimized images
        dry_run: If True, show what would be done without doing it
        chapter_numbers: Optional list of specific chapter numbers to process (e.g., [1, 2, 3])
                        If None, processes all chapters
        update_db: If True, update database with illustration URLs

    Returns:
        True if successful, False otherwise
    """
    # Initialize database connection if needed
    db = None
    if update_db and not dry_run:
        db = Database()
    # Define paths - source from data/illustration_originals, output to frontend/static/illustrations
    source_dir = project_root / "data" / "illustration_originals" / str(book_id)
    output_dir = config.ILLUSTRATIONS_DIR / str(book_id)

    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return False

    # Get all image files (PNG, JPG) from source directory
    all_image_files = list(source_dir.glob("*.png")) + list(source_dir.glob("*.jpg"))

    # Filter by chapter numbers if specified
    if chapter_numbers is not None:
        chapter_set = set(str(num) for num in chapter_numbers)
        image_files = [f for f in all_image_files if f.stem in chapter_set]
    else:
        image_files = all_image_files

    if not image_files:
        print(f"ℹ️  No image files found in {source_dir}")
        return True

    print(f"\n{'='*80}")
    print(f"Processing {len(image_files)} illustration(s) for book {book_id}")
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print(f"Max width: {max_width}px")
    print(f"Output: WebP + JPG")
    if dry_run:
        print("[DRY RUN MODE - No changes will be made]")
    print(f"{'='*80}\n")

    if dry_run:
        for img_file in sorted(image_files):
            chapter_num = img_file.stem
            print(f"Would process: {img_file.name} -> .webp + .jpg in {output_dir}")
        return True

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    all_success = True

    for img_file in sorted(image_files):
        # Extract chapter number from filename (e.g., "1.png" -> "1")
        chapter_num = img_file.stem

        print(f"\nProcessing: {img_file.name}")

        # Create optimized versions (WebP + JPG) in frontend/static/illustrations
        output_base = output_dir / chapter_num
        if optimize_image(img_file, output_base, max_width, create_webp=True):
            print(f"  ✅ Created optimized versions in {output_dir}")

            # Update database with illustration URL if requested
            if db:
                try:
                    # Get existing chapter data
                    chapter = db.get_chapter(book_id, int(chapter_num))
                    if chapter:
                        # Update with new illustration URL (using .png as base, frontend handles format selection)
                        illustration_url = f"/static/illustrations/{book_id}/{chapter_num}.png"
                        db.add_chapter(
                            book_id=book_id,
                            chapter_number=int(chapter_num),
                            chapter_title=chapter.get('chapter_title', ''),
                            summary=chapter.get('summary', ''),
                            chapter_text=chapter.get('chapter_text'),
                            section_id=chapter.get('section_id'),
                            illustration_url=illustration_url
                        )
                        print(f"  📝 Updated database: {illustration_url}")
                    else:
                        print(f"  ⚠️  Chapter {chapter_num} not found in database, skipping DB update")
                except Exception as e:
                    print(f"  ⚠️  Database update failed: {e}")
                    # Don't fail the whole process for DB errors
        else:
            all_success = False

    print(f"\n{'='*80}")
    if all_success:
        print("✅ All illustrations processed successfully!")
    else:
        print("⚠️  Some illustrations had errors")
    print(f"{'='*80}\n")

    return all_success


def get_unique_backup_path(backup_dir: Path, filename: str) -> Path:
    """Get a unique backup path, adding numbers if file exists

    Args:
        backup_dir: Directory to save backup
        filename: Original filename

    Returns:
        Unique Path object
    """
    backup_path = backup_dir / filename
    if not backup_path.exists():
        return backup_path

    # File exists, add number suffix
    stem = backup_path.stem
    suffix = backup_path.suffix
    counter = 1

    while True:
        new_path = backup_dir / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def process_book_covers(book_id: int = None, max_width: int = DEFAULT_COVER_WIDTH, dry_run: bool = False) -> bool:
    """Process book cover images

    Args:
        book_id: Specific book ID to process, or None for all covers
        max_width: Maximum width for optimized covers
        dry_run: If True, show what would be done without doing it

    Returns:
        True if successful, False otherwise
    """
    covers_dir = config.COVERS_DIR
    backup_dir = project_root / "data" / "cover_originals"

    if not covers_dir.exists():
        print(f"❌ Covers directory not found: {covers_dir}")
        return False

    # Get image files to process
    if book_id is not None:
        # Process specific book cover
        image_files = list(covers_dir.glob(f"{book_id}.*"))
    else:
        # Process all covers
        image_files = list(covers_dir.glob("*.png")) + list(covers_dir.glob("*.jpg"))

    # Filter out already optimized files (only process if both webp and jpg don't exist)
    image_files = [f for f in image_files
                   if f.suffix in ['.png', '.jpg']
                   and not (f.with_suffix('.webp').exists() and f.with_suffix('.jpg').exists())]

    if not image_files:
        print(f"ℹ️  No unprocessed cover images found")
        return True

    print(f"\n{'='*80}")
    print(f"Processing {len(image_files)} book cover(s)")
    print(f"Source: {covers_dir}")
    print(f"Backup: {backup_dir}")
    print(f"Max width: {max_width}px")
    print(f"Output: WebP + JPG")
    if dry_run:
        print("[DRY RUN MODE - No changes will be made]")
    print(f"{'='*80}\n")

    if dry_run:
        for img_file in sorted(image_files):
            backup_path = get_unique_backup_path(backup_dir, img_file.name)
            print(f"Would process: {img_file.name}")
            print(f"  Would backup to: {backup_path}")
            print(f"  Would create: {img_file.stem}.webp, {img_file.stem}.jpg")
        return True

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)

    all_success = True

    for img_file in sorted(image_files):
        # Get unique backup path (handles duplicates)
        backup_path = get_unique_backup_path(backup_dir, img_file.name)

        print(f"\nProcessing: {img_file.name}")

        # Backup original
        try:
            shutil.copy2(str(img_file), str(backup_path))
            print(f"  📦 Backed up to: {backup_path}")
        except Exception as e:
            print(f"  ❌ Error backing up file: {e}")
            all_success = False
            continue

        # Create optimized versions
        output_base = covers_dir / img_file.stem
        if optimize_image(backup_path, output_base, max_width, create_webp=True):
            # Remove original if optimization succeeded
            try:
                img_file.unlink()
                print(f"  🗑️  Removed original {img_file.name}")
            except Exception as e:
                print(f"  ⚠️  Could not remove original: {e}")
        else:
            all_success = False
            print(f"  ⚠️  Keeping original due to optimization failure")

    print(f"\n{'='*80}")
    if all_success:
        print("✅ All covers processed successfully!")
    else:
        print("⚠️  Some covers had errors")
    print(f"{'='*80}\n")

    return all_success


def main():
    parser = argparse.ArgumentParser(
        description='Optimize images with WebP + JPG fallback and backup originals'
    )
    parser.add_argument('--book-id', type=int, help='Book ID to process')
    parser.add_argument('--covers', action='store_true',
                       help='Process book covers instead of illustrations')
    parser.add_argument('--all', action='store_true', dest='process_all',
                       help='Process all covers (use with --covers)')
    parser.add_argument('--max-width', type=int,
                       help=f'Maximum width in pixels (default: {DEFAULT_MAX_WIDTH} for illustrations, {DEFAULT_COVER_WIDTH} for covers)')
    parser.add_argument('--chapters', type=str,
                       help='Comma-separated list of chapter numbers to process (e.g., "1,2,3" or "13-17")')
    parser.add_argument('--update-db', action='store_true',
                       help='Update database with illustration URLs after optimization')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without doing it')

    args = parser.parse_args()

    # Parse chapter numbers if provided
    chapter_numbers = None
    if args.chapters:
        chapter_numbers = []
        for part in args.chapters.split(','):
            part = part.strip()
            if '-' in part:
                # Handle ranges like "13-17"
                start, end = part.split('-')
                chapter_numbers.extend(range(int(start), int(end) + 1))
            else:
                # Handle individual numbers
                chapter_numbers.append(int(part))

    # Validate arguments
    if args.covers:
        # Processing covers
        if not args.process_all and args.book_id is None:
            parser.error("When using --covers, specify either --all or --book-id")
        max_width = args.max_width or DEFAULT_COVER_WIDTH
        book_id = None if args.process_all else args.book_id
        success = process_book_covers(book_id, max_width, args.dry_run)
    else:
        # Processing illustrations
        if args.book_id is None:
            parser.error("--book-id is required when processing illustrations")
        max_width = args.max_width or DEFAULT_MAX_WIDTH
        success = process_book_illustrations(args.book_id, max_width, args.dry_run, chapter_numbers, args.update_db)

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
