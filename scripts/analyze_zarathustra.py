#!/usr/bin/env python3
"""Analyze chapter structure of Thus Spake Zarathustra"""

import re
import json

def analyze_chapters(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by common chapter patterns
    # Look for patterns like "CHAPTER I.", "I.", numbered sections, etc.
    lines = content.split('\n')

    chapters = []
    current_chapter = None
    current_text = []
    chapter_num = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Look for chapter markers - various patterns
        # Pattern 1: Roman numerals or numbers followed by period and title
        # Pattern 2: All caps titles
        # Pattern 3: Lines that look like section headers

        is_chapter = False
        chapter_title = None

        # Check if line looks like a chapter heading
        if line_stripped and len(line_stripped) < 100:
            # All caps lines (potential chapter titles)
            if line_stripped.isupper() and len(line_stripped) > 3:
                is_chapter = True
                chapter_title = line_stripped
            # Roman numerals or numbers
            elif re.match(r'^[IVXLCDM]+\.?\s+', line_stripped) or re.match(r'^\d+\.?\s+', line_stripped):
                is_chapter = True
                chapter_title = line_stripped
            # Lines starting with "CHAPTER"
            elif line_stripped.startswith('CHAPTER'):
                is_chapter = True
                chapter_title = line_stripped

        if is_chapter and current_chapter is not None:
            # Save previous chapter
            text = ' '.join(current_text)
            word_count = len(text.split())
            if word_count > 50:  # Only count substantial chapters
                chapters.append({
                    'number': chapter_num,
                    'title': current_chapter,
                    'word_count': word_count
                })
                chapter_num += 1
            current_text = []

        if is_chapter:
            current_chapter = chapter_title
        elif current_chapter is not None:
            current_text.append(line_stripped)

    # Save last chapter
    if current_chapter is not None and current_text:
        text = ' '.join(current_text)
        word_count = len(text.split())
        if word_count > 50:
            chapters.append({
                'number': chapter_num,
                'title': current_chapter,
                'word_count': word_count
            })

    return chapters

if __name__ == '__main__':
    filepath = '/Users/pengyao/Documents/dev/summra/data/books/Thus_Spake_Zarathustra.txt'
    chapters = analyze_chapters(filepath)

    print(f"Total chapters found: {len(chapters)}\n")
    print("=" * 80)

    for ch in chapters:
        print(f"Chapter {ch['number']:3d}: {ch['title'][:60]:<60} ({ch['word_count']:,} words)")

    print("\n" + "=" * 80)
    print(f"\nTotal chapters: {len(chapters)}")
    print(f"Total words: {sum(ch['word_count'] for ch in chapters):,}")

    # Save to JSON
    output_file = '/tmp/zarathustra_chapters.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2)
    print(f"\nDetailed data saved to: {output_file}")
