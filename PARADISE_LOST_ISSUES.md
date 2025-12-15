# Paradise Lost Processing Issues

## Book Information
- **File**: `data/books/pg26.txt`
- **Title**: Paradise Lost
- **Author**: John Milton
- **Structure**: 12 Books (BOOK I through BOOK XII)
- **Size**: ~80,272 words, 459,436 characters

## Issues Found

### Issue 1: Coverage Bug (741.8%) - FIXED ✓
**Problem**: Chapter extraction was creating cumulative duplicates
- Original coverage: 741.8% (597,505 words parsed from 80,272 original)
- Each chapter included all content from start of book to end of that chapter
- Chapter 1 had full book, Chapter 2 had full book, etc.

**Root Cause**: Section boundary detection failure
- Code looked for patterns like `BOOK II: Title on same line`
- Paradise Lost format is:
  ```
  BOOK II

  High on a throne of royal state...
  ```
- Pattern never matched, so `section_end_line` defaulted to end-of-file

**Fix Applied**: Modified pattern matching in 3 locations (lines 3604-3636, 3700-3745, 3768-3805)
- Try matching section markers WITHOUT titles first
- Add fallback patterns for edge cases
- Match actual formatting used in books

**Result**: Coverage now 99.3% (79,739 words from 80,272 original) ✓

---

### Issue 2: Incorrect Chapter Titles - FIXED ✓
**Problem**: Chapter titles were long first lines instead of simple "Book I", "Book II"
- Chapter 1: "Of Man's First Disobedience, and the Fruit of That Forbidden Tree..."
- Chapter 2: "High on a Throne of Royal State Which Far Outshone the Wealth of Ormus..."

**Root Cause**: Code used `section['title']` which contained first line of content
- The body scanner captured the opening line as the "title"
- No validation that this was an actual title vs content

**Fix Applied**: Added heuristic to detect content vs real titles (lines 3962-4007, 4185-4230)
- Check if text starts with sentence words: "of", "in", "on", "at", "for", "and", "but", "or", "as", "if", "when", "while", "which", "who", "what", "how", "why"
- Check for sentence punctuation: commas, semicolons, possessive "'s"
- If detected as content, use format "{Type} {Numeral}" instead

**Result**: Chapters now titled "Book I", "Book II", etc. ✓

---

### Issue 3: Title-Case "Book I" Not Detected as Chapter Marker - FIXED ✓
**Problem**: Paradise Lost uses title-case "Book I", "Book II" instead of all-caps "BOOK I"
- Original pattern only matched all-caps "BOOK" (for 2-layer structures like Anna Karenina)
- Paradise Lost's title-case "Book" markers were completely ignored
- No chapters detected at all (showed as 1 chapter with all content merged)

**Root Cause**: Pattern mismatch
- `volume_book_pattern` only matched all-caps: `(BOOK|VOLUME|ACT)\s+...`
- Paradise Lost format in text file: "Book I", "Book II", etc. (title-case)
- Pattern was intentionally case-sensitive to avoid false positives in prose

**Edge Case**: Paradise Lost is unique
- Most books use all-caps "BOOK I" for 2-layer structures (sections containing chapters)
- Paradise Lost uses title-case "Book I" for 1-layer structure (Books ARE the chapters)
- Making main pattern case-insensitive would break 2-layer detection for other books

**Fix Applied**: Added special Paradise Lost pattern (lines 4484-4487, 4598-4620)
```python
# Pattern specifically for Paradise Lost style
paradise_lost_book_pattern = r'^(Book)\s+([IVXLCDM]+)$'

# Check in main loop BEFORE volume_book_pattern
paradise_lost_match = re.match(paradise_lost_book_pattern, line_stripped)
if paradise_lost_match:
    # Treat as chapter marker (not section marker)
    chapter_numeral = paradise_lost_match.group(2)
    chapter_number = self.roman_to_int(chapter_numeral)
    chapter_title = f"Book {chapter_numeral}"
    # Create chapter directly
```

**Why Special Logic**:
- Keeps main `volume_book_pattern` case-sensitive for 2-layer detection
- Only matches exact format "Book I" (title-case + Roman numeral + end of line)
- Checked BEFORE `volume_book_pattern` to take precedence
- Minimal risk of false positives due to strict pattern

**Result**:
- All 12 chapters detected correctly: "Book I" through "Book XII" ✓
- Proper 1-layer structure (no section/chapter nesting) ✓
- Coverage: 99.3% (79,739 words from 80,272 original) ✓

---

## Current State (as of latest dry run - 2025-12-14)

### Structure Detection
- Status: ✓ Correct - 1-layer structure
- Chapters: 12 (Book I through Book XII)
- Detection: Paradise Lost special pattern

### Chapter Titles
- Status: ✓ Correct
- Format: "Book I", "Book II", ..., "Book XII"

### Coverage
- Status: ✓ Correct
- Coverage: 99.3% (79,739 words / 80,272 original)
- Removed: 533 words (0.7%) - headers/footers

### Chapter Sizes
- Status: ✓ Realistic
- Range: 4,788 to 9,045 words per chapter
- Average: 6,645 words per chapter
- Chapter details:
  - Book I: 7,317 words
  - Book II: 6,117 words
  - Book III: 4,956 words
  - Book IV: 7,781 words
  - Book V: 6,824 words
  - Book VI: 6,780 words
  - Book VII: 4,788 words
  - Book VIII: 4,912 words
  - Book IX: 9,045 words
  - Book X: 8,345 words
  - Book XI: 6,894 words
  - Book XII: 4,928 words

### Processing Plan
- Batch 1: Chapters 1-10 (67,917 words → ~10,000 word summary)
- Batch 2: Chapters 11-12 (11,822 words → ~2,000 word summary)

---

## Summary

All parsing issues have been resolved! ✓

1. ✅ Coverage bug fixed (was 741.8%, now 99.3%)
2. ✅ Chapter titles fixed (now "Book I", "Book II" instead of first lines)
3. ✅ Title-case "Book I" pattern detection added (Paradise Lost specific)

The book is now ready for actual processing with `--parse-only` or full summary generation.
