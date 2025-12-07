#!/usr/bin/env python3
"""
Script to process and add character guide and timeline images to books.

This script:
1. Accepts absolute paths to image files
2. Moves them to data/guides_originals/
3. Processes them (converts to JPG if needed, creates WebP version)
4. Saves to frontend/static/guides/
5. Updates the database with the URLs

Usage:
    python scripts/add_guide_images.py <book_id> --character /path/to/character_image.jpg
    python scripts/add_guide_images.py <book_id> --timeline /path/to/timeline_image.png
    python scripts/add_guide_images.py <book_id> --character /path/to/char.jpg --timeline /path/to/time.png

Output:
    - Originals stored in: data/guides_originals/{book_id}_characters.ext, {book_id}_timeline.ext
    - Web-optimized in: frontend/static/guides/{book_id}_characters.jpg/webp, {book_id}_timeline.jpg/webp
"""

import sys
import argparse
from pathlib import Path
import subprocess
import shutil

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from models import Database
import config


def process_guide_image(original_path: Path, output_dir: Path, output_name: str, max_width: int = 1200) -> tuple:
    """
    Process a guide image: resize, convert to JPG if needed, create WebP version.

    Args:
        original_path: Path to original image file
        output_dir: Directory to save processed images
        output_name: Base name for output files (without extension)
        max_width: Maximum width in pixels (default: 1200)

    Returns:
        Tuple of (jpg_path, webp_path) or (None, None) on failure
    """
    from PIL import Image

    jpg_path = output_dir / f"{output_name}.jpg"
    webp_path = output_dir / f"{output_name}.webp"

    try:
        # Load and resize image
        img = Image.open(original_path)
        original_size = img.size

        # Resize if width exceeds max_width
        if img.width > max_width:
            aspect_ratio = img.height / img.width
            new_width = max_width
            new_height = int(new_width * aspect_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"  Resized: {original_size} -> {img.size}")
        else:
            print(f"  Size: {img.size} (no resize needed)")

        # Convert to RGB if necessary (e.g., for PNG with transparency)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Save as JPG with aggressive compression
        img.save(jpg_path, 'JPEG', quality=75, optimize=True)
        jpg_size_mb = jpg_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Saved JPG: {jpg_path.name} ({jpg_size_mb:.2f} MB)")

    except Exception as e:
        print(f"  ✗ Error processing image: {e}")
        return None, None

    # Create optimized WebP version using cwebp with aggressive compression
    print(f"  Creating optimized WebP version...")
    try:
        result = subprocess.run(
            ['cwebp', '-q', '70', str(jpg_path), '-o', str(webp_path)],
            capture_output=True,
            text=True,
            check=True
        )
        webp_size_mb = webp_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Saved WebP: {webp_path.name} ({webp_size_mb:.2f} MB)")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Error creating WebP: {e}")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        return jpg_path, None
    except FileNotFoundError:
        print(f"  ✗ cwebp not found. Install with: brew install webp")
        print(f"  ✓ JPG saved, but WebP conversion skipped")
        return jpg_path, None

    return jpg_path, webp_path


def move_to_originals(source_path: Path, book_id: int, image_type: str, originals_dir: Path) -> Path:
    """
    Move image file to guides_originals directory with proper naming.

    Args:
        source_path: Absolute path to source image file
        book_id: Book ID
        image_type: 'characters' or 'timeline'
        originals_dir: Directory for original images

    Returns:
        Path to moved file in originals_dir
    """
    # Get the file extension from source
    file_ext = source_path.suffix  # e.g., .jpg, .png, .webp

    # Create destination path with standard naming
    dest_path = originals_dir / f"{book_id}_{image_type}{file_ext}"

    # Move the file
    print(f"  Moving {source_path.name} -> {dest_path.name}")
    shutil.move(str(source_path), str(dest_path))

    return dest_path


def add_guide_images(book_id: int, character_path: str = None, timeline_path: str = None, themes_path: str = None, dry_run: bool = False):
    """Process and add character guide, timeline, and/or themes images to a book."""
    # Setup paths
    base_dir = Path(__file__).parent.parent
    originals_dir = base_dir / 'data' / 'guides_originals'
    output_dir = base_dir / 'frontend' / 'static' / 'guides'

    # Ensure directories exist
    originals_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Database setup
    db = Database()
    book = db.get_book(book_id)
    if not book:
        print(f"✗ Error: Book with ID {book_id} not found")
        return False

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing guide images for: {book['title']} by {book['author']}")
    print(f"Book ID: {book_id}\n")

    character_url = None
    timeline_url = None
    themes_url = None

    # Process character guide
    if character_path:
        print("Processing character guide...")
        source_file = Path(character_path).resolve()

        if not source_file.exists():
            print(f"  ✗ File not found: {source_file}")
            return False

        if not source_file.is_file():
            print(f"  ✗ Not a file: {source_file}")
            return False

        print(f"  Source: {source_file}")

        if not dry_run:
            # Move to originals directory
            original_path = move_to_originals(source_file, book_id, 'characters', originals_dir)
            print(f"  ✓ Moved to: {original_path.relative_to(base_dir)}")

            # Process the image
            jpg_path, webp_path = process_guide_image(original_path, output_dir, f"{book_id}_characters")

            if jpg_path:
                # Use WebP if available, otherwise JPG
                if webp_path:
                    character_url = f"/static/guides/{book_id}_characters.webp"
                else:
                    character_url = f"/static/guides/{book_id}_characters.jpg"
                print(f"  ✓ Character guide URL: {character_url}")
        else:
            print(f"  [DRY RUN] Would move to: {originals_dir / f'{book_id}_characters{source_file.suffix}'}")
            print(f"  [DRY RUN] Would process to: {book_id}_characters.jpg/webp")
            character_url = f"/static/guides/{book_id}_characters.webp"

    # Process timeline
    if timeline_path:
        print("\nProcessing timeline...")
        source_file = Path(timeline_path).resolve()

        if not source_file.exists():
            print(f"  ✗ File not found: {source_file}")
            return False

        if not source_file.is_file():
            print(f"  ✗ Not a file: {source_file}")
            return False

        print(f"  Source: {source_file}")

        if not dry_run:
            # Move to originals directory
            original_path = move_to_originals(source_file, book_id, 'timeline', originals_dir)
            print(f"  ✓ Moved to: {original_path.relative_to(base_dir)}")

            # Process the image
            jpg_path, webp_path = process_guide_image(original_path, output_dir, f"{book_id}_timeline")

            if jpg_path:
                # Use WebP if available, otherwise JPG
                if webp_path:
                    timeline_url = f"/static/guides/{book_id}_timeline.webp"
                else:
                    timeline_url = f"/static/guides/{book_id}_timeline.jpg"
                print(f"  ✓ Timeline URL: {timeline_url}")
        else:
            print(f"  [DRY RUN] Would move to: {originals_dir / f'{book_id}_timeline{source_file.suffix}'}")
            print(f"  [DRY RUN] Would process to: {book_id}_timeline.jpg/webp")
            timeline_url = f"/static/guides/{book_id}_timeline.webp"

    # Process themes
    if themes_path:
        print("\nProcessing themes...")
        source_file = Path(themes_path).resolve()

        if not source_file.exists():
            print(f"  ✗ File not found: {source_file}")
            return False

        if not source_file.is_file():
            print(f"  ✗ Not a file: {source_file}")
            return False

        print(f"  Source: {source_file}")

        if not dry_run:
            # Move to originals directory
            original_path = move_to_originals(source_file, book_id, 'themes', originals_dir)
            print(f"  ✓ Moved to: {original_path.relative_to(base_dir)}")

            # Process the image
            jpg_path, webp_path = process_guide_image(original_path, output_dir, f"{book_id}_themes")

            if jpg_path:
                # Use WebP if available, otherwise JPG
                if webp_path:
                    themes_url = f"/static/guides/{book_id}_themes.webp"
                else:
                    themes_url = f"/static/guides/{book_id}_themes.jpg"
                print(f"  ✓ Themes URL: {themes_url}")
        else:
            print(f"  [DRY RUN] Would move to: {originals_dir / f'{book_id}_themes{source_file.suffix}'}")
            print(f"  [DRY RUN] Would process to: {book_id}_themes.jpg/webp")
            themes_url = f"/static/guides/{book_id}_themes.webp"

    # Update database
    if character_url or timeline_url or themes_url:
        print("\nUpdating database...")

        if not dry_run:
            conn = db.get_connection()
            cursor = conn.cursor()

            # Build dynamic UPDATE query based on which URLs are provided
            updates = []
            params = []

            if character_url:
                updates.append("character_guide_url = ?")
                params.append(character_url)
            if timeline_url:
                updates.append("timeline_url = ?")
                params.append(timeline_url)
            if themes_url:
                updates.append("themes_url = ?")
                params.append(themes_url)

            params.append(book_id)

            query = f"UPDATE books SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)

            # Print what was updated
            updated_fields = []
            if character_url:
                updated_fields.append("character guide")
            if timeline_url:
                updated_fields.append("timeline")
            if themes_url:
                updated_fields.append("themes")

            print(f"  ✓ Updated {', '.join(updated_fields)} URL(s)")

            conn.commit()
            conn.close()
        else:
            print(f"  [DRY RUN] Would update database:")
            if character_url:
                print(f"    character_guide_url = {character_url}")
            if timeline_url:
                print(f"    timeline_url = {timeline_url}")
            if themes_url:
                print(f"    themes_url = {themes_url}")

    print("\n✓ Guide images processed successfully!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Process and add character guide and timeline images to a book',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Add character guide from absolute path:
    python scripts/add_guide_images.py 1 --character /Users/you/Downloads/pride_characters.jpg

  Add timeline from absolute path:
    python scripts/add_guide_images.py 1 --timeline ~/Documents/pride_timeline.png

  Add themes image from absolute path:
    python scripts/add_guide_images.py 1 --themes /Users/you/Downloads/pride_themes.jpg

  Add all three at once:
    python scripts/add_guide_images.py 1 \\
      --character /path/to/characters.jpg \\
      --timeline /path/to/timeline.png \\
      --themes /path/to/themes.jpg

  Dry run to see what would happen:
    python scripts/add_guide_images.py 1 --character /path/to/char.jpg --dry-run

The script will:
  1. Validate the source files exist
  2. Move them to data/guides_originals/ with naming: {book_id}_characters.ext, {book_id}_timeline.ext, {book_id}_themes.ext
  3. Convert images to JPG if needed
  4. Create optimized WebP versions
  5. Save to frontend/static/guides/
  6. Update database with URLs
        '''
    )

    parser.add_argument('book_id', type=int, help='Book ID to update')
    parser.add_argument('--character', type=str, metavar='PATH', help='Absolute path to character guide image')
    parser.add_argument('--timeline', type=str, metavar='PATH', help='Absolute path to timeline image')
    parser.add_argument('--themes', type=str, metavar='PATH', help='Absolute path to themes image')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    if not args.character and not args.timeline and not args.themes:
        parser.error('At least one of --character, --timeline, or --themes must be specified')

    success = add_guide_images(args.book_id, args.character, args.timeline, args.themes, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
