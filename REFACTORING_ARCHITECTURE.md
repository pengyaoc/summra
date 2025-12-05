# Refactoring Architecture: TOC Detection & Content Parsing Separation

## Problem Analysis

The current `detect_chapters()` method (1,342 lines) conflates two distinct responsibilities:
1. **TOC Detection**: Finding and parsing the table of contents structure
2. **Content Parsing**: Extracting actual chapter content based on boundaries

This mixing creates:
- Complex nested logic (5+ levels deep)
- Difficult to test or modify
- Hard to understand the flow
- Duplicate pattern matching
- Tight coupling between concerns

## Proposed Architecture

### High-Level Flow

```
Book Text
    ↓
┌───────────────────────────────────────┐
│  1. TOC Detection Phase               │
│  (Extract structure & metadata)       │
└───────────────────────────────────────┘
    ↓
  TOC Data Structure
  {chapters: [(num, name)], layers: 1|2, epilogue: bool}
    ↓
┌───────────────────────────────────────┐
│  2. Content Parsing Phase             │
│  (Extract actual text using TOC)      │
└───────────────────────────────────────┘
    ↓
  Chapter Content
  [(num, title, text)]
```

---

## Phase 1: TOC Detection

### Responsibility
Detect and extract the table of contents structure WITHOUT extracting content.

### Output: `TOCStructure` Data Class

```python
@dataclass
class TOCStructure:
    """Table of contents structure"""
    chapters: List[Tuple[int, str]]  # [(chapter_num, chapter_title), ...]
    has_toc: bool  # True if explicit TOC found, False if inferred
    toc_end_line: int  # Line number where TOC ends
    structure_type: str  # "single" or "two-level" (BOOK/PART)
    sections: List[Dict]  # For two-level: [{"type": "BOOK", "num": 1, "chapters": [...]}, ...]
    has_preface: bool  # Content before Chapter 1
    has_epilogue: bool  # Chapter after last numbered chapter
    epilogue_title: str  # e.g., "Epilogue", "Conclusion"
```

### Two Paths

#### Path 1a: Explicit TOC Available (Preferred)

```python
class TOCDetector:
    """Detect and parse table of contents"""

    def detect(self, text: str) -> TOCStructure:
        """Main entry point for TOC detection"""
        lines = text.split('\n')

        # Step 1: Find TOC section
        toc_start, toc_end = self._find_toc_boundaries(lines)

        if toc_start is not None:
            # Explicit TOC found
            return self._parse_explicit_toc(lines, toc_start, toc_end)
        else:
            # No TOC - infer structure from content
            return self._infer_toc_from_content(lines)

    def _find_toc_boundaries(self, lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
        """Find start and end lines of TOC section"""
        # Look for "CONTENTS", "TABLE OF CONTENTS", etc.
        # Return (start_line, end_line) or (None, None)
        pass

    def _parse_explicit_toc(self, lines: List[str], start: int, end: int) -> TOCStructure:
        """Parse TOC from explicit TOC section"""
        # Extract chapter numbers and titles from TOC
        # Detect if two-level structure (BOOK I, BOOK II, etc.)
        # Handle special chapters (PREFACE, EPILOGUE, etc.)
        pass

    def _infer_toc_from_content(self, lines: List[str]) -> TOCStructure:
        """Infer TOC by scanning for chapter markers in body"""
        # Scan entire text for CHAPTER markers
        # Build TOC structure from what we find
        # This is the fallback when no explicit TOC exists
        pass

    def _detect_structure_type(self, toc_entries: List) -> str:
        """Determine if single-level or two-level structure"""
        # Check if we have BOOK/PART/VOLUME markers
        # Return "single" or "two-level"
        pass

    def _detect_special_chapters(self, lines: List[str]) -> Dict:
        """Detect preface, epilogue, etc."""
        # Find PREFACE, PROLOGUE, INTRODUCTION (before Chapter 1)
        # Find EPILOGUE, CONCLUSION, AFTERWORD (after last numbered chapter)
        return {
            'has_preface': bool,
            'preface_marker': str,
            'has_epilogue': bool,
            'epilogue_title': str
        }
```

#### Path 1b: No TOC - Infer Structure (Fallback)

```python
class ContentStructureInferrer:
    """Infer book structure when no TOC exists"""

    def infer(self, text: str) -> TOCStructure:
        """Scan entire text to build TOC structure"""
        lines = text.split('\n')

        # Step 1: Find all chapter markers
        chapter_markers = self._find_all_chapter_markers(lines)

        # Step 2: Validate markers (not TOC entries, actual chapters)
        valid_markers = self._validate_chapter_markers(chapter_markers, lines)

        # Step 3: Build TOC structure
        toc = self._build_toc_from_markers(valid_markers)

        return toc

    def _find_all_chapter_markers(self, lines: List[str]) -> List[Dict]:
        """Find all lines that look like chapter markers"""
        # Scan for: "CHAPTER I", "Chapter 1", "I.", etc.
        # Return list of: {line_num, marker, chapter_num, inline_title}
        pass

    def _validate_chapter_markers(self, markers: List[Dict], lines: List[str]) -> List[Dict]:
        """Filter out false positives (TOC entries, embedded text)"""
        # Check if substantial content follows marker
        # Check if not embedded in paragraph
        # Remove duplicates
        pass
```

---

## Phase 2: Content Parsing

### Responsibility
Extract actual chapter content using the TOC structure as a guide.

### Input
- Book text (lines)
- TOC structure (from Phase 1)

### Output
- List of chapters: `[(chapter_num, chapter_title, chapter_text), ...]`

```python
class ContentParser:
    """Parse chapter content using TOC structure"""

    def parse(self, text: str, toc: TOCStructure) -> List[Tuple[int, str, str]]:
        """Main entry point for content parsing"""
        lines = text.split('\n')

        # Step 1: Split into major sections
        sections = self._split_into_sections(lines, toc)

        # Step 2: Extract each section
        chapters = []

        if sections['preface']:
            chapters.append(self._extract_preface(sections['preface']))

        chapters.extend(self._extract_chapters(sections['body'], toc))

        if sections['epilogue']:
            chapters.append(self._extract_epilogue(sections['epilogue'], toc))

        return chapters

    def _split_into_sections(self, lines: List[str], toc: TOCStructure) -> Dict:
        """Split book into: title/author, preface, TOC, body, epilogue"""
        # Title/Author: lines 0 to first substantial content
        # TOC: toc.toc_start_line to toc.toc_end_line
        # Preface: after TOC to Chapter 1 (if toc.has_preface)
        # Body: Chapter 1 to last chapter
        # Epilogue: after last chapter (if toc.has_epilogue)

        return {
            'title_author': (0, title_end),
            'toc': (toc_start, toc_end),
            'preface': (preface_start, preface_end) if toc.has_preface else None,
            'body': (body_start, body_end),
            'epilogue': (epilogue_start, epilogue_end) if toc.has_epilogue else None
        }

    def _extract_preface(self, section_range: Tuple[int, int]) -> Tuple[int, str, str]:
        """Extract preface content (Chapter 0)"""
        # Extract text from section_range
        # Normalize text
        # Return (0, "Preface", text)
        pass

    def _extract_chapters(self, section_range: Tuple[int, int], toc: TOCStructure) -> List[Tuple]:
        """Extract all numbered chapter content"""
        if toc.structure_type == "single":
            return self._extract_single_level(section_range, toc)
        else:
            return self._extract_two_level(section_range, toc)

    def _extract_single_level(self, section_range: Tuple[int, int], toc: TOCStructure) -> List[Tuple]:
        """Extract chapters from single-level structure"""
        chapters = []

        for i, (chapter_num, chapter_title) in enumerate(toc.chapters):
            # Find chapter boundaries
            start_line = self._find_chapter_start(chapter_num, chapter_title)

            # End is start of next chapter, or end of section
            if i + 1 < len(toc.chapters):
                next_num, next_title = toc.chapters[i + 1]
                end_line = self._find_chapter_start(next_num, next_title)
            else:
                end_line = section_range[1]

            # Extract content
            text = self._extract_content_between(start_line, end_line)
            text = self._normalize_chapter_text(text)

            chapters.append((chapter_num, chapter_title, text))

        return chapters

    def _find_chapter_start(self, chapter_num: int, chapter_title: str) -> int:
        """Find line number where chapter starts"""
        # Look for chapter marker matching this number/title
        # Use ChapterMarkerFinder (separate class)
        pass

    def _extract_content_between(self, start_line: int, end_line: int) -> str:
        """Extract text content between line numbers"""
        # Get lines[start_line:end_line]
        # Skip chapter marker line itself
        # Join into text
        pass

    def _normalize_chapter_text(self, text: str) -> str:
        """Normalize chapter text (existing method)"""
        # Remove extra whitespace
        # Fix formatting issues
        # etc.
        pass
```

---

## Phase 3: Chapter Marker Finding

### Responsibility
Find the exact line number for a chapter marker given chapter number/title.

```python
class ChapterMarkerFinder:
    """Find chapter markers in text"""

    def find(self, lines: List[str], chapter_num: int, chapter_title: str,
             search_start: int = 0, search_end: int = None) -> Optional[int]:
        """Find line number for chapter marker"""

        # Build all possible patterns for this chapter
        patterns = self._build_patterns(chapter_num, chapter_title)

        # Search in range
        search_end = search_end or len(lines)
        for line_num in range(search_start, search_end):
            line = lines[line_num]

            for pattern in patterns:
                if pattern.matches(line):
                    # Validate this is actual chapter, not TOC entry
                    if self._validate_chapter_marker(lines, line_num):
                        return line_num

        return None

    def _build_patterns(self, chapter_num: int, chapter_title: str) -> List['ChapterPattern']:
        """Build all possible chapter marker patterns"""
        # Pattern variations:
        # - "CHAPTER I", "CHAPTER 1", "Chapter I", "Chapter 1"
        # - "I", "1" (standalone)
        # - "I. Title", "1. Title" (with inline title)
        # - "[I]", "[1]" (brackets)
        # etc.
        pass

    def _validate_chapter_marker(self, lines: List[str], line_num: int) -> bool:
        """Validate this is actual chapter, not TOC or embedded text"""
        # Check: followed by substantial content (not another marker)
        # Check: not embedded in paragraph
        # Check: preceded by blank lines
        pass
```

---

## Special Handling

### Epilogue Detection & Numbering

```python
class EpilogueHandler:
    """Handle epilogue chapters that may lack numbers"""

    def detect_and_number(self, toc: TOCStructure, lines: List[str]) -> TOCStructure:
        """Detect epilogue and assign chapter number if needed"""

        if not toc.has_epilogue:
            return toc

        # Find epilogue marker
        epilogue_patterns = [
            r'^\s*EPILOGUE\s*$',
            r'^\s*CONCLUSION\s*$',
            r'^\s*AFTERWORD\s*$',
        ]

        # If epilogue has no number, assign next sequential number
        last_chapter_num = max(num for num, _ in toc.chapters)
        epilogue_num = last_chapter_num + 1

        # Add to TOC structure
        toc.chapters.append((epilogue_num, toc.epilogue_title))

        return toc
```

### Two-Level Structure (BOOK/PART → Chapters)

```python
class TwoLevelStructureHandler:
    """Handle two-level book structures (BOOK I → Chapter 1, 2, 3)"""

    def parse(self, lines: List[str], toc: TOCStructure) -> List[Tuple]:
        """Parse two-level structure into flat chapter list"""

        # toc.sections = [
        #     {"type": "BOOK", "num": 1, "title": "Book I",
        #      "chapters": [(1, "Chapter 1"), (2, "Chapter 2")]},
        #     {"type": "BOOK", "num": 2, "title": "Book II",
        #      "chapters": [(3, "Chapter 3"), (4, "Chapter 4")]}
        # ]

        # Strategy: Flatten to sequential numbering
        # BOOK I, Chapter 1 → Chapter 1
        # BOOK I, Chapter 2 → Chapter 2
        # BOOK II, Chapter 1 → Chapter 3
        # BOOK II, Chapter 2 → Chapter 4

        chapters = []
        sequential_num = 1

        for section in toc.sections:
            for _, chapter_title in section['chapters']:
                # Find chapter content
                # ...
                chapters.append((sequential_num, chapter_title, text))
                sequential_num += 1

        return chapters
```

---

## Migration Strategy

### Step 1: Extract TOCDetector (No Behavior Change)

```python
# Current in detect_chapters():
toc, toc_end_line = self.extract_toc(text)

# New:
toc_detector = TOCDetector()
toc_structure = toc_detector.detect(text)
```

### Step 2: Extract ContentParser (No Behavior Change)

```python
# Current: Mixed into detect_chapters() loop

# New:
content_parser = ContentParser()
chapters = content_parser.parse(text, toc_structure)
```

### Step 3: Update detect_chapters() to Orchestrate

```python
def detect_chapters(self, text: str, toc_structure: List[Dict] = None) -> Tuple[List[Tuple], set]:
    """Orchestrator: delegates to TOCDetector and ContentParser"""

    # Phase 1: Detect TOC structure
    if toc_structure:
        # Two-level structure provided
        toc = TOCStructure.from_two_level(toc_structure)
    else:
        # Detect from content
        toc_detector = TOCDetector()
        toc = toc_detector.detect(text)

    # Phase 2: Parse content using TOC
    content_parser = ContentParser()
    chapters = content_parser.parse(text, toc)

    # Return in existing format for compatibility
    consumed_indices = set()  # Track what we parsed
    return chapters, consumed_indices
```

---

## Obsolete Logic to Remove

### Chapter Merging Logic

**Current Problem**: Code tries to merge multi-part chapters (e.g., "Chapter I, Part 1", "Chapter I, Part 2")

**Why Remove**:
- If we parse on chapter boundaries correctly, parts are naturally included in chapter content
- Merging logic adds complexity without benefit
- Parts within a chapter should remain as single chapter text

**Location**: Look for logic that combines multiple chapter entries with same number

---

## Benefits of This Architecture

### 1. Separation of Concerns
- TOC detection: One job, well-defined
- Content parsing: One job, well-defined
- No mixing of responsibilities

### 2. Testability
- Can test TOC detection independently
- Can test content parsing with mock TOC
- Easier to write focused unit tests

### 3. Understandability
- Clear flow: TOC → Content
- Each class <300 lines
- Easy to reason about

### 4. Maintainability
- Fix TOC bugs in TOCDetector only
- Fix content bugs in ContentParser only
- No ripple effects across concerns

### 5. Extensibility
- Easy to add new TOC formats (add to TOCDetector)
- Easy to add new chapter patterns (add to ChapterMarkerFinder)
- No impact on other components

---

## Testing Strategy

### TOCDetector Tests

```python
def test_detect_explicit_toc():
    text = """
    CONTENTS

    Chapter I. The Beginning
    Chapter II. The Middle
    Chapter III. The End
    """
    detector = TOCDetector()
    toc = detector.detect(text)

    assert toc.has_toc == True
    assert len(toc.chapters) == 3
    assert toc.chapters[0] == (1, "The Beginning")

def test_detect_no_toc_infer_from_content():
    text = """
    CHAPTER I

    The Beginning

    Content here...

    CHAPTER II

    The Middle
    """
    detector = TOCDetector()
    toc = detector.detect(text)

    assert toc.has_toc == False
    assert len(toc.chapters) == 2
```

### ContentParser Tests

```python
def test_parse_with_toc():
    text = "... book text ..."
    toc = TOCStructure(
        chapters=[(1, "Chapter One"), (2, "Chapter Two")],
        has_toc=True,
        # ...
    )

    parser = ContentParser()
    chapters = parser.parse(text, toc)

    assert len(chapters) == 2
    assert chapters[0][0] == 1  # chapter_num
    assert chapters[0][1] == "Chapter One"  # chapter_title
    assert len(chapters[0][2]) > 0  # chapter_text
```

---

## Implementation Timeline

### Phase 1: TOC Detection (Week 1)
- Create `TOCDetector` class
- Extract TOC detection logic from `detect_chapters()`
- Create `TOCStructure` dataclass
- Write unit tests
- **Milestone**: Can detect TOC independently

### Phase 2: Content Parsing (Week 2)
- Create `ContentParser` class
- Extract content parsing logic
- Create `ChapterMarkerFinder` helper
- Write unit tests
- **Milestone**: Can parse content with given TOC

### Phase 3: Integration (Week 3)
- Update `detect_chapters()` to orchestrate
- Remove obsolete merging logic
- Run full integration tests
- **Milestone**: All existing tests pass

### Phase 4: Cleanup (Week 4)
- Remove dead code
- Update documentation
- Performance validation
- **Milestone**: Production ready

---

## Success Metrics

- ✅ All 242 existing tests pass
- ✅ Code coverage maintained or improved
- ✅ `detect_chapters()` reduced from 1,342 lines to <100 lines (orchestrator)
- ✅ No single function >300 lines
- ✅ TOCDetector and ContentParser independently testable
- ✅ Clear separation: TOC detection vs content parsing

---

This architecture provides a clean, maintainable foundation for the most complex part of the codebase.
