# Work Log

This file tracks all development tasks, both completed and in progress. It serves as context for future development sessions.

---

## 2025-11-25

### Summary Generation Script Major Improvements - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-25
**Completed:** 2025-11-25

**Objective:** Improve the chapter detection, rate limiting, and API reliability of the summary generation system through multiple enhancements addressing edge cases found in complex books like Moby Dick.

**Problems Addressed:**

1. **Rate Limit Bursts:** Large API calls (>100K tokens) could trigger rate limits even within quota
2. **Duplicate TOC Titles:** Some books had duplicate titles in table of contents
3. **BOOK Markers in Content:** Moby Dick's Cetology chapter has BOOK markers as part of the narrative, not chapter boundaries
4. **API Transient Failures:** 503/429 errors caused complete failures without retry
5. **Character Limit Inconsistency:** Different methods used different character limits

**Changes Made:**

1. **Large Call Throttling System** (`scripts/generate_summaries.py:84-127`):
   - Added `MAX_CHARS_PER_CALL = 900000` (900K chars ~= 225K tokens)
   - Added `LARGE_CALL_THRESHOLD = 100000` tokens
   - Added `LARGE_CALL_WAIT_SECONDS = 60` (1 minute spacing)
   - New `wait_if_needed_for_large_call()` method enforces spacing between large calls
   - Prevents burst rate limit errors from consecutive large API calls

2. **TOC Title Deduplication** (`scripts/generate_summaries.py:518`):
   - Changed `return titles` to `return list(dict.fromkeys(titles))`
   - Preserves order while removing duplicate chapter titles
   - Handles books with repeated TOC entries

3. **BOOK Marker Embedded Detection** (`scripts/generate_summaries.py:617-673`):
   - Sophisticated logic to distinguish embedded BOOK markers from actual chapter boundaries
   - Checks for substantial content (>20 chars, has lowercase) on adjacent lines
   - Requires no blank lines between marker and content for "embedded" classification
   - Special handling for first BOOK markers in numbered chapters
   - **Impact:** Correctly handles Moby Dick's Cetology chapter (Chapter 32) where "BOOK I (Folio)", "BOOK II (Octavo)" are part of whale classification discussion

4. **Immediate Continuation Line Consumption** (`scripts/generate_summaries.py:775, 800, 806`):
   - Added `consumed_lines.add(i + 1)` immediately when detecting continuation lines
   - Prevents continuation lines from being detected as separate chapters
   - Fixes duplicate chapter detection bugs

5. **Improved Chapter Title Handling** (`scripts/generate_summaries.py:842-844`):
   - Uses marker name itself when no explicit title provided
   - Changes "Introduction & Prefaces" to capitalized marker name (e.g., "Preface")
   - More accurate default titles

6. **Enhanced TOC Detection** (`scripts/generate_summaries.py:921-948`):
   - Skips consumed lines when looking ahead for TOC detection
   - Never skips PREFACE/INTRODUCTION as TOC (Chapter 0 always saved)
   - More reliable TOC vs content distinction

7. **BOOK-to-Chapter Conversion** (`scripts/generate_summaries.py:1127-1133`):
   - Preserves Chapter 0 (preface) when converting BOOK markers to chapters
   - Clears only merged intro content (chapters that won't be used)
   - Better handling of anthology-style books

8. **Title Position Matching** (`scripts/generate_summaries.py:1194-1212`):
   - Fuzzy pattern with optional "IN" prefix: `r'^\s*(?:IN\s+)?' + re.escape(title)`
   - Uses LAST occurrence instead of first (skips TOC, gets actual chapter)
   - Finds all matches, then keeps last one (most likely actual chapter location)
   - More reliable title-to-content mapping

9. **Character Limit Enforcement** (`scripts/generate_summaries.py:1264-1270, 1345-1351`):
   - Consistent use of `max_chars = min(len(text), self.MAX_CHARS_PER_CALL)`
   - Applied to `generate_concise_summary()` and `generate_medium_summary()`
   - Caps at 900K chars (225K tokens) to fit free tier 250K/min limit

10. **API Retry Logic with Exponential Backoff** (`scripts/generate_summaries.py:1291-1334, 1372-1414, 1604-1654, 1725-1752`):
    - Added retry loops to all API calls (concise, medium, bulk, single chapter)
    - Handles retriable errors: 503, UNAVAILABLE, 429, RESOURCE_EXHAUSTED
    - Extracts retry delay from error message: `Please retry in ([\d.]+)s`
    - Default wait times: 10s (503), 60s (429)
    - Max retries: 2 for summaries, 1 for chapter calls
    - Graceful degradation with clear error messages

11. **Dry Run Database Skip** (`scripts/generate_summaries.py:1944-1961`):
    - In dry-run mode, skip all database operations
    - Use dummy book_id = 999 for testing
    - Prevents database pollution during testing

**Technical Details:**

**Rate Limiting Call Sequence:**
```
1. wait_if_needed_for_large_call(estimated_tokens)  # 100K+ token spacing
2. rate_limiter.wait_if_needed(estimated_tokens)     # Standard rate limiting
3. Make API call with retry logic
```

**BOOK Marker Embedded Detection Algorithm:**
```
1. Check 3 lines before and after for substantial content
2. Substantial = has lowercase + >20 chars + not a marker
3. Must be ADJACENT (no blank lines between)
4. OR: Currently in numbered chapter AND no BOOK markers seen yet
5. If embedded: Add to current chapter text, skip boundary creation
```

**Retry Logic Pattern:**
```python
max_retries = 2
retry_count = 0
while retry_count <= max_retries:
    try:
        response = self.client.models.generate_content(...)
        result = self.clean_llm_response(response.text)
        break  # Success
    except Exception as e:
        is_retriable = ('503' in str(e) or '429' in str(e) or ...)
        if is_retriable and retry_count < max_retries:
            retry_count += 1
            wait_time = parse_wait_time(e) or default_wait
            print(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
        else:
            raise
```

**Files Modified:**
- `scripts/generate_summaries.py` - Multiple sections updated (see line numbers above)

**Impact:**

1. **Reliability:**
   - 503/429 errors now automatically retry instead of failing
   - Large calls properly spaced to avoid burst rate limits
   - More robust against transient API failures

2. **Accuracy:**
   - Correctly handles Moby Dick's embedded BOOK markers
   - No duplicate chapters from TOC title repetition
   - Better title matching (last occurrence vs first)
   - More accurate default chapter titles

3. **Performance:**
   - Character limits enforced consistently across all methods
   - Fits within free tier 250K tokens/min limit
   - Large call spacing prevents quota exhaustion

4. **Testability:**
   - Dry run mode skips database operations
   - Easier to test chapter detection without side effects

**Example Books Improved:**
- **Moby Dick:** Cetology chapter (32) no longer fragmented into 100+ sub-chapters
- **Books with duplicate TOC entries:** No duplicate chapters created
- **Large books:** Retry logic handles transient API errors gracefully

**Next Steps/Notes:**
- Monitor API retry frequency to tune wait times if needed
- Consider adding retry metrics/logging for production debugging
- May want to make LARGE_CALL_THRESHOLD configurable per book size

---

## 2025-11-25

### Flask App Refactoring and Production Navigation Fix - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-25
**Completed:** 2025-11-25

**Objective:** Refactor Flask application architecture to eliminate code duplication between app.py and app_prod.py by extracting common logic into app_base.py, and fix production navigation bug preventing users from clicking on books.

**Problems Identified:**
1. ~300 lines of duplicated code between app.py (551 lines) and app_prod.py (336 lines)
2. Risk of divergence: changes to routes need to be manually copied between files
3. Production navigation crash: "Cannot read properties of null (reading 'classList')" at app.js:477
4. Books not clickable on production home page (works locally)
5. Import errors when running with module execution (`python -m backend.app`)

**Root Cause Analysis:**

**Backend Duplication:**
- Both app.py and app_prod.py contained identical implementations of:
  - Flask app initialization and configuration
  - Database initialization
  - All common API routes: /api/books, /api/books/<id>, /api/books/<id>/summary/<type>, /api/books/<id>/chapters
  - Error handlers (404, 500)
  - Directory setup utilities
  - Cover image serving

**Frontend Navigation Bug:**
- Production environment running old code (commit aeda28e) before UI redesign
- UI redesign (commit d034498) added `book-info-cover` element to template
- Production template missing this element
- JavaScript attempted to access null element at line 477: `bookCoverEl.classList.remove('hidden')`
- Caused uncaught TypeError preventing book selection

**Import System Issues:**
- Used absolute imports (`import config`) which only work with direct execution
- Failed with module execution (`python -m backend.app`) expecting relative imports
- Error: `ModuleNotFoundError: No module named 'config'`

**Changes Made:**

1. **Created `backend/app_base.py`** (302 lines):
   - Extracted all common Flask routes and logic
   - Flask app initialization with static/template folders
   - CORS configuration
   - Database initialization: `db = models.Database()`
   - Common API routes:
     - `GET /` - Serve main page
     - `GET /api/books` - Get all books with cover URL conversion
     - `GET /api/books/<int:book_id>` - Get book details
     - `GET /api/books/<int:book_id>/summary/<summary_type>` - Get summary with chapters
     - `GET /api/books/<int:book_id>/chapters` - Get all chapters
     - `GET /api/summary-configs` - Get summary configurations
     - `GET /covers/<path:filename>` - Serve cover images
   - Error handlers (404, 500)
   - `ensure_directories()` utility function
   - Dual import pattern for both execution methods:
     ```python
     try:
         from . import config
         from . import models
     except ImportError:
         import config
         import models
     ```

2. **Refactored `backend/app.py`** (295 lines, down from 551):
   - Removed all common routes (now imported from app_base)
   - Imports Flask app: `from app_base import app, logger, ensure_directories`
   - Retained dev-specific TTS routes:
     - `POST /api/tts/generate` - Full TTS generation with streaming support
     - `POST /api/tts/stop` - Stop active TTS generation
   - Retained TTS handler initialization and active generations tracking
   - Dual import pattern:
     ```python
     try:
         from . import config
         from .app_base import app, logger, ensure_directories
     except ImportError:
         import config
         from app_base import app, logger, ensure_directories
     ```

3. **Refactored `backend/app_prod.py`** (104 lines, down from 336):
   - Removed all common routes (now imported from app_base)
   - Imports Flask app: `from app_base import app, logger, ensure_directories`
   - Retained prod-specific routes:
     - `POST /api/tts/generate` - Pre-generated audio only (no real-time generation)
     - `GET /health` - Health check endpoint for monitoring
   - Production TTS endpoint checks for existing audio files:
     - Priority 1: Gemini TTS (`*_gemini.wav`)
     - Priority 2: VITS TTS (`*_vits.wav`)
     - Priority 3: Legacy (`*_complete.wav`)
   - Dual import pattern for flexibility

4. **Fixed Production Navigation Bug** (`frontend/static/js/app.js:384`):
   - Added defensive null check before accessing DOM element:
     ```javascript
     const bookCoverEl = document.getElementById('book-info-cover');
     if (bookCoverEl) {  // ✅ Defensive check added
         if (book.cover_image_url) {
             bookCoverEl.src = book.cover_image_url;
             bookCoverEl.alt = `${book.title} cover`;
             bookCoverEl.classList.remove('hidden');
         } else {
             bookCoverEl.classList.add('hidden');
         }
     }
     ```
   - Prevents crash when element doesn't exist in older templates
   - Allows backward compatibility with production environment

**Technical Details:**

**Import Pattern - Both Execution Methods Supported:**
```python
# Supports both:
# 1. Direct execution: python backend/app.py
# 2. Module execution: python -m backend.app

try:
    from . import config  # Relative import for module execution
    from . import models
except ImportError:
    import config  # Absolute import for direct execution
    import models
```

**Code Reduction:**
- app_base.py: 302 lines (new)
- app.py: 551 → 295 lines (256 lines removed, 46% reduction)
- app_prod.py: 336 → 104 lines (232 lines removed, 69% reduction)
- Total lines eliminated: 488 lines of duplication
- Total backend lines: 701 (vs 887 before, 21% reduction)

**Architecture Pattern:**
```
app_base.py         (Common Flask app and routes)
     ↑                     ↑
     |                     |
app.py              app_prod.py
(Dev-specific       (Prod-specific
 TTS routes)        health checks)
```

**Testing Verification:**
```bash
# Both execution methods work:
python backend/app.py                    # ✅ Works
python -m backend.app                    # ✅ Works (after import fix)
python backend/app_prod.py               # ✅ Works
python -m backend.app_prod               # ✅ Works
```

**Production Environment Differences:**
- **Local**: Commit 7889e71 (latest, includes UI redesign with book-info-cover element)
- **Production**: Commit aeda28e (old, missing book-info-cover element)
- **Deployment Gap**: Production needs to pull latest code and restart service
- **Fix Applied**: Defensive JavaScript prevents crash until production is updated

**Files Created:**
- `backend/app_base.py` (302 lines) - Shared Flask application module

**Files Modified:**
- `backend/app.py` (lines 1-295) - Refactored to import from app_base
- `backend/app_prod.py` (lines 1-104) - Refactored to import from app_base
- `frontend/static/js/app.js` (line 384) - Added defensive null check

**Git Commits:**
- Commit 7889e71: "update db with new book data"
- Commit d034498: "Redesign UI with BeFreed-inspired minimal reading experience"
- Commit 3a4e04a: "Fix production bugs in app_prod.py"
- Additional commit needed for app_base.py refactoring (pending)

**Impact:**
1. **Code Maintainability:**
   - Single source of truth for common routes
   - Changes to API routes only need to be made once
   - Eliminates risk of divergence between dev and prod
   - Easier to review and understand codebase

2. **Development Workflow:**
   - Both execution methods supported (direct and module)
   - Flexible import system for different deployment scenarios
   - Easier testing with module execution

3. **Production Stability:**
   - Navigation bug fixed with defensive programming
   - Backward compatible with older templates
   - Graceful degradation when elements missing
   - Production can be updated independently of JavaScript

4. **Architecture:**
   - Clear separation: common vs environment-specific logic
   - app.py: 46% smaller (dev-specific TTS features only)
   - app_prod.py: 69% smaller (prod-specific health checks only)
   - Easier onboarding for new developers

**Verification:**
- ✅ Local development server works (port 5001)
- ✅ Module execution works (`python -m backend.app`)
- ✅ Direct execution works (`python backend/app.py`)
- ✅ All API routes functional
- ✅ TTS generation works in development
- ✅ Navigation works locally with defensive check
- ⏳ Production deployment pending (need to pull latest code)

**Next Steps:**
- Commit app_base.py refactoring changes
- Push to GitHub
- Deploy to production GCP instance:
  ```bash
  cd /path/to/summra
  git pull origin main
  sudo systemctl restart summra
  ```
- Verify navigation works in production after deployment
- Monitor production logs for any issues

**Lessons Learned:**
- Duplication leads to divergence - extract common logic early
- Defensive programming prevents crashes from environmental differences
- Production/development parity requires attention and testing
- Import flexibility important for different execution contexts
- Git deployment lag can cause unexpected bugs (old code + new assets)

---

### UI Redesign - BeFreed-Inspired Reading Experience - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-25
**Completed:** 2025-11-25

**Objective:** Redesign the Summra UI to improve the reading experience by removing unnecessary bounding boxes, streamlining content presentation, and implementing a chapter-focused navigation system inspired by the BeFreed app.

**Requirements:**
1. Remove unnecessary bounding boxes to maximize reading space
2. Display concise summary by default when selecting a book
3. Add medium summary sneak peek (first 200 words) below concise summary
4. Create tight chapter pill layout for easy navigation
5. Implement separate chapter detail pages
6. Keep chapter summaries collapsed by default to avoid spoilers

**Changes Made:**

1. **HTML Structure Redesign** (`frontend/templates/index.html`):
   - Removed the complex summary options cards interface (lines 29-68)
   - Created new book detail section with:
     - Cleaner header with smaller cover image (120px width) and book info side-by-side
     - Concise summary section with inline TTS button
     - Medium summary preview section (first 200 words) with expand/collapse
     - Chapter pills section for navigation
   - Added new chapter detail section:
     - Separate view for reading individual chapters
     - Collapsed chapter summary box with spoiler warning
     - Full chapter text section
     - Separate TTS buttons for summary and full text

2. **CSS Cleanup and Modernization** (`frontend/static/css/style.css`):
   - Removed heavy box shadows and borders from summary sections
   - Changed back button to transparent with blue text (not a big blue button)
   - Implemented cleaner section separators (1px border-bottom instead of boxes)
   - Added chapter pill styling:
     - Pills use subtle gray background with border
     - Hover effect transforms to blue with white text
     - Tight 10px gap between pills
   - Created chapter detail page styles:
     - Yellow/beige background for spoiler warning box
     - Collapsed summary with toggle button
     - Clean typography with improved line height (1.75)
   - Reduced max-width to 800px for better readability
   - Removed option cards styling entirely

3. **JavaScript Complete Rewrite** (`frontend/static/js/app.js`):
   - **New Routing System**:
     - `#/book/{slug}` - Book detail view
     - `#/book/{slug}/chapter/{num}` - Chapter detail view
   - **Book Selection Flow**:
     - Loads concise, medium summaries, and chapters in parallel
     - Shows concise summary immediately
     - Medium summary shows 200-word preview with expand button
     - Chapter pills display with click navigation
   - **Chapter Detail Page**:
     - New `showChapterDetail()` method
     - Loads chapter summary and full text
     - Summary collapsed by default with toggle button
     - Separate TTS buttons for summary and full text
   - **Simplified TTS Integration**:
     - Inline TTS buttons for each section
     - generateTTS() and generateChapterTTS() methods
     - Persistent audio player integration maintained
   - **Navigation**:
     - Back button from book view returns to books list
     - Back button from chapter view returns to book detail
     - Browser back/forward buttons work correctly

**Design Inspiration from BeFreed:**
- Minimal UI with focus on content first
- No unnecessary bounding boxes or heavy shadows
- Cleaner typography and spacing
- Content-first approach (summary shown immediately)
- Tight, efficient navigation elements (chapter pills)
- Collapsed spoiler sections by default

**Technical Details:**

**Chapter Pills Implementation:**
```css
.chapter-pill {
    background: var(--background-color);
    border: 1px solid var(--border-color);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
}

.chapter-pill:hover {
    background: var(--secondary-color);
    color: white;
    transform: translateY(-2px);
}
```

**Medium Summary Preview Logic:**
```javascript
const fullContent = data.summary.content;
const words = fullContent.split(/\s+/);
const preview = words.slice(0, 200).join(' ') + (words.length > 200 ? '...' : '');

mediumPreviewText.innerHTML = this.renderMarkdown(preview);
mediumFullText.innerHTML = this.renderMarkdown(fullContent);
```

**Routing Pattern Matching:**
```javascript
const bookMatch = hash.match(/#\/book\/([^\/]+)$/);
const chapterMatch = hash.match(/#\/book\/([^\/]+)\/chapter\/(\d+)$/);
```

**Files Modified:**
- `frontend/templates/index.html` (lines 29-101) - Complete restructure
- `frontend/static/css/style.css` (lines 153-411) - Removed boxes, added pills, clean design
- `frontend/static/js/app.js` (complete rewrite, 775 lines) - New routing and display logic

**UI Improvements:**
1. **Reduced Visual Clutter**:
   - Removed 4 large option cards
   - Removed heavy shadows and borders
   - Cleaner back button (text link vs big button)
   - Smaller cover image (120px vs 200px)

2. **Improved Reading Flow**:
   - Concise summary shown immediately
   - Medium preview below (200 words)
   - Chapter navigation always visible
   - Max-width 800px for optimal reading

3. **Better Navigation**:
   - Chapter pills are compact and scannable
   - Click to navigate to dedicated chapter page
   - Spoiler protection (summary collapsed)
   - Easy back navigation

4. **Maximized Reading Space**:
   - Content uses full container width (up to 800px)
   - Reduced padding and margins
   - No nested boxes
   - Clean section dividers

**Example User Flow:**
1. Click book from library → See concise summary + medium preview + chapter pills
2. Click "Read Full Summary" → Expand medium summary in place
3. Click chapter pill (e.g., "3. The Time Traveller Returns") → Navigate to chapter page
4. Chapter page shows full text with collapsed summary
5. Click "Show Summary" → Reveal chapter summary (if desired)
6. Click "Back to Book" → Return to book overview

**Impact:**
- Cleaner, more focused reading experience
- Better mobile responsiveness (fewer nested boxes)
- Faster navigation (chapter pills vs accordion)
- Spoiler protection (collapsed chapter summaries)
- Content-first design philosophy
- Improved accessibility (clear hierarchy, semantic HTML)

**Browser Compatibility:**
- Tested with modern browsers (Chrome, Firefox, Safari)
- Uses CSS Grid and Flexbox (widely supported)
- Hash routing works universally
- TTS features use standard Web Audio API

**Polish Improvements:**

After initial implementation, added two key polish features:

1. **Scroll to Top on Navigation:**
   - Added `window.scrollTo(0, 0)` in `showMediumDetail()` and `showChapterDetail()`
   - Users now always start reading from the top when navigating to new pages
   - Improves reading flow and prevents confusion

2. **White Background for Reading Pages:**
   - Added white card background (`var(--card-background)`) to:
     - `.medium-detail-content` (32px padding, 8px border radius)
     - `.chapter-detail-content` (32px padding, 8px border radius)
   - Creates consistent reading experience across all pages
   - Better visual separation from gray page background
   - Matches book details page styling

**Files Modified (Polish):**
- `frontend/static/js/app.js` - Added scroll to top calls
- `frontend/static/css/style.css` - Added white backgrounds to detail pages

**CSS Gradient Fix:**
- Updated `.preview-fade` gradient from `rgba(236,240,241,1)` to `rgba(255,255,255,1)`
- Ensures fade blends correctly with white background

**Next Steps:**
- Test with actual books in the database
- Verify all TTS buttons work correctly
- Ensure responsive design on mobile devices
- Consider adding breadcrumb navigation
- May want to add "Next Chapter" / "Previous Chapter" buttons

---

### Production Bug Fixes and Database Cleanup - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-25
**Completed:** 2025-11-25

**Objective:** Fix critical production bugs preventing chapter summaries and TTS audio playback, clean up duplicate database entries, and ensure app.py and app_prod.py are functionally aligned.

**Problems Identified:**
1. Duplicate "The King in Yellow" entries in database (Book ID 31 empty, Book ID 32 with content)
2. Chapter summaries not showing in production comprehensive view
3. Pre-generated TTS audio files not playing in production
4. Need to verify functional parity between development and production apps

**Changes Made:**

1. **Database Cleanup - Removed Duplicate Book Entry**:
   - Created `scripts/check_king_duplicates.py` to identify duplicates
   - Fixed column name error: `cover_image` → `cover_image_url` (correct schema)
   - Identified Book ID 31 (0 summaries, 0 chapters) as duplicate
   - Deleted Book ID 31 with `DELETE FROM books WHERE id = 31`
   - CASCADE deletion automatically removed related summaries and chapters
   - Verified Book ID 32 has correct data (2 summaries, 8 chapters)

2. **Fixed Chapter Summaries Not Showing in Production** (`backend/app_prod.py:86-243`):
   - **Problem**: `/api/books/<book_id>/summary/<summary_type>` endpoint missing:
     - Chapter fetching for comprehensive/full summary types
     - Book metadata (id, title, author, cover_image_url) in responses
     - Cover image URL conversion (relative path → `/static/` prefix)
   - **Solution**: Updated endpoint to match app.py functionality:
     - Added chapter fetching: `chapters = db.get_chapters(book_id)`
     - Added book metadata preparation with cover image URL conversion
     - Added chapters to response data when applicable
     - Handles both comprehensive and full summary types
   - **Also Fixed**: `/api/books/<book_id>/chapters` endpoint
     - Added book metadata to response
     - Added cover image URL conversion

3. **Fixed Pre-Generated TTS Audio Not Playing** (`backend/app_prod.py:259-324`):
   - **Problem**: `/api/tts/generate` endpoint immediately returned error 501 without checking for pre-generated files
   - **Solution**: Rewrote endpoint to check for existing audio before returning error:
     - Priority 1: Gemini TTS (`*_gemini.wav`) - offline pre-generated
     - Priority 2: VITS TTS (`*_vits.wav`) - previously generated
     - Priority 3: Legacy concatenated audio (`*_complete.wav`) - backward compatibility
     - Returns audio URL if file exists, otherwise returns 404 with helpful message
   - Added `request` to Flask imports for JSON parsing
   - TTS generation remains disabled in production (memory constraints)

4. **Comprehensive App Comparison**:
   - Compared all routes between app.py (550 lines) and app_prod.py (335 lines)
   - **Routes in app_prod.py NOT in app.py**:
     - `/covers/<path:filename>` - Serves cover images (production-specific)
     - `/health` - Health check endpoint for monitoring (production-specific)
   - **Routes in app.py NOT in app_prod.py**:
     - `/api/tts/stop` - Stops TTS generation (intentionally excluded - no real-time TTS in prod)
   - **Functional Alignment Achieved**:
     - ✅ All core API endpoints now identical
     - ✅ Production has appropriate additions (/health, /covers)
     - ✅ TTS disabled but pre-generated audio accessible

**Technical Details:**

**Database Schema Verification:**
```sql
.schema books
-- Confirmed: cover_image_url TEXT, gutenberg_id INTEGER
```

**Production Endpoint Updates:**
```python
# Chapter fetching now included
if summary_type == 'comprehensive':
    chapters = db.get_chapters(book_id)

# Book metadata now included
book_data = {
    'id': book['id'],
    'title': book['title'],
    'author': book['author']
}

# Cover image URL conversion
if book.get('cover_image_url'):
    cover_url = book['cover_image_url']
    if not cover_url.startswith('http'):
        cover_url = f"/static/{cover_url}"
    book_data['cover_image_url'] = cover_url
```

**TTS Audio Check Logic:**
```python
# Priority 1: Gemini TTS
gemini_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.wav"
if gemini_audio_path.exists():
    return jsonify({'success': True, 'audio_url': f'/static/{relative_path}', ...})

# Priority 2: VITS TTS
vits_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_vits.wav"
if vits_audio_path.exists():
    return jsonify({'success': True, 'audio_url': f'/static/{relative_path}', ...})

# Priority 3: Legacy
cached_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav"
if cached_audio_path.exists():
    return jsonify({'success': True, 'audio_url': f'/static/{relative_path}', ...})
```

**Files Modified:**
- `backend/app_prod.py` (lines 3, 86-243, 259-324) - 169 insertions, 12 deletions
- `data/database.db` - Deleted Book ID 31

**Files Created:**
- `scripts/check_king_duplicates.py` - Database inspection utility (reusable)

**Git Commits:**
- Commit a3b6899: "Add title-only TOC extraction for anthology books and cleanup King in Yellow duplicate"
- Commit 3a4e04a: "Fix production bugs in app_prod.py" - Combined both bug fixes

**Deployment Status:**
- Changes committed and pushed to GitHub (commit 3a4e04a)
- **⚠️ Production deployment pending**: Changes not yet deployed to GCP e2-micro VM
- **Deployment steps needed**:
  ```bash
  cd /path/to/summra
  git pull origin main
  sudo systemctl restart summra
  sudo systemctl status summra
  ```

**Production vs Development Differences Explained:**
- **Local dev**: Flask development server, auto-reload possible with `debug=True`
- **Production**: Gunicorn WSGI server managed by systemd
  - Does NOT auto-reload code changes (intentional for stability)
  - Requires explicit restart: `sudo systemctl restart summra`
  - Provides better performance and memory efficiency
  - Critical for e2-micro instance (1GB RAM constraint)

**Verification:**
- All core API endpoints functionally aligned
- Database cleaned of duplicate entries
- Production-specific routes (/health, /covers) appropriate for deployment
- TTS generation properly disabled while pre-generated files accessible

**Impact:**
- Chapter summaries now display correctly in production
- Pre-generated TTS audio files now play in production
- Database cleaned from 12 books to 11 books (removed duplicate)
- Production app maintains functional parity with development
- Production optimizations preserved (TTS disabled, health checks, cover serving)

**Next Steps:**
- Deploy changes to production VM
- Test comprehensive summary view on production
- Test pre-generated audio playback on production
- Monitor production logs after deployment

---

## 2025-11-25

### Chapter Summary UI Polish - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-25
**Completed:** 2025-11-25

**Objective:** Improve chapter summary UI/UX in the chapter detail view by reorganizing button layout and simplifying the toggle button design for a cleaner, more minimal interface.

**Changes Made:**

1. **Moved Listen Button to Summary Header** (`frontend/templates/index.html:110-113`):
   - Created new `chapter-summary-actions` wrapper div in header
   - Moved "🔊 Listen" button from bottom of summary content to header
   - Placed Listen button alongside Show/Hide toggle button
   - Simplified button text from "🔊 Listen to Summary" to "🔊 Listen"
   - Both buttons now side-by-side in header for better accessibility

2. **Simplified Toggle Button Design** (`frontend/static/css/style.css:524-539`):
   - Changed from styled button with border/background to minimal chevron-only design
   - Removed blue background (`background: transparent`)
   - Removed border and padding
   - Removed rounded corners
   - Increased font size to 1.2rem for better visibility
   - Button now displays just chevron: "▼" (collapsed) or "▲" (expanded)
   - Hover effect: color change and slight scale transform
   - Cleaner, more minimal aesthetic

3. **Updated JavaScript Toggle Logic** (`frontend/static/js/app.js:628-632`):
   - Changed button text from "Show Summary ▼" / "Hide Summary ▲" to just "▼" / "▲"
   - Maintains same functionality with simplified visual presentation

4. **Added Flexbox Layout for Button Container** (`frontend/static/css/style.css:518-522`):
   - New `.chapter-summary-actions` class with flexbox layout
   - 12px gap between buttons
   - Centered alignment for professional appearance

**Technical Details:**

**HTML Structure:**
```html
<div class="chapter-summary-header" id="chapter-summary-header">
    <h4>📝 Chapter Summary <span class="spoiler-warning">(may contain spoilers)</span></h4>
    <div class="chapter-summary-actions">
        <button class="tts-button-inline" id="chapter-summary-tts-button">🔊 Listen</button>
        <button class="toggle-summary-btn" id="toggle-summary-btn">▼</button>
    </div>
</div>
```

**CSS Styling:**
```css
.toggle-summary-btn {
    background: transparent;
    color: var(--secondary-color);
    border: none;
    padding: 0;
    font-size: 1.2rem;
    cursor: pointer;
    transition: all 0.2s;
    font-weight: normal;
    line-height: 1;
}

.toggle-summary-btn:hover {
    color: #2980b9;
    transform: scale(1.1);
}

.chapter-summary-actions {
    display: flex;
    gap: 12px;
    align-items: center;
}
```

**JavaScript Toggle:**
```javascript
toggleBtn.onclick = () => {
    if (isSummaryExpanded) {
        summaryContent.classList.add('hidden');
        toggleBtn.textContent = '▼';
        isSummaryExpanded = false;
    } else {
        summaryContent.classList.remove('hidden');
        toggleBtn.textContent = '▲';
        isSummaryExpanded = true;
    }
};
```

**Files Modified:**
- `frontend/templates/index.html` (lines 110-113) - Restructured header layout
- `frontend/static/css/style.css` (lines 518-522, 524-539) - Added container, simplified button
- `frontend/static/js/app.js` (lines 628-632) - Updated toggle text

**Design Improvements:**
1. **Better Organization:**
   - All chapter summary controls now in header
   - Listen and toggle buttons grouped together
   - Clearer visual hierarchy

2. **Reduced Visual Clutter:**
   - Minimal chevron-only toggle (no border, no background)
   - Consistent with overall minimal design philosophy
   - Less visual weight in UI

3. **Improved Accessibility:**
   - Listen button more discoverable (in header vs bottom)
   - Larger clickable chevron (1.2rem font size)
   - Clear hover states for both buttons

4. **Consistent with BeFreed Design:**
   - Minimal UI elements
   - Clean, unobtrusive controls
   - Focus on content first

**User Experience:**
- Users can now see both Listen and toggle options immediately when viewing chapter
- Simplified chevron is less distracting than full button
- Hover feedback provides clear indication of interactivity
- Layout matches other summary sections with Listen buttons in headers

**Impact:**
- Cleaner, more professional chapter detail page
- Better alignment with overall design system
- Improved button discoverability and usability
- Reduced visual noise in reading interface

**Next Steps/Notes:**
- Consider applying similar button simplification to other UI elements if needed
- Monitor user feedback on new layout
- May want to add keyboard shortcuts for toggle in future

---

## 2025-11-24

### Title-Only TOC Extraction for Books Without Chapter Numbers - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Implement TOC-based chapter extraction for books like "The King in Yellow" that use story titles without numbered chapter markers (no "Chapter 1", no Roman numerals).

**Problem:**
- "The King in Yellow" is a collection of 10 short stories with title-only TOC format
- Normal chapter detection only found 2 chapters (98.5% of content in one chunk)
- Book structure uses story titles directly without "Chapter" prefixes:
  ```
  CONTENTS

  THE REPAIRER OF REPUTATIONS
  THE MASK
  THE COURT OF THE DRAGON
  ...
  ```
- Initial TOC extraction was too permissive and included 29 entries (poetry epigraph mixed with actual titles)

**Solution:**
Created `extract_title_only_toc()` method with improved end-of-TOC detection and added fallback logic in `detect_chapters()`.

**Changes Made:**

1. **Enhanced `extract_title_only_toc()` method** (`scripts/generate_summaries.py:422-482`):
   - Detects CONTENTS section start
   - Tracks consecutive empty lines to detect section breaks
   - Stops after 2+ consecutive empty lines (separates TOC from epigraphs/poetry)
   - Excludes poetry patterns:
     - Lines ending with commas
     - Lines starting with quotes + lowercase
   - Stops early when hitting non-title lines (lowercase start, quotes)
   - Length filters: 5-60 characters
   - Excludes numbered patterns (Roman numerals, "Chapter X")

2. **Fallback logic in `detect_chapters()`** (`scripts/generate_summaries.py:1062-1112`):
   - Triggers when `len(chapters) <= 2` (very few chapters detected)
   - Extracts title-only TOC
   - Requires at least 3 titles to proceed
   - Searches for each title in content (skips TOC occurrence at lines <100)
   - Creates chapters from title positions
   - Requires finding at least 60% of titles to use TOC extraction
   - Uses `normalize_chapter_text()` for content cleanup

**Testing Results:**
- TOC extraction correctly found 10 story titles (validated with test script)
- No poetry/epigraph content included
- All 10 titles match expected story names:
  1. THE REPAIRER OF REPUTATIONS
  2. THE MASK
  3. THE COURT OF THE DRAGON
  4. THE YELLOW SIGN
  5. THE DEMOISELLE D'YS
  6. THE PROPHETS' PARADISE
  7. THE STREET OF THE FOUR WINDS
  8. THE STREET OF THE FIRST SHELL
  9. THE STREET OF OUR LADY OF THE FIELDS
  10. RUE BARRÉE

**Technical Details:**

**End-of-TOC Detection:**
```python
if found_any_titles and consecutive_empty_lines >= 2:
    break  # TOC section ended
```

**Poetry Exclusion Patterns:**
```python
not (line_stripped.startswith('"') and len(line_stripped) > 1 and line_stripped[1].islower()) and
not line_stripped.endswith(',')
```

**Early Stop Logic:**
```python
elif found_any_titles:
    if line_stripped and (line_stripped[0].islower() or line_stripped.startswith('"')):
        break  # Hit non-title content (poetry, etc.)
```

**Files Modified:**
- `scripts/generate_summaries.py` (lines 422-482, 1062-1112)

**Files Created:**
- `/tmp/test_toc_extraction.py` - Test script to validate TOC extraction logic

**Impact:**
- Enables proper chapter detection for anthology-style books
- Handles title-only TOC format without numbered chapters
- Robust separation of TOC from epigraphs/poetry/front matter
- Applicable to similar classic literature collections

**Next Steps:**
- Ready to process "The King in Yellow" with full summary generation
- TOC-based extraction can be used for other anthology books

---

## 2025-11-24

### Production Deployment Setup for GCP e2-micro - IN PROGRESS
**Status:** ⏳ In Progress
**Started:** 2025-11-24

**Objective:** Deploy Summra to GCP e2-micro instance (Debian 12 bookworm) for production use on free tier with TTS disabled to conserve memory.

**Changes Made:**

1. **Created e2-micro deployment configuration** (`deploy/setup-e2micro.sh`):
   - Automated setup script for Debian 12 (bookworm) and Ubuntu 22.04
   - Auto-detects OS and uses appropriate Python version
   - Installs dependencies WITHOUT TTS library (saves ~800MB memory)
   - Creates Python virtual environment with production packages
   - Configures Nginx reverse proxy
   - Sets up systemd service with memory limits (400MB max)
   - Enables 1GB swap file (critical for 1GB RAM environment)
   - Configures firewall (ports 22, 80, 443)
   - Prompts for domain name and Gemini API key
   - Total setup time: ~10-15 minutes

2. **Created quick start guide** (`deploy/QUICKSTART_E2MICRO.md`):
   - Step-by-step deployment instructions
   - GitHub clone via token or direct upload options
   - SSL setup with Let's Encrypt
   - Monitoring and maintenance commands
   - Troubleshooting section
   - Memory optimization tips

3. **Updated .gitignore**:
   - Commented out database and audio exclusions to allow deployment via GitHub
   - Database, audio files, and covers now included in repository
   - Enables simple `git clone` deployment without separate uploads

4. **Production deployment files**:
   - `requirements-prod.txt` - Minimal dependencies without TTS
   - `gunicorn_config.py` - Memory-optimized config (1 worker)
   - `backend/app_prod.py` - TTS-disabled Flask app
   - `deploy/nginx-summra.conf` - Nginx configuration
   - `deploy/systemd-summra.service` - Systemd service with memory limits

**Technical Details:**

**Memory Budget (e2-micro):**
```
System:           ~250 MB
Nginx:            ~20 MB
Summra (1 worker): ~150-200 MB
Swap (backup):     1GB
-----------------------
Total:            ~420-470 MB / 1024 MB ✅
Free:             ~550 MB
```

**Production Stack:**
- OS: Debian 12 (bookworm)
- Python: 3.11 (default in Debian 12)
- Web Server: Nginx (reverse proxy + static files)
- App Server: Gunicorn with gevent workers
- Database: SQLite (47MB)
- Assets: Audio files (266MB), Covers (38MB)

**Deployment Method:**
- GitHub clone with personal access token
- All data (database, audio, covers) in repository
- One-command setup via setup script
- No manual file uploads needed

**Current Status:**
- Setup script created and tested locally
- Script uploaded to VM via GitHub
- Fixed line ending issue (CRLF → LF) with dos2unix
- Setup script completed on VM
- Fixed `app_prod.py` import errors and Database API mismatches
- **✓ Local verification complete - app_prod.py working correctly**
- Ready to deploy fixed version to VM

**Issues Resolved:**
- ✓ Windows line endings (fixed with dos2unix)
- ✓ GitHub authentication (personal access token)
- ✓ ModuleNotFoundError for config (try/except pattern in models.py)
- ✓ ImportError for init_db (Database class instantiation)
- ✓ Wrong Database API (complete rewrite of app_prod.py)

**app_prod.py Rewrite:**
- **Problem**: Original version imported non-existent classes (`Book`, `Summary`, `Chapter`)
- **Problem**: Used incorrect methods (`Book.get_all()` instead of `Database.get_all_books()`)
- **Solution**: Complete rewrite to match working `app.py` API
- **Imports**: Uses `import models` and `import config` (not `from backend.models`)
- **Database**: Creates `db = models.Database()` instance
- **Methods**: Uses correct API (`get_all_books()`, `get_book()`, `get_summary()`, `get_chapters()`)
- **Testing**: All 10 routes defined, database operations verified with test script

**Files Created:**
- `deploy/setup-e2micro.sh` (155 lines) - Automated setup script
- `deploy/QUICKSTART_E2MICRO.md` (280 lines) - Deployment guide
- `test_app_prod.py` - Local verification test script

**Files Modified:**
- `.gitignore` - Commented out database/audio exclusions for deployment
- `backend/app_prod.py` - Complete rewrite with correct Database API
- `WORK_LOG.md` - This entry

**Next Steps:**
- Commit and push fixed app_prod.py to GitHub
- Pull changes on VM
- Restart summra service on VM
- Test health endpoint and API on VM
- Set up DNS (summra.pengyaochen.com → 35.203.172.2)
- Set up SSL certificate with Let's Encrypt
- Configure Nginx for multiple services (blog + Summra)
- Verify memory usage is within limits

**Cost:**
- E2-micro: $0/month (GCP free tier)
- Storage: $0/month (30GB included)
- Bandwidth: $0-5/month (1GB free, then $0.12/GB)
- Total: **FREE** (within free tier limits)

**Alternative Deployment (not chosen):**
- E2-small with TTS: ~$13/month (2GB RAM, full TTS support)
- Documentation created for both options

---

### Offline TTS Default Mode Change - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Update the `generate_offline_tts.py` script to change the default mode from generating both concise and medium summaries to only generating concise summary audio.

**Changes Made:**
1. Updated `scripts/generate_offline_tts.py` (lines 227-230):
   - Changed default from `['concise', 'medium']` to `['concise']`
   - Updated comment from "generate concise and medium summaries" to "generate concise summary"
   - Updated print message to reflect new default: "concise summary only"

**Rationale:**
- Reduces default API usage and cost
- Concise summaries are the most commonly listened-to format
- Users can still explicitly request medium or all summaries via command-line flags

**Usage Examples:**
```bash
# Default mode (concise only)
python scripts/generate_offline_tts.py --book "The Time Machine"

# Explicit modes still work
python scripts/generate_offline_tts.py --book "Book Title" --summaries concise medium
python scripts/generate_offline_tts.py --book "Book Title" --all-summaries
python scripts/generate_offline_tts.py --book "Book Title" --comprehensive-chapters 1-5
```

**Files Modified:**
- `scripts/generate_offline_tts.py` (lines 227-230)

**Impact:**
- Faster default TTS generation
- Lower API costs for batch processing
- More economical use of Gemini TTS API quota

---

### Documentation System Enhancement - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Establish comprehensive documentation structure with clear separation between user-facing features (PRD.md) and technical implementation details (ERD.md).

**Changes Made:**
1. Updated `CLAUDE.md` with new documentation requirements:
   - Added Documentation section with subsections for PRD.md and ERD.md
   - PRD.md: Product Requirements Document for user-facing features
   - ERD.md: Engineering Reference Document for technical details
   - Clear instructions on what each document should contain

2. Created `PRD.md` (Product Requirements Document):
   - Product vision and mission statement
   - Target user personas (Curious Reader, Student, Lifelong Learner, Accessibility User)
   - Detailed core feature specifications:
     - Three summary lengths (concise, medium, comprehensive)
     - Text-to-speech functionality
     - Book discovery and browsing
     - URL routing and navigation
     - Chapter navigation
   - User workflows and use cases
   - UI requirements and acceptance criteria
   - Non-functional requirements (performance, accessibility, usability)
   - Feature roadmap (5 phases from core to content expansion)
   - Success metrics and KPIs
   - Design principles
   - Risk assessment

**Files Created:**
- `PRD.md` (~400 lines) - Comprehensive product requirements

**Files Modified:**
- `CLAUDE.md` - Added documentation section

**Documentation Structure:**
```
CLAUDE.md         → Instructions for Claude (work log, documentation)
PRD.md           → User-facing features and product requirements
ERD.md           → Technical implementation and architecture (existing)
WORK_LOG.md      → Development task tracking (this file)
README.md        → User documentation and setup
PROJECT_OVERVIEW.md → Project summary and overview
```

**Next Steps/Notes:**
- PRD.md should be updated when new user-facing features are added
- ERD.md should be updated when technical architecture changes
- Both documents serve as critical context for future Claude Code sessions
- WORK_LOG.md tracks all development tasks chronologically

---

### TTS Debug Logging Enhancement - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Add comprehensive debug logging to TTS generation to identify special characters that may cause the TTS engine to jitter.

**Changes Made:**
1. Enhanced `backend/tts_handler.py::generate_audio()` method with detailed debug output:
   - Character inspection showing non-ASCII characters with Unicode codepoints
   - `repr()` view to reveal hidden characters
   - Warning detection for remaining special characters after cleaning
   - Detection of problematic whitespace/control characters (newlines, tabs, etc.)
   - Full text output at each stage: original → cleaned → final

2. Enhanced `backend/tts_handler.py::generate_audio_chunks()` method with chunk-level logging:
   - Total text statistics (length, word count)
   - Chunk breakdown (size, word count per chunk)
   - Preview of each chunk's content
   - Success/failure tracking for each chunk
   - Summary of chunk generation results

**Technical Details:**
- Debug logs show Unicode codepoint values (e.g., U+2019 for curly quotes)
- Limits display to first 20 problematic characters to avoid log overflow
- Uses `repr()` to expose hidden characters like `\n`, `\r`, `\t`, `\x00`
- All logging prints to stdout for easy monitoring during TTS generation

**Files Modified:**
- `backend/tts_handler.py` (lines 165-211, 250-300)

**Next Steps/Notes:**
- Monitor logs during TTS generation to identify patterns in jitter
- If specific Unicode characters cause issues, update `clean_text_for_speech()` method
- Consider adding optional debug flag to control logging verbosity

---

### Work Log System Setup - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Set up a work log system to track development tasks and provide context for future sessions.

**Changes Made:**
1. Created `claude.md` with high-level instructions for Claude
2. Created `WORK_LOG.md` as a separate file for tracking tasks
3. Added instruction to maintain work log with status updates

**Files Created:**
- `claude.md` - High-level instructions
- `WORK_LOG.md` - Development work log (this file)

**Next Steps/Notes:**
- Update work log at task start, during progress, and at completion
- Keep entries organized by date
- Include enough detail for future context

---

### Database Cleanup - Remove Test Books - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Remove all test books generated by unit tests from the production database to clean up test data.

**Changes Made:**
1. Created `scripts/check_test_books.py` to identify test books in the database
   - Searches for books with titles: "Book 1", "Book 2", "Book 3", "Test Book"
   - Displays book details and counts of related summaries/chapters
   - Provides summary before deletion

2. Created `scripts/delete_test_books.py` to remove test books
   - Deletes all books matching test patterns
   - CASCADE deletion automatically removes related summaries and chapters
   - Verifies deletion was successful

**Results:**
- Books deleted: 15 test books
- Summaries removed: 6
- Chapters removed: 7
- Database cleaned from 27 books down to 12 production books

**Test Books Removed:**
- "Book 1" entries: 2 books (IDs 20, 24)
- "Book 2" entries: 1 book (ID 21)
- "Book 3" entries: 1 book (ID 22)
- "Test Book" entries: 11 books (IDs 12-19, 23, 25, 27)

**Files Created:**
- `scripts/check_test_books.py` - Database inspection script
- `scripts/delete_test_books.py` - Database cleanup script

**Next Steps/Notes:**
- Both scripts can be reused for future database cleanup
- All test books had creation date of 2025-11-24 and very small word counts (2-7 words)
- CASCADE foreign key constraints ensured related data was properly cleaned up

---

### Test Suite Fixes - TTS Integration Test Mocking - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Fix all failing TTS integration tests by adding mocking to eliminate dependency on running backend server.

**Problem:**
- Tests were making real HTTP requests to `http://localhost:5001/api/tts/generate`
- Tests failing with connection errors when backend server not running
- Tests getting cached results instead of expected streaming responses
- Violated test isolation principle - integration tests should use mocks

**Changes Made:**
1. Modified `tests/test_tts_streaming.py::test_tts_streaming_backend()`:
   - Added `@patch('requests.head')` and `@patch('requests.post')` decorators
   - Mocked POST response to return streaming data with 3 audio chunks
   - Mocked HEAD responses to simulate chunk availability checks
   - Changed timeout assertion from `< 5s` to `< 1s` for mocked responses
   - Removed try/except blocks and used direct assertions
   - Lines 27-104

2. Modified `tests/test_tts_streaming.py::test_tts_single_file()`:
   - Added `@patch('requests.post')` decorator
   - Mocked POST response to return non-streaming single file response
   - Removed try/except blocks and used direct assertions
   - Lines 107-146

3. Already completed in previous session: `test_streaming_performance()` (lines 156-232)

**Technical Details:**
- Used `unittest.mock.Mock` and `@patch` decorators from existing imports
- Mock responses configured with `status_code` and `json.return_value` attributes
- `mock_post.return_value` for single responses
- `mock_post.side_effect` for multiple sequential responses (already used in test_streaming_performance)
- Tests now run reliably without network dependencies

**Results:**
- All 102 tests passing (previously 101 passing, 1 failing)
- Test execution time: ~188 seconds (3:08)
- No dependency on running backend server
- Proper test isolation achieved
- No flaky failures due to caching or network issues

**Files Modified:**
- `tests/test_tts_streaming.py` (lines 27-146)

**Test Suite Summary:**
- 102 total tests
- 0 failures
- 0 warnings
- Tests cover: bulk summary parsing, batching, chapter detection, database operations, Gutenberg integration, LLM helpers, rate limiting, and TTS streaming

**Next Steps/Notes:**
- Test suite is now fully passing and properly isolated
- All TTS tests use mocking instead of real HTTP requests
- Database tests use UUID-based temporary files for isolation
- LLM helper tests have proper mocking for Database and genai.Client dependencies

---

### Process "The Time Machine" Book - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Complete processing of "The Time Machine" by H. G. Wells, generating all summary types including comprehensive chapter-by-chapter summary.

**Initial State:**
- Book already existed in database (ID: 28)
- Had concise (484 words) and medium (3,857 words) summaries
- Missing comprehensive summary with chapters
- Book file (pg35.txt) was not in data/books directory

**Actions Taken:**
1. Downloaded book from Project Gutenberg (pg35.txt, ~180KB)
2. Ran summary generation script with virtual environment
3. Generated comprehensive summary with chapter breakdown

**Results:**
- Book: The Time Machine by H. G. Wells
- Word count: 32,453 words
- Summaries generated:
  - Concise: 409 words (regenerated)
  - Medium: 2,848 words (regenerated)
  - Comprehensive: 1 chapter summary (1,428 words)
- Chapter detection: Treated as single narrative (99.5% content coverage)
- Processing time: ~34 seconds

**Technical Details:**
- Used Gemini 2.5 Flash model for all summaries
- Book treated as single chapter (appropriate for this novella)
- Bulk chapter summary generation used for efficiency
- Results saved to: `data/summaries/pg35_summaries.json`
- Database updated with all new summaries

**Files Created:**
- `scripts/list_books.py` - Utility to list all books in database
- `scripts/check_book_summaries.py` - Utility to check summaries for specific book

**Next Steps/Notes:**
- ⚠️ ISSUE IDENTIFIED: Only 1 chapter detected instead of expected 17 chapters (16 numbered + Epilogue)
- Chapter detection failed due to multi-line chapter header format
- See next entry for fix and regeneration

---

### Fix Chapter Detection for Multi-Line Headers - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Fix chapter detection to handle multi-line chapter headers in "The Time Machine" and other books with similar formatting, then regenerate summaries with proper chapter breakdown.

**Problem Identified:**
- Initial processing detected only 1 chapter instead of 17
- "The Time Machine" uses multi-line chapter format:
  ```
   I.
   Introduction
  ```
- Existing regex pattern `r'^([IVXLCDM]+)\.\s+(.+)$'` required title on same line
- Epilogue not detected (no pattern existed for it)
- Epilogue was being converted as Roman numeral "IL" = 49

**Changes Made:**

1. **Added multi-line chapter pattern** (`scripts/generate_summaries.py:429`):
   - New pattern: `r'^([IVXLCDM]+)\.$'` to match Roman numeral with period only
   - Placed before existing pattern to match first
   - Existing continuation logic (lines 591-594) picks up title from next line

2. **Added Epilogue detection** (`scripts/generate_summaries.py:436-437`):
   - Added patterns: `r'^(EPILOGUE)$'` and `r'^(Epilogue)$'`
   - Handles standalone Epilogue sections

3. **Added Epilogue special handling** (`scripts/generate_summaries.py:616-619`):
   - Epilogue gets chapter number 999 (after all numbered chapters)
   - Default title "Epilogue" if not specified
   - Prevents incorrect Roman numeral conversion

4. **Created testing utilities**:
   - `scripts/test_chapter_detection.py` - Dry run chapter detection without API calls
   - Shows detected chapters, word counts, and content coverage
   - `scripts/list_books.py` - Already existed

**Testing Results:**
- Dry run confirmed 17 chapters detected (16 numbered + Epilogue)
- Content coverage: 99.5% (excellent)
- All chapters properly titled from table of contents

**Regeneration Results:**
- Book: The Time Machine by H. G. Wells (ID: 28)
- Word count: 32,453 words
- Summaries regenerated:
  - Concise: 432 words
  - Medium: 3,846 words
  - Comprehensive: 17 chapter summaries
- Chapter breakdown:
  - Chapter 0: Introduction
  - Chapters 2-16: The Machine through After the Story (Roman numerals II-XVI)
  - Chapter 999: Epilogue
- Batch processing: 4 batches for 17 chapters
  - Batch 1: Chapters 0-5 (5 chapters, 1,249 words total)
  - Batch 2: Chapters 6-8 (3 chapters, 1,687 words total)
  - Batch 3: Chapters 9-12 (4 chapters, 2,585 words total)
  - Batch 4: Chapters 13-999 (5 chapters including Epilogue, 1,336 words total)
- Processing time: ~3.5 minutes

**Technical Details:**
- Pattern matching order matters - specific patterns must come before general ones
- Roman numeral converter (`roman_to_int`) extracts any valid Roman letters
- Chapter numbering: 0 for intro, 1-16 for main chapters, 999 for epilogue
- Bulk summary generation batches chapters efficiently (4-5 chapters per batch)
- Gemini 2.5 Flash model used for all summaries

**Files Modified:**
- `scripts/generate_summaries.py` (lines 429, 436-437, 616-619)

**Files Created:**
- `scripts/test_chapter_detection.py` - Chapter detection testing utility

**Impact:**
- Fix applies to all books with multi-line chapter headers
- Epilogue detection now works universally
- More accurate chapter breakdown for better reading experience
- Improved summary quality with proper chapter granularity

**Next Steps/Notes:**
- ⚠️ ISSUE IDENTIFIED: "Introduction" treated as Chapter 0 (preface) instead of Chapter 1
- Chapter numbering doesn't match TOC (Chapters 0, 2-16, 999 instead of 1-17)
- See next entry for database correction

---

### Fix The Time Machine Chapter Numbering - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Correct chapter numbering in database to match Table of Contents, treating "Introduction" as Chapter I (Chapter 1) instead of a preface (Chapter 0).

**Problem Identified:**
- Script incorrectly treated "Introduction" as a preface (Chapter 0)
- Pattern `r'^(INTRODUCTION)$'` caused it to be assigned chapter number 0
- Epilogue was assigned chapter number 999 instead of 17
- Chapter numbering was: 0, 2-16, 999 (should be 1-17)

**Solution:**
- Created `scripts/fix_time_machine_chapters.py` to update database directly
- Manual correction rather than regenerating (saves API calls)
- Updated chapter numbers and titles based on TOC

**Database Updates:**
- Chapter 0 → Chapter 1: "Introduction & Prefaces" → "Introduction"
- Chapters 2-16: No number change, titles already correct
- Chapter 999 → Chapter 17: "Epilogue" (no title change)

**Results:**
```
Chapter 1: Introduction
Chapter 2: The Machine
Chapter 3: The Time Traveller Returns
Chapter 4: Time Travelling
Chapter 5: In the Golden Age
Chapter 6: The Sunset of Mankind
Chapter 7: A Sudden Shock
Chapter 8: Explanation
Chapter 9: The Morlocks
Chapter 10: When Night Came
Chapter 11: The Palace of Green Porcelain
Chapter 12: In the Darkness
Chapter 13: The Trap of the White Sphinx
Chapter 14: The Further Vision
Chapter 15: The Time Traveller's Return
Chapter 16: After the Story
Chapter 17: Epilogue
```

**Technical Details:**
- Direct SQL UPDATE on chapters table
- Updated both chapter_number and chapter_title columns
- Used book_id = 28 (The Time Machine)
- Total updates: 17 chapters (3 with changes: 0→1, 999→17, and title fix for ch1)

**Files Created:**
- `scripts/fix_time_machine_chapters.py` - Database update utility

**Verification:**
- All 17 chapters numbered sequentially 1-17
- All titles match TOC exactly
- Introduction correctly recognized as Chapter I, not preface

**Next Steps/Notes:**
- Book is now correctly processed with proper chapter numbering
- Future improvement: Update chapter detection logic to not treat "Introduction" as preface when it appears in TOC as Chapter I (see next entry)
- Testing utility can be used for other books with chapter detection issues
- Consider adding patterns for other chapter formats if needed (e.g., "Part I", "Section I")

---

### Chapter Detection Logic Improvements - IN PROGRESS
**Status:** ⏸ In Progress (Core logic implemented, tests need refinement)
**Started:** 2025-11-24

**Objective:** Update generate_summaries.py to automatically detect when "Introduction" is a numbered chapter (not a preface) and number Epilogue sequentially.

**Changes Made:**

1. **TOC-aware Introduction detection** (`scripts/generate_summaries.py:613-633`):
   - Check TOC first before assigning Chapter 0 to INTRODUCTION/PREFACE   - If "Introduction" appears in TOC with a Roman numeral, use that number
   - Only treat as Chapter 0 (preface) if not in TOC or no TOC exists
   - Prints debug message when TOC number is found

2. **Sequential Epilogue numbering** (`scripts/generate_summaries.py:901-914`):
   - Find highest non-Epilogue chapter number
   - Renumber Epilogue from 999 to next sequential number
   - Ensures Epilogue appears at end in proper order

3. **Avoid double-processing continuations** (`scripts/generate_summaries.py:457-464, 606-612`):
   - Track lines consumed as chapter title continuations in `consumed_lines` set
   - Skip consumed lines in main loop to avoid detecting same text twice
   - Fixes issue where "I. / Introduction" would be detected both as Chapter I and as standalone Introduction

4. **Pattern order optimization** (`scripts/generate_summaries.py:431-438`):
   - Moved EPILOGUE patterns before INTRODUCTION/PREFACE patterns
   - Added comments clarifying that INTRODUCTION/PREFACE are validated against TOC

**Test Cases Created:**
- `tests/test_chapter_numbering.py`:
  - test_introduction_as_chapter_one - Validates "I Introduction" treated as Chapter 1
  - test_introduction_as_preface_without_toc - Validates standalone Introduction as Chapter 0
  - test_epilogue_numbering - Validates Epilogue numbered sequentially

**Current Status:**
- Core logic implemented and working for real book (The Time Machine)
- Database already fixed manually with correct numbering (Chapters 1-17)
- Tests created but not fully passing yet (TOC extraction needs improvement for short test cases)
- Real-world usage confirmed working (The Time Machine processed correctly)

**Known Issues:**
- extract_toc() function may not work properly with minimal test cases
- Test cases may need more realistic book structure (longer CONTENTS section, etc.)
- Some edge cases in TOC matching need refinement

**Files Modified:**
- `scripts/generate_summaries.py` (lines 431-438, 457-464, 606-612, 613-633, 901-914)

**Files Created:**
- `tests/test_chapter_numbering.py` - Test suite for chapter numbering logic
- `scripts/debug_chapter_test.py` - Debug utility for troubleshooting
- `scripts/fix_time_machine_chapters.py` - One-time database fix utility

**Next Steps:**
- Refine tests to work with extract_toc function (may need more realistic test data)
- Consider making TOC extraction more robust for edge cases
- Run full test suite to ensure no regressions
- Test with other books that have "Introduction" chapters

---

### TTS Character Limit Increase - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Increase TTS character limit to handle longer chapters and improve text quality for speech synthesis.

**Changes Made:**
1. Updated character limit in `backend/tts_handler.py`:
   - Increased from 20,000 to 30,000 characters
   - Improved comment to clarify purpose: "Handle long chapters with higher limit for TTS"
   - Line 224

**Technical Details:**
- Higher limit allows processing of longer chapters without truncation
- Maintains word boundary truncation logic for readability
- Coqui TTS can handle longer texts efficiently

**Files Modified:**
- `backend/tts_handler.py` (line 224)

**Impact:**
- Better coverage for long-form content
- Fewer chapters need to be split or truncated
- Improved user experience for comprehensive summaries

---

### TTS Text Cleaning Enhancement - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Improve TTS audio quality by preserving natural punctuation while removing only formatting structures and markdown.

**Problem:**
- Previous implementation removed too many characters including natural punctuation
- This caused poor speech phrasing and unnatural pauses in TTS output
- Formatting characters (backticks, brackets, etc.) were being read as text

**Changes Made:**
1. Updated `clean_text_for_speech()` method in `backend/tts_handler.py`:
   - **Keep**: Natural punctuation for speech phrasing: . , ! ? ; : ' " -
   - **Remove**: Formatting characters: ` _ ( ) { } [ ] / \ | @ # $ % ^ & * + = ~ < >
   - Added detailed comment explaining the distinction (lines 112-115)
   - Line 115: Updated regex pattern

2. Also updated in `backend/gemini_tts_handler.py`:
   - Applied same text cleaning logic for consistency
   - Line 129: Updated regex pattern

**Technical Details:**
- Punctuation provides natural pauses and intonation cues for TTS engine
- Removing only formatting characters eliminates jitter-causing symbols
- Speech quality significantly improved with proper punctuation retention

**Files Modified:**
- `backend/tts_handler.py` (lines 112-115)
- `backend/gemini_tts_handler.py` (line 129)

**Impact:**
- More natural-sounding speech with proper pausing and phrasing
- Better listener comprehension
- Reduced TTS jitter from formatting characters

---

### The Time Machine Cover Art Update - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Update The Time Machine book cover to custom artwork.

**Problem:**
- Initial implementation used incorrect path format with `/static/` prefix
- Frontend was adding `/static/` prefix automatically, causing double `/static//static/` in URL
- Database path format needed to match other books (relative path without `/static/`)

**Changes Made:**
1. Created `scripts/update_time_machine_cover.py`:
   - Copies custom cover image from Downloads folder to covers directory
   - Updates database with correct relative path format
   - Finds book by title match (handles "The Time Machine" or partial matches)

**Technical Details:**
- Source: `/Users/pengyao/Downloads/9EDF63EA-B2FB-4B48-91AC-E55312121C63.png`
- Destination: `frontend/static/covers/time_machine_custom.png`
- Database path: `covers/time_machine_custom.png` (NOT `/static/covers/...`)
- Path format matches existing books in database

**Fixes Applied:**
- **Issue 1**: ModuleNotFoundError for config module
  - Fixed by adding both project root and backend directory to sys.path
- **Issue 2**: Incorrect path format causing `/static//static/` double prefix
  - Fixed by using relative path `covers/time_machine_custom.png`

**Files Created:**
- `scripts/update_time_machine_cover.py` - Cover update utility
- `frontend/static/covers/time_machine_custom.png` - Custom cover image

**Results:**
- Cover image successfully displayed on book listing page
- Path format consistent with other books in database
- No URL doubling issues

---

### Gemini TTS Offline Generation System - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Create offline TTS generation system using Google Gemini 2.5 Flash TTS API with rate limiting, allowing batch generation of high-quality audio files for book summaries and chapters.

**Requirements:**
- 3 requests per minute rate limit
- 10,000 tokens per minute rate limit
- Use existing GEMINI_API_KEY
- Store WAV files in same location as VITS TTS
- Make audio accessible through existing UI
- Gemini TTS only for offline generation (user-triggered TTS uses VITS)
- Support multiple voices (Puck, Charon, Kore, Fenrir, Aoede)

**Changes Made:**

1. **Updated `backend/config.py`** (lines 50-58):
   - Added Gemini TTS configuration section
   - Model: `gemini-2.5-flash-tts`
   - Default voice: `Puck`
   - Rate limits: 3 requests/min, 10k tokens/min
   - TTS output directory: `frontend/static/audio`

2. **Created `backend/gemini_tts_handler.py`** (229 lines):
   - `RateLimiter` class (lines 21-61):
     - Tracks requests and tokens over rolling 60-second windows
     - `wait_if_needed()`: Automatically sleeps when approaching limits
     - `record_request()`: Records completed requests with token counts
   - `GeminiTTSHandler` class (lines 63-228):
     - Initializes Google Generative AI client with API key
     - `estimate_tokens()`: Estimates token count (~4 chars per token)
     - `clean_text_for_speech()`: Removes markdown/formatting, preserves punctuation
     - `generate_audio()`: Main generation method with rate limiting
       - Generates unique filenames with `_gemini.wav` suffix
       - Implements file caching (skips if audio exists)
       - Calls Gemini TTS API with voice configuration
       - Extracts and saves WAV audio data
       - Returns path to generated audio file

3. **Created `scripts/generate_offline_tts.py`** (242 lines):
   - Command-line script for batch TTS generation
   - Argument parsing with argparse:
     - `--book`: Book title or ID (required)
     - `--summaries`: Summary types to generate (concise, medium, comprehensive)
     - `--all-summaries`: Generate TTS for all summary types
     - `--comprehensive-chapters`: Chapter numbers for comprehensive summary (e.g., "1-5")
     - `--voice`: Voice to use (Puck, Charon, Kore, Fenrir, Aoede)
   - `parse_chapter_range()`: Parses ranges like "1-5" or "1,3,5-7"
   - `generate_summary_audio()`: Generates audio for specific summary type
   - `generate_chapter_audio()`: Generates audio for multiple chapters
   - Database integration: Stores audio paths in `audio_files` table
   - Progress tracking and error reporting

**Technical Details:**

**Rate Limiting Implementation:**
```python
class RateLimiter:
    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.request_times = []  # Timestamps of requests
        self.token_counts = []   # (timestamp, token_count) tuples

    def wait_if_needed(self, estimated_tokens: int):
        # Clean old entries (older than 60 seconds)
        # Check request count, wait if at limit
        # Check token count, wait if at limit
```

**Audio File Naming:**
- Summaries: `summary_{book_id}_{summary_type}_gemini.wav`
- Chapters: `chapter_{book_id}_{chapter_number}_gemini.wav`
- `_gemini.wav` suffix distinguishes from VITS TTS files

**API Integration:**
```python
response = self.client.models.generate_content(
    model='gemini-2.5-flash-tts',
    contents=cleaned_text,
    config=types.GenerateContentConfig(
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=self.voice
                )
            )
        )
    )
)
```

**Usage Examples:**
```bash
# Generate TTS for specific summary types
python scripts/generate_offline_tts.py --book "The Time Machine" --summaries concise medium

# Generate TTS for comprehensive summary chapters
python scripts/generate_offline_tts.py --book "Alice's Adventures in Wonderland" --comprehensive-chapters 1-5

# Generate TTS for all summaries of a book
python scripts/generate_offline_tts.py --book "Pride and Prejudice" --all-summaries

# Specify custom voice
python scripts/generate_offline_tts.py --book "The Odyssey" --summaries concise --voice Charon
```

**Database Schema Integration:**
- Uses existing `audio_files` table
- Foreign keys: `summary_id` or `chapter_id`
- Stores `audio_path` (relative path for UI access)
- Duration field (set to 0.0, can be calculated later if needed)

**Files Created:**
- `backend/gemini_tts_handler.py` (229 lines) - TTS handler with rate limiting
- `scripts/generate_offline_tts.py` (242 lines) - Batch generation script

**Files Modified:**
- `backend/config.py` (lines 50-58) - Added Gemini TTS configuration

**Dependencies:**
- `google-genai` package (already in requirements)
- Uses same `GEMINI_API_KEY` as summary generation

**Testing Status:**
- Implementation complete and ready to use
- Not yet tested with real API calls
- Rate limiting logic verified in code review
- Database integration follows existing patterns

**Next Steps/Notes:**
- Test with a small book to verify API integration
- Monitor rate limiting behavior with actual API calls
- Consider adding audio duration calculation
- May want to add batch processing for multiple books
- Consider adding retry logic for failed API calls

**Impact:**
- Enables high-quality offline TTS generation for entire library
- Separate from real-time VITS TTS (user-triggered)
- Professional voice options (5 different voices)
- Efficient batch processing with rate limiting
- Seamless UI integration (same audio_files table)

---

### Huckleberry Finn Chapter Title Backfill - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Fix incorrect chapter titles for "Adventures of Huckleberry Finn" by parsing table of contents and updating database without making any LLM calls.

**Problem:**
- Initial chapter detection created generic titles ("Chapter 1", "Chapter 2", etc.)
- Table of contents contained descriptive multi-line titles that should be used
- User explicitly requested: "Don't make any LLM calls. Let's backfill the Chapter names based on the table of content"

**Solution:**
Created `scripts/fix_huck_finn_chapters.py` to parse TOC and update database directly.

**Changes Made:**

1. **Created `scripts/fix_huck_finn_chapters.py`** (165 lines):
   - `roman_to_int()`: Converts Roman numerals to integers (lines 19-38)
     - Handles subtraction rule (IV=4, IX=9, XL=40, etc.)
   - `parse_toc_from_book()`: Extracts chapter titles from table of contents (lines 41-98)
     - Detects TOC start with `CONTENTS.` marker
     - Detects TOC end with `ILLUSTRATIONS.` marker
     - Matches chapter headers: `CHAPTER [ROMAN_NUMERAL].`
     - Collects multi-line title parts
     - Joins title parts with `.—` separator
     - Special handling for "CHAPTER THE LAST" as chapter 43
   - `main()`: Updates database with TOC titles (lines 101-164)
     - Parses TOC from book file
     - Gets book ID from database
     - Compares current titles with TOC titles
     - Updates only changed titles
     - Reports all updates

**Technical Details:**

**TOC Format:**
```
CONTENTS.

CHAPTER I.
Civilizing Huck.—Miss Watson.—Tom Sawyer Waits.

CHAPTER II.
The Boys Escape Jim.—Torn Sawyer's Gang.—Deep-laid Plans.
...
```

**Multi-line Parsing:**
- Chapter marker: `CHAPTER I.`
- Title lines collected until next chapter or end marker
- Parts joined with `.—` to preserve formatting
- Example: `"Civilizing Huck.—Miss Watson.—Tom Sawyer Waits"`

**Database Update:**
```python
cursor.execute(
    "UPDATE chapters SET chapter_title = ? WHERE book_id = ? AND chapter_number = ?",
    (toc_title, book_id, chapter_num)
)
```

**Results:**
- Found 43 chapters in TOC (I through XLII plus "CHAPTER THE LAST")
- Updated all 42 chapters in database (CHAPTER THE LAST not present as separate chapter)
- No LLM calls made (as explicitly requested)
- Processing time: <1 second

**Example Updates:**
- Chapter 1: "Chapter 1" → "Civilizing Huck.—Miss Watson.—Tom Sawyer Waits"
- Chapter 2: "Chapter 2" → "The Boys Escape Jim.—Torn Sawyer's Gang.—Deep-laid Plans"
- Chapter 10: "Chapter 10" → "What Comes of Handlin' Snakeskin.—The Vigilantes.—And a Steamboat Fight"
- Chapter 42: Generic → "Tom Sawyer Wounded.—The Doctor's Story.—Tom Confesses.—Aunt Polly.—Arrives.—Hand Out Them Letters"

**Files Created:**
- `scripts/fix_huck_finn_chapters.py` (165 lines) - TOC parser and database updater

**Files Modified:**
- Database: Updated 42 chapter titles in `chapters` table

**Verification:**
All chapter titles now match the table of contents exactly.

**Next Steps/Notes:**
- This is a one-time backfill script specific to Huckleberry Finn
- Similar approach can be used for other books if chapter detection fails
- Consider improving chapter detection logic in `generate_summaries.py` to handle multi-line TOC entries automatically

---

### Huckleberry Finn "CHAPTER THE LAST" Detection - COMPLETED
**Status:** ✓ Completed
**Started:** 2025-11-24
**Completed:** 2025-11-24

**Objective:** Add Chapter 43 detection for "CHAPTER THE LAST" marker in Huckleberry Finn and regenerate the missing chapter summary.

**Problem:**
- Initial chapter detection only found 42 chapters, missing Chapter 43
- Book uses "CHAPTER THE LAST" instead of "CHAPTER XLIII" for the final chapter
- User requested: "Parse the book for 'CHAPTER THE LAST' as the Chapter 43."

**Solution:**
Extended chapter detection regex patterns and special handling logic in `generate_summaries.py`.

**Changes Made:**

1. **Modified `scripts/generate_summaries.py`**:
   - **Line 431** - Added regex pattern to detect "CHAPTER THE LAST":
     ```python
     r'^(CHAPTER\s+THE\s+LAST)\.?$',  # "CHAPTER THE LAST" or "CHAPTER THE LAST."
     ```
   - **Lines 654-658** - Added special handling logic:
     ```python
     elif 'CHAPTER' in chapter_marker.upper() and 'THE' in chapter_marker.upper() and 'LAST' in chapter_marker.upper():
         # "CHAPTER THE LAST" - assign chapter number 43
         base_chapter_num = 43
         if not chapter_title:
             chapter_title = "Chapter the Last"
     ```

2. **Regenerated Chapter 43**:
   - Command: `python scripts/generate_summaries.py data/books/huckleberry_finn.txt --title "Adventures of Huckleberry Finn" --author "Mark Twain" --regenerate-chapters "43"`
   - Successfully generated chapter summary with 361 words (2,318 chars)

**Technical Details:**
- Pattern matching order ensures "CHAPTER THE LAST" is matched before generic patterns
- Special chapter numbering (43) assigned to avoid conflict with Roman numeral conversion
- Chapter title from TOC: "Out of Bondage.—Paying the Captive.—Yours Truly, Huck Finn."

**Results:**
- Chapter 43 successfully added to database
- Book now has complete set of 43 chapters (1-43)
- All chapter titles match table of contents

**Files Modified:**
- `scripts/generate_summaries.py` (lines 431, 654-658)
- Database: Added Chapter 43 to `chapters` table

**Final Book Status:**
"Adventures of Huckleberry Finn" (Book ID: 29) is now fully processed:
- Concise summary: 404 words
- Medium summary: 2,960 words
- Comprehensive summary: 43 chapter summaries with descriptive TOC titles
- Cover image: from Project Gutenberg (eBook #76)

**Impact:**
- Improved chapter detection for books with non-standard ending chapters
- Pattern can be reused for other classic literature with similar formatting
- Demonstrates ability to handle special cases without reprocessing entire book

---
