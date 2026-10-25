#!/usr/bin/env python3
"""Test chapter detection for a specific book"""
import sys
import os



from scripts.content.generate_summaries import SummaryGenerator

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_chapter_detection.py <book_file>")
        sys.exit(1)

    book_file = sys.argv[1]

    # Read the book
    with open(book_file, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"Book file: {book_file}")
    print(f"Total length: {len(text)} characters")
    print("=" * 80)

    # API key not needed for chapter detection, just pass empty string
    generator = SummaryGenerator("")

    # Extract content
    content = generator.extract_gutenberg_content(text)
    print(f"\nExtracted content: {len(content)} characters")
    print("=" * 80)

    # Detect chapters
    print("\nDetecting chapters...")
    chapters = generator.detect_chapters(content)

    print(f"\n{'='*80}")
    print(f"DETECTED {len(chapters)} CHAPTER(S)")
    print(f"{'='*80}\n")

    for i, (chapter_num, chapter_title, chapter_text) in enumerate(chapters):
        print(f"Chapter {chapter_num}: {chapter_title}")
        print(f"  Length: {len(chapter_text)} chars, ~{len(chapter_text.split())} words")
        print(f"  First 100 chars: {chapter_text[:100].strip()}...")
        print()

    # Calculate coverage
    total_chapter_chars = sum(len(text) for _, _, text in chapters)
    coverage = (total_chapter_chars / len(content)) * 100 if content else 0

    print(f"{'='*80}")
    print(f"Content Coverage:")
    print(f"  Original text: {len(content):,} chars")
    print(f"  Parsed chapters: {total_chapter_chars:,} chars")
    print(f"  Coverage: {coverage:.1f}%")
    if coverage > 95:
        print(f"  ✓ Good coverage - parsing looks correct")
    elif coverage > 80:
        print(f"  ⚠ Decent coverage - some content may be missing")
    else:
        print(f"  ✗ Low coverage - chapter detection may have issues")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
