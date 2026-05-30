#!/usr/bin/env python3
"""
Process icon.png for website favicon and logo usage.

This script:
1. Takes icon.png from data/img/
2. Creates multiple sizes:
   - 512x512 (original quality for logo)
   - 192x192 (PWA icon)
   - 180x180 (Apple touch icon)
   - 32x32 (standard favicon)
   - 16x16 (small favicon)
3. Outputs both PNG and WebP for each size to frontend/static/images/

Usage:
    python scripts/images/process_icon.py
"""

import sys
from pathlib import Path
import subprocess
from PIL import Image

# Add parent directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "backend"))


def process_icon_size(img: Image.Image, size: int, output_dir: Path, name_prefix: str = "icon"):
    """
    Process icon at a specific size.

    Args:
        img: PIL Image object
        size: Target size (width and height in pixels)
        output_dir: Output directory
        name_prefix: Prefix for output filename
    """
    # Resize maintaining aspect ratio (assuming square icon)
    if img.width != size or img.height != size:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
    else:
        resized = img

    # Determine suffix based on size
    if size == 512:
        suffix = ""  # Main logo size, no suffix
    else:
        suffix = f"-{size}"

    png_path = output_dir / f"{name_prefix}{suffix}.png"
    webp_path = output_dir / f"{name_prefix}{suffix}.webp"

    # Save PNG (lossless for icons)
    resized.save(png_path, 'PNG', optimize=True)
    png_size_kb = png_path.stat().st_size / 1024
    print(f"  ✅ PNG ({size}x{size}): {png_path.name} ({png_size_kb:.1f} KB)")

    # Save WebP
    try:
        # Use lossless WebP for icons to maintain quality
        result = subprocess.run(
            ['cwebp', '-lossless', str(png_path), '-o', str(webp_path)],
            capture_output=True,
            text=True,
            check=True
        )
        webp_size_kb = webp_path.stat().st_size / 1024
        print(f"  ✅ WebP ({size}x{size}): {webp_path.name} ({webp_size_kb:.1f} KB)")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  ⚠️  WebP creation failed: {e}")


def main():
    # Directories
    original_path = project_root / "data" / "img" / "icon.png"
    output_dir = project_root / "frontend" / "static" / "images"

    if not original_path.exists():
        print(f"❌ Icon not found: {original_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"PROCESSING WEBSITE ICON")
    print(f"{'='*80}")

    try:
        # Load original
        img = Image.open(original_path)
        original_size = img.size
        original_file_size_mb = original_path.stat().st_size / (1024 * 1024)
        print(f"Original: {original_size} ({original_file_size_mb:.2f} MB)")

        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Generate multiple sizes
        sizes = [512, 192, 180, 32, 16]

        print(f"\nGenerating {len(sizes)} sizes:")
        for size in sizes:
            print(f"\n{size}x{size}:")
            process_icon_size(img, size, output_dir, "icon")

        print(f"\n{'='*80}")
        print(f"✅ Successfully processed icon in {len(sizes)} sizes")
        print(f"{'='*80}\n")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
