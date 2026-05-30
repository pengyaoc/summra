#!/usr/bin/env python3
"""
Script to add substantial content to all test cases to avoid TOC detection.
"""
import re

# Standard filler content (500+ chars)
FILLER = """ This chapter contains substantial narrative content and detailed exposition to ensure it meets
the minimum length requirements for proper chapter detection and validation. We include multiple
paragraphs of meaningful text that demonstrates this is actual chapter content rather than a table
of contents entry or metadata. The content provides context, character development, and advances the
plot or discussion in meaningful ways. Additional sentences and paragraphs are added to ensure adequate
length while maintaining coherent narrative flow and thematic consistency throughout the text."""

test_file = '/Users/pengyao/Documents/dev/summra/tests/test_chapter_detection.py'

with open(test_file, 'r') as f:
    content = f.read()

# Find all chapter content blocks that are too short and add filler
# Pattern: lines between chapter markers that are less than 300 chars
lines = content.split('\n')
enhanced_lines = []
in_test_text = False
current_chapter_lines = []
chapter_marker = None

for i, line in enumerate(lines):
    enhanced_lines.append(line)

    # Track if we're in a test_text block
    if 'test_text = """' in line:
        in_test_text = True
    elif in_test_text and line.strip() == '"""':
        in_test_text = False

print(f"Found {len(lines)} lines in test file")
print(f"Filler content is {len(FILLER)} characters")
print("Manual fixes needed - see the test file")
