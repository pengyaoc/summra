#!/usr/bin/env python3
"""
Remove "PART I", "PART II", "PART III", "PART IV" headers from book text files.
This converts 3-layer structures (Part → Book → Chapter) to 2-layer (Book → Chapter).

Usage:
    python remove_part_headers.py <input_file> [output_file]

If output_file is not specified, will overwrite the input file.
"""

import sys
import re
from pathlib import Path


def remove_part_headers(text: str) -> str:
    """
    Remove standalone "PART I", "PART II", "PART III", "PART IV" headers.

    Matches patterns like:
    - "PART I"
    - "PART II"
    - "PART III"
    - "PART IV"

    Also handles variations with different spacing and roman numerals.
    """
    # Pattern to match PART headers (case insensitive, with optional whitespace)
    # Matches "PART I", "PART II", "PART III", "PART IV" as standalone lines
    pattern = r'^\s*PART\s+[IVX]+\s*$'

    lines = text.split('\n')
    filtered_lines = []

    for line in lines:
        # Skip lines that match the PART header pattern
        if not re.match(pattern, line, re.IGNORECASE):
            filtered_lines.append(line)
        else:
            print(f"Removing: '{line.strip()}'")

    return '\n'.join(filtered_lines)


def main():
    if len(sys.argv) < 2:
        print("Error: No input file specified")
        print(__doc__)
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    # Determine output file
    if len(sys.argv) >= 3:
        output_file = Path(sys.argv[2])
    else:
        # Overwrite input file
        output_file = input_file

    print(f"Reading from: {input_file}")

    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    original_line_count = len(text.split('\n'))
    print(f"Original line count: {original_line_count}")

    # Remove PART headers
    print("\nRemoving PART headers...")
    modified_text = remove_part_headers(text)

    new_line_count = len(modified_text.split('\n'))
    removed_count = original_line_count - new_line_count

    print(f"\nNew line count: {new_line_count}")
    print(f"Lines removed: {removed_count}")

    # Write output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(modified_text)

    print(f"\n✓ Output written to: {output_file}")

    if output_file == input_file:
        print("  (Original file has been overwritten)")


if __name__ == '__main__':
    main()
