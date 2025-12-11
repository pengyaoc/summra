#!/usr/bin/env python3
"""
Process hero section images for the homepage.

This script:
1. Finds hero images in data/img/ (chapter_view, infographic, summary)
2. Processes them with:
   - Resize to max width 800px for optimal web display
   - JPG quality 85
   - WebP quality 80
3. Saves optimized versions to frontend/static/images/

Usage:
    python scripts/process_hero_images.py
"""

import sys
from pathlib import Path
import subprocess
from PIL import Image

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))


def process_hero_image(original_path: Path, output_dir: Path, max_width: int = 800):
    """
    Process a hero image with web-optimized settings.

    Args:
        original_path: Path to original image in data/img/
        output_dir: Output directory (frontend/static/images/)
        max_width: Maximum width in pixels
    """
    output_base = original_path.stem
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

        # Save JPG with quality compression
        img.save(jpg_path, 'JPEG', quality=85, optimize=True)
        jpg_size_mb = jpg_path.stat().st_size / (1024 * 1024)
        jpg_reduction = ((original_file_size_mb - jpg_size_mb) / original_file_size_mb * 100) if original_file_size_mb > 0 else 0
        print(f"✅ JPG: {jpg_path.name} ({jpg_size_mb:.2f} MB, {jpg_reduction:.1f}% reduction)")

        # Create WebP
        try:
            result = subprocess.run(
                ['cwebp', '-q', '80', str(jpg_path), '-o', str(webp_path)],
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
    # Directories
    originals_dir = project_root / "data" / "img"
    output_dir = project_root / "frontend" / "static" / "images"

    if not originals_dir.exists():
        print(f"❌ Originals directory not found: {originals_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Process specific hero images
    hero_images = [
        'chapter_view.png',
        'infographic.png',
        'summary.png'
    ]

    original_paths = [originals_dir / name for name in hero_images]
    found_images = [path for path in original_paths if path.exists()]

    if not found_images:
        print(f"❌ No hero images found in {originals_dir}")
        return 1

    print(f"\n{'='*80}")
    print(f"PROCESSING HERO IMAGES")
    print(f"{'='*80}")
    print(f"Found {len(found_images)} images to process")
    print(f"Max width: 800px")
    print(f"JPG quality: 85")
    print(f"WebP quality: 80")
    print(f"{'='*80}\n")

    # Process each image
    success_count = 0
    for img_path in found_images:
        if process_hero_image(img_path, output_dir, max_width=800):
            success_count += 1

    print(f"\n{'='*80}")
    print(f"✅ Successfully processed {success_count}/{len(found_images)} images")
    print(f"{'='*80}\n")

    return 0 if success_count == len(found_images) else 1


if __name__ == '__main__':
    sys.exit(main())
