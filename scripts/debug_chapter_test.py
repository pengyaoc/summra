#!/usr/bin/env python3
"""Debug chapter detection for test case"""
import sys
import os

# Add backend and scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.dirname(__file__))

from generate_summaries import SummaryGenerator

text = """*** START OF THE PROJECT GUTENBERG EBOOK 35 ***

The Time Machine

CONTENTS

 I Introduction
 II The Machine
 III The Time Traveller Returns


 I.
 Introduction


The Time Traveller was expounding a recondite matter to us.
This is the first chapter content.

 II.
 The Machine


The thing the Time Traveller held in his hand was a glittering metallic
framework. This is the second chapter content.

 III.
 The Time Traveller Returns


I think that at that time none of us quite believed in the Time Machine.
This is the third chapter content.

*** END OF THE PROJECT GUTENBERG EBOOK 35 ***
"""

generator = SummaryGenerator("")
content = generator.extract_gutenberg_content(text)

print("Content:")
print(content)
print("\n" + "="*80 + "\n")

# Extract TOC
toc = generator.extract_toc(content)
print(f"TOC: {toc}")
print("\n" + "="*80 + "\n")

# Detect chapters
chapters = generator.detect_chapters(content)

print(f"Detected {len(chapters)} chapters:\n")
for num, title, text in chapters:
    print(f"Chapter {num}: {title}")
    print(f"  Text length: {len(text)} chars")
    print(f"  First 50 chars: {text[:50]}")
    print()
