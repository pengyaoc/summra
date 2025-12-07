#!/usr/bin/env python3
"""
Recompress existing guide images with more aggressive compression settings.

This script:
1. Finds all guide images in data/guides_originals/
2. Reprocesses them with:
   - Resize to max width 1200px
   - JPG quality 75 (down from 95)
   - WebP quality 70 (down from 85)
3. Saves optimized versions to frontend/static/guides/

Usage:
    python scripts/recompress_guide_images.py
    python scripts/recompress_guide_images.py --dry-run
"""

import sys
import argparse
from pathlib import Path
import subprocess
from PIL import Image

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

import config


def recompress_guide_image(original_path: Path, output_dir: Path, max_width: int = 1200):
    """
    Recompress a guide image with aggressive settings.

    Args:
        original_path: Path to original image in data/guides_originals/
        output_dir: Output directory (frontend/static/guides/)
        max_width: Maximum width in pixels
    """
    # Extract book_id and type from filename (e.g., "35_characters.jpg" -> "35", "characters")
    name_parts = original_path.stem.split('_', 1)
    if len(name_parts) != 2:
        print(f"⚠️  Skipping {original_path.name}: unexpected filename format")
        return False

    book_id, image_type = name_parts
    output_base = f"{book_id}_{image_type}"

    jpg_path = output_dir / f"{output_base}.jpg"
    webp_path = output_dir / f"{output_base}.webp"

    print(f"\n{'='*80}")
    print(f"Processing: {original_path.name}")
    print(f"{'='*80}")

    try:
        # Load image
        img = Image.open(original_path)
        original_size = img.size
        original_file_size_mb = original_path.stat().st_size / (1024 * 1024)
        print(f"Original: {original_size} ({original_file_size_mb:.2f} MB)")

        # Resize if needed
        if img.width > max_width:
            aspect_ratio = img.height / img.width
            new_width = max_width
            new_height = int(new_width * aspect_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"Resized to: {img.size}")

        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Save JPG with aggressive compression
        img.save(jpg_path, 'JPEG', quality=75, optimize=True)
        jpg_size_mb = jpg_path.stat().st_size / (1024 * 1024)
        jpg_reduction = ((original_file_size_mb - jpg_size_mb) / original_file_size_mb * 100) if original_file_size_mb > 0 else 0
        print(f"✅ JPG: {jpg_path.name} ({jpg_size_mb:.2f} MB, {jpg_reduction:.1f}% reduction)")

        # Create WebP with aggressive compression
        try:
            result = subprocess.run(
                ['cwebp', '-q', '70', str(jpg_path), '-o', str(webp_path)],
                capture_output=True,
                text=True,
                check=True
            )
            webp_size_mb = webp_path.stat().st_size / (1024 * 1024)
            webp_reduction = ((original_file_size_mb - webp_size_mb) / original_file_size_mb * 100) if original_file_size_mb > 0 else 0
            print(f"✅ WebP: {webp_path.name} ({webp_size_mb:.2f} MB, {webp_reduction:.1f}% reduction)")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠️  WebP creation failed: {e}")
            print(f"   JPG still saved successfully")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Recompress guide images with aggressive settings')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--max-width', type=int, default=1200, help='Maximum width in pixels (default: 1200)')
    args = parser.parse_args()

    # Directories
    originals_dir = project_root / "data" / "guides_originals"
    output_dir = project_root / "frontend" / "static" / "guides"

    if not originals_dir.exists():
        print(f"❌ Originals directory not found: {originals_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all original guide images
    original_images = list(originals_dir.glob("*_characters.*")) + \
                     list(originals_dir.glob("*_timeline.*")) + \
                     list(originals_dir.glob("*_themes.*"))

    if not original_images:
        print(f"❌ No guide images found in {originals_dir}")
        return 1

    print(f"\n{'='*80}")
    print(f"RECOMPRESSING GUIDE IMAGES")
    print(f"{'='*80}")
    print(f"Found {len(original_images)} images to recompress")
    print(f"Max width: {args.max_width}px")
    print(f"JPG quality: 75")
    print(f"WebP quality: 70")
    print(f"{'='*80}\n")

    if args.dry_run:
        print("[DRY RUN MODE - No files will be modified]\n")
        for img_path in sorted(original_images):
            print(f"Would recompress: {img_path.name}")
        return 0

    # Process each image
    success_count = 0
    for img_path in sorted(original_images):
        if recompress_guide_image(img_path, output_dir, max_width=args.max_width):
            success_count += 1

    print(f"\n{'='*80}")
    print(f"✅ Successfully recompressed {success_count}/{len(original_images)} images")
    print(f"{'='*80}\n")

    return 0 if success_count == len(original_images) else 1


if __name__ == '__main__':
    sys.exit(main())
