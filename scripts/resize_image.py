#!/usr/bin/env python3
"""
Script to resize PNG images to approximately 1MB file size.

Usage:
    Single file mode:
        python scripts/resize_image.py input.png output.png
        python scripts/resize_image.py input.png  # outputs to input_resized.png

    Bulk mode:
        python scripts/resize_image.py --bulk file1.png file2.png file3.png
        python scripts/resize_image.py --bulk *.png
        python scripts/resize_image.py --bulk --target 0.5 *.png  # Target 0.5MB

    Hero image mode (reduce height by 1/3, convert to JPG/WebP):
        python scripts/resize_image.py --hero-img input.png [output_dir] [max_width]
        python scripts/resize_image.py --hero-img data/img/library_view.png frontend/static/images 1920
"""

import sys
import os
import glob
import subprocess
from pathlib import Path
from PIL import Image


def get_file_size_mb(filepath):
    """Get file size in MB."""
    return os.path.getsize(filepath) / (1024 * 1024)


def resize_image_to_target_size(input_path, output_path, target_mb=1.0, tolerance_mb=0.1, verbose=True):
    """
    Resize a PNG image to approximately target_mb file size.

    Args:
        input_path: Path to input PNG file
        output_path: Path to output PNG file
        target_mb: Target file size in MB (default: 1.0)
        tolerance_mb: Acceptable tolerance in MB (default: 0.1)
        verbose: Print detailed progress (default: True)

    Returns:
        dict: Result info with keys 'success', 'original_size_mb', 'final_size_mb', 'dimensions'
    """
    try:
        # Open the image
        img = Image.open(input_path)
        original_width, original_height = img.size
        original_size_mb = get_file_size_mb(input_path)

        if verbose:
            print(f"Original image size: {original_width}x{original_height}")
            print(f"Original file size: {original_size_mb:.2f} MB")

        # Check if input is already small enough
        if original_size_mb <= target_mb:
            if verbose:
                print(f"Input file is already {original_size_mb:.2f} MB (target: {target_mb} MB)")
                print("Copying file without resizing...")
            img.save(output_path, 'PNG', optimize=True)
            final_size_mb = get_file_size_mb(output_path)
            if verbose:
                print(f"Saved to: {output_path}")
            return {
                'success': True,
                'original_size_mb': original_size_mb,
                'final_size_mb': final_size_mb,
                'dimensions': f"{original_width}x{original_height}",
                'skipped': True
            }

        # Start with a scale factor
        scale = 1.0
        min_scale = 0.1
        max_scale = 1.0

        # Binary search for the right scale
        for iteration in range(15):  # Max 15 iterations
            # Calculate new dimensions
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

            # Resize image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save temporarily to check size
            resized_img.save(output_path, 'PNG', optimize=True)
            current_size_mb = get_file_size_mb(output_path)

            if verbose:
                print(f"Iteration {iteration + 1}: Scale={scale:.3f}, Size={new_width}x{new_height}, File size={current_size_mb:.2f} MB")

            # Check if we're within tolerance
            if abs(current_size_mb - target_mb) <= tolerance_mb:
                if verbose:
                    print(f"\nSuccess! Final size: {current_size_mb:.2f} MB")
                    print(f"Final dimensions: {new_width}x{new_height}")
                    print(f"Saved to: {output_path}")
                return {
                    'success': True,
                    'original_size_mb': original_size_mb,
                    'final_size_mb': current_size_mb,
                    'dimensions': f"{new_width}x{new_height}",
                    'skipped': False
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
        if verbose:
            print(f"\nCompleted! Final size: {final_size_mb:.2f} MB")
            print(f"Final dimensions: {resized_img.size[0]}x{resized_img.size[1]}")
            print(f"Saved to: {output_path}")

        return {
            'success': True,
            'original_size_mb': original_size_mb,
            'final_size_mb': final_size_mb,
            'dimensions': f"{resized_img.size[0]}x{resized_img.size[1]}",
            'skipped': False
        }

    except Exception as e:
        if verbose:
            print(f"Error processing {input_path}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'original_size_mb': 0,
            'final_size_mb': 0,
            'dimensions': 'N/A'
        }


def process_bulk(file_list, target_mb=1.0, output_dir=None):
    """
    Process multiple files in bulk mode.

    Args:
        file_list: List of input file paths
        target_mb: Target file size in MB
        output_dir: Optional output directory (default: same as input with _resized suffix)
    """
    results = []
    total = len(file_list)

    print(f"Processing {total} file(s)...\n")

    for idx, input_path in enumerate(file_list, 1):
        print(f"[{idx}/{total}] Processing: {input_path}")
        print("-" * 60)

        if not os.path.exists(input_path):
            print(f"Error: File not found, skipping.\n")
            results.append({'file': input_path, 'success': False, 'error': 'File not found'})
            continue

        # Determine output path
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.basename(input_path)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{base_name}_resized.png")
        else:
            base_name = os.path.splitext(input_path)[0]
            output_path = f"{base_name}_resized.png"

        # Process the image
        result = resize_image_to_target_size(input_path, output_path, target_mb, verbose=True)
        result['file'] = input_path
        result['output'] = output_path
        results.append(result)

        print()

    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    skipped = [r for r in successful if r.get('skipped', False)]

    print(f"Total files: {total}")
    print(f"Successful: {len(successful)}")
    print(f"  - Resized: {len(successful) - len(skipped)}")
    print(f"  - Skipped (already small): {len(skipped)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed files:")
        for r in failed:
            print(f"  - {r['file']}: {r.get('error', 'Unknown error')}")

    print()
    return results


def process_hero_image(input_path, output_dir=None, max_width=1920):
    """
    Process hero background image by reducing height by 1/3 and converting to JPG/WebP.

    Args:
        input_path: Path to input image
        output_dir: Output directory (default: same as input directory)
        max_width: Maximum width in pixels (default: 1920)

    Returns:
        dict: Result info with success status
    """
    try:
        input_path = Path(input_path)

        # Determine output directory and base name
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent

        # Use base name from input file (without extension)
        output_base = input_path.stem

        print(f"\n{'='*80}")
        print(f"PROCESSING HERO IMAGE")
        print(f"{'='*80}")
        print(f"Input: {input_path}")
        print(f"Output directory: {output_dir}")
        print(f"{'='*80}\n")

        # Load image
        img = Image.open(input_path)
        original_width, original_height = img.size
        original_file_size_mb = input_path.stat().st_size / (1024 * 1024)

        print(f"Original dimensions: {original_width}x{original_height}")
        print(f"Original file size: {original_file_size_mb:.2f} MB\n")

        # Calculate new dimensions - maintain original aspect ratio
        original_aspect_ratio = original_width / original_height

        # Respect max_width while maintaining aspect ratio
        if original_width > max_width:
            new_width = max_width
            new_height = int(new_width / original_aspect_ratio)
        else:
            new_width = original_width
            new_height = original_height

        print(f"Step 1: Calculating dimensions with original aspect ratio")
        print(f"  New dimensions: {new_width}x{new_height}")
        print(f"  Original aspect ratio: {original_aspect_ratio:.2f}")
        print(f"  New aspect ratio: {new_width/new_height:.2f}\n")

        # Resize image
        print(f"Step 2: Resizing image...")
        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"  ✓ Resized to {new_width}x{new_height}\n")

        # Convert to RGB if necessary (for JPG)
        if resized_img.mode in ('RGBA', 'LA', 'P'):
            print(f"Step 3: Converting {resized_img.mode} to RGB...")
            background = Image.new('RGB', resized_img.size, (255, 255, 255))
            if resized_img.mode == 'P':
                resized_img = resized_img.convert('RGBA')
            background.paste(
                resized_img,
                mask=resized_img.split()[-1] if resized_img.mode in ('RGBA', 'LA') else None
            )
            resized_img = background
            print(f"  ✓ Converted to RGB\n")
        else:
            print(f"Step 3: Image already in RGB mode\n")

        # Save JPG
        jpg_path = output_dir / f"{output_base}.jpg"
        print(f"Step 4: Saving JPG...")
        resized_img.save(jpg_path, 'JPEG', quality=80, optimize=True)
        jpg_size_mb = jpg_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Saved: {jpg_path}")
        print(f"  Size: {jpg_size_mb:.2f} MB\n")

        # Create WebP
        webp_path = output_dir / f"{output_base}.webp"
        print(f"Step 5: Creating WebP...")
        try:
            result = subprocess.run(
                ['cwebp', '-q', '70', str(jpg_path), '-o', str(webp_path)],
                capture_output=True,
                text=True,
                check=True
            )
            webp_size_mb = webp_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Saved: {webp_path}")
            print(f"  Size: {webp_size_mb:.2f} MB\n")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  ⚠️  WebP creation failed: {e}")
            print(f"  JPG still saved successfully\n")
            webp_path = None

        # Summary
        print(f"{'='*80}")
        print(f"✅ PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Original: {original_width}x{original_height} ({original_file_size_mb:.2f} MB)")
        print(f"Processed: {new_width}x{new_height}")
        print(f"Output files:")
        print(f"  - {jpg_path} ({jpg_size_mb:.2f} MB)")
        if webp_path and webp_path.exists():
            print(f"  - {webp_path} ({webp_size_mb:.2f} MB)")
        print(f"{'='*80}\n")

        return {
            'success': True,
            'original_dimensions': f"{original_width}x{original_height}",
            'processed_dimensions': f"{new_width}x{new_height}",
            'jpg_path': str(jpg_path),
            'webp_path': str(webp_path) if webp_path and webp_path.exists() else None
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file mode:")
        print("    python scripts/resize_image.py input.png [output.png] [target_mb]")
        print("  Bulk mode:")
        print("    python scripts/resize_image.py --bulk [--target MB] [--output-dir DIR] file1.png file2.png ...")
        print("  Hero image mode:")
        print("    python scripts/resize_image.py --hero-img input.png [output_dir] [max_width]")
        print("\nExamples:")
        print("  python scripts/resize_image.py input.png output.png")
        print("  python scripts/resize_image.py input.png output.png 0.5  # Target 0.5MB")
        print("  python scripts/resize_image.py input.png  # Output to input_resized.png")
        print("  python scripts/resize_image.py --bulk *.png")
        print("  python scripts/resize_image.py --bulk --target 0.5 file1.png file2.png")
        print("  python scripts/resize_image.py --bulk --output-dir resized/ *.png")
        print("  python scripts/resize_image.py --hero-img data/img/library_view.png frontend/static/images")
        sys.exit(1)

    # Check for hero image mode
    if sys.argv[1] == '--hero-img':
        if len(sys.argv) < 3:
            print("Error: --hero-img requires an input file")
            print("Usage: python scripts/resize_image.py --hero-img input.png [output_dir] [max_width]")
            sys.exit(1)

        input_path = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
        max_width = int(sys.argv[4]) if len(sys.argv) > 4 else 1920

        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found")
            sys.exit(1)

        result = process_hero_image(input_path, output_dir, max_width)
        sys.exit(0 if result['success'] else 1)

    # Check for bulk mode
    if sys.argv[1] == '--bulk':
        # Parse bulk mode arguments
        args = sys.argv[2:]
        target_mb = 1.0
        output_dir = None
        file_list = []

        i = 0
        while i < len(args):
            if args[i] == '--target' and i + 1 < len(args):
                try:
                    target_mb = float(args[i + 1])
                    i += 2
                except ValueError:
                    print(f"Error: Invalid target size '{args[i + 1]}'")
                    sys.exit(1)
            elif args[i] == '--output-dir' and i + 1 < len(args):
                output_dir = args[i + 1]
                i += 2
            else:
                # Expand glob patterns
                expanded = glob.glob(args[i])
                if expanded:
                    file_list.extend(expanded)
                else:
                    file_list.append(args[i])
                i += 1

        if not file_list:
            print("Error: No input files specified for bulk mode")
            sys.exit(1)

        # Filter for PNG files only
        png_files = [f for f in file_list if f.lower().endswith('.png')]
        if not png_files:
            print("Error: No PNG files found in the input list")
            sys.exit(1)

        if len(png_files) < len(file_list):
            print(f"Warning: Filtered {len(file_list) - len(png_files)} non-PNG file(s)\n")

        # Process in bulk
        process_bulk(png_files, target_mb, output_dir)
        return

    # Single file mode
    input_path = sys.argv[1]

    # Determine output path
    if len(sys.argv) >= 3 and not sys.argv[2].replace('.', '').replace('-', '').isdigit():
        output_path = sys.argv[2]
        target_mb_idx = 3
    else:
        # Generate output filename
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_resized.png"
        target_mb_idx = 2

    # Get target size if provided
    target_mb = 1.0
    if len(sys.argv) > target_mb_idx:
        try:
            target_mb = float(sys.argv[target_mb_idx])
        except ValueError:
            print(f"Invalid target size: {sys.argv[target_mb_idx]}")
            sys.exit(1)

    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found")
        sys.exit(1)

    # Resize the image
    resize_image_to_target_size(input_path, output_path, target_mb)


if __name__ == "__main__":
    main()
