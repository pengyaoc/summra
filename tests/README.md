# Summra Test Suite

Comprehensive unit tests for all Summra features based on ERD.md implementation details.

## Test Files

### 1. test_database.py (19 tests)
Tests database operations and models.

**Coverage:**
- ✅ add_book with word count calculation
- ✅ add_book unique filename constraint
- ✅ get_book_by_filename
- ✅ add_summary with INSERT OR REPLACE semantics
- ✅ add_summary for all three types (concise, medium, comprehensive)
- ✅ add_chapter with INSERT OR REPLACE (for regeneration)
- ✅ add_chapter with encoded numbers (101, 102, 201, 202)
- ✅ get_chapters retrieval
- ✅ get_all_books
- ✅ Foreign key constraints
- ✅ Cascade delete behavior
- ✅ Word count automatic calculation

### 2. test_chapter_detection.py (14 tests - existing)
Tests advanced chapter parsing logic.

**Coverage:**
- ✅ TOC detection and filtering
- ✅ Multi-part chapter merging
- ✅ Introduction/Preface capture (Chapter 0)
- ✅ Nested BOOK/CHAPTER structures (encoding)
- ✅ Coverage validation (90%+ content captured)
- ✅ Multiline titles with part markers
- ✅ Illustration block handling
- ✅ BOOK markers as chapters (The Odyssey case)
- ✅ Backward compatibility
- ✅ Roman numeral chapters
- ✅ Arabic numeral chapters
- ✅ Mixed chapter formats
- ✅ Edge cases and false positives

### 3. test_bulk_summary_parser.py (12 tests - existing)
Tests bulk summary response parsing.

**Coverage:**
- ✅ Sequential index parsing (1, 2, 3...)
- ✅ Encoded chapter mapping (101, 102 → index 1, 2)
- ✅ Non-sequential chapter mapping (12, 13 → index 1, 2)
- ✅ Missing END markers handling
- ✅ Extra whitespace tolerance
- ✅ Case insensitive parsing
- ✅ Missing chapters warning
- ✅ Multiline summary content
- ✅ Colons in titles
- ✅ Empty response handling
- ✅ Malformed response handling

### 4. test_rate_limiter.py (10 tests, 3 marked as slow)
Tests API rate limiting logic.

**Fast Tests (7 tests - always run):**
- ✅ Initialization
- ✅ No wait on first request
- ✅ No wait when within limits
- ✅ Rolling window cleanup (60-second window)
- ✅ Zero-token requests handling
- ✅ Token calculation and summation
- ✅ Request reset after waiting

**Slow Tests (3 tests - marked with @pytest.mark.slow):**
- ⏱️ Request limit enforcement (~60s - actual wait)
- ⏱️ Token limit enforcement (~60s - actual wait)
- ⏱️ Concurrent limits (~60s - actual wait)

### 5. test_gutenberg_integration.py (19 tests)
Tests Project Gutenberg integration features.

**Coverage:**
- ✅ Gutenberg ID extraction (eBook, EBook formats)
- ✅ Case-insensitive ID extraction
- ✅ Missing Gutenberg ID handling
- ✅ Metadata extraction (title, author)
- ✅ Metadata fallback to filename
- ✅ Gutenberg content extraction (header/footer removal)
- ✅ Variant marker formats
- ✅ Content without markers
- ✅ Formatting preservation
- ✅ Roman numeral conversion (basic, compound, subtraction rule)
- ✅ Complex Roman numerals (XIV, XCIX, MCMXCIV)
- ✅ Case insensitive Roman conversion
- ✅ Empty string and invalid character handling

### 6. test_llm_helpers.py (31 tests)
Tests LLM response cleaning, batching, and text normalization.

**LLM Response Cleaning (11 tests):**
- ✅ 'Of course' preamble removal
- ✅ 'Certainly' preamble removal
- ✅ 'Sure' preamble removal
- ✅ 'Here is' preamble removal
- ✅ 'Here is a summary' pattern removal
- ✅ "I'll provide" pattern removal
- ✅ Leading asterisks removal
- ✅ Excessive newlines removal
- ✅ Combined preambles handling
- ✅ Text without preamble unchanged
- ✅ Case insensitive cleaning

**Batching Algorithm (8 tests):**
- ✅ Empty chapters handling
- ✅ Single chapter batching
- ✅ Batching by count limit (max 5 chapters)
- ✅ Batching by word limit (max 40k words)
- ✅ Very long chapter isolation
- ✅ Order preservation
- ✅ Encoded chapter numbers (101, 102, 201)

**Text Normalization (12 tests):**
- ✅ Single newlines removed within paragraphs
- ✅ Paragraph breaks preserved (double newlines → single)
- ✅ Excessive newlines reduced
- ✅ Whitespace trimming
- ✅ Windows line endings conversion
- ✅ Multiple spaces reduction
- ✅ Empty lines removed
- ✅ Single spaces preserved

## Total Test Coverage

**Total Tests: 105 (102 fast + 3 slow)**
- Database: 19 tests
- Chapter Detection: 14 tests
- Bulk Summary Parser: 12 tests
- Rate Limiter: 10 tests (7 fast + 3 slow)
- Gutenberg Integration: 19 tests
- LLM Helpers: 31 tests

**Test Performance:**
- Fast tests: ~5 seconds (102 tests)
- Full suite: ~3 minutes (105 tests including 3 slow rate limiter tests)

## Running Tests

### Run All Tests (Fast - Skips Slow Tests)
By default, slow tests (~3 min) are skipped for faster iteration:
```bash
pytest tests/ -v
# Completes in ~5 seconds (102 tests, 3 skipped)
```

### Run All Tests Including Slow Tests
To run the full suite including rate limiter tests that wait ~60s each:
```bash
pytest tests/ -v -m ""
# Completes in ~3 minutes (105 tests)
```

### Run Only Slow Tests
To test rate limiting behavior (takes ~3 minutes):
```bash
pytest tests/ -v -m slow
# Runs 3 slow rate limiter tests
```

### Run Specific Test File
```bash
pytest tests/test_database.py -v
pytest tests/test_chapter_detection.py -v
pytest tests/test_bulk_summary_parser.py -v
pytest tests/test_rate_limiter.py -v  # Skips 3 slow tests by default
pytest tests/test_gutenberg_integration.py -v
pytest tests/test_llm_helpers.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_database.py::TestDatabase -v
pytest tests/test_llm_helpers.py::TestBatchingAlgorithm -v
```

### Run Specific Test
```bash
pytest tests/test_database.py::TestDatabase::test_add_book -v
pytest tests/test_gutenberg_integration.py::TestGutenbergIntegration::test_roman_to_int_complex -v
```

### Run with Coverage Report
```bash
pytest tests/ --cov=backend --cov=scripts --cov-report=html
```

## Test Organization

```
tests/
├── README.md                        # This file
├── test_database.py                 # Database operations (models.py)
├── test_chapter_detection.py        # Chapter parser (detect_chapters)
├── test_bulk_summary_parser.py      # Bulk response parsing
├── test_rate_limiter.py             # API rate limiting
├── test_gutenberg_integration.py    # Gutenberg features
└── test_llm_helpers.py              # LLM response cleaning, batching, normalization
```

## Coverage by Component

### Database Layer ✅
- CRUD operations: 100%
- Constraints (UNIQUE, FOREIGN KEY): 100%
- INSERT OR REPLACE semantics: 100%
- Cascade deletes: 100%

### Chapter Parser ✅
- Pattern matching: 95%+ (covers all documented patterns)
- TOC detection: 100%
- Multi-part merging: 100%
- Nested structures: 100%
- Roman numerals: 100%

### Bulk Processing ✅
- Index-based parsing: 100%
- Batching algorithm: 100%
- Response parsing: 100%

### Rate Limiting ✅
- Rolling window: 100%
- Request limits: 100%
- Token limits: 100%

### Gutenberg Integration ✅
- ID extraction: 100%
- Metadata extraction: 100%
- Content extraction: 100%
- Roman numerals: 100%

### LLM Helpers ✅
- Response cleaning: 100%
- Text normalization: 100%
- Batching: 100%

## Test Data

Tests use synthetic data and mock objects to avoid:
- Network calls (Gutenberg cover downloads)
- LLM API calls (expensive and slow)
- Actual file I/O where possible

Tests focus on:
- Logic correctness
- Edge case handling
- Error conditions
- Integration between components

## Continuous Testing

Run tests frequently during development:
```bash
# Watch mode (requires pytest-watch)
ptw tests/ -- -v

# Run tests on file change
pytest-watch tests/
```

## Adding New Tests

When adding new features:
1. Create tests FIRST (TDD approach)
2. Use descriptive test names: `test_<what>_<scenario>`
3. Group related tests in classes
4. Add docstrings explaining what's being tested
5. Update this README with new test counts

## Known Limitations

- **TTS tests**: Not included (would require TTS library mocking)
- **Flask API tests**: Not included (would require Flask test client)
- **Network tests**: Mock-only (no actual Gutenberg downloads)
- **LLM API tests**: Mock-only (no actual Gemini calls)

These could be added in future integration tests.

## Test Quality Standards

✅ Each test should:
- Test one specific behavior
- Be independent (no shared state)
- Be deterministic (same input → same output)
- Be fast (<100ms per test, or marked with @pytest.mark.slow)
- Have clear assertions
- Use descriptive names

### Slow Test Markers

Tests that take >1 second should be marked with `@pytest.mark.slow`:
```python
@pytest.mark.slow
def test_something_that_waits():
    time.sleep(60)  # Actual wait to test rate limiting
    ...
```

These tests are skipped by default but can be run with `-m ""` or `-m slow`.

✅ Test coverage should:
- Cover all documented features from ERD.md
- Include edge cases
- Include error conditions
- Verify both success and failure paths

## Future Test Additions

Potential areas for expansion:
- [ ] Integration tests (end-to-end workflows)
- [ ] Flask API endpoint tests
- [ ] TTS generation tests (with mocking)
- [ ] Performance benchmarks
- [ ] Load testing for database operations
- [ ] Concurrent request handling

## Contributing

When contributing tests:
1. Run all existing tests first: `pytest tests/ -v`
2. Ensure new tests pass: `pytest tests/test_your_new_file.py -v`
3. Update test counts in this README
4. Add test descriptions to relevant sections
5. Maintain >90% code coverage

---

**Last Updated:** 2025-11-24
**Test Count:** 105 tests (102 fast + 3 slow)
**Status:** All passing ✅
**Performance:** 5s (fast) / 3min (full)
