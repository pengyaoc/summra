#!/usr/bin/env python3
"""Debug chapter detection with detailed output"""
import sys
import os
import re



text = """The Time Machine

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
"""

lines = text.split('\n')

# Test the pattern directly
pattern = r'^([IVXLCDM]+)\.$'

for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped and re.match(pattern, stripped):
        print(f"Line {i}: '{line}' | stripped: '{stripped}'")
        print(f"  Pattern match: {re.match(pattern, stripped).groups()}")
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            print(f"  Next line: '{next_line}'")
