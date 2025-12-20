# Summra - Technical Implementation Details

This document provides in-depth technical documentation for the Summra project, including entity relationship diagrams, detailed algorithm implementations, and code-level architecture. This is intended for developers and for providing context to future Claude Code sessions.

## Table of Contents

1. [Database Schema & ERD](#database-schema--erd)
2. [SEO Architecture](#seo-architecture)
3. [Related Books System](#related-books-system)
4. [Chapter Parser Implementation](#chapter-parser-implementation)
5. [TTS Engine Implementation](#tts-engine-implementation)
6. [LLM Call Logic & Rate Limiting](#llm-call-logic--rate-limiting)
7. [Bulk Summary Processing](#bulk-summary-processing)
8. [Project Gutenberg Integration](#project-gutenberg-integration)
9. [Gemini Image Generation System](#gemini-image-generation-system)
10. [Book Metadata Enrichment](#book-metadata-enrichment)
11. [Discover Page Architecture](#discover-page-architecture-added-2025-12-11)
12. [Blog Header Images & Unsplash Integration](#blog-header-images--unsplash-integration)
13. [Pagination System](#pagination-system-added-2025-12-19)

---

## Database Schema & ERD

### Entity Relationship Diagram

```
                                    ┌─────────────────────────┐
                                    │       authors           │
                                    │  (added 2025-12-02)     │
                                    ├─────────────────────────┤
                                    │ id (PK)                 │
                                    │ name (UNIQUE)           │
                                    │ country                 │
                                    │ bio                     │
                                    │ other_books             │
                                    │ created_at              │
                                    └─────────────────────────┘
                                              │
                                              │ 1:N
                                              ▼
┌─────────────────────────┐         ┌─────────────────────────┐         ┌─────────────────────────┐
│    categories           │         │       books             │         │   similar_books         │
│                         │         │                         │         │  (added 2025-12-02)     │
├─────────────────────────┤         ├─────────────────────────┤         ├─────────────────────────┤
│ id (PK)                 │         │ id (PK)                 │         │ id (PK)                 │
│ name (UNIQUE)           │         │ title                   │◄────────┤ book_id (FK)            │
│ description             │         │ author                  │◄────────┤ similar_book_id (FK)    │
│ created_at              │         │ author_id (FK)          │         │ rank (1-5)              │
└─────────────────────────┘         │ filename (UNIQUE)       │         │ created_at              │
         │                          │ full_text               │         └─────────────────────────┘
         │                          │ word_count              │
         │                          │ gutenberg_id            │         Many-to-many (self-ref)
         │                          │ slug (UNIQUE)           │         Stores LLM-generated
         │                          │ cover_image_url         │         book recommendations
         │                          │ cover_source            │
         │                          │ about_text              │
         │                          │ relevance_now           │
         │ N:N                      │ created_at              │
         │                          │ updated_at              │
         │                          └─────────────────────────┘
         │                                    │
         │                                    │ 1:N
         │                                    │
         │                                    ├──────────────────────────┬──────────────────────────┬──────────────────────────┐
         │                                    │                          │                          │                          │
         ▼                                    ▼                          ▼                          ▼                          ▼
┌─────────────────────┐            ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  book_categories    │            │    summaries        │    │   book_sections     │    │     chapters        │    │   audio_files       │
├─────────────────────┤            ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│ id (PK)             │            │ id (PK)             │    │ id (PK)             │    │ id (PK)             │    │ id (PK)             │
│ book_id (FK)        │            │ book_id (FK)        │    │ book_id (FK)        │    │ book_id (FK)        │    │ summary_id (FK)     │
│ category_id (FK)    │            │ summary_type        │    │ section_type        │    │ section_id (FK)     │◄───┼─┤ chapter_id (FK)     │
│ created_at          │            │ content             │    │ section_number      │    │ chapter_number      │    │ file_path           │
└─────────────────────┘            │ word_count          │    │ section_title       │    │ chapter_title       │    │ duration_seconds    │
         ▲                         │ created_at          │    │ created_at          │    │ summary             │    │ created_at          │
         │                         └─────────────────────┘    └─────────────────────┘    │ full_text           │    └─────────────────────┘
         │                                  │                          │                 │ word_count          │
         │                                  │                          │                 │ illustration_url    │
         └──────────────────────────────────┴──────────────────────────┘                 │ created_at          │
                                                                                         └─────────────────────┘

┌─────────────────────────┐
│     blog_posts          │
│  (added 2025-12-12)     │
├─────────────────────────┤
│ id (PK)                 │
│ slug (UNIQUE)           │
│ title                   │
│ content                 │
│ excerpt                 │
│ author                  │
│ published_date          │
│ updated_date            │
│ header_image_url        │
│ created_at              │
└─────────────────────────┘

Standalone table for blog content.
No foreign key relationships.

UNIQUE Constraints:
- books: (filename), (slug)
- authors: (name)
- categories: (name)
- summaries: (book_id, summary_type)
- book_sections: (book_id, section_number)
- chapters: (book_id, chapter_number)
- book_categories: (book_id, category_id)
- similar_books: (book_id, similar_book_id)
- blog_posts: (slug)

Foreign Keys:
- books.author_id → authors.id
- summaries.book_id → books.id
- book_sections.book_id → books.id
- chapters.book_id → books.id
- chapters.section_id → book_sections.id
- audio_files.summary_id → summaries.id
- audio_files.chapter_id → chapters.id
- book_categories.book_id → books.id
- book_categories.category_id → categories.id
- similar_books.book_id → books.id
- similar_books.similar_book_id → books.id

Notes:
- section_id in chapters is nullable (NULL for single-level books)
- similar_books is self-referential (book_id and similar_book_id both reference books table)
- Enhanced metadata fields added 2025-12-02: about_text, relevance_now, author country, similar books
```

### Table Definitions

#### books Table

```sql
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    author_id INTEGER,  -- FK to authors table (added 2025-12-02 for SEO)
    filename TEXT UNIQUE NOT NULL,
    full_text TEXT,
    word_count INTEGER,
    gutenberg_id INTEGER,
    slug TEXT UNIQUE,  -- SEO-friendly URL slug (added 2025-12-02)
    cover_image_url TEXT,
    cover_source TEXT DEFAULT 'unknown',  -- 'custom', 'gutenberg', or 'unknown'
    -- SEO Content Fields (added 2025-12-02)
    about_text TEXT,  -- Editorial "About the Book" section (150-200 words)
    publication_year INTEGER,  -- Publication year for metadata
    literary_period VARCHAR(100),  -- e.g., "Victorian", "Modernist", "Romantic"
    notable_themes TEXT,  -- JSON array of key themes
    historical_context TEXT,  -- Historical background (2-3 sentences)
    why_important TEXT,  -- Literary significance (2-3 sentences)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES authors(id)
)
```

**Cover Management:**
- `cover_image_url`: Relative path to cover image (e.g., `covers/1.png`)
- `cover_source`: Tracks origin of cover ('custom' for uploaded, 'gutenberg' for auto-fetched)
- **Naming convention**: Book covers use `{book_id}.{ext}` format (e.g., `1.png`, `2.jpg`)
- **Large covers**: Originals >1.5MB stored in `data/cover_originals/` (gitignored), web versions resized to ~1MB
- **Chapter illustrations**: Stored in hierarchical directory structure `frontend/static/illustrations/{book_id}/{chapter_num}.{ext}` (added 2025-12-01)

**Indexes:**
- Primary key on `id` (auto-indexed)
- Unique index on `filename` (auto-created from UNIQUE constraint)
- Unique index on `slug` (added 2025-12-02 for SEO-friendly URLs)
- Index on `author_id` (added 2025-12-02 for author page queries)

**Purpose:** Stores complete book metadata, full text content, and SEO-optimized editorial content.

**SEO Fields (added 2025-12-02):**
- `slug`: URL-friendly identifier (e.g., "pride-and-prejudice")
- `about_text`: Human-written editorial content for E-E-A-T signals
- `publication_year`: Enables historical context filtering and display
- `literary_period`: Supports period-based topic clusters
- `notable_themes`: JSON array for theme-based discovery
- `historical_context`: Adds depth beyond AI summaries
- `why_important`: Demonstrates literary expertise
- `author_id`: Links to authors table for author hub pages

#### summaries Table

```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    summary_type TEXT NOT NULL CHECK(summary_type IN ('concise', 'medium', 'comprehensive')),
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, summary_type)
)
```

**Indexes:**
- Primary key on `id`
- Unique composite index on `(book_id, summary_type)`

**Purpose:** Stores the three types of summaries (concise, medium, comprehensive overall).

**Note:** Comprehensive overall summaries are currently disabled (empty strings saved), but the schema supports them for future use.

#### book_sections Table (Added 2025-11-27)

```sql
CREATE TABLE book_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    section_type TEXT NOT NULL,        -- 'PART', 'BOOK', 'ACT', etc.
    section_number INTEGER NOT NULL,   -- 1, 2, 3, etc.
    section_title TEXT,                -- e.g., "The Old Buccaneer", "1805"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, section_number)
)
```

**Indexes:**
- Primary key on `id`
- Unique composite index on `(book_id, section_number)`

**Purpose:** Stores two-level book structure information (PART/BOOK/ACT organization).

**Examples:**
- Treasure Island: 6 sections (PART ONE - PART SIX)
- War and Peace: 15 sections (BOOK ONE - BOOK FIFTEEN)
- Romeo and Juliet: 5 sections (ACT I - ACT V)

**Note:** Only populated for books with detected hierarchical structure. Single-level books have no entries in this table.

#### chapters Table

```sql
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    section_id INTEGER,                -- NULL for single-level books
    chapter_number INTEGER NOT NULL,   -- Sequential numbering (1, 2, 3...)
    chapter_title TEXT,
    summary TEXT NOT NULL,
    full_text TEXT,
    word_count INTEGER,
    illustration_url TEXT,             -- Path to chapter illustration image (added 2025-12-01)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES book_sections(id),
    UNIQUE(book_id, chapter_number)
)
```

**Indexes:**
- Primary key on `id`
- Unique composite index on `(book_id, chapter_number)`

**Purpose:** Stores individual chapter summaries and full chapter text.

**Chapter Numbering (Updated 2025-12-01):**
- **Sequential numbering:** All books use sequential numbering (1, 2, 3, ...) regardless of structure
- **Section association:** Two-level books link chapters to sections via `section_id` FK
  - Example: Part 1, Chapter 1 = 1, Part 1, Chapter 2 = 2, Part 2, Chapter 1 = 3
  - Section structure preserved through `section_id` relationship, not encoded in chapter number

**Special Note:** The UNIQUE constraint on `(book_id, chapter_number)` enables `INSERT OR REPLACE` semantics for chapter regeneration mode.

#### audio_files Table

```sql
CREATE TABLE audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id INTEGER,
    chapter_id INTEGER,
    file_path TEXT NOT NULL,
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (summary_id) REFERENCES summaries(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    CHECK((summary_id IS NOT NULL AND chapter_id IS NULL) OR
          (summary_id IS NULL AND chapter_id IS NOT NULL))
)
```

**Indexes:**
- Primary key on `id`
- Foreign key indexes on `summary_id` and `chapter_id`

**Purpose:** Stores TTS-generated audio files linked to either a summary or a chapter.

**Constraint:** Audio file must be linked to EITHER a summary OR a chapter, not both or neither.

#### authors Table

```sql
CREATE TABLE authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    country TEXT,
    bio TEXT,
    other_books TEXT,  -- JSON array of other notable works (max 10, format changed from comma-separated to JSON 2025-12-04)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Indexes:**
- Primary key on `id`
- Unique index on `name` (auto-created from UNIQUE constraint)

**Purpose:** Stores author metadata including country of origin and other notable works.

**Fields (Enhanced 2025-12-02):**
- `name`: Author's full name (unique constraint prevents duplicates)
- `country`: Country of origin (e.g., "England", "United States", "France")
- `bio`: Author biography (optional, future use)
- `other_books`: Comma-separated list of author's other notable works (max 10 titles)
  - Generated by LLM during summary creation
  - Used for "Other Books by This Author" sections
  - Deduplicates when multiple books by same author are processed

**Usage:**
- Linked from `books.author_id` for relational integrity
- Enables author-based book recommendations
- Supports "Books by Country" filtering and discovery

#### similar_books Table

```sql
CREATE TABLE similar_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    similar_book_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,  -- 1-5, indicating order of similarity
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (similar_book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, similar_book_id),
    CHECK(book_id != similar_book_id)  -- Prevent self-references
)
```

**Indexes:**
- Primary key on `id`
- Index on `book_id` (for efficient recommendation queries)
- Index on `similar_book_id` (for reverse lookups)
- Unique constraint on `(book_id, similar_book_id)` (prevents duplicates)

**Purpose:** Stores book similarity relationships for recommendation features.

**Fields:**
- `book_id`: The source book (FK to books table)
- `similar_book_id`: The recommended similar book (FK to books table)
- `rank`: Order of recommendation (1 = most similar, 5 = least similar)
  - Enables "Top 5 Similar Books" queries with ORDER BY rank
  - Generated by LLM during summary creation

**Constraints:**
- `UNIQUE(book_id, similar_book_id)`: Each pair can only exist once
- `CHECK(book_id != similar_book_id)`: Book cannot be similar to itself
- Both FKs use `ON DELETE CASCADE` (cleanup when book is deleted)

**Relationship:** Many-to-many between books and books (self-referential)

**Usage Pattern:**
```python
# Get similar books for a book
similar = db.get_similar_books(book_id=1, limit=5)
# Returns: [{'title': 'Book A', 'author': 'Author A', 'rank': 1}, ...]

# Save similar books (LLM-generated)
similar_books = [
    {'title': 'Pride and Prejudice', 'author': 'Jane Austen'},
    {'title': 'Emma', 'author': 'Jane Austen'},
    ...
]
db.save_similar_books(book_id=1, similar_books=similar_books)
# Attempts fuzzy matching to existing books in database
# Only creates relationships for books that exist in our collection
```

**Matching Logic:**
- When saving similar books, attempts to match LLM recommendations to existing books
- Uses title matching + author first name fuzzy matching
- If no match found, recommendation is not stored (only tracks books we have)
- This ensures all `similar_book_id` values point to valid books in our collection

#### categories Table

```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Purpose:** Stores book genre/category taxonomy for discovery and filtering.

#### book_categories Table

```sql
CREATE TABLE book_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE(book_id, category_id)
)
```

**Purpose:** Many-to-many junction table linking books to categories. Books can have multiple categories, categories can have multiple books.

### Database Operations

#### Models Layer (models.py)

The `Database` class in `backend/models.py` provides all CRUD operations:

**Key Methods:**

```python
def add_book(self, title, author, filename, full_text=None,
             gutenberg_id=None, cover_image_url=None) -> int
```
- Inserts or updates book (based on filename uniqueness)
- Returns book_id

```python
def add_summary(self, book_id, summary_type, content) -> int
```
- Uses `INSERT OR REPLACE` semantics via UNIQUE constraint
- Automatically calculates word count

```python
def add_chapter(self, book_id, chapter_number, chapter_title,
                summary, full_text=None, section_id=None,
                illustration_url=None, modern_english_text=None) -> int
```
- Uses `INSERT OR REPLACE` via UNIQUE(book_id, chapter_number)
- **CRITICAL:** Preserves existing values when parameters are None (added 2025-12-12)
  - Prevents data loss during two-step processing (--parse-only then async batch)
  - Queries existing row before INSERT OR REPLACE
  - Uses existing chapter_text, section_id, illustration_url, modern_english_text when new values are None
- Critical for chapter regeneration mode
- Automatically calculates word count
- Optional `illustration_url` parameter for chapter illustrations (added 2025-12-01)
- Optional `section_id` parameter for two-level book structure (added 2025-12-01)
- Optional `modern_english_text` parameter for Shakespeare translations (added 2025-12-03)

```python
def get_book_by_filename(self, filename) -> dict
```
- Checks if book already exists before processing

---

## User Authentication & Progress Tracking (Added 2025-12-20)

### Overview

User authentication system with reading progress tracking stored in a separate database (`summra.db`). Supports offline operation with localStorage sync and provides persistent login sessions for PWA users.

### Database: summra.db

**Location:** `summra.db` (root directory, separate from content database)

**Purpose:** Store user accounts, authentication data, and reading progress. Separation from `database.db` keeps user data isolated from book content.

### Entity Relationship Diagram

```
┌─────────────────────────┐
│       users             │
├─────────────────────────┤
│ id (PK)                 │
│ username (UNIQUE)       │
│ password_hash           │
│ salt                    │
│ created_at              │
│ last_login              │
└─────────────────────────┘
         │
         │ 1:N
         ├──────────────────────────┬──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  reading_progress   │    │ chapter_completion  │    │  (future tables)    │
├─────────────────────┤    ├─────────────────────┤    │                     │
│ id (PK)             │    │ id (PK)             │    │ - bookmarks         │
│ user_id (FK)        │    │ user_id (FK)        │    │ - notes             │
│ book_id             │    │ book_id             │    │ - highlights        │
│ chapter_number      │    │ chapter_number      │    └─────────────────────┘
│ page_number         │    │ completed           │
│ scroll_position     │    │ completed_at        │
│ updated_at          │    │ created_at          │
└─────────────────────┘    └─────────────────────┘

UNIQUE(user_id, book_id)   UNIQUE(user_id, book_id, chapter_number)
```

### Database Schema

#### users table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `username`: Unique username (min 3 characters, case-sensitive)
- `password_hash`: SHA-256 hash of (password + salt)
- `salt`: Random 32-byte salt (hex-encoded, unique per user)
- `created_at`: Account creation timestamp
- `last_login`: Last successful login timestamp

**Security:**
- Password never stored in plaintext
- Each user has unique random salt
- Hash algorithm: SHA-256 (password + salt)
- No password recovery (reset only)

#### reading_progress table

```sql
CREATE TABLE reading_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER,
    page_number INTEGER DEFAULT 0,
    scroll_position REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id)
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table (cascading delete)
- `book_id`: Book ID (references books.id in database.db conceptually)
- `chapter_number`: Current chapter (0 = preface, NULL = no progress)
- `page_number`: Current page in paginated view (0-indexed)
- `scroll_position`: Scroll position in non-paginated view (0.0-1.0)
- `updated_at`: Last update timestamp

**Constraints:**
- UNIQUE(user_id, book_id): One progress record per user per book
- Uses `INSERT OR REPLACE` to update existing progress

#### chapter_completion table

```sql
CREATE TABLE chapter_completion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    completed INTEGER DEFAULT 1,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id, chapter_number)
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table (cascading delete)
- `book_id`: Book ID (references books.id conceptually)
- `chapter_number`: Completed chapter number
- `completed`: Boolean flag (1 = completed, 0 = reset)
- `completed_at`: Completion timestamp
- `created_at`: First completion timestamp

**Constraints:**
- UNIQUE(user_id, book_id, chapter_number): One completion record per chapter per user
- Uses `INSERT OR REPLACE` to toggle completion status

### UserDatabase Class

**Location:** `backend/user_models.py`

**Purpose:** Abstraction layer for all user and progress operations.

#### Key Methods

**Authentication:**
```python
def create_user(self, username: str, password: str) -> Optional[int]
    """Create new user with hashed password. Returns user_id or None if username exists."""

def authenticate_user(self, username: str, password: str) -> Optional[Dict]
    """Verify credentials. Returns user dict or None if invalid."""

def update_last_login(self, user_id: int) -> None
    """Update last_login timestamp."""
```

**Reading Progress:**
```python
def save_reading_progress(self, user_id: int, book_id: int,
                         chapter_number: int, page_number: int = 0,
                         scroll_position: float = 0.0) -> None
    """Save or update reading position."""

def get_reading_progress(self, user_id: int, book_id: int) -> Optional[Dict]
    """Get current reading position."""

def mark_chapter_complete(self, user_id: int, book_id: int,
                         chapter_number: int, completed: bool = True) -> None
    """Mark chapter as completed or reset."""

def get_completed_chapters(self, user_id: int, book_id: int) -> List[int]
    """Get list of completed chapter numbers."""
```

**Statistics:**
```python
def get_user_stats(self, user_id: int) -> Dict
    """Get reading statistics:
    - books_started: Count of books with progress
    - chapters_completed: Total completed chapters
    """
```

### Authentication Flow

#### Registration
1. User submits username and password (min 3 chars each)
2. Backend validates username doesn't exist
3. Generate random 32-byte salt
4. Hash password: SHA-256(password + salt)
5. Store username, password_hash, salt, created_at
6. Create Flask session with user_id
7. Mark session as permanent (30-day duration)

#### Login
1. User submits username and password
2. Backend retrieves user record by username
3. Hash submitted password with stored salt
4. Compare hashes (constant-time comparison)
5. If match: create Flask session, update last_login
6. Return user data (excluding password_hash and salt)

#### Session Management
- Flask server-side sessions
- SESSION_PERMANENT = True
- PERMANENT_SESSION_LIFETIME = 30 days
- Session data stored in signed cookie
- Auto-cleanup on expiration

### Progress Tracking Flow

#### Auto-Save Reading Position
1. User views chapter → `showChapterDetail()` called
2. Track initial view: `trackChapterView(book_id, chapter_num, page=0)`
3. User navigates pages → `displayCurrentPage()` called
4. Track page change: `trackPageChange(book_id, chapter_num, page_num)`
5. On last page: Auto-mark complete via `onChapterComplete()`

**Debouncing:** Progress saves are debounced (500ms) to avoid excessive API calls.

#### Chapter Completion Logic
```javascript
// In displayCurrentPage()
const isLastPage = this.pagination.currentPage === this.pagination.totalPages - 1;
if (isLastPage) {
    window.authModule.onChapterComplete(this.currentBook.id, this.currentChapter);
}
```

**Backend:** Uses `INSERT OR REPLACE` to handle completion toggle.

### Offline Support (PWA)

#### localStorage Keys
```javascript
STORAGE_KEYS = {
    OFFLINE_PROGRESS: 'summra_offline_progress',     // Array of progress updates
    OFFLINE_COMPLETED: 'summra_offline_completed',   // Array of completions
    LAST_SYNC: 'summra_last_sync',                   // Last sync timestamp
    CURRENT_USER: 'summra_current_user'              // Cached user object
}
```

#### Offline Flow
1. **Online:** Save to server + localStorage cache
2. **Offline:** Save to localStorage arrays
3. **Back Online:** Auto-sync localStorage to server
4. **Conflict Resolution:** Server data takes precedence

#### Service Worker Caching
```javascript
registerRoute(
    ({ url }) => url.pathname === '/api/auth/check',
    new NetworkFirst({
        cacheName: 'auth-cache',
        networkTimeoutSeconds: 3,
        plugins: [
            new ExpirationPlugin({ maxAgeSeconds: 60 * 60 }) // 1 hour
        ]
    })
);
```

**Behavior:**
- Try network first with 3-second timeout
- Fallback to cached auth status if offline
- Cache expires after 1 hour

### Frontend Integration

#### auth.js Module
**Location:** `frontend/static/js/auth.js`

**Initialization:**
```javascript
window.authModule = {
    initAuth(),                                    // Initialize on page load
    checkAuthStatus(),                             // Verify login status
    login(username, password),                     // Login user
    register(username, password),                  // Register user
    logout(),                                      // Logout and clear session
    trackChapterView(book_id, chapter_num, page),  // Save progress
    trackPageChange(book_id, chapter_num, page),   // Update page position
    onChapterComplete(book_id, chapter_num),       // Mark complete
    getCompletedChaptersForBook(book_id),          // Fetch completions
    getReadingProgress(book_id)                    // Fetch current position
}
```

#### UI Integration Points

**Header Account Button:** (`index.html:107-110`)
```html
<button class="header-nav-btn user-account-btn" id="user-account-btn">
    <span class="user-icon">👤</span>
    <span class="user-name" id="header-user-name">Account</span>
</button>
```
- Shows username when logged in
- Opens modal on click

**Continue Reading Button:** (`app.js:showResumeReadingButton()`)
- Created dynamically in `book-detail-info` section
- Only shown when user has progress for book
- Button text: "Continue Reading: Chapter X, Page Y"
- Positioned near Save for Offline button

**Completed Chapters:** (`app.js:loadChapters()`)
```javascript
const completedChapters = await window.authModule.getCompletedChaptersForBook(book_id);
// Apply .completed class to chapter boxes
box.className = 'chapter-box' + (isCompleted ? ' completed' : '');
```
- Chapters marked with grey styling + checkmark
- Visual indicator persists across sessions

### API Endpoints

#### Authentication
- `POST /api/auth/register` - Create new account
- `POST /api/auth/login` - Login with credentials
- `POST /api/auth/logout` - Logout and clear session
- `GET /api/auth/check` - Verify authentication status
- `GET /api/auth/me` - Get current user info

#### Progress Tracking
- `POST /api/progress/save` - Save reading position
- `GET /api/progress/get/<book_id>` - Get reading position
- `POST /api/progress/chapter/complete` - Mark chapter complete
- `POST /api/progress/sync` - Sync offline progress
- `GET /api/progress/stats` - Get user statistics

**Authentication Required:** All progress endpoints require valid session.

### Security Considerations

**Password Security:**
- SHA-256 hashing (not plaintext)
- Unique salt per user
- Salt stored separately from hash
- No password recovery (reset only)

**Session Security:**
- HTTPOnly cookies (JavaScript can't access)
- SameSite=Lax (CSRF protection)
- Signed session data (tamper-proof)
- 30-day expiration

**CSRF Protection:**
- SameSite cookie policy
- Session-based authentication
- No third-party cookie sharing

**Future Enhancements:**
- HTTPS enforcement
- Rate limiting on login attempts
- Password strength requirements
- Two-factor authentication
- Email verification

---

## SEO Architecture

### Overview

**Added:** 2025-12-02

The SEO architecture provides search engine optimization through breadcrumb navigation, structured data, and context-aware meta tags. This improves discoverability and user navigation throughout the site.

### Breadcrumb Navigation System

**Location:** `backend/app_base.py:40-93`

**Purpose:** Replace traditional back buttons with context-aware breadcrumb trails that show the user's current location in the site hierarchy.

#### build_breadcrumbs() Function

```python
def build_breadcrumbs(page_type, **kwargs):
    """
    Build breadcrumb data for SEO and navigation.

    Returns list of breadcrumb items with:
    - name: Display text
    - url: Relative URL
    - position: Position in breadcrumb trail (starts at 1)
    """
```

**Supported Page Types:**
- `'home'`: Home page (no breadcrumbs shown)
- `'categories'`: All Categories page
- `'category'`: Specific category detail page
- `'all_books'`: All Books grid page
- `'book'`: Book detail page
- `'book_summary'`: Medium summary page
- `'chapter'`: Chapter detail page

**Example Breadcrumb Trails:**

```
Home
Home → All Books
Home → Categories
Home → Categories → Victorian Literature
Home → All Books → Pride and Prejudice
Home → All Books → Pride and Prejudice → Summary
Home → All Books → Pride and Prejudice → Chapter 1
```

**Context-Aware Breadcrumbs:**

When a user selects a book from a category page, the breadcrumb trail reflects this:
```
Home → Categories → Romance → Pride and Prejudice
```

When selected from All Books page:
```
Home → All Books → Pride and Prejudice
```

This is tracked via `app.originCategory` in the frontend (`frontend/static/js/app.js:29`).

#### breadcrumbs_to_schema() Function

**Location:** `backend/app_base.py:95-106`

Converts breadcrumb data to Schema.org BreadcrumbList JSON-LD format for search engines.

**Output Example:**
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://summra.com/"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "All Books",
      "item": "https://summra.com/all-books"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "Pride and Prejudice"
    }
  ]
}
```

**Note:** Last breadcrumb item has no `item` URL (represents current page).

### Frontend Breadcrumb Rendering

**Location:** `frontend/static/js/app.js:1625-1731` (`updateBreadcrumbs()` method)

**HTML Structure:**
```html
<nav class="breadcrumb-nav" aria-label="Breadcrumb">
    <ol class="breadcrumb-list">
        <li class="breadcrumb-item">
            <a href="/" class="breadcrumb-link">← Home</a>
        </li>
        <li class="breadcrumb-item">
            <span class="breadcrumb-separator">›</span>
            <a href="/all-books" class="breadcrumb-link">All Books</a>
        </li>
        <li class="breadcrumb-item">
            <span class="breadcrumb-separator">›</span>
            <span class="breadcrumb-current">Pride and Prejudice</span>
        </li>
    </ol>
</nav>
```

**Styling:** `frontend/static/css/style.css:111-159`

**Features:**
- First breadcrumb automatically gets back arrow (`← `)
- Links are clickable (navigate via hash routing)
- Current page shown in plain text (not a link)
- Responsive design (wraps on mobile)
- Accessible (semantic HTML + ARIA labels)

### Page Title Updates

**Location:** `frontend/static/js/app.js:159-161` (`updatePageTitle()` method)

Each route dynamically updates `document.title` for:
- Browser tabs
- Bookmarks
- Search engine results
- Social media sharing

**Examples:**
```
Home: "Free Classic Book Summaries, Chapter Summaries & Full Text | Summra"
Book: "Pride and Prejudice by Jane Austen | Summra"
Summary: "Summary of Pride and Prejudice by Jane Austen | Summra"
Chapter: "Full Text of Chapter 1 - Pride and Prejudice | Summra"
```

### Meta Tag Improvements

**Location:** `backend/app_base.py`

**Updated Routes:**
- `/` (line 164): `meta_title='Free Classic Book Summaries, Chapter Summaries & Full Text | Summra'`
- `/books` (line 505): Changed "AI Summaries" to "Free Summaries"
- Footer (template line 329): Updated to emphasize "Free summaries and full text"

**SEO Benefits:**
- Keyword-rich titles for search ranking
- Clear value proposition ("Free")
- Emphasizes comprehensive content (summaries + full text)
- Brand consistency (all titles end with "| Summra")

---

## Related Books System

### Overview

**Added:** 2025-12-02

The Related Books system provides personalized book recommendations based on author, category, and country. This increases user engagement and helps readers discover similar works.

### Database Schema

**New Table:** `similar_books`

```sql
CREATE TABLE similar_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    similar_book_id INTEGER NOT NULL,
    rank INTEGER,  -- 1-5 (order of recommendation)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (similar_book_id) REFERENCES books(id),
    UNIQUE(book_id, similar_book_id)
)
```

**Purpose:** Store AI-generated book recommendations (many-to-many self-referential).

**New Table:** `authors`

```sql
CREATE TABLE authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    country TEXT,
    bio TEXT,
    other_books TEXT,  -- JSON array of other book titles
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Purpose:** Normalize author data for author-based queries and recommendations.

**Modified Table:** `books`
- Added `author_id INTEGER` foreign key to `authors` table
- Keeps `author TEXT` for backward compatibility

### Related Books API

**Endpoint:** `GET /api/books/<book_id>/related`

**Location:** `backend/app_base.py:912-935`

**Response Format:**
```json
{
  "success": true,
  "book_id": 1,
  "related": {
    "by_author": [
      {"id": 5, "title": "Sense and Sensibility", "author": "Jane Austen", "cover_image_url": "..."}
    ],
    "by_category": [
      {"id": 12, "title": "Emma", "author": "Jane Austen", "cover_image_url": "..."}
    ],
    "by_country": [
      {"id": 23, "title": "Wuthering Heights", "author": "Emily Brontë", "cover_image_url": "..."}
    ]
  }
}
```

**Algorithm:**

**Location:** `backend/models.py:933-1019` (`get_related_books()` method)

```python
def get_related_books(self, book_id: int, limit: int = 10) -> Dict:
    """
    Get related books for a specific book

    Returns dictionary with three lists:
    - by_author: Books by same author
    - by_category: Books in same categories (excluding same author)
    - by_country: Books by authors from same country (excluding above)
    """
```

**Selection Strategy:**

1. **By Author** (priority 1):
   - Find all books by the same author
   - Exclude the current book
   - Order: Random (for variety)
   - Limit: No limit (all books by author)

2. **By Category** (priority 2):
   - Find books in same categories as current book
   - Exclude books by same author (already in list)
   - Exclude current book
   - Order: Random
   - Limit: No limit

3. **By Country** (priority 3):
   - Find books by authors from same country
   - Exclude books already in by_author or by_category
   - Exclude current book
   - Order: Random
   - Limit: No limit

**Frontend Deduplication:**
- Frontend merges all three lists
- Removes duplicates (books may appear in multiple categories)
- Limits to 10 total books

### Frontend Related Books Carousel

**Location:** `frontend/static/js/app.js:918-1023` (`loadRelatedBooks()` method)

**UI Components:**

1. **Carousel Container**: Horizontal scrolling row
2. **Book Cards**: Cover + title + author (same style as category carousels)
3. **Navigation Arrows**: Left/right scroll buttons
4. **Responsive**: Adapts to mobile/tablet/desktop

**Styling:** `frontend/static/css/style.css:648-774`

**Card Dimensions:**
- Desktop: 200px wide, 300px cover height
- Tablet: 150px wide, 200px cover height
- Mobile: 130px wide, 180px cover height

**Scroll Behavior:**
- Smooth scroll by 3 cards at a time
- Arrow buttons disabled at edges
- Touch-friendly horizontal scrolling
- No visible scrollbar

**Section Header:** "You May Also Like" (`frontend/templates/index.html:122`)

**Visibility:**
- Hidden if no related books found
- Displayed at bottom of book detail page (after chapters)
- Separated by border-top divider

### Database Methods

**Location:** `backend/models.py:933-1305`

**Author Management:**
```python
def add_author(self, name: str, country: str = None, bio: str = None) -> int
def get_author(self, author_id: int) -> Optional[Dict]
def get_author_by_name(self, name: str) -> Optional[Dict]
def update_author(self, author_id: int, country: str = None, bio: str = None)
def get_books_by_author(self, author_id: int) -> List[Dict]
```

**Similar Books Management:**
```python
def add_similar_book(self, book_id: int, similar_book_id: int, rank: int = None)
def get_similar_books(self, book_id: int) -> List[Dict]
def remove_similar_book(self, book_id: int, similar_book_id: int)
```

**Performance Considerations:**
- Queries use indexes on `author_id`, `category_id`, and foreign keys
- Random ordering via `ORDER BY RANDOM()`
- Frontend caching of category data reduces redundant API calls
- Lazy loading of related books (only fetched when viewing book detail)

---

## Chapter Parser Implementation

The chapter detection system is one of the most complex parts of Summra. It handles diverse book structures, from simple sequential chapters to complex nested hierarchies.

### Overview

**Location:** `scripts/generate_summaries.py:406-874` (`detect_chapters` method)

**Input:** Raw book text (after Gutenberg header/footer removal)

**Output:** List of tuples: `[(chapter_number, chapter_title, chapter_text), ...]`

**Chapter Numbering Scheme:**
- Simple books: 1, 2, 3, 4...
- Nested books: encoded as `book_num * 100 + chapter_num` (e.g., 101, 102, 201, 202)
- Special: Chapter 0 for Introduction/Preface

### Supported Chapter Patterns

#### 1. Standard Chapter Patterns (Regex)

```python
chapter_patterns = [
    r'CHAPTER\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # CHAPTER I: Title or CHAPTER 1
    r'Chapter\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # Mixed case
    r'SCENE\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',    # SCENE I. (for plays)
    r'Scene\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',    # Scene 1. (for plays)
    r'^([IVXLCDM]+)\.\s+(.+)$',                      # Roman numeral only: "I. TITLE"
    r'^(INTRODUCTION)$',                              # Standalone "INTRODUCTION"
    r'^(Introduction)$',                              # Standalone "Introduction"
    r'^(PREFACE)(?:\s+.*)?$',                        # "PREFACE" or "PREFACE By Editor"
    r'^(Preface)(?:\s+.*)?$',                        # "Preface" or "Preface Of Author"
]
```

**Pattern Explanation:**

- **`[IVXLCDMivxlcdm]+`**: Matches Roman numerals (uppercase I, II, III or lowercase i, ii, iii) - **Updated 2025-11-30** to support lowercase
- **`[0-9]+`**: Matches Arabic numerals (1, 2, 3...)
- **`[:\.\s]*`**: Matches optional colon, period, or whitespace
- **`(.*)$`**: Captures rest of line as title
- **`^` anchor**: Ensures pattern starts at beginning of line (after stripping whitespace)

**Lowercase Roman Numeral Support (2025-11-30):**

Books like "The History of Tom Jones, a Foundling" use lowercase Roman numerals for chapters:
```
Chapter i.
Chapter ii.
Chapter iii.
```

The regex patterns were updated from `[IVXLCDM]+` (uppercase only) to `[IVXLCDMivxlcdm]+` (case-inclusive) in three locations:
- Line 1104: Main chapter pattern
- Line 1106: Standalone Roman numeral pattern
- Line 1107: Standalone Roman numeral with period pattern

This change allows detection of both uppercase (Chapter I) and lowercase (Chapter i) formats without breaking existing functionality.

#### 2. Nested Structure Patterns

```python
volume_book_pattern = r'(BOOK|VOLUME|ACT)\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$'
```

**Examples:**
- `BOOK I` → book_num = 1
- `VOLUME II: The War Years` → book_num = 2, title = "The War Years"
- `ACT III` → book_num = 3

**Encoding:**
- Chapters within BOOK I: 101, 102, 103...
- Chapters within BOOK II: 201, 202, 203...
- Chapters within VOLUME III: 301, 302, 303...

#### 3. PART Markers (Explicitly Ignored)

```python
part_pattern = r'^PART\s+([IVXLCDM]+|[0-9]+)'
```

**Rationale:** PART markers are section dividers WITHIN chapters, not chapter boundaries. They should be included in chapter content, not treated as separate chapters.

**Example:** "Decline and Fall of the Roman Empire" has chapters with parts:
```
CHAPTER I.—Part I.
CHAPTER I.—Part II.
```
These are merged into single Chapter 1.

### Roman Numeral Conversion

**Location:** `scripts/generate_summaries.py:261-283`

```python
def roman_to_int(self, s: str) -> int:
    """Convert Roman numeral to integer"""
    if not s:
        return 0

    roman_map = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }

    s = s.upper()
    result = 0
    prev_value = 0

    # Process in reverse order
    for char in reversed(s):
        value = roman_map.get(char, 0)
        if value < prev_value:
            result -= value  # Subtraction rule (IV = 4, IX = 9)
        else:
            result += value
        prev_value = value

    return result
```

**Algorithm:** Right-to-left scan with subtraction rule
- IV = 5 - 1 = 4
- IX = 10 - 1 = 9
- XL = 50 - 10 = 40
- MCMXCIV = 1000 + (1000-100) + (100-10) + (5-1) = 1994

### Finite State Machine (FSM) Logic

The chapter detection uses a stateful line-by-line scan with explicit state tracking to avoid arbitrary distance-based heuristics.

```
State Variables:
- current_chapter: (chapter_num, chapter_title) or None
- current_text: List[str] - lines accumulated for current chapter
- current_book_num: int - tracks which BOOK/VOLUME we're in (for encoding)
- has_book_markers: bool - detected any BOOK/VOLUME/ACT markers
- expecting_first_chapter_of_book: bool - flag set when BOOK marker seen (2025-11-26)
- in_illustration: bool - inside [Illustration: ...] block
- potential_chapters: List[dict] - all detected chapter markers (for TOC filtering)
- book_markers: List[dict] - all detected BOOK/VOLUME/ACT markers
- consumed_lines: set - line indices consumed as title continuations
```

**State Transitions:**

```
State 1: No active chapter (current_chapter = None)
  - Detect chapter marker → Transition to State 2
  - Skip lines

State 2: Active chapter (current_chapter != None)
  - Accumulate lines to current_text
  - Detect new chapter marker → Save current chapter, start new chapter
  - Skip TOC entries, illustration blocks

Special States:
  - in_illustration = True → Skip all lines until ']'
  - BOOK marker detected → Update current_book_num, set has_book_markers = True,
                          set expecting_first_chapter_of_book = True
  - First chapter after BOOK → Use expecting_first_chapter_of_book flag,
                               clear flag after processing chapter
```

**State Tracking Pattern (Refactored 2025-11-26):**

Instead of arbitrary distance-based scanning (e.g., "look back 10 lines"), the parser uses explicit boolean flags to track state:

**Location:** `scripts/generate_summaries.py:817, 970, 1247-1249, 1367`

```python
# Initialize state flag
expecting_first_chapter_of_book = False  # Line 817

# Event: BOOK marker detected
if volume_book_match:
    # ... process BOOK marker ...
    expecting_first_chapter_of_book = True  # Line 970

# Event: Check if chapter is after BOOK marker (no backward scan needed)
recently_saw_book_marker = expecting_first_chapter_of_book  # Line 1247-1249

# Event: Chapter processed
current_chapter = (chapter_num, chapter_title)
current_text = []
expecting_first_chapter_of_book = False  # Clear flag (Line 1367)
```

**Benefits:**
- No magic numbers (removed arbitrary 10-line backward scan)
- State is explicit, not inferred from distances
- More robust (works regardless of spacing between BOOK markers and chapters)
- Easier to understand and maintain
- No risk of missing markers due to arbitrary distance limits

### Multi-Line Title Handling

**Problem:** Some books have titles split across multiple lines:
```
CHAPTER I
The Three Metamorphoses
```

**Solution:** Look ahead to next line after detecting chapter marker

**Location:** `scripts/generate_summaries.py:565-598`

```python
# Check if next line is a continuation of the title
if i + 1 < len(lines):
    next_line = lines[i + 1].strip()

    # Detect part marker continuation (skip these)
    is_part_marker_continuation = re.match(r'^[IVXLCDM]+\.$', next_line)

    # Detect title continuation
    is_continuation = (
        next_line and
        not is_part_marker_continuation and
        not re.match(r'(CHAPTER|Chapter|SCENE|...) next_line) and
        not next_line.startswith('[Illustration') and
        not next_line.startswith('By ') and
        len(next_line) < 100 and  # Reasonable title length
        len(next_line) > 1 and
        (next_line[0].islower() or next_line[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    )

    if not chapter_title or is_continuation:
        chapter_title = chapter_title + ' ' + next_line if chapter_title else next_line
```

### Part Marker Removal

**Problem:** Chapter titles often include part markers that should be cleaned:
```
"The Three Metamorphoses.—Part I"
"Of the Friend.—Part II."
"Of the Sublime Ones. Part IV"
```

**Solution:** Regex substitution after title concatenation

**Location:** `scripts/generate_summaries.py:599-604`

```python
# Remove part markers from titles
# Handles: "—Part I", "—Part", ".—Part II.", ". Part IV", etc.
chapter_title = re.sub(
    r'[.\s]*[—–-]?\s*Part\s+[IVXLCDM]+[.\s]*$',
    '',
    chapter_title,
    flags=re.IGNORECASE
).strip()

chapter_title = re.sub(
    r'[.\s]*[—–-]?\s*Part[.\s]*$',
    '',
    chapter_title,
    flags=re.IGNORECASE
).strip()
```

**Regex Breakdown:**
- `[.\s]*` - Optional leading periods/spaces
- `[—–-]?` - Optional em dash, en dash, or hyphen
- `\s*Part\s+` - "Part" with surrounding whitespace
- `[IVXLCDM]+` - Roman numeral
- `[.\s]*$` - Optional trailing periods/spaces at end of string

### Multi-Line Title Detection with Empty Line Skipping (Tom Jones Fix - 2025-11-30)

**Problem:** Books like "The History of Tom Jones, a Foundling" have titles on separate lines with empty lines in between:

**Example - BOOK Section Titles:**
```
BOOK I.

CONTAINING AS MUCH OF THE BIRTH OF THE FOUNDLING
AS IS NECESSARY OR PROPER TO ACQUAINT THE READER WITH
IN THE BEGINNING OF THIS HISTORY.
```

**Example - Chapter Titles:**
```
Chapter i.

The introduction to the work, or bill of fare to the feast.
```

**Solution 1: BOOK Section Title Detection**

**Location:** `scripts/generate_summaries.py:1185-1212`

```python
# If not on same line, check next few lines for section title
# Skip empty lines and collect multi-line titles (e.g., Tom Jones)
if not section_title and i + 1 < len(lines):
    title_lines = []
    # Look ahead up to 5 lines, skipping empty ones
    for offset in range(1, 6):
        if i + offset >= len(lines):
            break
        candidate_line = lines[i + offset].strip()

        # Skip empty lines
        if not candidate_line:
            continue

        # Stop if we hit a chapter marker
        if re.match(chapter_pattern, candidate_line):
            break

        # Check if it looks like a title line (all caps or title case, not too long)
        if (candidate_line[0].isupper() or candidate_line[0].isdigit()) and len(candidate_line) < 100:
            title_lines.append(candidate_line)
        else:
            # Hit prose content, stop collecting title
            break

    # Join multi-line title with spaces
    if title_lines:
        section_title = ' '.join(title_lines)
```

**Algorithm:**
1. **Lookahead window:** 5 lines (not just 1)
2. **Skip empty lines:** Continue past blank lines
3. **Collect title lines:** All-caps or title case lines < 100 chars
4. **Stop conditions:**
   - Hit chapter marker (e.g., "Chapter i.")
   - Hit prose content (lowercase start or long line)
5. **Join:** Concatenate collected lines with spaces

**Result:** BOOK titles now correctly detected:
- Before: "(untitled)"
- After: "CONTAINING AS MUCH OF THE BIRTH OF THE FOUNDLING AS IS NECESSARY OR PROPER TO ACQUAINT THE READER WITH IN THE BEGINNING OF THIS HISTORY."

**Solution 2: Chapter Title Detection**

**Location:** `scripts/generate_summaries.py:1248-1274`

```python
# If title is empty, check next few lines (skip empty lines)
# Format: "CHAPTER I" or "Chapter i." on one line, empty line(s), then title
# Tom Jones: "Chapter i." → empty line → "The introduction to the work..."
if not chapter_title:
    # Look ahead up to 3 lines, skipping empty ones
    for offset in range(1, 4):
        if i + offset >= len(lines):
            break
        next_line = lines[i + offset].strip()

        # Skip empty lines
        if not next_line:
            continue

        # If next line doesn't look like another marker, use it as title
        # Also verify it looks like a title (starts with capital or quote, isn't too long)
        # Include both straight quotes (", ') and curly quotes (\u201c, \u201d, \u2018, \u2019)
        if (not re.match(chapter_pattern, next_line) and
            not re.match(standalone_roman_pattern, next_line) and
            not re.match(section_pattern, next_line, re.IGNORECASE) and
            len(next_line) > 3 and len(next_line) < 150 and
            (next_line[0].isupper() or next_line[0] in '"\'\u201c\u201d\u2018\u2019')):
            chapter_title = next_line
            break
        else:
            # Hit a marker or prose, stop searching
            break
```

**Algorithm:**
1. **Lookahead window:** 3 lines (increased from 1)
2. **Skip empty lines:** Continue past blank lines
3. **Validation checks:**
   - Not another chapter marker
   - Not a standalone Roman numeral
   - Not a section marker (BOOK/VOLUME/ACT)
   - Length between 3-150 characters (increased max from 100)
   - Starts with uppercase or quote character
4. **Stop conditions:**
   - Find valid title → use it and break
   - Hit another marker → stop searching
   - Hit prose content → stop searching

**Result:** Chapter titles now correctly detected:
- Before: Empty strings
- After: "The Introduction to the Work, or Bill of Fare to the Feast."

**Impact:**
- Fixes title detection for books with titles on separate lines
- Handles multi-line titles automatically (BOOK sections)
- Backward compatible with existing single-line title detection
- Improves metadata quality for chapter summaries

**Test Coverage:**
- Unit tests in `tests/test_book_chapter_name_detection.py`
- Validated with "The History of Tom Jones, a Foundling" (pg6593)
- Coverage: 99.1% (208 chapters detected)

### Multi-Part Chapter Merging

**Problem:** Books like "Decline and Fall" split chapters into parts that should be merged:
```
CHAPTER I.—Part I.   (2000 words)
CHAPTER I.—Part II.  (3000 words)
CHAPTER I.—Part III. (1500 words)
```

**Solution:** Merge all parts with same chapter number

**Location:** `scripts/generate_summaries.py:714-753`

```python
# After collecting all chapters, merge duplicates
chapter_dict = {}
for chapter_num, chapter_title, chapter_text in chapters:
    if chapter_num in chapter_dict:
        # Already have this chapter - merge the parts
        existing_title, existing_text = chapter_dict[chapter_num]
        existing_length = len(existing_text)
        new_length = len(chapter_text)

        # Concatenate with paragraph separator
        merged_text = existing_text + "\n\n" + chapter_text

        # Keep the LONGEST title (most complete version)
        better_title = existing_title
        if len(chapter_title) > len(existing_title):
            better_title = chapter_title

        print(f"Merged Chapter {chapter_num} parts: {existing_length} + {new_length} = {len(merged_text)} chars")
        chapter_dict[chapter_num] = (better_title, merged_text)
    else:
        chapter_dict[chapter_num] = (chapter_title, chapter_text)

# Rebuild chapters list from dict, sorted by chapter number
chapters = [(num, title, text) for num, (title, text) in sorted(chapter_dict.items())]
```

### Table of Contents (TOC) Detection & Filtering

**Problem:** Books include TOC that looks like actual chapters:
```
CONTENTS

I. The Three Metamorphoses
II. The Academic Chairs
III. Despisers of the Body
...
```

**Solution 1:** Extract expected TOC entries

**Location:** `scripts/generate_summaries.py:370-404`

```python
def extract_toc(self, text: str) -> Dict[str, str]:
    """
    Extract table of contents from text.
    Returns dict mapping roman numerals to expected chapter titles.
    """
    toc = {}
    lines = text.split('\n')
    in_toc = False

    # Look for CONTENTS section
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Start of TOC
        if re.match(r'^\s*CONTENTS\.?\s*$', line_stripped, re.IGNORECASE):
            in_toc = True
            continue

        # End of TOC - when we hit actual content markers
        if in_toc and any(marker in line_stripped for marker in
                         ['INTRODUCTION BY', 'CHAPTER I', 'FIRST PART']):
            if i > 100:  # Make sure past the TOC section
                break

        # Parse TOC entries: "LVI. Old and New Tables"
        # MUST have period after numeral to avoid matching "I have..." sentences (Bug fix 2025-11-29)
        if in_toc and line_stripped:
            match = re.match(r'^([IVXLCDM]+)\.\s+(.+?)\.*\s*$', line_stripped)
            if match:
                roman_num = match.group(1)
                title = match.group(2).strip('. ')
                toc[roman_num] = title

    return toc
```

**TOC Detection Bug Fix (2025-11-29):**

**Problem:** The pattern `^([IVXLCDM]+)\.?\s+` with optional period was matching sentences starting with "I" in preface prose:
```
"I have carefully perused them three times."
```
This was incorrectly detected as a TOC entry with Roman numeral "I" and title "have carefully...".

**Solution:** Made period mandatory in pattern: `^([IVXLCDM]+)\.\s+`

**Impact:**
- Prevents false positives in preface/prose text
- Correctly identifies TOC end boundary
- Fixed Gulliver's Travels preface detection (was starting at line 47 instead of 0)

### Preface Extraction Logic (Chapter 0)

**Location:** `scripts/generate_summaries.py:2301-2398, 2462-3143`

**Objective:** Collect all introductory material before the first numbered chapter into Chapter 0 (Preface).

**Two-Phase Collection Strategy:**

The preface extraction uses two complementary collection mechanisms with deduplication:

**Phase 1: Initial Preface Extraction (lines 2301-2398)**
- **What:** Filters lines from start of book to first chapter marker
- **How:** Removes TOC, illustrations, and title page boilerplate
- **Output:** `initial_preface_text` + `combined_preface_line_indices`

**Phase 2: Main Loop Collection (lines 2462+)**
- **What:** Collects any remaining pre-chapter content during chapter parsing
- **How:** Adds lines before `found_first_chapter = True` if not already in `combined_preface_line_indices`
- **Output:** `preface_text`

**Final Combination (line 3064):**
```python
combined_preface = initial_preface_text + preface_text
```

**Deduplication Fix (2025-12-04):**

**Problem:** Content appearing twice in preface for books like "Ten Years Later":
- Lines 31-105: Transcriber's Notes (not filtered by Phase 1)
- Lines 106-223: Introduction section
- Lines 106-223 were collected in BOTH phases, causing duplication

**Solution:** Added deduplication check at lines 2505, 2570, 3137:
```python
if not found_first_chapter and not in_illustration and i not in combined_preface_line_indices:
    preface_text.append(line)
```

**Filtering Strategy (Simplified 2025-12-04):**

Previously relied on regex matching specific preface headers:
```python
# OLD APPROACH (removed)
is_preface_header = re.match(r'^\s*(AUTHOR[\'\']S\s+PREFACE|TRANSLATOR[\'\']S\s+PREFACE|...')
```

**New Approach:** Keep everything before Chapter 1 EXCEPT:
1. **TOC entries** - detected by CONTENTS header and page number patterns
2. **Illustration captions** - `[Illustration...]` blocks
3. **Title page boilerplate** - BY, COPYRIGHT, publisher info, years

**Benefits:**
- Simpler, more maintainable code
- No need to maintain exhaustive list of preface keywords
- Works for any introductory content (Transcriber's Notes, Prelude, Introduction, etc.)
- Eliminates duplication bug

**TOC Title Deduplication (2025-11-25):**

Titles extracted from title-only TOC are deduplicated while preserving order:

**Location:** `scripts/generate_summaries.py:518`

```python
# Deduplicate titles while preserving order (dict keys maintain insertion order in Python 3.7+)
return list(dict.fromkeys(titles))
```

**Rationale:**
- Some books repeat titles in TOC (e.g., multiple editions, errata sections)
- `dict.fromkeys()` preserves first occurrence of each title
- Prevents duplicate chapter entries in parsed results

**Solution 2:** Validate detected chapters against TOC

```python
# If TOC exists, verify chapter marker is in TOC
if toc:
    if chapter_marker not in toc:
        # Not in TOC - skip this false positive
        is_chapter = False
        continue

    # Use TOC title as authoritative version
    toc_title = toc[chapter_marker]
    if detected_normalized != toc_normalized:
        print(f"Using TOC title '{toc_title}' instead of '{chapter_title}'")
        chapter_title = toc_title
```

**Solution 3:** Filter out short chapter instances (likely TOC)

**Location:** `scripts/generate_summaries.py:754-790`

```python
# Filter out TOC entries by length
chapter_groups = {}
for ch_num, ch_title, ch_text in chapters:
    if ch_num not in chapter_groups:
        chapter_groups[ch_num] = []
    chapter_groups[ch_num].append((ch_num, ch_title, ch_text, len(ch_text)))

# Keep only instances > 500 chars (actual chapters, not TOC)
filtered_chapters = []
for ch_num in sorted(chapter_groups.keys()):
    instances = chapter_groups[ch_num]
    if len(instances) > 1:
        # Multiple instances - keep only long ones
        long_instances = [inst for inst in instances if inst[3] > 500]
        if long_instances:
            longest = max(long_instances, key=lambda x: x[3])
            filtered_chapters.append((longest[0], longest[1], longest[2]))
    else:
        # Single instance - keep it
        filtered_chapters.append((instances[0][0], instances[0][1], instances[0][2]))
```

**Solution 4:** Inline TOC entry filtering

```python
# Skip TOC entries while accumulating chapter text
is_toc_entry = (
    line_stripped.startswith('Heading to') or
    line_stripped in ['PAGE', 'CONTENTS', 'TABLE OF CONTENTS'] or
    # Text followed by 10+ spaces and page number (e.g., "Chapter Title    123")
    re.match(r'.+\s{10,}[ivxlcdm\d]+\s*$', line_stripped, re.IGNORECASE)
)
if is_toc_entry:
    continue
```

**Solution 5:** Title-Only TOC Detection with Paragraph Content Heuristic (2025-11-30)

**Problem:** Books like fairy tale collections have TOC with only titles (no chapter numbers):
```
CONTENTS

  A Story
  The Angel
  The Dumb Cook
  The Elf of the Rose
  ...
```

Some titles appear only in TOC and not in actual content. Using TOC entries as chapter boundaries creates massive chapters or missing stories.

**Example:** Hans Christian Andersen's Fairy Tales (pg27200.txt):
- TOC lists 125 titles
- Only 120 stories actually exist in book
- "The Dumb Cook" appears in TOC but not in content

**Solution:** Paragraph content detection heuristic

**Location:** `scripts/generate_summaries.py:2642-2684`

```python
# Filter matches to find actual chapter starts (not TOC entries)
# A real chapter is followed by substantial paragraph content within 5 lines
chapter_matches = []
for match_idx in matches:
    # Look ahead only 5 lines - real chapters have immediate content
    has_paragraph = False
    uppercase_subtitle_count = 0
    for lookahead in range(match_idx + 1, min(match_idx + 6, len(lines))):
        lookahead_line = lines[lookahead].strip()
        if not lookahead_line:
            continue

        # Check if this is paragraph content (> 40 chars with mixed case or punctuation)
        if len(lookahead_line) > 40:
            has_mixed_case = not lookahead_line.isupper()
            ends_with_punctuation = lookahead_line[-1] in '.,"!?;:'
            if has_mixed_case or ends_with_punctuation:
                has_paragraph = True
                break

        # Allow 1-2 uppercase subtitles like "AN OLD STORY TOLD ANEW"
        if lookahead_line.isupper() and len(lookahead_line) < 50:
            uppercase_subtitle_count += 1
            if uppercase_subtitle_count > 2:
                break  # Too many uppercase lines without paragraph = TOC

    if has_paragraph:
        chapter_matches.append(match_idx)

# Only use matches that have paragraph content nearby
if chapter_matches:
    title_positions.append((chapter_matches[-1], title))
elif matches:
    print(f"Skipping '{title}' - likely TOC-only")
```

**Key Design Decisions:**

1. **5-line lookahead limit:**
   - Real chapters have content immediately after title
   - TOC entries have other titles or blank lines
   - Prevents detecting content from subsequent stories

2. **Paragraph detection criteria:**
   - Length > 40 characters (substantial content)
   - Mixed case OR ends with punctuation
   - Filters out short uppercase titles in TOC

3. **Subtitle tolerance:**
   - Allow up to 2 uppercase lines (e.g., "AN OLD STORY TOLD ANEW")
   - More than 2 = likely in TOC section

4. **No fallback:**
   - Previously fell back to using any match without verification
   - Now skips titles with no nearby paragraph content
   - Prevents creating chapters for TOC-only entries

**Impact:**
- pg27200.txt: Correctly detects 120 chapters (down from 125 false positives)
- Skips 5 TOC-only entries (The Dumb Cook, Ole-Luk-Oie the Dream God, etc.)
- All chapters have proper content (no 0-byte or oversized chapters)

**Test Case:** `tests/test_title_only_toc.txt`
- 4 titles in TOC, only 3 actual stories
- Correctly detects 3 chapters, skips "The Missing Story"

### Illustration Block Handling

**Problem:** Books contain illustration markers that can include chapter-like text:
```
[Illustration: CHAPTER heading shown in decorative border]
```

**Solution:** Track illustration state and skip chapter detection inside them

```python
# State tracking
in_illustration = False

for i, line in enumerate(lines):
    line_stripped = line.strip()

    # Track illustration blocks
    if line_stripped.startswith('[Illustration'):
        in_illustration = True

    closes_illustration = in_illustration and line_stripped.endswith(']')

    if closes_illustration:
        in_illustration = False
        continue

    # Skip chapter detection if inside illustration
    if in_illustration:
        continue

    # ... proceed with chapter detection ...
```

### False Positive Prevention

**Problem:** Lines like "Frederick II. But Fate..." should not match Roman numeral pattern

**Solution:** Require all-caps first word in title for Roman-numeral-only pattern

**Location:** `scripts/generate_summaries.py:533-548`

```python
# For pattern: r'^([IVXLCDM]+)\.\s+(.+)$'
if pattern == r'^([IVXLCDM]+)\.\s+(.+)$':
    # Check original line only has whitespace before Roman numeral
    if not line.lstrip() == line_stripped:
        continue

    # Require ALL CAPS first word in title
    title_part = match.group(2).strip()
    first_word = title_part.split()[0] if title_part else ""

    # Skip if first word is not all caps
    # Allows: "I. THE THREE METAMORPHOSES"
    # Rejects: "II. But Fate lay behind it all"
    if first_word and not first_word.isupper():
        continue
```

### BOOK Marker Embedded Detection (2025-11-25)

**Problem:** Some books like "Moby-Dick" have BOOK markers embedded within chapter content rather than as actual chapter boundaries.

**Example:** In Moby Dick's "Cetology" chapter:
```
CHAPTER 32. Cetology.

Already we have encountered whole Whales of various sizes...

BOOK I. (Folio)
CHAPTER I. (Sperm Whale).
BOOK II. (Octavo)
CHAPTER I. (Grampus).
...
```

These BOOK markers are part of Ishmael's classification system discussion, NOT separate chapters.

**Solution:** Sophisticated embedded marker detection

**Location:** `scripts/generate_summaries.py:617-673`

```python
# Check if this BOOK marker is embedded in a paragraph
# by looking at surrounding lines for substantial content
# IMPORTANT: Only treat as embedded if substantial content is on ADJACENT lines
# (no blank lines in between), to avoid false positives where BOOK markers
# appear between sections separated by blank lines
is_embedded = False

# Look at 3 lines before and after for context
context_range = 3
for offset in range(-context_range, context_range + 1):
    if offset == 0:
        continue  # Skip current line

    context_idx = i + offset
    if 0 <= context_idx < len(lines):
        context_line = lines[context_idx].strip()

        # Check if this is substantial content (not a marker, not empty)
        # Substantial = has lowercase letters and is longer than 20 chars
        has_lowercase = any(c.islower() for c in context_line)
        is_long_enough = len(context_line) > 20
        is_not_marker = not re.match(r'^(CHAPTER|BOOK|VOLUME|PART|ACT)\s+', context_line)

        if has_lowercase and is_long_enough and is_not_marker:
            # Found substantial content - check if there are blank lines in between
            # If all lines between current and context line are non-empty, it's truly embedded
            has_blank_between = False
            start_check = min(i, context_idx)
            end_check = max(i, context_idx)
            for check_idx in range(start_check + 1, end_check):
                if not lines[check_idx].strip():
                    has_blank_between = True
                    break

            # Only treat as embedded if no blank lines between
            if not has_blank_between:
                is_embedded = True
                break

# If embedded in a paragraph, treat as content not a chapter boundary
# ALSO: If we're currently inside a numbered chapter (not preface/intro) AND we haven't
# seen any BOOK markers yet, treat BOOK markers as content. This handles cases like
# Moby Dick's Cetology chapter where BOOK markers are part of the discussion
# (BOOK I Folio, BOOK II Octavo, etc.)
# BUT: If we already have BOOK markers, this is a nested BOOK/CHAPTER structure
# and we should process BOOK markers as book boundaries
# ALSO: Preface (Chapter 0) doesn't prevent BOOK markers from being processed
is_embedded_in_chapter = (current_chapter is not None and
                         current_chapter[0] != 0 and  # Not preface/intro
                         len(book_markers) == 0)
if is_embedded or is_embedded_in_chapter:
    # This is content within a chapter (e.g., Moby Dick's Cetology chapter)
    # Add to current chapter text instead of treating as boundary
    if current_chapter is not None and not in_illustration:
        current_text.append(line)
    elif not found_first_chapter and not in_illustration:
        preface_text.append(line)
    continue
```

**Detection Criteria:**

1. **Substantial Content Check:**
   - Surrounding lines must have lowercase letters
   - Surrounding lines must be longer than 20 characters
   - Surrounding lines must not be other markers (CHAPTER, BOOK, etc.)

2. **Adjacency Check:**
   - Content must be ADJACENT (no blank lines between marker and content)
   - Prevents false positives where BOOK markers separate sections

3. **Chapter Context Check:**
   - If currently inside a numbered chapter (not Chapter 0)
   - AND no BOOK markers have been seen yet
   - THEN treat BOOK markers as embedded content

**Impact:**
- Correctly handles Moby Dick's Cetology chapter (Chapter 32) where BOOK markers are part of the whale classification discussion
- Prevents fragmentation of narrative chapters that discuss book/volume structures
- Still correctly detects BOOK-based chapter structures like "The Odyssey"

### BOOK Markers as Chapters

**Problem:** Books like "The Odyssey" use BOOK markers as the actual chapters:
```
BOOK I
BOOK II
...
BOOK XXIV
```

**Solution:** Detect when BOOK markers should be converted to chapters

**Location:** `scripts/generate_summaries.py:800-868`

```python
# Condition: Many BOOK markers but few nested chapters
should_convert_books = False
if book_markers and len(book_markers) > 3:
    # Count non-intro chapters (not chapter 0 or X00)
    non_intro_chapters = [ch for ch in chapters if ch[0] != 0 and ch[0] % 100 != 0]

    # If we have < 30% expected chapters, convert BOOK markers
    if len(non_intro_chapters) < len(book_markers) * 0.3:
        should_convert_books = True

if should_convert_books:
    chapters = []

    # Deduplicate book_markers - keep last occurrence
    # (BOOK markers appear twice: TOC and actual content)
    seen_numbers = {}
    for marker in book_markers:
        seen_numbers[marker['number']] = marker

    unique_book_markers = [seen_numbers[num] for num in sorted(seen_numbers.keys())]

    # Extract content for each BOOK marker
    for idx, marker_info in enumerate(unique_book_markers):
        start_line = marker_info['line_index']
        end_line = unique_book_markers[idx + 1]['line_index'] if idx + 1 < len(unique_book_markers) else len(lines)

        # Extract content between markers
        book_content = '\n'.join(lines[start_line + 1:end_line])
        book_content = self.normalize_chapter_text(book_content)

        # Create chapter with simple numbering (1, 2, 3...)
        chapter_num = marker_info['number']
        chapter_title = f"{marker_info['marker_type']} {marker_info['numeral']}"

        chapters.append((chapter_num, chapter_title, book_content))
```

### Text Normalization

**Problem:** Raw text has inconsistent newlines and spacing

**Solution:** Normalize to single newlines within paragraphs, preserve paragraph breaks

**Location:** `scripts/generate_summaries.py:333-368`

```python
def normalize_chapter_text(self, text: str) -> str:
    """
    Normalize chapter text:
    - Remove single newlines within paragraphs
    - Keep paragraph breaks (double newlines)
    - Trim whitespace from each line
    - Use single newline between paragraphs
    """
    # Windows to Unix line endings
    text = text.replace('\r\n', '\n')

    # Replace 3+ newlines with exactly 2 (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Split into paragraphs
    paragraphs = text.split('\n\n')

    # For each paragraph: trim lines and join with space
    normalized_paragraphs = []
    for paragraph in paragraphs:
        lines = paragraph.split('\n')
        trimmed_lines = [line.strip() for line in lines if line.strip()]
        normalized_paragraph = ' '.join(trimmed_lines)
        if normalized_paragraph:
            normalized_paragraphs.append(normalized_paragraph)

    # Join paragraphs with single newline
    result = '\n'.join(normalized_paragraphs)

    # Clean up multiple spaces
    result = re.sub(r' {2,}', ' ', result)

    return result
```

### Chapter Title Normalization

**Problem:** Chapter titles have inconsistent capitalization from source texts
- ALL CAPS titles: `"VARIATION UNDER DOMESTICATION"`
- Words after em-dashes not capitalized: `"Huck.—miss Watson.—tom Sawyer"`
- First words in quotes not capitalized: `""it Is The Child!""`
- Mixed hyphenation: `"Tea-Party"` vs `"Tea-party"`

**Solution:** Normalize all chapter titles to consistent title case with proper punctuation handling

**Location:** `scripts/generate_summaries.py:556-640`

**Implementation:**

```python
def normalize_chapter_title(self, title: str) -> str:
    """
    Normalize chapter title to use consistent title case.

    Handles special cases:
    - Words inside quotes are always capitalized (including first word)
    - Words after em-dashes (—) are capitalized
    - Words after colons (:) are capitalized
    - Words after periods (.) are capitalized
    """
    import re

    if not title or not title.strip():
        return title

    # Words that should remain lowercase (unless first word or after punctuation)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    # Step 1: Add spaces around em-dashes for proper word splitting
    # "Huck.—miss" → "Huck. — miss"
    title = title.replace('—', ' — ')
    title = re.sub(r':(\S)', r': \1', title)  # Handle colons
    title = re.sub(r'\s+', ' ', title).strip()  # Collapse spaces

    # Step 2: Process each word
    in_quotes = False
    capitalize_next = True  # First word always capitalized
    result = []

    for word in title.split():
        # Detect quote characters (straight and curly: U+201C, U+201D)
        has_quote = '"' in word or '\u201c' in word or '\u201d' in word
        starts_with_quote = word.startswith('"') or word.startswith('\u201c') or word.startswith('\u201d')

        if has_quote:
            in_quotes = not in_quotes

        # Handle standalone em-dash
        if word == '—':
            result.append(word)
            capitalize_next = True
            continue

        # Process quoted words
        if starts_with_quote:
            quote_char = word[0]
            rest = word[1:]
            if capitalize_next:
                result.append(quote_char + rest.capitalize())
            else:
                # Capitalize first letter after quote
                result.append(quote_char + rest[0].upper() + rest[1:].lower() if len(rest) > 1 else quote_char + rest.upper())
            capitalize_next = False
            in_quotes = True
        # Capitalize if needed
        elif capitalize_next or in_quotes:
            result.append(word.capitalize())
            capitalize_next = False
        # Apply lowercase rule
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # Default: capitalize
        else:
            result.append(word.capitalize())

        # Set flag for next word after punctuation
        if result[-1].endswith(':') or result[-1].endswith('.'):
            capitalize_next = True

    # Step 3: Clean up - remove added spaces around em-dashes
    result_str = ' '.join(result)
    result_str = result_str.replace(' — ', '—')

    return result_str
```

**Key Features:**

1. **Em-dash Handling:**
   - Temporarily adds spaces around em-dashes for word splitting
   - Capitalizes words after em-dashes
   - Removes added spaces after processing
   - Example: `"Huck.—miss Watson"` → `"Huck.—Miss Watson"`

2. **Quote Handling:**
   - Supports both straight quotes (U+0022) and curly quotes (U+201C, U+201D)
   - Capitalizes first word inside quotes
   - Respects capitalization after punctuation even in quotes
   - Example: `""it Is The Child!""` → `""It Is The Child!""`

3. **Punctuation Capitalization:**
   - Words after colons, periods, and em-dashes are capitalized
   - Example: `"Medieval. a"` → `"Medieval. A"`

4. **Article/Preposition Handling:**
   - Small words (a, an, the, of, in, etc.) are lowercase
   - Unless they're the first word or after punctuation
   - Example: `"Of the Division of Labour"` (first word capitalized)

5. **Usage:**
   - Called when saving chapters: `scripts/generate_summaries.py:1638`
   - Backfill script available: `scripts/backfill_chapter_title_case.py`
   - Dry-run mode: `python3 scripts/backfill_chapter_title_case.py --dry-run`

**Results:**
- Fixed 1,013 out of 2,965 chapter titles
- Consistent title case across all 80 books in database

### Coverage Validation

**Problem:** Detect if chapter parsing is losing significant content

**Solution:** Calculate percentage of original text captured

**Location:** `scripts/generate_summaries.py:1624-1639`

```python
# Calculate total parsed content
total_parsed_chars = sum(len(ch_text) for _, _, ch_text in chapters)
original_chars = len(text)
coverage_percent = (total_parsed_chars / original_chars * 100) if original_chars > 0 else 0

print(f"\nContent Coverage:")
print(f"  Original text: {original_chars:,} chars")
print(f"  Parsed chapters: {total_parsed_chars:,} chars")
print(f"  Coverage: {coverage_percent:.1f}%")

if coverage_percent < 90:
    print(f"  ⚠️  WARNING: Only {coverage_percent:.1f}% of content captured - may be losing content!")
elif coverage_percent > 110:
    print(f"  ⚠️  WARNING: Parsed content is {coverage_percent:.1f}% - may have duplicates!")
else:
    print(f"  ✓ Good coverage - parsing looks correct")
```

---

## TTS Engine Implementation

### Overview

**Technology:** VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech)

**Library:** Coqui TTS (https://github.com/coqui-ai/TTS)

**Model:** `tts_models/en/vctk/vits` - Multi-speaker English model

**Location:** `backend/tts_handler.py`

### Architecture

```
User Request (text to convert)
        ↓
Flask API (/api/tts/generate)
        ↓
TTS Handler (tts_handler.py)
        ↓
Check cache (file already exists?)
        ├─ YES → Return cached file path
        └─ NO → Continue
            ↓
Text validation (length, characters)
            ↓
Load VITS model (lazy loading)
            ↓
Generate audio waveform
            ↓
Save WAV file to static/audio/
            ↓
Return file path
```

### TTS Handler Class

**Location:** `backend/tts_handler.py`

```python
class TTSHandler:
    def __init__(self):
        self.model = None  # Lazy loading
        self.model_name = config.TTS_MODEL_NAME
        self.output_dir = config.TTS_OUTPUT_DIR
        self.max_length = config.MAX_TTS_LENGTH

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_model(self):
        """Lazy load TTS model (only when first needed)"""
        if self.model is None:
            from TTS.api import TTS
            self.model = TTS(self.model_name)

    def generate_audio(self, text: str, summary_id: int = None,
                      chapter_id: int = None) -> str:
        """
        Generate TTS audio for given text.
        Returns: file_path (relative to static/)
        """
        # 1. Validate text length
        if len(text) > self.max_length:
            raise ValueError(f"Text too long ({len(text)} chars, max {self.max_length})")

        # 2. Generate unique filename based on content hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        filename = f"tts_{text_hash}.wav"
        file_path = os.path.join(self.output_dir, filename)

        # 3. Check cache - return if already exists
        if os.path.exists(file_path):
            return f"audio/{filename}"

        # 4. Load model (lazy)
        self._load_model()

        # 5. Generate audio
        self.model.tts_to_file(
            text=text,
            file_path=file_path,
            speaker="p225"  # Female speaker
        )

        # 6. Return relative path for web serving
        return f"audio/{filename}"
```

### VITS Model Details

**Model Architecture:**
- Variational autoencoder (VAE) for latent representation
- Normalizing flows for improved expressiveness
- Adversarial training (GAN discriminator)
- Multi-speaker conditioning

**VCTK Model Specifics:**
- Dataset: VCTK Corpus (110 English speakers with different accents)
- Sample Rate: 22050 Hz
- Audio Format: 16-bit WAV
- Speakers: 109 available speaker IDs (p225-p376)
- Language: English (various UK accents)

**Speaker Selection:**
- Default: `p225` (female, English accent)
- Configurable in code for multi-voice support

### Caching Strategy

**Cache Key:** MD5 hash of text content

```python
text_hash = hashlib.md5(text.encode()).hexdigest()
filename = f"tts_{text_hash}.wav"
```

**Benefits:**
- Identical text reuses same audio file
- Reduces computation time (0.1s vs 10-30s)
- Reduces storage (multiple references to same file)

**Cache Storage:**
```
frontend/static/audio/
├── tts_a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4.wav
├── tts_b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4.wav
└── ...
```

**Cache Lifetime:** Permanent (no automatic expiration)

**Manual Cleanup:**
```bash
rm frontend/static/audio/*.wav
```

### Audio Generation Process

**Step 1: Text Preprocessing** (handled by TTS library)
- Normalize punctuation
- Expand abbreviations (Dr. → Doctor)
- Convert numbers to words (123 → one hundred twenty-three)
- Handle special characters

**Step 2: Phoneme Conversion**
- Grapheme-to-phoneme (G2P) conversion
- Uses learned phoneme representations
- Handles English pronunciation rules

**Step 3: Mel Spectrogram Generation**
- VITS posterior encoder generates mel spectrogram
- Uses attention mechanism for text-audio alignment
- Variational inference for diverse prosody

**Step 4: Waveform Generation**
- HiFi-GAN vocoder converts mel spectrogram to waveform
- High-fidelity audio output (22050 Hz)
- Natural prosody and intonation

**Step 5: File Writing**
- WAV format (uncompressed)
- File size: ~220 KB per second of audio
- Typical summary: 5-10 KB text → 2-5 MB audio

### Flask API Integration

**Endpoint:** `POST /api/tts/generate`

**Request:**
```json
{
  "text": "Summary text to convert...",
  "summary_id": 123,  // optional
  "chapter_id": null   // optional
}
```

**Response:**
```json
{
  "audio_url": "/static/audio/tts_a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4.wav",
  "duration": 45.2
}
```

**Implementation:**
```python
@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    data = request.json
    text = data.get('text', '')

    try:
        # Generate audio (uses cache if available)
        file_path = tts_handler.generate_audio(text)

        # Calculate duration from file
        audio_path = os.path.join('frontend/static', file_path)
        duration = get_audio_duration(audio_path)

        return jsonify({
            'audio_url': f'/static/{file_path}',
            'duration': duration
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Error Handling

**Text Length Validation:**
```python
if len(text) > config.MAX_TTS_LENGTH:
    raise ValueError(f"Text too long ({len(text)} chars, max {config.MAX_TTS_LENGTH})")
```

**Model Loading Errors:**
- Network errors when downloading model (first run)
- Disk space errors (model is ~100 MB)
- GPU/CPU compatibility issues

**Audio Generation Errors:**
- Out of memory (text too long)
- Invalid characters (rare, TTS library handles most)
- File write permission errors

### Performance Characteristics

**Model Download (First Run Only):**
- Size: ~100 MB
- Time: 1-5 minutes (depends on network)
- Location: `~/.local/share/tts/tts_models--en--vctk--vits/`

**First Generation (Cold Start):**
- Model loading: 5-10 seconds
- Audio generation: 10-30 seconds (depends on text length)

**Subsequent Generations (Warm):**
- Model already loaded: 0s
- Audio generation: 10-30 seconds
- Cached audio: 0.1 seconds

**Memory Usage:**
- Model loaded: ~500 MB RAM
- During generation: +200 MB (temporary)

### Configuration Options

**`backend/config.py`:**

```python
TTS_MODEL_NAME = "tts_models/en/vctk/vits"
TTS_OUTPUT_DIR = Path(__file__).parent.parent / 'frontend' / 'static' / 'audio'
MAX_TTS_LENGTH = 5000  # characters
```

**Alternative Models:**
- `tts_models/en/ljspeech/tacotron2-DDC` - Single speaker, faster
- `tts_models/en/ljspeech/glow-tts` - Flow-based, faster inference
- `tts_models/multilingual/multi-dataset/your_tts` - Multi-language support

### Gemini TTS (Offline Generation)

**Overview:**

In addition to real-time VITS TTS for user-triggered audio generation, Summra supports offline batch TTS generation using Google Gemini 2.5 Flash TTS API. This enables pre-generating high-quality audio files for entire books.

**Technology:** Google Gemini 2.5 Flash TTS API

**Model:** `gemini-2.5-flash-tts`

**Location:** `backend/gemini_tts_handler.py`, `scripts/generate_offline_tts.py`

**Purpose:**
- Offline batch generation of TTS audio for book summaries and chapters
- Separate from real-time VITS TTS (user-triggered remains VITS)
- Professional voice options with higher quality than VITS
- Pre-generation for instant playback

**Architecture:**

```
Offline Script (generate_offline_tts.py)
        ↓
Gemini TTS Handler (gemini_tts_handler.py)
        ↓
Rate Limiter (3 req/min, 10k tokens/min)
        ↓
Check cache (file already exists?)
        ├─ YES → Skip generation
        └─ NO → Continue
            ↓
Text cleaning (remove markdown, preserve punctuation)
            ↓
Token estimation (~4 chars per token)
            ↓
Wait for rate limit if needed
            ↓
Gemini API call with voice configuration
            ↓
Extract audio data (WAV format)
            ↓
Save to frontend/static/audio/ with _gemini.wav suffix
            ↓
Store path in database (audio_files table)
            ↓
Return file path
```

**Rate Limiting Implementation:**

**Location:** `backend/gemini_tts_handler.py:21-61`

```python
class RateLimiter:
    """Rate limiter for Gemini TTS API"""
    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests = max_requests_per_minute  # 3
        self.max_tokens = max_tokens_per_minute      # 10,000
        self.request_times = []      # Rolling window of request timestamps
        self.token_counts = []       # (timestamp, token_count) tuples

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Wait if approaching rate limits"""
        current_time = time.time()
        one_minute_ago = current_time - 60

        # Clean old entries (older than 60 seconds)
        self.request_times = [t for t in self.request_times if t > one_minute_ago]
        self.token_counts = [(t, c) for t, c in self.token_counts if t > one_minute_ago]

        # Check request limit (3/min)
        if len(self.request_times) >= self.max_requests:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                print(f"Rate limit approaching - waiting {wait_time:.1f}s...")
                time.sleep(wait_time + 1)

        # Check token limit (10k/min)
        total_tokens = sum(c for _, c in self.token_counts)
        if total_tokens + estimated_tokens > self.max_tokens:
            wait_time = 60 - (current_time - self.token_counts[0][0])
            if wait_time > 0:
                print(f"Token limit approaching - waiting {wait_time:.1f}s...")
                time.sleep(wait_time + 1)

    def record_request(self, tokens_used: int):
        """Record completed request"""
        current_time = time.time()
        self.request_times.append(current_time)
        self.token_counts.append((current_time, tokens_used))
```

**Token Estimation:**
```python
# Rough estimate: 1 token ≈ 4 characters
estimated_tokens = len(text) // 4
```

**Gemini TTS Handler Class:**

**Location:** `backend/gemini_tts_handler.py:63-228`

```python
class GeminiTTSHandler:
    def __init__(self, voice: str = None):
        self.output_dir = config.TTS_OUTPUT_DIR  # frontend/static/audio
        self.voice = voice or config.GEMINI_TTS_VOICE  # Default: "Puck"
        self.model_name = config.GEMINI_TTS_MODEL  # "gemini-2.5-flash-tts"

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            config.GEMINI_TTS_MAX_REQUESTS_PER_MINUTE,  # 3
            config.GEMINI_TTS_MAX_TOKENS_PER_MINUTE     # 10,000
        )

        # Initialize Gemini client
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)

    def generate_audio(self, text: str, audio_id: str = None) -> Optional[str]:
        """
        Generate audio from text using Gemini TTS API
        Returns: Path to generated WAV file
        """
        # 1. Generate unique filename
        if audio_id:
            filename = f"{audio_id}_gemini.wav"
        else:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            filename = f"{text_hash}_gemini.wav"

        output_path = self.output_dir / filename

        # 2. Check cache
        if output_path.exists():
            return str(output_path)

        # 3. Clean text for TTS
        cleaned_text = self.clean_text_for_speech(text)

        # 4. Rate limiting
        estimated_tokens = self.estimate_tokens(cleaned_text)
        self.rate_limiter.wait_if_needed(estimated_tokens)

        # 5. Generate speech
        response = self.client.models.generate_content(
            model=self.model_name,
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

        # 6. Record request
        self.rate_limiter.record_request(estimated_tokens)

        # 7. Extract and save audio
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = part.inline_data.data
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                return str(output_path)

        return None
```

**Text Cleaning:**

Same text cleaning logic as VITS TTS to ensure consistent quality:

```python
def clean_text_for_speech(self, text: str) -> str:
    """
    Remove markdown/HTML formatting, preserve natural punctuation
    """
    # Remove markdown headers, bold, italic, links, code
    # Remove HTML tags
    # Replace curly quotes/dashes with standard characters
    # KEEP: . , ! ? ; : ' " - (for natural speech phrasing)
    # REMOVE: ` _ ( ) { } [ ] / \ | @ # $ % ^ & * + = ~ < >
    # Normalize whitespace
    return cleaned
```

**Available Voices:**

Gemini TTS provides 5 high-quality prebuilt voices:

1. **Puck** (Default) - Neutral, clear
2. **Charon** - Deep, authoritative
3. **Kore** - Feminine, warm
4. **Fenrir** - Strong, dynamic
5. **Aoede** - Expressive, engaging

**Audio File Naming:**

```
frontend/static/audio/
├── summary_28_concise_gemini.wav      # Book 28, concise summary
├── summary_28_medium_gemini.wav       # Book 28, medium summary
├── chapter_28_1_gemini.wav            # Book 28, Chapter 1
├── chapter_28_2_gemini.wav            # Book 28, Chapter 2
└── ...
```

**Naming Convention:**
- Summaries: `summary_{book_id}_{summary_type}_gemini.wav`
- Chapters: `chapter_{book_id}_{chapter_number}_gemini.wav`
- `_gemini.wav` suffix distinguishes from VITS TTS files

**Offline Generation Script:**

**Location:** `scripts/generate_offline_tts.py`

**Usage:**
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

**Script Features:**

1. **Book Selection:**
   - By exact title: `--book "The Time Machine"`
   - By partial title: `--book "Time Machine"`
   - By book ID: `--book 28`

2. **Summary Generation:**
   - Specific types: `--summaries concise medium`
   - All summaries: `--all-summaries`
   - Checks for existing audio in database (skips if present)

3. **Chapter Generation:**
   - Chapter ranges: `--comprehensive-chapters 1-5`
   - Multiple ranges: `--comprehensive-chapters 1-5,10,15-20`
   - Parses format: "1-5" → [1, 2, 3, 4, 5]
   - Parses format: "1,3,5-7" → [1, 3, 5, 6, 7]

4. **Voice Selection:**
   - Default: Puck (from config)
   - Custom: `--voice Charon`

5. **Database Integration:**
   - Stores audio paths in `audio_files` table
   - Links to `summary_id` or `chapter_id`
   - UI can fetch and play audio transparently

**Configuration:**

**Location:** `backend/config.py:50-58`

```python
# Gemini TTS API configuration (for offline generation only)
GEMINI_TTS_MODEL = 'gemini-2.5-flash-tts'
GEMINI_TTS_VOICE = 'Puck'  # Default voice
GEMINI_TTS_MAX_REQUESTS_PER_MINUTE = 3
GEMINI_TTS_MAX_TOKENS_PER_MINUTE = 10000
```

**Performance Characteristics:**

**Rate Limits:**
- Requests: 3 per minute (API constraint)
- Tokens: 10,000 per minute (API constraint)

**Generation Speed:**
- Small summary (500 words): ~5-10 seconds
- Medium summary (2500 words): ~15-30 seconds
- Chapter summary (1000 words): ~10-20 seconds

**Throughput:**
- Maximum: 3 summaries per minute
- Typical: ~2.5 summaries per minute (accounting for rate limiting)
- Full book (3 summaries + 20 chapters): ~10-15 minutes

**Cost Estimation:**
- Gemini TTS pricing: ~$0.01 per 1000 characters
- Concise summary (500 words ≈ 2500 chars): ~$0.025
- Medium summary (2500 words ≈ 12500 chars): ~$0.125
- Chapter (1000 words ≈ 5000 chars): ~$0.05
- Full book (3 summaries + 20 chapters): ~$1.25

**Quality Comparison:**

| Feature | VITS (Coqui TTS) | Gemini TTS |
|---------|------------------|------------|
| **Use Case** | Real-time user requests | Offline batch generation |
| **Quality** | Good (synthetic) | Excellent (near-human) |
| **Voices** | 109 VCTK speakers | 5 professional voices |
| **Speed** | 10-30s (local) | 5-30s (API call) |
| **Cost** | Free (compute only) | ~$0.01 per 1000 chars |
| **Scalability** | Limited by server | Limited by API quota |
| **Customization** | Speaker selection | Voice selection |

**Database Integration:**

Both VITS and Gemini TTS use the same `audio_files` table:

```sql
CREATE TABLE audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id INTEGER,           -- FK to summaries table
    chapter_id INTEGER,           -- FK to chapters table
    file_path TEXT NOT NULL,      -- Path to WAV file (includes _gemini suffix)
    duration_seconds REAL,        -- Duration (can be calculated from WAV)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (summary_id) REFERENCES summaries(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    CHECK((summary_id IS NOT NULL AND chapter_id IS NULL) OR
          (summary_id IS NULL AND chapter_id IS NOT NULL))
)
```

**UI Access:**

Frontend queries audio files the same way for both TTS engines:

```python
# Get audio for a summary
audio = db.get_audio_file(summary_id=123)
if audio:
    audio_url = f"/static/{audio['file_path']}"
    # Plays: /static/audio/summary_28_concise_gemini.wav
```

**Caching:**

- Both engines check file existence before generation
- Gemini TTS: Checks `{audio_id}_gemini.wav` exists
- VITS TTS: Checks `tts_{hash}.wav` exists
- Database tracks which audio files exist
- Regeneration skipped if file already present

**Error Handling:**

**Common Errors:**

1. **API Key Missing:**
   ```python
   if not api_key:
       raise ValueError("GEMINI_API_KEY environment variable not set")
   ```

2. **Rate Limit Exceeded:**
   - Automatic waiting handled by RateLimiter
   - Prints wait time and sleeps
   - Resumes after quota resets

3. **Network Errors:**
   - API call failures caught and logged
   - Returns None (skip this audio file)
   - Continues with next file

4. **Empty Text:**
   ```python
   if not cleaned_text or cleaned_text.isspace():
       print("Warning: Text is empty after cleaning")
       return None
   ```

5. **Response Parsing Errors:**
   - No audio data in response
   - Malformed API response
   - Returns None with error message

**Future Enhancements:**

1. **Audio Duration Calculation:**
   - Read WAV file header to get duration
   - Update database with accurate duration
   - Used for progress bars in UI

2. **Batch Book Processing:**
   - Process multiple books in one script run
   - Queue-based processing
   - Progress tracking

3. **Retry Logic:**
   - Automatic retry on transient failures
   - Exponential backoff
   - Maximum retry attempts

4. **Voice Rotation:**
   - Different voices for different characters/chapters
   - Configurable voice mapping
   - Enhanced listening experience

---

## LLM Call Logic & Rate Limiting

### Overview

**LLM Provider:** Google Gemini API (via `google-genai` SDK)

**Models Used:**
- `gemini-2.0-flash-exp` - Concise and medium summaries (fast, cost-effective)
- `gemini-exp-1206` - Comprehensive chapter summaries (more capable)

**Rate Limits:**
- Requests: 10 per minute
- Tokens: 250,000 per minute (input + output)

**Call Size Limits:**
- Maximum: 900,000 characters per call (~225K tokens)
- Large Call Threshold: 100,000 tokens
- Large Call Spacing: 60 seconds between large calls

### Rate Limiter Implementation

**Location:** `scripts/generate_summaries.py:40-79`

**Algorithm:** Rolling window token bucket with large call throttling

```python
class RateLimiter:
    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.request_times = []  # List of timestamps
        self.token_counts = []   # List of (timestamp, token_count) tuples

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Wait if we're approaching rate limits"""
        current_time = time.time()

        # 1. Remove requests older than 1 minute (rolling window)
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        self.token_counts = [(t, count) for t, count in self.token_counts
                            if current_time - t < 60]

        # 2. Check request limit
        if len(self.request_times) >= self.max_requests:
            # Wait until oldest request expires
            sleep_time = 60 - (current_time - self.request_times[0]) + 1
            print(f"Rate limit: Waiting {sleep_time:.1f}s for request quota...")
            time.sleep(sleep_time)
            self.request_times = []  # Reset after waiting

        # 3. Check token limit
        total_tokens = sum(count for _, count in self.token_counts)
        if total_tokens + estimated_tokens > self.max_tokens:
            if self.token_counts:
                # Wait until oldest token request expires
                sleep_time = 60 - (current_time - self.token_counts[0][0]) + 1
                print(f"Rate limit: Waiting {sleep_time:.1f}s for token quota...")
                time.sleep(sleep_time)
            self.token_counts = []  # Reset after waiting

        # 4. Record this request
        self.request_times.append(current_time)
        if estimated_tokens > 0:
            self.token_counts.append((current_time, estimated_tokens))
```

**Large Call Throttling:**

**Location:** `scripts/generate_summaries.py:102-127`

In addition to the standard rate limiter, large API calls (>100K tokens) trigger additional spacing to prevent burst rate limit errors:

```python
def wait_if_needed_for_large_call(self, estimated_tokens: int):
    """Wait if a large API call was recently made to avoid rate limits"""
    if estimated_tokens < self.LARGE_CALL_THRESHOLD:  # 100K tokens
        return  # Small call, no wait needed

    if self.last_large_call_time is None:
        # First large call, just record the time
        self.last_large_call_time = time.time()
        return

    # Calculate time since last large call
    elapsed = time.time() - self.last_large_call_time
    wait_needed = self.LARGE_CALL_WAIT_SECONDS - elapsed  # 60 seconds

    if wait_needed > 0:
        print(f"\n⏱️  Large API call detected ({estimated_tokens:,} tokens)")
        print(f"   Waiting {wait_needed:.1f}s to avoid rate limits...")
        time.sleep(wait_needed)

    # Update last large call time
    self.last_large_call_time = time.time()
```

**Call Sequence:**
```
1. wait_if_needed_for_large_call(estimated_tokens)  # Large call spacing
2. rate_limiter.wait_if_needed(estimated_tokens)     # Standard rate limiting
3. Make API call
```

**Token Estimation:**
```python
# Rough estimate: 1 token ≈ 4 characters
# Cap at maximum call size
max_chars = min(len(text), self.MAX_CHARS_PER_CALL)  # 900K chars
estimated_tokens = max_chars // 4 + expected_output_words
```

**Example Timeline:**
```
Time 0s:  Request 1 (30k tokens)
Time 5s:  Request 2 (30k tokens)
Time 10s: Request 3 (30k tokens)
...
Time 45s: Request 10 (30k tokens) - total = 300k tokens
Time 46s: Request 11 would exceed 250k limit
          → Wait 14s (until Time 60s, when Request 1 expires)
Time 60s: Request 11 proceeds (only counting Requests 2-11 = 300k - 30k = 270k)

Large Call Example:
Time 0s:  Large call (150K tokens) - first large call
Time 30s: Another large call attempted (120K tokens)
          → Wait 30s (60s - 30s elapsed)
Time 60s: Large call proceeds
```

### LLM Client Initialization

**Location:** `scripts/generate_summaries.py:84-91`

```python
class SummaryGenerator:
    def __init__(self, api_key: str):
        # Initialize Gemini client with API key
        self.client = genai.Client(api_key=api_key)
        self.db = models.Database()
        self.rate_limiter = RateLimiter(
            config.MAX_REQUESTS_PER_MINUTE,
            config.MAX_TOKENS_PER_MINUTE
        )
```

### Combined Summary & Metadata Generation (Added 2025-12-02, Optimized 2025-12-12)

**Purpose:** Generate all summaries (concise + medium) and book metadata in a single LLM call for efficiency and cost savings.

**Model:** `gemini-2.5-flash`

**Location:** `scripts/generate_summaries.py:1629-1788`

**Token Optimization (2025-12-12):** Book content removed from prompt. The LLM now relies on its training data knowledge of classic literature, using only title and author. This reduced input tokens from ~140,000 to ~200 per call (99.86% reduction).

**Returns:** Dictionary with 7 fields:
1. `about_text` - Short "About the Book" section (75-100 words)
2. `concise_summary` - Spoiler-free overview (~500 words)
3. `medium_summary` - Comprehensive analysis (2000-3000 words)
4. `relevance_now` - Why relevant today (75-100 words)
5. `author_country` - Author's country of origin (country name only)
6. `similar_books` - List of 5 similar books (title/author pairs)
7. `other_books_by_author` - List of author's other notable works (max 10)

```python
def generate_combined_summaries(self, text: str, title: str, author: str,
                                dry_run: bool = False) -> Dict:
    """
    Generate summaries and metadata in a single API call.
    Returns dictionary with: about_text, concise_summary, medium_summary,
    relevance_now, author_country, similar_books, other_books_by_author

    Note: This method does NOT include book content in the prompt - it relies on
    the LLM's training data knowledge of classic books.
    """
    model_name = config.SUMMARY_CONFIGS['concise']['model']

    # Estimate tokens for prompt only (no book content)
    estimated_tokens = 500 + 3000  # prompt + output

    prompt = f"""Analyze "{title}" by {author} and provide the following information.
Follow the format exactly with each section clearly marked:

### ABOUT THE BOOK (75-100 words)
[Generate a short, engaging summary for the "About the Book" section - 75-100 words]

This should be concise but compelling, suitable for a book overview page. **ABSOLUTELY
NO SPOILERS** - do not reveal plot twists, endings, character fates, or major reveals.
Focus only on the premise, themes, and setting.

### CONCISE SUMMARY (500 words)
[Generate a concise 500-word summary here]

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers
(no plot twists, endings, or major reveals). For non-fiction, cover main arguments
and key takeaways. Write in an engaging, accessible style.

### MEDIUM SUMMARY (2000-3000 words)
[Generate a comprehensive 2000-3000 word summary here]

Cover all major plot points, themes, and character developments in chronological order.
Discuss the author's writing style and analyze major themes. Spoilers are acceptable.
For non-fiction, cover all main arguments, evidence, and conclusions.

### RELEVANCE NOW (75-100 words)
[Explain why this book is relevant to modern audiences - 75-100 words]

Focus on contemporary themes, timeless insights, or how it speaks to current issues.

### AUTHOR COUNTRY
[State ONLY the country name where the author is from, without any other text]

### SIMILAR BOOKS
[List exactly 5 books similar to this one, in this exact format:]
TITLE|AUTHOR
TITLE|AUTHOR
TITLE|AUTHOR
TITLE|AUTHOR
TITLE|AUTHOR

### OTHER BOOKS BY AUTHOR
[List the author's other notable works, maximum 10 books, one per line]"""

    if dry_run:
        return {
            'about_text': '[DRY RUN] About the Book (150-200 words)...',
            'concise_summary': '[DRY RUN] Concise summary (500 words)...',
            'medium_summary': '[DRY RUN] Medium summary (2000-3000 words)...',
            'relevance_now': '[DRY RUN] Relevance Now (100-150 words)...',
            'author_country': '[DRY RUN] Country Name',
            'similar_books': [
                {'title': '[DRY RUN] Similar Book 1', 'author': '[DRY RUN] Author 1'},
                # ... 5 total
            ],
            'other_books_by_author': [
                '[DRY RUN] Other Book 1',
                # ... max 10
            ]
        }

    # Make API call
    response = self.client.models.generate_content(
        model=model_name,
        contents=prompt
    )

    result = response.text

    # Parse all 7 sections using regex
    about_match = re.search(r'### ABOUT THE BOOK.*?\n(.*?)(?=### CONCISE SUMMARY|###|$)',
                           result, re.DOTALL | re.IGNORECASE)
    concise_match = re.search(r'### CONCISE SUMMARY.*?\n(.*?)(?=### MEDIUM SUMMARY|###|$)',
                             result, re.DOTALL | re.IGNORECASE)
    medium_match = re.search(r'### MEDIUM SUMMARY.*?\n(.*?)(?=### RELEVANCE NOW|###|$)',
                            result, re.DOTALL | re.IGNORECASE)
    relevance_match = re.search(r'### RELEVANCE NOW.*?\n(.*?)(?=### AUTHOR COUNTRY|###|$)',
                               result, re.DOTALL | re.IGNORECASE)
    country_match = re.search(r'### AUTHOR COUNTRY.*?\n(.*?)(?=### SIMILAR BOOKS|###|$)',
                             result, re.DOTALL | re.IGNORECASE)
    similar_match = re.search(r'### SIMILAR BOOKS.*?\n(.*?)(?=### OTHER BOOKS|###|$)',
                             result, re.DOTALL | re.IGNORECASE)
    other_match = re.search(r'### OTHER BOOKS BY AUTHOR.*?\n(.*?)(?=###|$)',
                           result, re.DOTALL | re.IGNORECASE)

    # Extract and clean each section
    about_text = self.clean_llm_response(about_match.group(1)) if about_match else ''
    concise_summary = self.clean_llm_response(concise_match.group(1)) if concise_match else ''
    medium_summary = self.clean_llm_response(medium_match.group(1)) if medium_match else ''
    relevance_now = self.clean_llm_response(relevance_match.group(1)) if relevance_match else ''

    # Clean author country (remove prefixes like "Country:", "The author is from", etc.)
    author_country = ''
    if country_match:
        country_text = country_match.group(1).strip()
        # Remove common prefixes
        country_text = re.sub(r'^(Country:|The author is from|The author was from)\s*', '',
                             country_text, flags=re.IGNORECASE)
        author_country = country_text.strip()

    # Parse similar books from TITLE|AUTHOR format
    similar_books = []
    if similar_match:
        similar_text = similar_match.group(1).strip()
        for line in similar_text.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    similar_books.append({
                        'title': parts[0].strip(),
                        'author': parts[1].strip()
                    })

    # Parse other books by author (one per line)
    other_books_by_author = []
    if other_match:
        other_text = other_match.group(1).strip()
        for line in other_text.split('\n'):
            line = line.strip()
            # Remove leading numbers, bullets, dashes
            line = re.sub(r'^[\d\.\-\*\•]+\s*', '', line)
            if line and len(line) > 3:  # Filter out very short/empty lines
                other_books_by_author.append(line)

    return {
        'about_text': about_text,
        'concise_summary': concise_summary,
        'medium_summary': medium_summary,
        'relevance_now': relevance_now,
        'author_country': author_country,
        'similar_books': similar_books[:5],  # Limit to 5
        'other_books_by_author': other_books_by_author[:10]  # Limit to 10
    }
```

**Benefits:**
- **Cost Efficiency:** 85% reduction (7 separate calls → 1 call)
- **Better Context:** LLM sees full book when answering all questions
- **Consistency:** All metadata generated with same understanding of the book
- **Performance:** Faster than sequential calls (2-3 min vs 10-15 min for 7 calls)

**Typical Usage:**
- Input: 100k-300k words (book)
- Output: ~3,000-4,000 total words across all sections
- Time: 2-3 minutes
- Database Storage: Metadata saved to `books` table (about_text, relevance_now), `authors` table (country, other_books), and `similar_books` table

**Integration:** Called from `process_book()` during book ingestion. Results are automatically saved to database using helper methods:
- `update_book_metadata()` - Saves about_text and relevance_now
- `update_author_info()` - Creates/updates author with country and other_books
- `save_similar_books()` - Fuzzy matches and stores similar book relationships

---

### Concise Summary Generation (Legacy)

**Purpose:** 500-word overview without spoilers (fiction) or with key takeaways (non-fiction)

**Note:** This method is now deprecated in favor of `generate_combined_summaries()` which is more efficient.

**Model:** `gemini-2.0-flash-exp`

**Location:** `scripts/generate_summaries.py:1261-1335`

```python
def generate_concise_summary(self, text: str, title: str, author: str,
                            dry_run: bool = False) -> str:
    """Generate concise 500-word summary without spoilers for fiction"""
    model_name = config.SUMMARY_CONFIGS['concise']['model']

    # Cap text at maximum chars per call, preserving smaller limits
    max_chars = min(len(text), self.MAX_CHARS_PER_CALL)  # 900K chars

    # Estimate tokens (rough estimate: 1 token ≈ 4 characters)
    estimated_tokens = max_chars // 4 + 500

    prompt = f"""Generate a concise 500-word summary of "{title}" by {author}.

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers (no plot twists, endings, or major reveals). For non-fiction, cover main arguments and key takeaways. Write in an engaging, accessible style.

{text[:max_chars]}"""

    if dry_run:
        print(f"\n[DRY RUN] Would generate concise summary using {model_name}")
        print(f"Estimated tokens: {estimated_tokens:,}")
        print(f"Prompt length: {len(prompt):,} chars")
        print("-" * 60)
        return "[DRY RUN] Summary would be generated here"

    # Wait if needed for large API calls
    self.wait_if_needed_for_large_call(estimated_tokens)

    self.rate_limiter.wait_if_needed(estimated_tokens)

    # Log input word count
    input_words = len(text.split())
    print(f"Generating concise summary using {model_name}...")
    print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

    # Make API call with retry logic for retriable errors
    max_retries = 2  # Allow more retries for rate limits
    retry_count = 0
    result = None

    while retry_count <= max_retries:
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            result = self.clean_llm_response(response.text)
            break  # Success - exit retry loop
        except Exception as e:
            error_message = str(e)

            # Check if error is retriable (503, UNAVAILABLE, or 429 RESOURCE_EXHAUSTED)
            is_retriable = ('503' in error_message or 'overloaded' in error_message.lower() or
                           'UNAVAILABLE' in error_message or '429' in error_message or
                           'RESOURCE_EXHAUSTED' in error_message)

            # Extract retry delay from error message if present
            wait_time = 10  # Default
            if '429' in error_message or 'RESOURCE_EXHAUSTED' in error_message:
                # Try to extract retry delay from error message
                import re
                retry_match = re.search(r'Please retry in ([\d.]+)s', error_message)
                if retry_match:
                    wait_time = int(float(retry_match.group(1))) + 1
                else:
                    wait_time = 60  # Default to 1 minute for rate limits

            if is_retriable and retry_count < max_retries:
                retry_count += 1
                print(f"  ⚠️  API error (retriable): Rate limit or server issue")
                print(f"  ⏳ Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries + 1})")
                time.sleep(wait_time)
            else:
                if retry_count > 0:
                    print(f"  ❌ Max retries exceeded")
                raise

    output_words = len(result.split())
    print(f"  ← Output: {output_words:,} words")

    return result
```

**Context Window:** 2M tokens (Gemini 2.0 Flash)

**Character Limit:** 900K characters (~225K tokens) per call

**Retry Logic:**
- Max retries: 2
- Retriable errors: 503, UNAVAILABLE, 429, RESOURCE_EXHAUSTED
- Wait times: 10s (default), 60s (rate limits), or parsed from error message

**Typical Usage:**
- Input: 100k-300k words (book)
- Output: ~500 words
- Time: 30-60 seconds

### Medium Summary Generation

**Purpose:** 2000-3000 word comprehensive summary with all plot points

**Model:** `gemini-2.0-flash-exp`

**Location:** `scripts/generate_summaries.py:916-954`

```python
def generate_medium_summary(self, text: str, title: str, author: str,
                           dry_run: bool = False) -> str:
    """Generate medium-length 2000-3000 word summary"""
    model_name = config.SUMMARY_CONFIGS['medium']['model']

    estimated_tokens = min(len(text), 1000000) // 4 + 3000

    prompt = f"""Generate a comprehensive 2000-3000 word summary of "{title}" by {author}.

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions.

{text[:1000000]}"""

    self.rate_limiter.wait_if_needed(estimated_tokens)

    response = self.client.models.generate_content(
        model=model_name,
        contents=prompt
    )

    result = self.clean_llm_response(response.text)
    return result
```

**Typical Usage:**
- Input: 100k-300k words
- Output: 2000-3000 words
- Time: 1-2 minutes

### Single Chapter Summary Generation

**Purpose:** Detailed summary of individual chapter (legacy mode)

**Model:** `gemini-exp-1206` (more capable for detailed analysis)

**Location:** `scripts/generate_summaries.py:1173-1253`

```python
def generate_chapter_summary(self, chapter_text: str, chapter_num: int,
                            chapter_title: str, book_title: str,
                            medium_summary: str = None,
                            previous_chapter_text: str = None,
                            dry_run: bool = False) -> str:
    """Generate summary for a single chapter"""
    model_name = config.SUMMARY_CONFIGS['comprehensive']['model']
    max_words = config.SUMMARY_CONFIGS['comprehensive']['words_per_chapter']

    # Dynamic target: min(chapter_words / 4, max_words)
    chapter_word_count = len(chapter_text.split())
    target_words = min(chapter_word_count // 4, max_words)
    target_words = max(target_words, 200)  # Minimum 200 words

    # Build context sections
    context_sections = []
    if medium_summary:
        context_sections.append(f"""## CONTEXT: Overall Book Summary
{medium_summary[:10000]}""")

    if previous_chapter_text:
        context_sections.append(f"""## CONTEXT: Previous Chapter {chapter_num-1}
{previous_chapter_text[:20000]}""")

    context = "\n\n".join(context_sections) if context_sections else ""

    prompt = f"""Summarize Chapter {chapter_num} of "{book_title}" in approximately {target_words} words.

Chapter title: {chapter_title}

{context}

## CHAPTER {chapter_num} TO SUMMARIZE:

{chapter_text}

Cover important events, dialogues, and developments. Analyze character development and relationships. Identify key themes and symbols. Note important quotes. Explain how this chapter advances the overall narrative."""

    estimated_tokens = (len(chapter_text) + len(context)) // 4 + target_words
    self.rate_limiter.wait_if_needed(estimated_tokens)

    response = self.client.models.generate_content(
        model=model_name,
        contents=prompt
    )

    return response.text
```

**Dynamic Word Count:**
```
Short chapter (2000 words):
  target = min(2000/4, 2000) = min(500, 2000) = 500 words

Average chapter (8000 words):
  target = min(8000/4, 2000) = min(2000, 2000) = 2000 words

Long chapter (12000 words):
  target = min(12000/4, 2000) = min(3000, 2000) = 2000 words (capped)

Very short chapter (600 words):
  target = min(600/4, 2000) = 150 → max(150, 200) = 200 words (minimum)
```

### Response Cleaning

**Problem:** LLM responses often include preamble like "Of course. Here is..."

**Solution:** Regex-based cleaning

**Location:** `scripts/generate_summaries.py:93-126`

```python
def clean_llm_response(self, text: str) -> str:
    """
    Remove common LLM preamble phrases and clean up response.
    """
    preamble_patterns = [
        r'^Of course[.!]?\s*',
        r'^Certainly[.!]?\s*',
        r'^Sure[.!]?\s*',
        r'^Here is\s+',
        r'^Here\'s\s+',
        r"^Here is a.*?summary.*?[:\n]",
        r"^Here's a.*?summary.*?[:\n]",
        r"^I'll provide.*?[:\n]",
        r"^I will provide.*?[:\n]",
        r"^This is.*?summary.*?[:\n]",
        r"^a\s+(comprehensive|detailed|complete|thorough)\s+summary.*?[:\n]",
    ]

    cleaned = text
    for pattern in preamble_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Strip whitespace and newlines
    cleaned = cleaned.strip()

    # Remove leading asterisks and separator lines
    cleaned = re.sub(r'^\*+\s*\n*', '', cleaned)

    # Remove excessive leading newlines
    cleaned = re.sub(r'^\n+', '', cleaned)

    return cleaned
```

**Example:**
```
Input:  "Of course. Here is a comprehensive summary:\n\n**Summary**\n\nThe Odyssey is an epic poem..."
Output: "The Odyssey is an epic poem..."
```

---

## Summary Regeneration Modes (Added 2025-12-12)

### --regenerate-overall Flag

**Purpose:** Efficiently regenerate overall book summaries (concise + medium) and metadata (about_text, relevance_now) without reprocessing chapter structure or chapter summaries.

**Use Cases:**
- Updating summary style/tone across all books
- Fixing summary quality issues
- Testing new summary prompts
- Recovering from database corruption (summaries only)

**Command Line Usage:**
```bash
python scripts/generate_summaries.py data/books/pg996.txt --regenerate-overall
```

**What It Does:**
1. Loads book from database (skips file parsing)
2. Generates summaries using `generate_combined_summaries()` (single API call)
3. Updates `summaries` table (concise + medium)
4. Updates `books` table (about_text, relevance_now)
5. Skips: Chapter detection, chapter summaries, categorization

**What It Skips:**
- Chapter detection and parsing
- Chapter summary generation
- Book categorization
- Author metadata updates

**Performance:**
- Execution time: ~30-40 seconds per book
- Token usage: ~200 tokens input (vs ~140,000 before optimization)
- Cost: ~$0.000015 per book (vs ~$0.0105 before)
- Savings: 99.86% cost reduction

**Implementation Details:**

**Location:** `scripts/generate_summaries.py:6103-6479`

```python
def process_book(self, file_path: Path, title: str = None, author: str = None,
                dry_run: bool = False, parse_only: bool = False,
                partial_run: bool = False, regenerate_chapters: List[int] = None,
                regenerate_overall: bool = False) -> Dict:
    """
    Process a book to generate summaries, chapters, and metadata.

    Args:
        regenerate_overall: If True, regenerate only overall summaries
                           (concise + medium) without reprocessing chapters
    """

    # Display regenerate_overall mode banner
    if regenerate_overall:
        print("\n" + "=" * 60)
        print(f"REGENERATE OVERALL MODE - Regenerating concise and medium summaries only")
        print("Will skip chapter detection and summaries")
        print("=" * 60 + "\n")

    # ... book loading and metadata extraction ...

    # Generate summaries using combined method (single API call)
    if not regenerate_chapters or regenerate_overall:
        summary_data = self.generate_combined_summaries(text, title, author, dry_run)
        concise = summary_data['concise_summary']
        medium = summary_data['medium_summary']

        if not dry_run:
            # Save summaries (uses INSERT OR REPLACE)
            self.db.add_summary(book_id, 'concise', concise)
            self.db.add_summary(book_id, 'medium', medium)

            # Save book metadata
            self.db.update_book_metadata(
                book_id,
                about_text=summary_data.get('about_text'),
                relevance_now=summary_data.get('relevance_now')
            )

    # Skip categorization in regenerate_overall mode
    if not dry_run and not regenerate_overall:
        self.categorize_book(book_id, medium, title, author)

    # Early return for regenerate_overall mode
    if regenerate_overall:
        print(f"\n{'='*60}")
        print("✓ REGENERATE OVERALL MODE COMPLETE")
        print(f"{'='*60}\n")
        print(f"✓ Updated concise summary: {results['summaries']['concise']['word_count']} words")
        print(f"✓ Updated medium summary: {results['summaries']['medium']['word_count']} words\n")
        return results
```

**Database Operations:**

**Summaries Table:** Uses `INSERT OR REPLACE` via `add_summary()` method
```sql
INSERT OR REPLACE INTO summaries (book_id, summary_type, content, word_count)
VALUES (?, ?, ?, ?)
```

**Books Table:** Updates metadata fields via `update_book_metadata()` method
```sql
UPDATE books
SET about_text = ?, relevance_now = ?, updated_at = CURRENT_TIMESTAMP
WHERE id = ?
```

**Example Output:**
```
============================================================
Processing: pg996.txt
============================================================

Book loaded: 2318534 characters, ~430277 words
Title: Don Quixote
Author: Miguel de Cervantes Saavedra

============================================================
REGENERATE OVERALL MODE - Regenerating concise and medium summaries only
Will skip chapter detection and summaries
============================================================

Book already exists in database (ID: 98)

[14:58:07] --- Generating Combined Summaries (Concise + Medium) ---
[14:58:07] Generating combined summaries using gemini-2.5-flash...
  → Input: 197 words (~1,327 chars)
[14:58:07] Making API call (attempt 1/3)...
[14:58:44] ✓ API call successful
  ← Output: 2,630 words total
     About: 111 words
     Concise: 423 words
     Medium: 1,988 words
     Relevance: 108 words
✓ Concise summary: 423 words
✓ Medium summary: 1988 words

============================================================
✓ REGENERATE OVERALL MODE COMPLETE
============================================================

✓ Updated concise summary: 423 words
✓ Updated medium summary: 1988 words
```

---

## Bulk Summary Processing

### Overview

**Purpose:** Generate summaries for multiple chapters in a single API call to reduce cost and time

**Cost Savings:** 80% fewer API calls for books with many chapters

**Example:** 24-chapter book = 8 API calls (instead of 24)

**Location:** `scripts/generate_summaries.py:956-1171`

### Batching Algorithm

**Configuration:**
```python
BULK_SUMMARY_CONFIG = {
    'enabled': True,
    'max_chapters_per_batch': 5,
    'max_batch_words': 40000
}

# Additional batch limits (Added 2025-11-28)
MAX_BATCH_CHARS = 400000         # 400K characters max per batch
MAX_CHAPTERS_PER_BATCH = 10      # 10 chapters max per batch
```

**Dual Batch Limit System (Added 2025-11-28):**

**Problem:** Large batches with many chapters cause LLM parsing complexity and errors (e.g., forgetting END markers).

**Example Issue:** Some batches had 28 chapters, increasing risk of LLM forgetting END markers for Chapter 55 (Ferdinand Count Fathom bug).

**Solution:** Enforce BOTH character limit AND chapter count limit.

**Location:** `scripts/generate_summaries.py:2931-2943`

```python
# Constants
MAX_BATCH_CHARS = 400000  # 400K characters (~100K tokens)
MAX_CHAPTERS_PER_BATCH = 10  # Limit chapters per batch to improve quality and reduce parsing errors

# Batching condition
if current_batch and (current_batch_chars + chapter_chars > MAX_BATCH_CHARS or
                     len(current_batch) >= MAX_CHAPTERS_PER_BATCH):
    # Split batch on EITHER condition
    batches.append(current_batch)
    current_batch = []
    current_batch_chars = 0
```

**Benefits:**
- Clearer instructions to LLM (smaller, more focused batches)
- Reduced parsing errors (fewer chapters = simpler prompt)
- More granular progress tracking
- Better LLM attention to individual chapters

**Impact on Batching:**

**BEFORE (character limit only):**
```
Book with 28 short chapters (3K words each):
Batch 1: Chapters 1-28 (84K words, 336K chars, 28 chapters) ← TOO MANY CHAPTERS
Total batches: 1
```

**AFTER (dual limit):**
```
Book with 28 short chapters (3K words each):
Batch 1: Chapters 1-10 (30K words, 120K chars, 10 chapters)
Batch 2: Chapters 11-20 (30K words, 120K chars, 10 chapters)
Batch 3: Chapters 21-28 (24K words, 96K chars, 8 chapters)
Total batches: 3 ← More manageable
```

**Implementation:**
```python
def batch_chapters(self, chapters: List[Tuple]) -> List[List[Tuple]]:
    """
    Batch chapters together for bulk processing.
    Returns list of batches, where each batch is a list of (chapter_num, title, text) tuples.
    """
    if not config.BULK_SUMMARY_CONFIG['enabled']:
        return [[ch] for ch in chapters]  # Each chapter is own batch

    max_batch_words = config.BULK_SUMMARY_CONFIG['max_batch_words']
    max_chapters_per_batch = config.BULK_SUMMARY_CONFIG['max_chapters_per_batch']

    batches = []
    current_batch = []
    current_batch_words = 0

    for chapter_num, chapter_title, chapter_text in chapters:
        chapter_words = len(chapter_text.split())

        # Check if adding this chapter would exceed limits
        would_exceed_words = current_batch_words + chapter_words > max_batch_words
        would_exceed_count = len(current_batch) >= max_chapters_per_batch

        if current_batch and (would_exceed_words or would_exceed_count):
            # Start new batch
            batches.append(current_batch)
            current_batch = []
            current_batch_words = 0

        # Add chapter to current batch
        current_batch.append((chapter_num, chapter_title, chapter_text))
        current_batch_words += chapter_words

    # Add final batch
    if current_batch:
        batches.append(current_batch)

    return batches
```

**Batching Logic:**

```
Book with 24 chapters (average 3000 words each):

Batch 1: Chapters 1-5 (15000 words, 5 chapters)
Batch 2: Chapters 6-10 (15000 words, 5 chapters)
Batch 3: Chapters 11-15 (15000 words, 5 chapters)
Batch 4: Chapters 16-20 (15000 words, 5 chapters)
Batch 5: Chapters 21-24 (12000 words, 4 chapters)

Total batches: 5 (instead of 24 single-chapter calls)
```

**Edge Cases:**
- Very long chapter (>40k words): Becomes its own batch
- Mix of short/long chapters: Batched by word count, not just count
- Last batch may be smaller: Always process remaining chapters

### Index-Based Parsing

**Problem:** LLM responses need defensive parsing independent of chapter numbering schemes

**Solution:** Use sequential indices (1, 2, 3...) in prompts and responses

**Index Mapping:**
```python
index_to_chapter = {}  # Map sequential index → actual chapter number

for idx, (chapter_num, chapter_title, chapter_text) in enumerate(chapters_batch, start=1):
    index_to_chapter[idx] = chapter_num
    # idx is always 1, 2, 3, 4, 5
    # chapter_num might be 12, 13, 15, 21, 22 (non-sequential)
    # or 101, 102, 201, 202 (encoded)
    # or XII, XIII, XIV (Roman - converted to int)
```

**Example Mappings:**

```python
# Regenerating specific chapters
chapters_to_regenerate = [15, 16, 21, 22, 23]
index_to_chapter = {1: 15, 2: 16, 3: 21, 4: 22, 5: 23}

# Nested book structure
chapters_batch = [(101, "Book I, Ch 1", text), (102, "Book I, Ch 2", text)]
index_to_chapter = {1: 101, 2: 102}

# Sequential chapters
chapters_batch = [(1, "Chapter 1", text), (2, "Chapter 2", text)]
index_to_chapter = {1: 1, 2: 2}
```

### Bulk Prompt Construction

**Location:** `scripts/generate_summaries.py:2459-2558`

```python
def generate_bulk_chapter_summaries(self, chapters_batch: List[Tuple],
                                   book_title: str,
                                   medium_summary: str = None,
                                   previous_chapter_text: str = None) -> Dict[int, str]:
    """
    Generate summaries for multiple chapters in a single API call.
    Uses sequential indices (1, 2, 3...) for defensive parsing.

    Args:
        previous_chapter_text: Text from last chapter of previous batch for continuity (Added 2025-11-28)
    """
    # Create index mapping
    index_to_chapter = {}
    chapter_targets = {}
    chapters_text = []

    for idx, (chapter_num, chapter_title, chapter_text) in enumerate(chapters_batch, start=1):
        index_to_chapter[idx] = chapter_num

        # Calculate dynamic target words
        chapter_word_count = len(chapter_text.split())
        target_words = min(chapter_word_count // 4, 2000)
        target_words = max(target_words, 200)
        chapter_targets[chapter_num] = target_words

        # Format using sequential index (NOT actual chapter number)
        chapter_section = f"""CHAPTER {idx} (Book Chapter {chapter_num}: {chapter_title})

{chapter_text}"""
        chapters_text.append(chapter_section)

    # Build word count instructions
    chapter_instructions = []
    for idx, (chapter_num, chapter_title, _) in enumerate(chapters_batch, start=1):
        target = chapter_targets[chapter_num]
        chapter_instructions.append(
            f"  - Chapter {idx} (Book Chapter {chapter_num}: {chapter_title}) (~{target} words)"
        )

    # Context section
    context = ""
    if medium_summary:
        context = f"""## CONTEXT: Overall Book Summary (for reference)

{medium_summary[:5000]}

"""

    # Build prompt
    prompt = f"""Summarize the following {len(chapters_batch)} chapters from "{book_title}".

IMPORTANT: Format your response EXACTLY as shown below. Use sequential chapter numbers (1, 2, 3...) in your response markers, NOT the book chapter numbers. Follow the word count targets for each chapter:

{chr(10).join(chapter_instructions)}

FORMAT (use sequential numbers 1, 2, 3... in the markers):
### CHAPTER 1: TITLE
[Your summary here following the word count target above]
Cover important events, dialogues, and developments. Analyze character development and relationships. Identify key themes and symbols. Note important quotes. Explain how this chapter advances the overall narrative.

### END CHAPTER 1

### CHAPTER 2: TITLE
[Your summary for the second chapter...]

### END CHAPTER 2

... and so on for all {len(chapters_batch)} chapters.

{context}## CHAPTERS TO SUMMARIZE:

{"=" * 80}
{chr(10).join(chapters_text)}
{"=" * 80}

Now provide summaries for all {len(chapters_batch)} chapters above, following the exact format and word count targets specified. Remember to use sequential numbers (1, 2, 3...) in the ### CHAPTER markers."""

    # Make API call
    response = self.client.models.generate_content(
        model=config.SUMMARY_CONFIGS['comprehensive']['model'],
        contents=prompt
    )

    # Parse response using index mapping
    summaries = self.parse_bulk_summary_response(response.text, index_to_chapter)
    return summaries
```

**Prompt Structure:**

```
1. Instructions (use sequential indices)
2. Word count targets for each chapter
3. Format specification (with examples)
4. Context (medium summary, if available)
5. Chapters to summarize (with sequential indices)
6. Reminder to use sequential indices
```

### Bulk Response Parsing

**Expected Format:**
```
### CHAPTER 1: The Three Metamorphoses
[Summary content for first chapter...]

### END CHAPTER 1

### CHAPTER 2: The Academic Chairs
[Summary content for second chapter...]

### END CHAPTER 2

...
```

**Parser Implementation:**

**Location:** `scripts/generate_summaries.py:995-1040`

```python
def parse_bulk_summary_response(self, response_text: str,
                               index_to_chapter: Dict[int, int]) -> Dict[int, str]:
    """
    Parse bulk summary response to extract individual chapter summaries.

    Args:
        response_text: Raw LLM response
        index_to_chapter: {1: 15, 2: 16, 3: 21, ...} mapping

    Returns:
        {15: "summary...", 16: "summary...", 21: "summary...", ...}
    """
    summaries = {}

    # Regex pattern: ### CHAPTER N: TITLE\n[content]\n### END CHAPTER N
    # N must be sequential index (1, 2, 3...)
    pattern = r'###\s*CHAPTER\s+(\d+):\s*[^\n]*\n(.*?)(?=###\s*(?:CHAPTER\s+|END\s+CHAPTER\s+)|$)'

    matches = re.finditer(pattern, response_text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        index_str = match.group(1).strip()
        summary_text = match.group(2).strip()

        # Convert to integer
        index = int(index_str)

        # Remove END CHAPTER marker if present
        summary_text = re.sub(
            r'###\s*END\s+CHAPTER\s+\d+\s*$',
            '',
            summary_text,
            flags=re.IGNORECASE
        ).strip()

        # Map index back to actual chapter number
        if index in index_to_chapter:
            chapter_num = index_to_chapter[index]
            summaries[chapter_num] = summary_text
        else:
            print(f"  ⚠️  Warning: Parsed index {index} not found in mapping")

    # Verify we got all expected chapters
    expected_chapters = set(index_to_chapter.values())
    missing = expected_chapters - set(summaries.keys())
    if missing:
        print(f"  ⚠️  Warning: Missing summaries for chapters: {sorted(missing)}")

    return summaries
```

**Regex Breakdown:**

```regex
###\s*CHAPTER\s+(\d+):\s*[^\n]*\n(.*?)(?=###\s*(?:CHAPTER\s+|END\s+CHAPTER\s+)|$)

###\s*               - "###" followed by optional whitespace
CHAPTER\s+          - "CHAPTER" followed by whitespace
(\d+)               - Capture group 1: one or more digits (the index)
:\s*                - Colon followed by optional whitespace
[^\n]*              - Any characters except newline (the title - not captured)
\n                  - Newline
(.*?)               - Capture group 2: non-greedy any characters (the summary)
(?=...)             - Lookahead (don't consume)
  ###\s*(?:CHAPTER\s+|END\s+CHAPTER\s+)  - Next chapter marker or end marker
  |$                - OR end of string
```

**Flags:**
- `re.DOTALL`: `.` matches newlines (for multiline summaries)
- `re.IGNORECASE`: Case-insensitive matching

**Parsing Example:**

```
Input response:
  "### CHAPTER 1: First\n[content1]\n### END CHAPTER 1\n### CHAPTER 2: Second\n[content2]"

index_to_chapter = {1: 15, 2: 16}

Match 1:
  index_str = "1"
  summary_text = "[content1]\n### END CHAPTER 1"
  After cleaning: "[content1]"
  index = 1 → chapter_num = 15
  summaries[15] = "[content1]"

Match 2:
  index_str = "2"
  summary_text = "[content2]"
  index = 2 → chapter_num = 16
  summaries[16] = "[content2]"

Return: {15: "[content1]", 16: "[content2]"}
```

### Batch Processing Flow

```
1. detect_chapters(text)
   → chapters = [(15, "title", text), (16, "title", text), ...]

2. batch_chapters(chapters)
   → batches = [
       [(15, "title", text), (16, "title", text), (21, "title", text)],
       [(22, "title", text), (23, "title", text)]
     ]

3. For each batch:
   a. Get previous chapter context (Added 2025-11-28):
      - Batch 1: previous_chapter_text = None
      - Batch 2+: previous_chapter_text = last chapter from previous batch (first 100K chars)

   b. Create index mapping:
      Batch 1: {1: 15, 2: 16, 3: 21}
      Batch 2: {1: 22, 2: 23}

   c. Build prompt with sequential indices (1, 2, 3...)
      - Includes previous chapter context for narrative continuity (if available)

   d. Make API call

   e. Parse response:
      "### CHAPTER 1: ..." → index=1 → chapter_num=15
      "### CHAPTER 2: ..." → index=2 → chapter_num=16
      "### CHAPTER 3: ..." → index=3 → chapter_num=21

   f. Save to database:
      db.add_chapter(book_id, 15, "title", summary, text)
      db.add_chapter(book_id, 16, "title", summary, text)
      db.add_chapter(book_id, 21, "title", summary, text)

   g. Track last chapter for next batch:
      previous_batch_last_chapter = batch[-1]  # (23, "title", text)

4. Next batch...
```

**Previous Chapter Context Feature (Added 2025-11-28):**

**Purpose:** Provide narrative continuity across batch boundaries by including the last chapter from the previous batch as context.

**Implementation:** `scripts/generate_summaries.py:2737-2760`

```python
# Initialize tracking
previous_batch_last_chapter = None  # Track last chapter from previous batch for context

for batch_idx, batch in enumerate(batches, 1):
    # Get previous chapter text for continuity (first 100K chars)
    previous_chapter_text = previous_batch_last_chapter[2] if previous_batch_last_chapter else None

    # Generate summaries with context
    batch_summaries = self.generate_bulk_chapter_summaries(
        batch,
        title,
        medium_summary=medium_summary,
        previous_chapter_text=previous_chapter_text,  # Pass to API call
        dry_run=dry_run,
        partial_run=partial_run
    )

    # ... save summaries to database ...

    # Track last chapter for next batch
    previous_batch_last_chapter = batch[-1]
```

**Benefits:**
- Helps AI understand character references that carry over between batches
- Maintains plot thread continuity across batch boundaries
- Improves summary quality for sequential narrative fiction
- Example: Batch 2 processing Chapters 6-10 receives Chapter 5 context

**Context Limit:** First 100,000 characters of previous chapter text (lines 2513-2520)

### Performance Metrics

**Single Chapter Mode (Disabled):**
- 24 chapters → 24 API calls
- Time: ~25-35 minutes
- Cost: ~$0.10-0.25 per book

**Bulk Mode (Current):**
- 24 chapters → 8 batches → 8 API calls
- Time: ~8-12 minutes
- Cost: ~$0.05-0.15 per book

**Savings:**
- API calls: 67% reduction
- Time: 60% faster
- Cost: 50% cheaper

---

## Project Gutenberg Integration

### Overview

**Purpose:** Automatically extract metadata, clean content, and download cover images from Project Gutenberg books

**Location:** `scripts/generate_summaries.py`

### Gutenberg ID Extraction

**Location:** `scripts/generate_summaries.py:163-179`

```python
def extract_gutenberg_id(self, text: str) -> int:
    """
    Extract Project Gutenberg ID from book text header.
    Returns Gutenberg ID or None.
    """
    lines = text.split('\n')[:100]  # Check first 100 lines

    for line in lines:
        line = line.strip()
        # Look for patterns like "Release Date: ... [EBook #11]" or "eBook #11"
        # Case-insensitive search for both "EBook" and "eBook"
        if 'ebook' in line.lower() and '#' in line:
            match = re.search(r'#(\d+)', line)
            if match:
                return int(match.group(1))

    return None
```

**Example Input:**
```
The Project Gutenberg eBook of The Odyssey, by Homer

This eBook is for the use of anyone anywhere in the United States and
most other parts of the world at no cost and with almost no restrictions
whatsoever. You may copy it, give it away or re-use it under the terms
of the Project Gutenberg License included with this eBook or online at
www.gutenberg.org. If you are not located in the United States, you
will have to check the laws of the country where you are located before
using this eBook.

Title: The Odyssey

Author: Homer

Release Date: April 1, 1999 [eBook #1727]
[Most recently updated: November 20, 2021]
```

**Extracted ID:** 1727

### Content Extraction

**Problem:** Project Gutenberg books include lengthy headers and footers with license information

**Solution:** Remove everything before "START OF THE PROJECT GUTENBERG EBOOK" and after "END OF THE PROJECT GUTENBERG EBOOK"

**Location:** `scripts/generate_summaries.py:285-331`

```python
def extract_gutenberg_content(self, text: str) -> str:
    """
    Extract actual book content from Project Gutenberg ebooks.
    Removes headers, footers, and license information.
    """
    # Start markers
    start_markers = [
        '*** START OF THE PROJECT GUTENBERG EBOOK',
        '*** START OF THIS PROJECT GUTENBERG EBOOK',
        '***START OF THE PROJECT GUTENBERG EBOOK'
    ]

    # End markers
    end_markers = [
        '*** END OF THE PROJECT GUTENBERG EBOOK',
        '*** END OF THIS PROJECT GUTENBERG EBOOK',
        '***END OF THE PROJECT GUTENBERG EBOOK'
    ]

    # Find start position
    start_pos = 0
    for marker in start_markers:
        pos = text.upper().find(marker)
        if pos != -1:
            # Find end of line after marker
            start_pos = text.find('\n', pos) + 1
            break

    # Find end position
    end_pos = len(text)
    for marker in end_markers:
        pos = text.upper().find(marker)
        if pos != -1:
            end_pos = pos
            break

    # Extract content
    if start_pos > 0 or end_pos < len(text):
        content = text[start_pos:end_pos]
        # Remove excessive leading/trailing newlines
        content = content.strip('\n')
        print(f"Extracted Gutenberg content: {len(content)} chars (original: {len(text)})")
        return content

    return text
```

**Example:**
```
Original: 500,000 chars (with header/footer)
Extracted: 450,000 chars (pure book content)
Removed: 50,000 chars (10% reduction)
```

### Metadata Extraction

**Location:** `scripts/generate_summaries.py:138-161`

```python
def extract_metadata(self, text: str, filename: str) -> Tuple[str, str]:
    """
    Extract title and author from book text.
    Returns (title, author)
    """
    lines = text.split('\n')[:50]  # Check first 50 lines

    title = None
    author = None

    for line in lines:
        line = line.strip()
        if line.startswith('Title:'):
            title = line.replace('Title:', '').strip()
        elif line.startswith('Author:'):
            author = line.replace('Author:', '').strip()

    # Fallback to filename if not found
    if not title:
        title = filename.replace('.txt', '').replace('_', ' ').title()
    if not author:
        author = "Unknown"

    return title, author
```

**Example:**
```
Input lines:
  "Title: The Odyssey"
  "Author: Homer"

Output:
  title = "The Odyssey"
  author = "Homer"
```

### Cover Image Download

**Cover URL Pattern:**
```
https://www.gutenberg.org/cache/epub/{id}/pg{id}.cover.medium.jpg
```

**Alternative Formats:**
- `pg{id}.cover.small.jpg`
- `{id}-h/images/cover.jpg`

**Location:** `scripts/generate_summaries.py:181-259`

```python
def get_gutenberg_cover_url(self, gutenberg_id: int) -> str:
    """Get cover image URL for a Project Gutenberg book"""
    formats = [
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.medium.jpg",
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.small.jpg",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/images/cover.jpg",
    ]

    for url in formats:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                print(f"Found cover image: {url}")
                return url
        except Exception:
            continue

    return None

def download_gutenberg_cover(self, gutenberg_id: int, dry_run: bool = False) -> str:
    """
    Download and save cover image for a Project Gutenberg book.
    Returns local file path relative to static directory.
    Example return: 'covers/pg11.jpg'
    """
    # Get cover URL
    cover_url = self.get_gutenberg_cover_url(gutenberg_id)
    if not cover_url:
        return None

    if dry_run:
        print(f"[DRY RUN] Would download: {cover_url}")
        return f"covers/pg{gutenberg_id}.jpg"

    try:
        # Create covers directory
        config.COVERS_DIR.mkdir(parents=True, exist_ok=True)

        # Determine file extension
        file_ext = '.jpg'
        if cover_url.endswith('.png'):
            file_ext = '.png'

        # Create local filename
        local_filename = f"pg{gutenberg_id}{file_ext}"
        local_path = config.COVERS_DIR / local_filename

        # Check if already exists
        if local_path.exists():
            print(f"Cover already exists: {local_path}")
            return f"covers/{local_filename}"

        # Download
        print(f"Downloading cover from: {cover_url}")
        response = requests.get(cover_url, timeout=10)
        response.raise_for_status()

        # Save
        with open(local_path, 'wb') as f:
            f.write(response.content)

        print(f"✓ Saved cover to: {local_path}")

        # Return relative path for web serving
        return f"covers/{local_filename}"

    except Exception as e:
        print(f"Error downloading cover: {e}")
        return None
```

**Storage Structure:**
```
frontend/static/covers/
├── pg11.jpg       # A Christmas Carol
├── pg1727.jpg     # The Odyssey
├── pg1342.jpg     # Pride and Prejudice
└── odyssey_custom.png  # Custom cover (manual)
```

**Database Storage:**
```sql
UPDATE books SET cover_image_url = 'covers/pg1727.jpg' WHERE id = 11;
```

**Web Serving:**
```
http://localhost:5000/static/covers/pg1727.jpg
```

### Custom Covers

**Support:** Users can manually add custom covers

**Naming Convention:** `{bookname}_custom.{ext}`

**Example:** `odyssey_custom.png`

**Update Script:** `scripts/update_odyssey_cover.py`

```python
def main():
    db = models.Database()
    new_cover_path = "covers/odyssey_custom.png"

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE books SET cover_image_url = ? WHERE id = ?",
        (new_cover_path, 11)
    )
    conn.commit()
    conn.close()

    print(f"✓ Updated cover to: {new_cover_path}")
```

---

## Backend Architecture

### Flask Application Structure (Refactored 2025-11-25)

**Purpose:** Eliminate code duplication between development and production Flask applications while maintaining environment-specific functionality.

**Architecture Pattern:**

```
┌─────────────────────────────────────────┐
│         backend/app_base.py             │
│   (Common Flask App & Routes - 302L)    │
├─────────────────────────────────────────┤
│ • Flask app initialization              │
│ • CORS configuration                    │
│ • Database initialization               │
│ • Common API routes:                    │
│   - GET /                                │
│   - GET /api/books                       │
│   - GET /api/books/<id>                  │
│   - GET /api/books/<id>/summary/<type>   │
│   - GET /api/books/<id>/chapters         │
│   - GET /api/summary-configs             │
│   - GET /covers/<filename>               │
│ • Error handlers (404, 500)             │
│ • Directory setup utilities             │
└─────────────────────────────────────────┘
         ↑                       ↑
         │                       │
         │                       │
┌────────┴─────────┐    ┌────────┴──────────┐
│  backend/app.py  │    │ backend/app_prod  │
│   (295 lines)    │    │    (104 lines)    │
├──────────────────┤    ├───────────────────┤
│ Dev-Specific:    │    │ Prod-Specific:    │
│ • POST /api/tts/ │    │ • POST /api/tts/  │
│   generate       │    │   generate        │
│   (Full TTS with │    │   (Pre-generated  │
│    streaming)    │    │    files only)    │
│ • POST /api/tts/ │    │ • GET /health     │
│   stop           │    │   (Monitoring)    │
│ • TTS handler    │    │                   │
│   initialization │    │                   │
│ • Active TTS     │    │                   │
│   tracking       │    │                   │
└──────────────────┘    └───────────────────┘
```

**Code Reduction:**
- **Before Refactoring:**
  - app.py: 551 lines
  - app_prod.py: 336 lines
  - Total: 887 lines (with ~300 lines duplicated)
- **After Refactoring:**
  - app_base.py: 302 lines (new)
  - app.py: 295 lines
  - app_prod.py: 104 lines
  - Total: 701 lines (21% reduction, zero duplication)

### Dual Import System

**Problem:** Python requires different import styles for different execution methods:
- **Direct execution:** `python backend/app.py` → Requires absolute imports (`import config`)
- **Module execution:** `python -m backend.app` → Requires relative imports (`from . import config`)

**Solution:** Try/except pattern in all backend modules:

**Location:** `backend/app_base.py:16-21`, `backend/app.py:11-16`, `backend/app_prod.py:11-16`

```python
# Handle both direct execution and module execution
try:
    from . import config
    from . import models
except ImportError:
    import config
    import models
```

**Benefits:**
- Works with both `python backend/app.py` and `python -m backend.app`
- Flexible for different deployment scenarios
- Supports both development and testing workflows
- No runtime overhead (import happens once at startup)

### Flask App Initialization

**Location:** `backend/app_base.py:30-37`

```python
# Create Flask app
app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Initialize database
db = models.Database()
```

**Exported Symbols:**
- `app` - Flask application instance (imported by app.py and app_prod.py)
- `db` - Database instance (used by routes in app_base.py)
- `logger` - Logging instance (imported by app.py and app_prod.py)
- `ensure_directories()` - Utility function (called at startup)

### Environment-Specific Routes

**Development (app.py) - TTS Generation Enabled:**

```python
@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """
    Generate TTS audio with streaming support.
    - Full VITS TTS model loaded in memory
    - Supports chunked generation for long text
    - Returns streaming status updates
    - Memory intensive (~500MB for model)
    """
    # Implementation: lines 70-243
```

**Production (app_prod.py) - TTS Generation Disabled:**

```python
@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """
    Check for pre-generated TTS audio only.
    TTS generation disabled to conserve memory on e2-micro (1GB RAM).
    - Checks for Gemini TTS files (_gemini.wav)
    - Checks for VITS TTS files (_vits.wav)
    - Checks for legacy files (_complete.wav)
    - Returns 404 if no pre-generated audio exists
    """
    # Implementation: lines 31-88
```

### Route Coverage

**Common Routes (app_base.py):**
- ✅ `GET /` - Main page
- ✅ `GET /api/books` - All books
- ✅ `GET /api/books/<id>` - Book details
- ✅ `GET /api/books/<id>/summary/<type>` - Summary with chapters
- ✅ `GET /api/books/<id>/chapters` - All chapters
- ✅ `GET /api/summary-configs` - Summary configurations
- ✅ `GET /covers/<filename>` - Cover images
- ✅ Error handlers (404, 500)

**Development-Only Routes (app.py):**
- ✅ `POST /api/tts/generate` - Full TTS generation
- ✅ `POST /api/tts/stop` - Stop TTS generation

**Production-Only Routes (app_prod.py):**
- ✅ `POST /api/tts/generate` - Pre-generated audio lookup (overrides base)
- ✅ `GET /health` - Health check for monitoring

### Defensive Programming Pattern

**Problem:** Production environment may lag behind in deployments, causing template/JavaScript version mismatches.

**Example:** Production template missing `book-info-cover` element added in UI redesign.

**Solution:** Defensive null checks before DOM access.

**Location:** `frontend/static/js/app.js:384-394`

```javascript
const bookCoverEl = document.getElementById('book-info-cover');
if (bookCoverEl) {  // ✅ Defensive check
    if (book.cover_image_url) {
        bookCoverEl.src = book.cover_image_url;
        bookCoverEl.alt = `${book.title} cover`;
        bookCoverEl.classList.remove('hidden');
    } else {
        bookCoverEl.classList.add('hidden');
    }
}
```

**Benefits:**
- Prevents crashes from missing DOM elements
- Backward compatible with older templates
- Graceful degradation
- Production can be updated independently
- No user-facing errors during deployment transitions

### Development vs Production Differences

| Aspect | Development (app.py) | Production (app_prod.py) |
|--------|---------------------|-------------------------|
| **TTS Generation** | Full VITS model loaded | Disabled (pre-generated only) |
| **Memory Usage** | ~500-800 MB | ~150-200 MB |
| **API Calls** | Real-time generation | File lookup only |
| **Health Endpoint** | None | `/health` for monitoring |
| **Server** | Flask dev server | Gunicorn WSGI |
| **Debug Mode** | Enabled | Disabled |
| **Auto-Reload** | Yes | No (requires restart) |
| **Target Environment** | Local MacOS | GCP e2-micro (Debian 12) |

### Deployment Workflow

**Local Development:**
```bash
cd /Users/pengyao/Documents/dev/summra
source venv/bin/activate
python backend/app.py  # or: python -m backend.app
# Server runs on http://localhost:5001
```

**Production Deployment:**
```bash
# On GCP e2-micro instance
cd /path/to/summra
git pull origin main
sudo systemctl restart summra
sudo systemctl status summra
# Server runs behind Nginx on http://summra.pengyaochen.com
```

**Production Stack:**
- OS: Debian 12 (bookworm)
- Python: 3.11
- Web Server: Nginx (reverse proxy + static files)
- App Server: Gunicorn with gevent workers (1 worker, 400MB memory limit)
- Service Manager: systemd
- Database: SQLite (105MB)

### Database Deployment to Production

**Important:** The database file (`data/database.db`) is not tracked in git due to its size (105+ MB, exceeds GitHub's 100 MB limit). It must be manually deployed to production.

**Step 1: Copy database from local to VM** (run on local machine)
```bash
gcloud auth login
gcloud compute scp \
    /Users/pengyao/Documents/dev/summra/data/database.db \
    instance-20251125-033837:/tmp/database.db \
    --zone=us-west1-b \
    --project=project-7f192cbf-77f3-4f7a-acc
```

**Step 2: Move to production directory and set permissions** (run on remote VM)
```bash
# Backup existing database (optional but recommended)
sudo cp /var/www/summra/data/database.db /var/www/summra/data/database.db.backup

# Move new database to production location
sudo mv /tmp/database.db /var/www/summra/data/database.db

# Set correct ownership (www-data is the Nginx/Gunicorn user)
sudo chown www-data:www-data /var/www/summra/data/database.db

# Restart the application to use new database
sudo systemctl restart summra

# Verify service started successfully
sudo systemctl status summra
```

**Step 3: Verify deployment**
```bash
# Check database file size
ls -lh /var/www/summra/data/database.db

# Check database integrity
sudo -u www-data sqlite3 /var/www/summra/data/database.db "PRAGMA integrity_check;"
# Should output: ok

# Test the application
curl http://localhost:5000/api/books | jq length
# Should return number of books in database
```

**Alternative: Using rsync for incremental updates**
```bash
# More efficient for large files with small changes
gcloud compute ssh instance-20251125-033837 \
    --zone=us-west1-b \
    --project=project-7f192cbf-77f3-4f7a-acc

# On remote VM, rsync from local (requires SSH access)
rsync -avz --progress \
    pengyao@<LOCAL_IP>:/Users/pengyao/Documents/dev/summra/data/database.db \
    /tmp/database.db

# Then move and set permissions as above
```

**Database Size Management:**
- Current size: ~105 MB (as of 2025-11-29)
- Growth rate: ~1-2 MB per book added
- Excluded from git via `.gitignore` (all `*.db` files)
- Production database may differ from local (production has fewer books)
- Always backup before replacing

---

## Frontend Architecture (Redesigned 2025-11-25)

### Overview

The Summra frontend is a vanilla JavaScript single-page application (SPA) with hash-based routing. The redesign focuses on minimalist UI, content-first presentation, and dedicated pages for reading experiences.

### Technology Stack

- **Framework:** Vanilla JavaScript (no framework dependencies)
- **Styling:** Custom CSS with CSS variables for theming
- **Markdown:** Marked.js v11.1.1 for rendering summaries
- **Routing:** Hash-based client-side routing
- **Audio:** HTML5 Audio API for TTS playback

### File Structure

```
frontend/
├── templates/
│   └── index.html              # Main HTML template (single page)
├── static/
│   ├── js/
│   │   └── app.js              # Main application logic (820 lines)
│   ├── css/
│   │   └── style.css           # All styling (900+ lines)
│   ├── audio/                  # Generated TTS audio files
│   ├── covers/                 # Book cover images
│   └── (marked.js loaded via CDN)
```

### Routing System

**Type:** Hash-based SPA routing (no server-side routing required)

**Route Patterns:**
```javascript
/                                  → Books library (grid view)
#/book/{slug}                      → Book overview page
#/book/{slug}/medium               → Full medium summary page
#/book/{slug}/chapter/{num}        → Individual chapter page
```

**Route Handling Implementation:**
```javascript
async handleRoute() {
    const hash = window.location.hash;

    // Route matching with regex
    const bookMatch = hash.match(/#\/book\/([^\/]+)$/);
    const mediumMatch = hash.match(/#\/book\/([^\/]+)\/medium$/);
    const chapterMatch = hash.match(/#\/book\/([^\/]+)\/chapter\/(\d+)$/);

    // Navigate to appropriate view
    if (chapterMatch) {
        await this.showChapterDetail(book, chapterNum);
    } else if (mediumMatch) {
        await this.showMediumDetail(book);
    } else if (bookMatch) {
        await this.selectBook(book);
    }
}
```

**Slug Generation (Updated 2025-12-13):**

**Backend (Single Source of Truth):**
```python
# backend/models.py
def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

# Auto-generated when books are added
def add_book(self, title, ...):
    slug = slugify(title)  # Automatically set
    cursor.execute('''
        INSERT INTO books (..., slug)
        VALUES (..., ?)
    ''', (..., slug))
```

**Frontend (Uses Backend Slug):**
```javascript
// frontend/static/js/app.js
updateURL(book, page = null) {
    // Use slug from backend, fallback to client-side generation
    const slug = book.slug || this.slugify(book.title);
    let newPath = `/books/${slug}`;

    if (page === 'summary') {
        newPath = `/books/${slug}/summary`;
    } else if (typeof page === 'number') {
        newPath = `/books/${slug}/chapters/${page}`;
    }

    window.history.pushState(null, '', newPath);
}

// Routing: find books by slug
const book = this.allBooks.find(b => (b.slug || this.slugify(b.title)) === bookSlug);
```

**Key Design Decision:**
- Backend stores canonical slugs in database for SEO and consistency
- Frontend uses backend slugs preferentially, with client-side fallback
- All new books automatically get slugs via `models.py:add_book()`
- Legacy books backfilled using `scripts/backfill_book_slugs.py`

### Page Sections & State Management

**Main Application Class:**
```javascript
class SummraApp {
    constructor() {
        this.apiBase = '/api';
        this.currentBook = null;           // Selected book object
        this.currentChapter = null;        // Current chapter number
        this.mediumSummaryContent = null;  // Cached medium summary
        this.chapters = [];                // Loaded chapters
        this.allBooks = [];                // All available books
        this.booksLoaded = false;          // Loading state
        this.currentPlayback = {           // TTS playback state
            isPlaying: false,
            currentChunk: 0,
            audioUrls: [],
            bookTitle: '',
            chapterTitle: '',
            audioId: null
        };
    }
}
```

**Page Sections (mutually exclusive visibility):**

1. **Books Section** (`#books-section`)
   - Grid of book cards
   - Default view

2. **Summary Section** (`#summary-section`)
   - Book overview page
   - Contains: concise summary, medium preview, chapter boxes

3. **Medium Detail Section** (`#medium-detail-section`)
   - Full medium summary page
   - Dedicated reading view

4. **Chapter Detail Section** (`#chapter-detail-section`)
   - Individual chapter page
   - Full text + collapsible summary

### Performance Optimizations

1. **Lazy Loading:** Books loaded once, cached in `this.allBooks`
2. **Parallel Fetching:** Concise, medium, and chapters loaded simultaneously
3. **Medium Summary Caching:** Stored in `this.mediumSummaryContent` for reuse
4. **Chapter Caching:** Stored in `this.chapters` array
5. **CSS Animations:** GPU-accelerated transforms and opacity
6. **Minimal Reflows:** Content cards prevent layout shifts
7. **Image Lazy Loading (Added 2025-11-28):** All book cover images use `loading="lazy"` attribute
   - Carousel images: line 484 in `renderCategoryCarousel()`
   - Grid images: line 1386 in `showAllBooksPage()`
   - Defers loading of off-screen images until user scrolls
   - Reduces initial page load time and bandwidth usage
8. **Carousel Order Caching (Added 2025-11-28):** Randomized book order preserved across page loads
   - Cached in `this.carouselOrderCache` object (line 27)
   - Key format: `{categoryId}_{containerIdOverride || 'default'}`
   - Shuffled order created once and reused on subsequent renders
   - Maintains consistent visual experience across page refreshes
9. **Category Data Caching (Added 2025-11-28):** API responses cached in-memory
   - Cached in `this.categoryCache` object (line 27)
   - Stores both category metadata and book list
   - Eliminates redundant API calls when returning to category pages
   - Prevents flash/reload effect during navigation

### UI Components

#### Book Overview Page

**HTML Structure:**
```html
<section class="summary-section" id="summary-section">
    <button class="back-button">← Back to Books</button>

    <!-- Book header with small cover -->
    <div class="book-detail-header">
        <img class="book-detail-cover" />
        <div class="book-detail-info">
            <h2>Book Title</h2>
            <p class="book-author">by Author</p>
        </div>
    </div>

    <!-- Concise summary -->
    <div class="concise-summary-section">
        <div class="section-header">
            <h3>Quick Summary</h3>
            <button class="tts-button-inline">🔊 Listen</button>
        </div>
        <div class="summary-text"></div>
    </div>

    <!-- Medium summary preview with fade -->
    <div class="medium-preview-section">
        <div class="section-header">
            <h3>Detailed Overview</h3>
        </div>
        <div class="medium-preview-container">
            <div class="summary-text"></div>
            <div class="preview-fade"></div>
        </div>
        <button class="expand-link">Read Full Summary →</button>
    </div>

    <!-- Chapter boxes -->
    <div class="chapters-section">
        <h3>Chapters</h3>
        <div class="chapters-list"></div>
    </div>
</section>
```

**CSS Styling:**
```css
/* Fade effect for medium preview */
.medium-preview-container {
    position: relative;
    max-height: 300px;
    overflow: hidden;
}

.preview-fade {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 120px;
    background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,1));
    pointer-events: none;
}

/* Chapter boxes */
.chapter-box {
    background: var(--background-color);
    border: 1px solid var(--border-color);
    border-left: 4px solid var(--secondary-color);
    padding: 16px 20px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.chapter-box:hover {
    background: #e8f4f8;
    border-left-color: #2980b9;
    transform: translateX(4px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
```

#### Chapter Detail Page

**HTML Structure (Updated 2025-11-25):**
```html
<section class="chapter-detail-section" id="chapter-detail-section">
    <div class="back-button-container">
        <button class="back-button">← Back to Book</button>
    </div>

    <div class="chapter-detail-header">
        <h2>1. Introduction</h2>
        <p class="chapter-detail-subtitle">The Time Machine</p>
    </div>

    <div class="chapter-detail-content">
        <!-- Collapsed summary (spoiler protection) -->
        <div class="chapter-summary-box">
            <div class="chapter-summary-header">
                <h4>📝 Chapter Summary <span class="spoiler-warning">(may contain spoilers)</span></h4>
                <div class="chapter-summary-actions">
                    <button class="tts-button-inline">🔊 Listen</button>
                    <button class="toggle-summary-btn">▼</button>
                </div>
            </div>
            <div class="chapter-summary-content hidden">
                <div class="summary-text"></div>
            </div>
        </div>

        <!-- Full chapter text -->
        <div class="chapter-fulltext-section">
            <div class="section-header">
                <h4>📖 Full Chapter Text</h4>
                <button class="tts-button-inline">🔊 Listen</button>
            </div>
            <div class="chapter-fulltext"></div>
        </div>
    </div>
</section>
```

**UI Polish Changes (2025-11-25):**

1. **Back Button Container:**
   - Wrapped in `.back-button-container` div for proper alignment
   - Inherits padding from parent section rules
   - Maintains consistent left alignment with text content

2. **Chapter Summary Header Reorganization:**
   - Created `.chapter-summary-actions` wrapper div
   - Moved "Listen" button from bottom of summary to header
   - Placed side-by-side with toggle button
   - Simplified button text: "🔊 Listen to Summary" → "🔊 Listen"

3. **Toggle Button Simplification:**
   - Changed from full button to minimal chevron-only design
   - Removed border, background, and padding
   - Displays just "▼" (collapsed) or "▲" (expanded)
   - Transparent background with color-only hover effect
   - Larger font size (1.2rem) for better visibility

**JavaScript Logic:**
```javascript
async showChapterDetail(book, chapterNum) {
    // Scroll to top for better reading experience
    window.scrollTo(0, 0);

    // Hide other sections
    document.getElementById('books-section').classList.add('hidden');
    document.getElementById('summary-section').classList.add('hidden');
    document.getElementById('medium-detail-section').classList.add('hidden');
    document.getElementById('chapter-detail-section').classList.remove('hidden');

    // Load chapter data
    const chapter = this.chapters.find(c => c.chapter_number === chapterNum);

    // Update header
    document.getElementById('chapter-detail-title').textContent =
        `${chapterNum}. ${chapter.chapter_title}`;

    // Render summary (collapsed by default)
    document.getElementById('chapter-summary-text').innerHTML =
        this.renderMarkdown(chapter.summary);

    // Render full text
    document.getElementById('chapter-fulltext').innerHTML =
        this.formatChapterText(chapter.chapter_text);
}
```

### Data Loading Strategy

**Parallel Loading:**
```javascript
async selectBook(book) {
    this.currentBook = book;

    // Load all data in parallel for faster page load
    await Promise.all([
        this.loadConciseSummary(),
        this.loadMediumSummary(),
        this.loadChapters()
    ]);

    this.updateURL(book);
}
```

**API Integration:**
```javascript
async loadConciseSummary() {
    const response = await fetch(`${this.apiBase}/books/${this.currentBook.id}/summary/concise`);
    const data = await response.json();

    if (data.success && data.summary) {
        document.getElementById('concise-summary-text').innerHTML =
            this.renderMarkdown(data.summary.content);
    }
}
```

### CSS Architecture

**Design System Variables:**
```css
:root {
    --primary-color: #2c3e50;       /* Dark blue-gray for headers */
    --secondary-color: #3498db;     /* Bright blue for accents */
    --accent-color: #e74c3c;        /* Red for errors */
    --background-color: #ecf0f1;    /* Light gray background */
    --card-background: #ffffff;     /* White for cards */
    --text-color: #2c3e50;          /* Main text color */
    --text-light: #7f8c8d;          /* Light text for metadata */
    --border-color: #bdc3c7;        /* Borders */
    --shadow: 0 2px 4px rgba(0,0,0,0.1);
    --shadow-hover: 0 4px 12px rgba(0,0,0,0.15);
}
```

**Header Navigation Styling (Updated 2025-11-28):**
```css
/* Container for navigation menu items */
.header-nav-buttons {
    display: flex;
    gap: 20px;
    margin-left: 20px;  /* Changed from 'auto' to left-align near logo */
}

/* Individual menu item styling */
.header-nav-btn {
    background: transparent;     /* Changed from semi-transparent white */
    color: white;
    border: none;               /* Removed border */
    padding: 0;                 /* Removed padding */
    font-size: 0.95rem;
    cursor: pointer;
    transition: opacity 0.2s;
    text-decoration: none;
    font-weight: 400;
}

/* Hover effect - minimal and clean */
.header-nav-btn:hover {
    opacity: 0.8;              /* Slight opacity change */
    text-decoration: underline; /* Underline on hover */
}
```

**Layout Principles:**
- Max-width: 800px for optimal reading
- Padding: 32px inside white content cards
- Line-height: 1.75 for body text
- Font-size: 1.05rem for readable text
- Responsive grid for book cards
- Flexbox for headers and controls

**Key CSS Classes:**
- `.summary-section` - Main content container, max-width 800px (1200px for header)
- `.book-detail-header` - Flexbox layout, cover + info side-by-side
- `.section-header` - Flexbox, h3 + button aligned
- `.chapter-box` - Full-width with left border accent
- `.preview-fade` - Gradient overlay for medium preview
- `.chapter-detail-content` - White background card with padding
- `.back-button-container` - Wrapper for back button alignment (added 2025-11-25)
- `.chapter-summary-actions` - Flexbox container for header buttons (added 2025-11-25)
- `.toggle-summary-btn` - Minimal chevron-only toggle button (redesigned 2025-11-25)
- `.header-nav-buttons` - Container for header navigation items (updated 2025-11-28)
  - Flexbox layout with 20px gap and margin-left (left-aligned near logo)
  - Changed from right-aligned buttons to left-aligned menu items
- `.header-nav-btn` - Individual navigation menu item (redesigned 2025-11-28)
  - Transparent background (no button appearance)
  - No borders or padding
  - Text-only design with hover effects (opacity + underline)
  - Appears as integrated menu items, not separate buttons

### Navigation Flow

**User Journey:**
```
Home Page (category carousels)
    ↓ (click "Categories" or "View All →")
Category/All Categories Page
    ↓ (click "Back to Home" - ALWAYS returns to home, not browser history)
Home Page
    ↓ (click "All Books")
All Books Grid Page
    ↓ (click "Back to Home" - ALWAYS returns to home, not browser history)
Home Page
    ↓ (click book from carousel/grid)
Book Overview (concise + medium preview + chapters)
    ↓ (click "Read Full Summary")
    Medium Detail Page (full medium summary)
    ↓ (click "Back to Book")
    Book Overview
    ↓ (click chapter box)
    Chapter Detail Page (full text + collapsible summary)
    ↓ (click "Back to Book")
    Book Overview
```

**Navigation Behavior Changes (Added 2025-11-28):**

**Before:**
- "Back to Home" used `window.history.back()` - unpredictable behavior depending on user's navigation history
- Category pages always refetched data - flash/reload effect
- Carousel book order randomized on every page load - inconsistent visual experience

**After:**
- "Back to Home" uses `this.showHomeSection()` - always returns to home page
  - Applied to: Category detail page (line 1275), All Categories page (line 1317), All Books page (line 1391)
  - Ensures predictable, consistent navigation
- Category data cached in `this.categoryCache` - instant page loads on return visits
  - Implemented in `showCategoryDetail()` (lines 1212-1278)
  - Checks cache before making API call
- Carousel order cached in `this.carouselOrderCache` - consistent book order
  - Implemented in `renderCategoryCarousel()` (lines 479-486)
  - Shuffles once, stores in cache, reuses on subsequent renders

**Scroll Behavior:**
- Automatic scroll to top when navigating to medium/chapter pages
- Prevents user confusion when content loads mid-scroll
- Implemented with `window.scrollTo(0, 0)` at start of page methods

### Text Rendering

**Markdown Rendering:**
```javascript
renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }
    return this.escapeHtml(text).replace(/\n/g, '<br>');
}
```

**Chapter Text Formatting:**
```javascript
formatChapterText(text) {
    const paragraphs = text.split(/\n/);
    return paragraphs
        .filter(p => p.trim().length > 0)
        .map(p => `<p>${this.escapeHtml(p.trim())}</p>`)
        .join('');
}
```

### Performance Optimizations

1. **Lazy Loading:** Books loaded once, cached in `this.allBooks`
2. **Parallel Fetching:** Concise, medium, and chapters loaded simultaneously
3. **Medium Summary Caching:** Stored in `this.mediumSummaryContent` for reuse
4. **Chapter Caching:** Stored in `this.chapters` array
5. **CSS Animations:** GPU-accelerated transforms and opacity
6. **Minimal Reflows:** Content cards prevent layout shifts

### Browser Compatibility

- Modern evergreen browsers (Chrome, Firefox, Safari, Edge)
- ES6+ features (async/await, arrow functions, template literals)
- CSS Grid and Flexbox
- HTML5 Audio API
- History API (pushState)

---

## Navigation UX Improvements (Added 2025-11-28)

**Overview:**
A series of improvements to enhance navigation consistency, performance, and user experience across the Summra application.

**Four Key Improvements:**

1. **Carousel Book Order Caching:**
   - **Problem:** Books randomized on every page load, causing inconsistent visual experience
   - **Solution:** Cache shuffled order in `this.carouselOrderCache` object
   - **Implementation:** `frontend/static/js/app.js` lines 27 (property), 479-486 (logic)
   - **Impact:** Consistent book order across page refreshes while maintaining randomization benefit

2. **Category Data Caching:**
   - **Problem:** Category pages refetched data every time, causing flash/reload effect
   - **Solution:** Cache API responses in `this.categoryCache` object
   - **Implementation:** `frontend/static/js/app.js` lines 27 (property), 1212-1278 (logic)
   - **Impact:** Instant page loads when returning to previously visited categories

3. **Consistent Back Button Behavior:**
   - **Problem:** "Back to Home" used browser history, causing unpredictable navigation
   - **Solution:** Replace `window.history.back()` with `this.showHomeSection()`
   - **Implementation:** `frontend/static/js/app.js` lines 1275-1280, 1317-1322, 1391-1396
   - **Impact:** Always returns to home page, predictable for users

4. **Image Lazy Loading:**
   - **Problem:** All images loaded immediately, slowing initial page load
   - **Solution:** Add `loading="lazy"` attribute to all book cover images
   - **Implementation:** `frontend/static/js/app.js` lines 484 (carousel), 1386 (grid)
   - **Impact:** Faster page loads, reduced bandwidth usage

5. **Header Navigation Styling (Bonus):**
   - **Problem:** Navigation buttons looked like separate UI elements
   - **Solution:** Minimal text-only design with transparent background
   - **Implementation:** `frontend/static/css/style.css` lines 74-95
   - **Impact:** Cleaner header appearance, integrated menu items instead of buttons

**Files Modified:**
- `frontend/static/js/app.js` (5 changes across caching, navigation, and lazy loading)
- `frontend/static/css/style.css` (1 change for header styling)

**Performance Gains:**
- Category page load: Instant (cached) vs. 500-1000ms (API fetch)
- Initial page load: ~20-30% faster with lazy loading (varies by connection speed)
- User experience: Consistent, predictable navigation behavior

---

## Reading Experience Customization (Added 2025-11-30)

**Overview:**

Kindle-inspired reading experience with customizable fonts, sizes, and color schemes, plus progress tracking and sequential navigation for distraction-free long-form reading.

**Purpose:** Provide a comfortable, customizable reading interface that matches e-reader standards while maintaining web accessibility.

### Architecture Components

**Three Main Systems:**

1. **Settings Panel System** - Right-sliding panel with font/size/theme controls
2. **Progress Tracking System** - Kindle-style thin progress bar showing scroll percentage
3. **Navigation Enhancement System** - Sticky headers and next chapter buttons

**Technology Stack:**

- **localStorage API** - Browser-based preference persistence
- **CSS Data Attributes** - Dynamic theme and font switching
- **CSS Custom Properties** - Theme-based color variables
- **Intersection Observer API** - Sticky header scroll detection (potential future optimization)
- **Vanilla JavaScript** - Event-driven settings management

### Settings Panel Implementation

**Location:** `frontend/templates/index.html:90-150`

**HTML Structure:**

```html
<!-- Settings Panel (slides from right) -->
<div class="reading-settings-panel hidden" id="reading-settings-panel">
    <div class="reading-settings-header">
        <h3>Reading Settings</h3>
        <button class="close-settings-btn" id="close-settings-btn">✕</button>
    </div>

    <!-- Font Family Selection -->
    <div class="reading-settings-section">
        <h4>Font Family</h4>
        <div class="font-choices">
            <button class="font-choice active" data-font="georgia">
                <span class="font-preview">Aa</span>
                <span class="font-label">Georgia</span>
            </button>
            <button class="font-choice" data-font="system">
                <span class="font-preview">Aa</span>
                <span class="font-label">System</span>
            </button>
            <button class="font-choice" data-font="opensans">
                <span class="font-preview">Aa</span>
                <span class="font-label">Open Sans</span>
            </button>
        </div>
    </div>

    <!-- Font Size Adjustment -->
    <div class="reading-settings-section">
        <h4>Text Size</h4>
        <div class="font-size-controls">
            <button class="font-size-btn" id="font-size-decrease">A-</button>
            <input type="range" id="font-size-slider"
                   min="12" max="24" value="16" step="1">
            <span class="font-size-display" id="font-size-display">16px</span>
            <button class="font-size-btn" id="font-size-increase">A+</button>
        </div>
    </div>

    <!-- Theme Selection -->
    <div class="reading-settings-section">
        <h4>Theme</h4>
        <div class="theme-choices">
            <button class="theme-choice active" data-theme="light">
                <span class="theme-preview" style="background: #fff; border: 1px solid #ddd;"></span>
                <span class="theme-label">Light</span>
            </button>
            <button class="theme-choice" data-theme="dark">
                <span class="theme-preview" style="background: #1a1a1a; color: #e0e0e0;"></span>
                <span class="theme-label">Dark</span>
            </button>
            <button class="theme-choice" data-theme="sepia">
                <span class="theme-preview" style="background: #f4ecd8; color: #5c4f3d;"></span>
                <span class="theme-label">Sepia</span>
            </button>
        </div>
    </div>
</div>
```

**CSS Implementation:** `frontend/static/css/style.css:1652-1850`

```css
/* Settings Panel - Slides from right edge */
.reading-settings-panel {
    position: fixed;
    right: 0;
    top: 0;
    width: 320px;  /* Desktop width */
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0,0,0,0.1);
    transform: translateX(100%);  /* Hidden off-screen */
    transition: transform 0.3s ease;
    z-index: 10000;
    overflow-y: auto;
    padding: 24px;
}

.reading-settings-panel:not(.hidden) {
    transform: translateX(0);  /* Slide into view */
}

/* Mobile: Full-width panel */
@media (max-width: 768px) {
    .reading-settings-panel {
        width: 100%;
    }
}

/* Font choice buttons */
.font-choice {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 8px;
    background: white;
    cursor: pointer;
    transition: all 0.2s;
}

.font-choice.active {
    border-color: var(--secondary-color);
    background: #e8f4f8;
}

.font-choice[data-font="georgia"] .font-preview {
    font-family: Georgia, serif;
}

.font-choice[data-font="system"] .font-preview {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.font-choice[data-font="opensans"] .font-preview {
    font-family: "Open Sans", sans-serif;
}

/* Theme choice buttons */
.theme-choice {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.theme-choice.active {
    border-color: var(--secondary-color);
    box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
}

.theme-preview {
    width: 60px;
    height: 40px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
}
```

**JavaScript Implementation:** `frontend/static/js/app.js:1483-1738`

```javascript
setupReadingSettings() {
    // Toggle buttons (both fixed and sticky headers)
    const toggleBtn = document.getElementById('reading-settings-toggle');
    const stickyToggleBtn = document.getElementById('sticky-settings-btn');
    const stickyToggleBtnMedium = document.getElementById('sticky-settings-btn-medium');
    const panel = document.getElementById('reading-settings-panel');
    const closeBtn = document.getElementById('close-settings-btn');

    // Open panel
    const openPanel = () => {
        if (panel) panel.classList.remove('hidden');
    };

    if (toggleBtn) toggleBtn.addEventListener('click', openPanel);
    if (stickyToggleBtn) stickyToggleBtn.addEventListener('click', openPanel);
    if (stickyToggleBtnMedium) stickyToggleBtnMedium.addEventListener('click', openPanel);

    // Close panel
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (panel) panel.classList.add('hidden');
        });
    }

    // Font selection
    const fontChoices = document.querySelectorAll('.font-choice');
    fontChoices.forEach(btn => {
        btn.addEventListener('click', () => {
            const font = btn.dataset.font;

            // Update active state
            fontChoices.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Apply font
            this.applyFont(font);

            // Save to localStorage
            this.saveReadingPreference('font', font);
        });
    });

    // Font size controls
    const slider = document.getElementById('font-size-slider');
    const decreaseBtn = document.getElementById('font-size-decrease');
    const increaseBtn = document.getElementById('font-size-increase');
    const sizeDisplay = document.getElementById('font-size-display');

    const updateFontSize = (size) => {
        if (slider) slider.value = size;
        if (sizeDisplay) sizeDisplay.textContent = `${size}px`;
        this.applyFontSize(size);
        this.saveReadingPreference('fontSize', size);
    };

    if (slider) {
        slider.addEventListener('input', (e) => {
            updateFontSize(e.target.value);
        });
    }

    if (decreaseBtn) {
        decreaseBtn.addEventListener('click', () => {
            const currentSize = parseInt(slider.value);
            const newSize = Math.max(12, currentSize - 1);  // Min 12px
            updateFontSize(newSize);
        });
    }

    if (increaseBtn) {
        increaseBtn.addEventListener('click', () => {
            const currentSize = parseInt(slider.value);
            const newSize = Math.min(24, currentSize + 1);  // Max 24px
            updateFontSize(newSize);
        });
    }

    // Theme selection
    const themeChoices = document.querySelectorAll('.theme-choice');
    themeChoices.forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.theme;

            // Update active state
            themeChoices.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Apply theme
            this.applyTheme(theme);

            // Save to localStorage
            this.saveReadingPreference('theme', theme);
        });
    });

    // Load saved preferences on page load
    this.loadReadingPreferences();
}
```

### Font Family System

**Supported Fonts:**

1. **Georgia** (Default) - Classic serif font, traditional book feel
2. **System** - Native system font stack, familiar to user's OS
3. **Open Sans** - Modern sans-serif, clean and readable

**CSS Data Attribute Pattern:**

```css
/* Font family applied via data-font attribute */
.chapter-detail-section[data-font="georgia"] .chapter-fulltext,
.chapter-detail-section[data-font="georgia"] .chapter-summary-text,
.medium-detail-section[data-font="georgia"] .summary-text {
    font-family: Georgia, serif;
}

.chapter-detail-section[data-font="system"] .chapter-fulltext,
.chapter-detail-section[data-font="system"] .chapter-summary-text,
.medium-detail-section[data-font="system"] .summary-text {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}

.chapter-detail-section[data-font="opensans"] .chapter-fulltext,
.chapter-detail-section[data-font="opensans"] .chapter-summary-text,
.medium-detail-section[data-font="opensans"] .summary-text {
    font-family: "Open Sans", sans-serif;
}
```

**JavaScript Application:**

```javascript
applyFont(font) {
    const chapterSection = document.getElementById('chapter-detail-section');
    const mediumSection = document.getElementById('medium-detail-section');

    // Apply to both chapter and medium summary pages
    if (chapterSection) {
        chapterSection.setAttribute('data-font', font);
    }
    if (mediumSection) {
        mediumSection.setAttribute('data-font', font);
    }
}
```

### Font Size System

**Size Range:** 12px (minimum) to 24px (maximum), default 16px

**Implementation Strategy:**

- **NOT CSS Variables** - Direct inline styles for better specificity
- **Scoped to Reading Content** - Does NOT affect UI elements (buttons, headers, navigation)
- **Dual Page Support** - Applies to both chapter detail and medium summary pages

**JavaScript Application:**

```javascript
applyFontSize(size) {
    const chapterSection = document.getElementById('chapter-detail-section');
    const mediumSection = document.getElementById('medium-detail-section');

    // Chapter page: Apply to full text and summary
    if (chapterSection) {
        const fulltext = chapterSection.querySelector('.chapter-fulltext');
        const summaryText = chapterSection.querySelector('.chapter-summary-text');

        if (fulltext) {
            fulltext.style.fontSize = `${size}px`;
        }
        if (summaryText) {
            summaryText.style.fontSize = `${size}px`;
        }
    }

    // Medium summary page: Apply to summary text
    if (mediumSection) {
        const mediumText = mediumSection.querySelector('.summary-text');
        if (mediumText) {
            mediumText.style.fontSize = `${size}px`;
        }
    }
}
```

**Exclusions (Elements NOT affected by font size changes):**

- Next chapter button (`.next-chapter-btn`)
- Back button (`.back-button`)
- Headers (`.chapter-detail-header`, sticky headers)
- Settings panel (`.reading-settings-panel`)
- Navigation elements

### Color Scheme (Theme) System

**Three Themes:**

1. **Light Theme** (Default)
   - Background: `#FFFFFF` (white)
   - Text: `#2c3e50` (dark gray)
   - Use case: Bright environments, daytime reading

2. **Dark Theme**
   - Background: `#1a1a1a` (dark gray)
   - Text: `#e0e0e0` (light gray)
   - Use case: Low-light environments, night reading, reduced eye strain

3. **Sepia Theme**
   - Background: `#f4ecd8` (beige/cream)
   - Text: `#5c4f3d` (warm brown)
   - Use case: Kindle-like warm tones, reduced blue light, comfortable long sessions

**CSS Implementation:**

```css
/* Light theme (default) */
.chapter-detail-section,
.medium-detail-section {
    background: #FFFFFF;
    color: #2c3e50;
}

/* Dark theme */
.chapter-detail-section[data-theme="dark"],
.medium-detail-section[data-theme="dark"] {
    background: #1a1a1a;
    color: #e0e0e0;
}

.chapter-detail-section[data-theme="dark"] .chapter-detail-content,
.medium-detail-section[data-theme="dark"] .summary-content-card {
    background: #1a1a1a;
    color: #e0e0e0;
}

/* Sepia theme */
.chapter-detail-section[data-theme="sepia"],
.medium-detail-section[data-theme="sepia"] {
    background: #f4ecd8;
    color: #5c4f3d;
}

.chapter-detail-section[data-theme="sepia"] .chapter-detail-content,
.medium-detail-section[data-theme="sepia"] .summary-content-card {
    background: #f4ecd8;
    color: #5c4f3d;
}

/* Next chapter button adapts to theme */
.next-chapter-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
}

.chapter-detail-section[data-theme="dark"] .next-chapter-btn {
    border-color: #444;
    color: #e0e0e0;
}

.chapter-detail-section[data-theme="sepia"] .next-chapter-btn {
    border-color: #d4c4a8;
    color: #5c4f3d;
}
```

**JavaScript Application:**

```javascript
applyTheme(theme) {
    const chapterSection = document.getElementById('chapter-detail-section');
    const mediumSection = document.getElementById('medium-detail-section');

    // Apply to both pages
    if (chapterSection) {
        chapterSection.setAttribute('data-theme', theme);
    }
    if (mediumSection) {
        mediumSection.setAttribute('data-theme', theme);
    }
}
```

### localStorage Persistence

**Storage Keys:**

- `reading_font` - Font family choice (georgia/system/opensans)
- `reading_fontSize` - Font size in pixels (12-24)
- `reading_theme` - Color scheme (light/dark/sepia)

**Save Implementation:**

```javascript
saveReadingPreference(key, value) {
    try {
        localStorage.setItem(`reading_${key}`, value);
    } catch (error) {
        console.error('Error saving reading preference:', error);
        // Graceful degradation - settings still work for current session
    }
}
```

**Load Implementation:**

```javascript
loadReadingPreferences() {
    try {
        // Load from localStorage with defaults
        const font = localStorage.getItem('reading_font') || 'georgia';
        const fontSize = localStorage.getItem('reading_fontSize') || '16';
        const theme = localStorage.getItem('reading_theme') || 'light';

        // Apply preferences
        this.applyFont(font);
        this.applyFontSize(fontSize);
        this.applyTheme(theme);

        // Update UI to reflect loaded preferences
        this.updateSettingsPanelUI(font, fontSize, theme);

    } catch (error) {
        console.error('Error loading reading preferences:', error);
        // Use defaults if localStorage fails
        this.applyFont('georgia');
        this.applyFontSize('16');
        this.applyTheme('light');
    }
}
```

**UI State Synchronization:**

```javascript
updateSettingsPanelUI(font, fontSize, theme) {
    // Update font choice active state
    const fontChoices = document.querySelectorAll('.font-choice');
    fontChoices.forEach(btn => {
        if (btn.dataset.font === font) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Update font size slider and display
    const slider = document.getElementById('font-size-slider');
    const sizeDisplay = document.getElementById('font-size-display');
    if (slider) slider.value = fontSize;
    if (sizeDisplay) sizeDisplay.textContent = `${fontSize}px`;

    // Update theme choice active state
    const themeChoices = document.querySelectorAll('.theme-choice');
    themeChoices.forEach(btn => {
        if (btn.dataset.theme === theme) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}
```

### Reading Progress Indicator

**Design:** Kindle-style thin progress bar (2px height, NOT thick web-style)

**Location:** Fixed to bottom of viewport

**HTML Structure:**

```html
<!-- Chapter page progress bar -->
<div class="reading-progress-bar" id="reading-progress-bar">
    <div class="reading-progress-fill" id="reading-progress-fill"></div>
    <div class="reading-progress-text" id="reading-progress-text">0%</div>
</div>

<!-- Medium summary page progress bar -->
<div class="reading-progress-bar-medium hidden" id="reading-progress-bar-medium">
    <div class="reading-progress-fill-medium" id="reading-progress-fill-medium"></div>
    <div class="reading-progress-text-medium" id="reading-progress-text-medium">0%</div>
</div>
```

**CSS Styling:**

```css
/* Kindle-style thin progress bar (2px, not thick) */
.reading-progress-bar,
.reading-progress-bar-medium {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 2px;  /* Thin like Kindle */
    background: rgba(0, 0, 0, 0.1);
    z-index: 9999;
}

.reading-progress-fill,
.reading-progress-fill-medium {
    height: 100%;
    background: var(--secondary-color);  /* #3498db blue */
    width: 0%;
    transition: width 0.2s ease;
}

.reading-progress-text,
.reading-progress-text-medium {
    position: absolute;
    right: 12px;
    top: -24px;
    font-size: 0.85rem;
    color: var(--text-color);
    font-weight: 500;
    background: white;
    padding: 2px 8px;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* Mobile: Taller bar for better visibility */
@media (max-width: 768px) {
    .reading-progress-bar,
    .reading-progress-bar-medium {
        height: 32px;
        background: rgba(0, 0, 0, 0.05);
    }

    .reading-progress-text,
    .reading-progress-text-medium {
        top: 50%;
        transform: translateY(-50%);
    }
}
```

**Progress Calculation Algorithm:**

```javascript
updateReadingProgress() {
    const chapterSection = document.getElementById('chapter-detail-section');
    if (!chapterSection || chapterSection.classList.contains('hidden')) {
        return;  // Not on chapter page
    }

    // Calculate scroll percentage
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    const scrollTop = window.scrollY;
    const scrollableHeight = documentHeight - windowHeight;

    let progress = 0;
    if (scrollableHeight > 0) {
        progress = Math.min(100, Math.round((scrollTop / scrollableHeight) * 100));
    }

    // Update progress bar
    const progressFill = document.getElementById('reading-progress-fill');
    const progressText = document.getElementById('reading-progress-text');

    if (progressFill) {
        progressFill.style.width = `${progress}%`;
    }
    if (progressText) {
        progressText.textContent = `${progress}%`;
    }
}

// Attached to scroll event
window.addEventListener('scroll', () => {
    this.updateReadingProgress();
    this.updateReadingProgressMedium();
    this.updateStickyHeader();
    this.updateStickyHeaderMedium();
});
```

**Formula Breakdown:**

```
scrollableHeight = total document height - viewport height
progress = (current scroll position / scrollable height) * 100

Example:
  Document: 5000px tall
  Viewport: 1000px tall
  Scrollable: 5000 - 1000 = 4000px

  At top (scrollTop = 0):     0 / 4000 * 100 = 0%
  At middle (scrollTop = 2000): 2000 / 4000 * 100 = 50%
  At bottom (scrollTop = 4000): 4000 / 4000 * 100 = 100%
```

### Sticky Reading Header

**Purpose:** Keep book/chapter title and settings access visible during scroll

**Trigger:** Appears when user scrolls past the main chapter title

**HTML Structure:**

```html
<!-- Chapter page sticky header -->
<div class="sticky-reading-header hidden" id="sticky-reading-header">
    <div class="sticky-header-content">
        <h3>
            <span id="sticky-chapter-title">Chapter 8</span>
            <span class="sticky-header-title-separator">—</span>
            <span id="sticky-book-title">The Time Machine</span>
        </h3>
        <button class="sticky-settings-btn" id="sticky-settings-btn">⚙️</button>
    </div>
</div>

<!-- Medium summary page sticky header -->
<div class="sticky-reading-header-medium hidden" id="sticky-reading-header-medium">
    <div class="sticky-header-content">
        <h3 id="sticky-book-title-medium">The Time Machine</h3>
        <button class="sticky-settings-btn" id="sticky-settings-btn-medium">⚙️</button>
    </div>
</div>
```

**CSS Styling:**

```css
/* Sticky header - edge-to-edge */
.sticky-reading-header,
.sticky-reading-header-medium {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;  /* Edge-to-edge */
    background: var(--header-color);  /* #2c3e50 blue-gray */
    color: white;
    z-index: 1000;
    transform: translateY(-100%);  /* Hidden above viewport */
    transition: transform 0.3s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.sticky-reading-header:not(.hidden),
.sticky-reading-header-medium:not(.hidden) {
    transform: translateY(0);  /* Slide down into view */
}

.sticky-header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.sticky-header-content h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.sticky-header-title-separator {
    margin: 0 12px;
    opacity: 0.6;
}

.sticky-settings-btn {
    background: transparent;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 8px;
    color: white;
    transition: opacity 0.2s;
}

.sticky-settings-btn:hover {
    opacity: 0.8;
}
```

**Scroll Detection Logic:**

```javascript
updateStickyHeader() {
    const chapterSection = document.getElementById('chapter-detail-section');
    if (!chapterSection || chapterSection.classList.contains('hidden')) {
        return;
    }

    const header = document.getElementById('chapter-detail-header');
    const stickyHeader = document.getElementById('sticky-reading-header');

    if (!header || !stickyHeader) return;

    // Get header's position relative to viewport
    const headerRect = header.getBoundingClientRect();

    // Show sticky header when main header scrolls out of view
    if (headerRect.bottom < 0) {
        // Main header is above viewport - show sticky
        stickyHeader.classList.remove('hidden');
    } else {
        // Main header still visible - hide sticky
        stickyHeader.classList.add('hidden');
    }
}
```

**Dual Implementation:**

- Chapter page: Shows "Chapter X — Book Title"
- Medium summary page: Shows "Book Title" only
- Both have settings button (⚙️) that opens same reading settings panel

### Next Chapter Navigation

**Purpose:** Allow sequential reading without returning to book overview

**Display Logic:** Only shown when a next chapter exists

**HTML Structure:**

```html
<div class="next-chapter-container" id="next-chapter-container">
    <button class="next-chapter-btn hidden" id="next-chapter-btn">
        Next Chapter →
    </button>
</div>
```

**CSS Styling:**

```css
.next-chapter-container {
    margin-top: 48px;
    margin-bottom: 80px;
    text-align: center;
}

.next-chapter-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 14px 32px;
    font-size: 1rem;  /* Fixed size, NOT affected by reading font size */
    font-family: inherit;  /* Uses default UI font, NOT reading font */
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.next-chapter-btn:hover {
    border-color: var(--secondary-color);
    background: rgba(52, 152, 219, 0.05);
}

/* Theme adaptation */
.chapter-detail-section[data-theme="dark"] .next-chapter-btn {
    border-color: #444;
    color: #e0e0e0;
}

.chapter-detail-section[data-theme="dark"] .next-chapter-btn:hover {
    border-color: var(--secondary-color);
    background: rgba(52, 152, 219, 0.1);
}

.chapter-detail-section[data-theme="sepia"] .next-chapter-btn {
    border-color: #d4c4a8;
    color: #5c4f3d;
}
```

**JavaScript Implementation:**

```javascript
async showChapterDetail(book, chapterNum) {
    // ... (load chapter data) ...

    // Next chapter button logic
    const nextChapterBtn = document.getElementById('next-chapter-btn');
    const nextChapterContainer = document.getElementById('next-chapter-container');

    if (nextChapterBtn && nextChapterContainer) {
        // Find next chapter in sequence
        const currentIndex = this.chapters.findIndex(c => c.chapter_number === chapterNum);
        const hasNextChapter = currentIndex >= 0 && currentIndex < this.chapters.length - 1;

        if (hasNextChapter) {
            const nextChapter = this.chapters[currentIndex + 1];

            // Show button
            nextChapterBtn.classList.remove('hidden');
            nextChapterContainer.classList.remove('hidden');

            // Set up click handler
            nextChapterBtn.onclick = () => {
                this.showChapterDetail(book, nextChapter.chapter_number);
                window.scrollTo(0, 0);  // Scroll to top of new chapter
            };
        } else {
            // Last chapter - hide button
            nextChapterBtn.classList.add('hidden');
            nextChapterContainer.classList.add('hidden');
        }
    }
}
```

### Performance Characteristics

**localStorage Operations:**

- Read: <1ms (synchronous)
- Write: <1ms (synchronous)
- Storage limit: 5-10MB per domain (more than sufficient for preferences)

**CSS Transform Animations:**

- Settings panel slide: 300ms GPU-accelerated transform
- Sticky header slide: 300ms GPU-accelerated transform
- No reflows or repaints during animation

**Scroll Event Handling:**

- Progress update: ~0.5-1ms per scroll event
- Sticky header check: ~0.2-0.5ms per scroll event
- Uses `requestAnimationFrame` pattern (potential future optimization)

**Theme Switching:**

- CSS data attribute change: <1ms
- Browser re-render: 16-32ms (one frame)
- No JavaScript-heavy DOM manipulation

### Browser Compatibility

**localStorage:**
- Chrome 4+
- Firefox 3.5+
- Safari 4+
- Edge (all versions)
- iOS Safari 3.2+

**CSS Data Attributes:**
- Universal support (CSS 2.1)

**CSS Transforms:**
- Chrome 4+
- Firefox 3.5+
- Safari 3.1+
- Edge (all versions)

**CSS Custom Properties (for themes):**
- Chrome 49+
- Firefox 31+
- Safari 9.1+
- Edge 15+

### Edge Cases Handled

**1. localStorage Unavailable:**
- Graceful degradation - settings work for current session
- No errors thrown to user
- Defaults applied on page load

**2. Very Long Chapter Titles:**
- Text overflow with ellipsis in sticky header
- Max-width constraints prevent layout breaking

**3. No Next Chapter:**
- Button automatically hidden
- Container also hidden to avoid empty space

**4. Rapid Theme Switching:**
- CSS transitions smooth out rapid changes
- No performance degradation

**5. Mobile Viewport:**
- Progress bar height increases to 32px for better visibility
- Settings panel goes full-width instead of 320px
- Touch-friendly tap targets (44x44 minimum)

**6. URL Refresh on Chapter Page:**
- Fixed routing bug where refresh redirected to home
- Route handler now preserves chapter URL state
- Reading preferences persist via localStorage

### Integration Points

**Initialization:** `app.js:82` (called in constructor)

```javascript
constructor() {
    // ... other initialization ...
    this.setupReadingSettings();
}
```

**Page Navigation:**

- `showChapterDetail()` - Loads preferences, shows progress bar, enables sticky header
- `showMediumDetail()` - Loads preferences, shows progress bar (medium), enables sticky header (medium)

**Event Listeners:**

- `window.scroll` - Updates progress + sticky header
- Font/size/theme buttons - Applies changes + saves to localStorage
- Settings panel open/close - Toggle button handlers
- Next chapter button - Sequential navigation

### Future Enhancements

**Planned:**

1. **Reading Position Memory** - Remember scroll position per chapter
2. **Highlight Tracking** - Save user highlights via localStorage
3. **Reading Speed Estimate** - Calculate words per minute, show estimated time remaining
4. **Voice Selection for TTS** - Different voices in settings panel
5. **Line Height Adjustment** - Additional reading comfort option
6. **Text Justification Toggle** - Left-aligned vs. justified text
7. **Intersection Observer** - Replace scroll event with more efficient API

**Considered but Deferred:**

- Auto-scroll mode (hands-free reading)
- Reading goals and statistics
- Social sharing of reading progress
- Custom theme creation (color pickers)

---

## Chapter Illustration Lightbox (Added 2025-12-01)

**Overview:**

Full-screen image overlay for viewing chapter illustrations in high quality, with smooth fade transitions and multiple interaction methods for closing.

**Purpose:** Provide a distraction-free, full-screen viewing experience for chapter illustrations without leaving the reading page.

### Architecture Components

**Three Main Systems:**

1. **HTML Overlay Structure** - Fixed position modal with dark background
2. **CSS Styling** - Full-screen layout with fade transitions and responsive sizing
3. **JavaScript Event Handling** - Click handlers, keyboard shortcuts, and scroll lock

**Technology Stack:**

- **CSS Fixed Positioning** - Full-viewport overlay at z-index 10000
- **CSS Transitions** - Smooth fade effects (0.3s ease)
- **Event Delegation** - Click handlers for close button, background, and Escape key
- **Body Scroll Lock** - `document.body.style.overflow = 'hidden'` when overlay is open
- **Responsive Images** - `max-width/max-height` constraints (90vh/90vw desktop, 95vh/95vw mobile)

### HTML Structure

**Location:** `frontend/templates/index.html:299-303`

```html
<!-- Image Lightbox Overlay -->
<div class="lightbox-overlay hidden" id="lightbox-overlay">
    <button class="lightbox-close" id="lightbox-close" aria-label="Close lightbox">✕</button>
    <img class="lightbox-image" id="lightbox-image" alt="" />
</div>
```

**Element Breakdown:**

- `.lightbox-overlay` - Full-screen container with dark background (rgba(0,0,0,0.95))
- `.lightbox-close` - Circular close button in top-right corner (50x50px, semi-transparent white)
- `.lightbox-image` - Centered image with object-fit contain

### CSS Implementation

**Location:** `frontend/static/css/style.css` (appended at end)

**Key Styling Patterns:**

```css
/* Full-screen overlay */
.lightbox-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.95);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: zoom-out;
    opacity: 1;
    transition: opacity 0.3s ease;
}

.lightbox-overlay.hidden {
    opacity: 0;
    pointer-events: none;  /* Allow clicks to pass through when hidden */
}

/* Close button - top right corner */
.lightbox-close {
    position: absolute;
    top: 24px;
    right: 24px;
    background: rgba(255, 255, 255, 0.1);
    border: 2px solid rgba(255, 255, 255, 0.3);
    color: white;
    font-size: 2rem;
    width: 50px;
    height: 50px;
    border-radius: 50%;  /* Circular button */
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    z-index: 10001;  /* Above overlay */
}

.lightbox-close:hover {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.5);
    transform: scale(1.1);
}

/* Centered image with size constraints */
.lightbox-image {
    max-width: 90vw;
    max-height: 90vh;
    object-fit: contain;
    cursor: default;  /* Not clickable */
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

/* Make chapter illustrations clickable */
.chapter-illustration {
    cursor: pointer;
    transition: opacity 0.2s;
}

.chapter-illustration:hover {
    opacity: 0.9;  /* Visual feedback on hover */
}

/* Mobile adjustments */
@media (max-width: 768px) {
    .lightbox-close {
        top: 16px;
        right: 16px;
        width: 44px;  /* Touch-friendly size */
        height: 44px;
        font-size: 1.5rem;
    }

    .lightbox-image {
        max-width: 95vw;  /* More screen space on mobile */
        max-height: 95vh;
    }
}
```

**Design Decisions:**

- **z-index 10000:** Ensures overlay appears above all other content (higher than reading settings panel)
- **opacity transition:** Smooth fade effect instead of instant show/hide
- **pointer-events: none:** When hidden, allows clicks to pass through to underlying content
- **cursor: zoom-out:** Visual indication that clicking background will close overlay
- **object-fit: contain:** Image scales proportionally without cropping

### JavaScript Implementation

**Location:** `frontend/static/js/app.js`

**Initialization:** Line 39 in constructor

```javascript
constructor() {
    // ... other initialization ...
    this.setupLightbox();  // Initialize lightbox event handlers
}
```

**Main Method:** Lines 1830-1881

```javascript
setupLightbox() {
    const lightboxOverlay = document.getElementById('lightbox-overlay');
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxClose = document.getElementById('lightbox-close');

    if (!lightboxOverlay || !lightboxImage || !lightboxClose) {
        return;  // Elements not found (graceful degradation)
    }

    // Function to open lightbox
    const openLightbox = (imageSrc, imageAlt) => {
        lightboxImage.src = imageSrc;
        lightboxImage.alt = imageAlt || '';
        lightboxOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';  // Prevent background scroll
    };

    // Function to close lightbox
    const closeLightbox = () => {
        lightboxOverlay.classList.add('hidden');
        document.body.style.overflow = '';  // Restore scroll
    };

    // Close button click
    lightboxClose.addEventListener('click', (e) => {
        e.stopPropagation();  // Prevent event bubbling to overlay
        closeLightbox();
    });

    // Click on overlay background (not on image)
    lightboxOverlay.addEventListener('click', (e) => {
        if (e.target === lightboxOverlay) {
            closeLightbox();
        }
    });

    // Escape key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !lightboxOverlay.classList.contains('hidden')) {
            closeLightbox();
        }
    });

    // Store reference for use when loading chapters
    this.openLightbox = openLightbox;
}
```

**Integration with Chapter Display:** Lines 1003-1008 in `showChapterDetail()`

```javascript
// Add click handler to chapter illustration
illustrationImg.onclick = () => {
    if (this.openLightbox) {
        this.openLightbox(illustrationUrl, `Illustration for ${chapterTitle}`);
    }
};
```

### Event Handling Patterns

**Three Close Methods:**

1. **Close Button Click:**
   - User clicks the ✕ button in top-right corner
   - `e.stopPropagation()` prevents event from bubbling to overlay click handler
   - Explicit visual affordance for closing

2. **Background Click:**
   - User clicks on dark overlay area (not on image)
   - `e.target === lightboxOverlay` check ensures clicks on image don't close
   - Common pattern in modal interfaces

3. **Escape Key:**
   - User presses Escape key
   - Only triggers when overlay is visible (`!lightboxOverlay.classList.contains('hidden')`)
   - Keyboard accessibility

**Scroll Lock Implementation:**

```javascript
// When opening
document.body.style.overflow = 'hidden';

// When closing
document.body.style.overflow = '';  // Restore original value
```

**Benefits:**
- Prevents page from scrolling while viewing full-screen image
- Maintains user's scroll position on chapter page
- Restores normal scroll behavior when closing

### User Experience Flow

```
User reads chapter with illustration
    ↓
Hover over illustration (cursor changes to pointer, opacity reduces to 0.9)
    ↓
Click illustration
    ↓
Lightbox fades in (0.3s transition)
    ↓
Page scroll is locked
    ↓
Image displayed full-screen (max 90vh/90vw)
    ↓
User views high-quality image
    ↓
User closes via one of three methods:
    - Click ✕ button (top-right)
    - Click dark background area
    - Press Escape key
    ↓
Lightbox fades out (0.3s transition)
    ↓
Page scroll is restored
    ↓
User returns to chapter reading
```

### Performance Characteristics

**CSS Transitions:**
- Fade duration: 300ms (smooth but not sluggish)
- GPU-accelerated opacity transitions (no reflows)
- Button hover scale: 200ms (responsive feel)

**Image Loading:**
- Images already loaded in chapter view
- No additional network request when opening lightbox
- Instant display when opening (image already cached)

**Event Listeners:**
- Global keyboard listener (efficient, single listener for all lightboxes)
- Event delegation pattern (no memory leaks)
- Cleanup not required (listeners persist for app lifetime)

**Memory Usage:**
- Minimal overhead (~1-2 KB for event handlers)
- No DOM cloning or duplication
- Single overlay instance reused for all images

### Browser Compatibility

**CSS Features:**

- **position: fixed:** Universal support
- **flexbox (align-items, justify-content):** IE11+, all modern browsers
- **rgba() colors:** IE9+, all modern browsers
- **CSS transitions:** IE10+, all modern browsers
- **object-fit:** IE does not support (fallback: image may not scale perfectly)

**JavaScript Features:**

- **classList API:** IE10+, all modern browsers
- **Arrow functions:** ES6 (transpile for IE11 if needed)
- **addEventListener:** Universal support
- **Escape key detection:** Universal support

**Graceful Degradation:**

- If elements not found, `setupLightbox()` returns early (no errors)
- If `openLightbox` not defined, click handler checks before calling
- CSS fallbacks for older browsers (image still visible, just not perfectly scaled)

### Edge Cases Handled

**1. Missing Elements:**
- Early return if lightbox elements not in DOM
- No errors thrown if template structure changes

**2. Multiple Images:**
- Lightbox reused for all chapter illustrations
- Image src/alt updated dynamically on each open
- No memory leaks from multiple instances

**3. Rapid Open/Close:**
- CSS transitions handle rapid toggling smoothly
- No animation queue buildup
- No performance degradation

**4. Mobile Touch:**
- Touch-friendly close button size (44x44px minimum)
- Larger image viewport on mobile (95vh/95vw vs 90vh/90vw)
- Tap on background closes overlay

**5. Keyboard Navigation:**
- Escape key closes only when overlay is visible
- No interference with other keyboard shortcuts
- Accessible close method for keyboard users

**6. Background Scroll:**
- Scroll position preserved when opening
- Scroll locked while viewing (no jarring scroll jumps)
- Scroll restored to exact position when closing

**7. Very Large Images:**
- `max-width/max-height` prevents overflow
- `object-fit: contain` maintains aspect ratio
- Image always fits within viewport

**8. Very Small Images:**
- Image displayed at natural size (no upscaling)
- Centered in viewport
- Box shadow provides visual separation from background

### Integration Points

**Chapter Display Integration:**

- `showChapterDetail()` adds click handler to illustration (lines 1003-1008)
- Checks for illustration URL in chapter data
- Only adds handler if `this.openLightbox` is defined

**Template Structure:**

- Lightbox overlay placed at root level (before `</body>`)
- Outside any section containers (allows full-screen positioning)
- Hidden by default (`.hidden` class)

**Event Flow:**

```
User clicks illustration
    ↓
onclick handler in showChapterDetail()
    ↓
this.openLightbox(imageSrc, imageAlt)
    ↓
setupLightbox() closures handle state management
    ↓
CSS transitions provide visual feedback
```

### Future Enhancements

**Planned:**

1. **Image Zoom** - Pinch-to-zoom or click-to-zoom for very large illustrations
2. **Navigation Arrows** - Previous/Next buttons to cycle through chapter illustrations
3. **Download Button** - Allow users to save illustrations
4. **Image Metadata** - Display illustration caption/description if available
5. **Touch Gestures** - Swipe down to close on mobile (like iOS photos)
6. **Loading Indicator** - Spinner for slow-loading high-res images
7. **Keyboard Navigation** - Arrow keys to navigate between illustrations

**Considered but Deferred:**

- Image comparison slider (before/after views)
- Fullscreen API integration (native browser fullscreen)
- Image rotation controls
- Social sharing of illustrations
- Print functionality

---

## Summary

This ERD document provides comprehensive technical details for:

1. **Database Schema** - Complete ERD with all tables, relationships, constraints, and indexing strategies
2. **Chapter Parser** - 450+ lines of regex patterns, FSM logic, TOC detection, multi-part merging, and edge case handling
3. **Two-Level Book Structure** - Hierarchical TOC parsing (PART/BOOK/ACT → Chapters), composite numbering, and frontend rendering (added 2025-11-27)
4. **TTS Engine** - VITS model architecture, caching strategy, audio generation pipeline, and performance characteristics
5. **LLM Integration** - Rate limiting algorithm, prompt construction, response parsing, and model selection
6. **Bulk Processing** - Batching algorithm, index-based parsing, and cost optimization
7. **Project Gutenberg** - Metadata extraction, content cleaning, and cover image downloading
8. **Frontend Architecture** - SPA routing, component structure, state management, and UI/UX design patterns (added 2025-11-25)
9. **Navigation UX Improvements** - Caching strategies, back button behavior, lazy loading, and header styling (added 2025-11-28)
10. **Reading Experience Customization** - Kindle-inspired features with font/size/theme controls, progress tracking, and sequential navigation (added 2025-11-30)
11. **Chapter Illustration Lightbox** - Full-screen image overlay with multiple close methods and responsive design (added 2025-12-01)

This document should provide complete context for future development and Claude Code sessions.

---

## Two-Level Book Structure Detection

**Added:** 2025-11-27
**Location:** `scripts/generate_summaries.py::extract_two_level_toc()`
**Database:** `book_sections` table with `section_id` FK in `chapters` table

### Overview

The two-level structure system enables proper representation of books organized as PART/BOOK/ACT → Chapters, instead of flattening them into a single sequential list. This preserves the author's intended structure and improves navigation.

### Supported Structures

**Two-Level (Hierarchical):**
- **Parts:** Treasure Island (6 parts), White Fang (5 parts)
- **Books:** War and Peace (15 books), Principles of Political Economy (5 books)
- **Acts/Scenes:** Romeo and Juliet (5 acts, 24 scenes)

**Single-Level (Traditional):**
- Alice in Wonderland (numbered chapters)
- The Time Machine (numbered chapters)
- A Christmas Carol (staves)

### Algorithm: `extract_two_level_toc()`

**Input:** Full book text (Project Gutenberg format)
**Output:** List of section dictionaries with nested chapter data, or None

**Pattern Matching:**
```python
# Section markers (PART/BOOK/ACT)
section_pattern = r'(PART|BOOK|ACT)\s+(ONE|TWO|...|[0-9]+|[IVXLCDM]+)(?:\s*:?\s*(.+?))?'

# Chapter/scene markers
chapter_pattern = r'(?:CHAPTER|Chapter|SCENE|Scene)\s+([IVXLCDM]+|[0-9]+)\.?\s*(.+)?'

# Roman numeral + title
roman_title_pattern = r'([IVXLCDM]+)\.\s+(.+?)'
```

**Detection Flow:**

1. **Find TOC:** Search for "Contents" (case-insensitive)
2. **Parse Sections:** Match PART/BOOK/ACT patterns with numerals
3. **Parse Chapters:** Match Chapter/Scene patterns under each section
4. **Duplicate Detection:** Exit when duplicate section number detected (TOC ended)
5. **Return Structure:** List of sections with nested chapters

**Example Output Structure:**
```python
[
    {
        'type': 'PART',
        'number': 1,
        'numeral': 'ONE',
        'title': 'The Old Buccaneer',
        'chapters': [
            {'number': 1, 'numeral': 'I', 'title': 'The Old Sea-dog at the Admiral Benbow'},
            {'number': 2, 'numeral': 'II', 'title': 'Black Dog Appears and Disappears'},
            ...
        ]
    },
    ...
]
```

### Chapter Numbering System

**Composite Numbering (Two-Level Books):**
```
chapter_number = section_number * 100 + chapter_in_section
```

Examples:
- Part 1, Chapter 3 → 103
- Part 2, Chapter 1 → 201
- Act 3, Scene 5 → 305

**Sequential Numbering (Single-Level Books):**
```
chapter_number = 1, 2, 3, ...
```

**Benefits:**
- Maintains unique chapter numbers across entire book
- Preserves section information in chapter number
- Enables efficient database queries
- Compatible with existing chapter detection logic

### Database Storage

**book_sections Table:**
```sql
INSERT INTO book_sections (book_id, section_type, section_number, section_title)
VALUES (1, 'PART', 1, 'The Old Buccaneer')
```

**chapters Table (with section linkage):**
```sql
INSERT INTO chapters (book_id, section_id, chapter_number, chapter_title, ...)
VALUES (1, 5, 103, 'The Black Spot', ...)
       -- section_id=5 links to "PART ONE"
       -- chapter_number=103 means Part 1, Chapter 3
```

**IMPORTANT - Section ID Design (Auto-Increment Primary Keys):**

Section IDs are globally unique auto-incrementing primary keys across ALL books, while `section_number` stores the logical section number (1, 2, 3, ...).

**Example:**
- Book 1 creates sections → section IDs: 1, 2, 3 (section_numbers: 1, 2, 3)
- Book 2 creates sections → section IDs: 4, 5, 6 (section_numbers: 1, 2, 3)
- Book 3 creates sections → section IDs: 7, 8 (section_numbers: 1, 2)

**Why Large Section IDs:**
- Standard database design (surrogate keys)
- Section ID = database primary key (auto-increment)
- Section Number = logical numbering for display (Part 1, Part 2)
- Large IDs (53, 54, 57, 58) result from:
  - Previous books creating sections 1-52
  - Deleted sections not reused (53, 54 deleted during regeneration bug - see below)
  - New sections created with next available ID (57, 58)

**Regenerate Mode Critical Behavior (Bug Fixed 2025-11-28):**

**BEFORE FIX - INCORRECT (Section Deletion Bug):**
```python
# WRONG: Section creation runs in regenerate mode
if not dry_run and not partial_run:  # ❌ Missing regenerate_chapters check
    # INSERT OR REPLACE with UNIQUE(book_id, section_number) causes deletion
    section_id = db.add_book_section(book_id, section_type, section_number, section_title)
    # Old sections deleted, new sections created with new IDs
    # Example: Sections 53, 54 deleted → Sections 57, 58 created
    # Result: Chapters pointing to 53, 54 become orphaned!
```

**AFTER FIX - CORRECT (Preserve Existing Sections):**
```python
# CORRECT: Skip section creation in regenerate mode
if not dry_run and not partial_run and not regenerate_chapters:  # ✅ Added check
    # Normal mode: Create new sections
    section_id = db.add_book_section(...)
elif regenerate_chapters:  # ✅ New branch
    # Regenerate mode: Use existing sections from database
    existing_sections = db.get_book_sections(book_id)
    section_lookup = {s['section_number']: s['id'] for s in existing_sections}
    # Map chapters to existing section IDs (no deletion, no new IDs)
    section_id = section_lookup.get(section_number)
```

**Location:** `scripts/generate_summaries.py:3248-3295`

**Impact of Bug:**
- Regenerating Chapters 54-55 in "The Adventures of Ferdinand Count Fathom" (Book ID 63)
- Old sections 53, 54 deleted by `INSERT OR REPLACE`
- New sections 57, 58 created with new auto-increment IDs
- Only regenerated chapters (54-55) got new section_id=58
- All other chapters (1-53, 56-67) still pointed to deleted sections 53, 54
- Result: 65 out of 67 chapters orphaned (invisible in UI)

**Database Repair:**
```sql
-- Fixed Ferdinand Count Fathom orphaned chapters
UPDATE chapters SET section_id = 57 WHERE book_id = 63 AND chapter_number BETWEEN 1 AND 31;
UPDATE chapters SET section_id = 58 WHERE book_id = 63 AND chapter_number BETWEEN 32 AND 67;
-- All 67 chapters now properly assigned to Part 1 (57) or Part 2 (58)
```

**Code Fix Ensures:**
- Regenerating chapters no longer deletes/recreates sections
- Existing section IDs preserved
- No orphaned chapter references
- Data integrity maintained across regenerations

### Chapter 0 Display Fix (Bug Fixed 2025-11-28)

**Problem:** Books with two-level structure had Chapter 0 (PREFACE/INTRODUCTION) that wasn't displayed in UI.

**Root Cause:** `get_book_structure()` and `get_book_structure_metadata()` only returned chapters with matching `section_id`, excluding chapters with `section_id = NULL`.

**Example:**
- "The Adventures of Ferdinand Count Fathom" has Chapter 0 titled "INTRODUCTION"
- Chapter 0 has `section_id = NULL` (not belonging to Part 1 or Part 2)
- Original code query: `WHERE section_id = ?` → excludes NULL values
- Result: Chapter 0 invisible in UI

**Fix - Added Helper Functions:**

**Location:** `backend/models.py:413-469`

```python
def get_chapters_without_section(self, book_id: int) -> List[Dict]:
    """Get chapters that don't belong to any section (preface/introduction chapters)"""
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, book_id, chapter_number, chapter_title, summary, word_count,
               created_at, chapter_text, section_id
        FROM chapters
        WHERE book_id = ? AND section_id IS NULL
        ORDER BY chapter_number
    ''', (book_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chapters_metadata_without_section(self, book_id: int) -> List[Dict]:
    """Get chapter metadata only for chapters without section (no summary or full text)"""
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, book_id, chapter_number, chapter_title, word_count, section_id
        FROM chapters
        WHERE book_id = ? AND section_id IS NULL
        ORDER BY chapter_number
    ''', (book_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

**Fix - Modified Structure Retrieval:**

**Location:** `backend/models.py:515-579`

```python
def get_book_structure_metadata(self, book_id: int) -> Dict:
    sections = self.get_book_sections(book_id)

    if sections:
        result = {
            'has_sections': True,
            'sections': []
        }

        # First, add any chapters without section_id (preface/introduction)
        preface_chapters = self.get_chapters_metadata_without_section(book_id)
        if preface_chapters:
            result['sections'].append({
                'id': None,
                'type': 'PREFACE',
                'number': 0,
                'title': preface_chapters[0].get('chapter_title', 'Preface'),
                'chapters': preface_chapters
            })

        # Then add regular sections
        for section in sections:
            chapters = self.get_chapters_metadata_by_section(section['id'])
            result['sections'].append({
                'id': section['id'],
                'type': section['section_type'],
                'number': section['section_number'],
                'title': section['section_title'],
                'chapters': chapters
            })

        return result
```

**Result:**
- Chapter 0 now appears as first section with type "PREFACE"
- Section structure preserves original ordering (Preface → Part 1 → Part 2)
- UI displays complete book structure
- Same fix applied to both `get_book_structure()` and `get_book_structure_metadata()`

### Frontend Rendering

**API Response Structure (Updated with PREFACE section):**
```json
{
  "success": true,
  "book": {...},
  "has_sections": true,
  "sections": [
    {
      "id": null,
      "type": "PREFACE",
      "number": 0,
      "title": "INTRODUCTION",
      "chapters": [
        {
          "id": 123,
          "chapter_number": 0,
          "chapter_title": "INTRODUCTION",
          "section_id": null,
          ...
        }
      ]
    },
    {
      "id": 57,
      "type": "PART",
      "number": 1,
      "title": "",
      "chapters": [...]
    },
    {
      "id": 58,
      "type": "PART",
      "number": 2,
      "title": "",
      "chapters": [...]
    }
  ]
}
```

**UI Rendering Logic (`frontend/static/js/app.js::loadChapters()`):**

```javascript
if (data.has_sections && data.sections.length > 1) {
    // Render hierarchical structure
    data.sections.forEach(section => {
        // Create section header
        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'section-header';
        sectionHeader.innerHTML = `<h4>${section.type} ${section.number}: ${section.title}</h4>`;

        // Render indented chapters
        section.chapters.forEach(chapter => {
            const box = document.createElement('div');
            box.className = 'chapter-box indented';  // 20px left margin
            ...
        });
    });
} else {
    // Render flat structure (traditional)
    chapters.forEach(chapter => {
        const box = document.createElement('div');
        box.className = 'chapter-box';  // No indentation
        ...
    });
}
```

### CSS Styling

```css
/* Section headers */
.section-header {
    margin-top: 24px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border-color);
}

.section-header h4 {
    font-size: 1.1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Indented chapters under sections */
.chapter-box.indented {
    margin-left: 20px;
}
```

### Document Body Scanning (Added 2025-11-27)

**Problem:** Books like Anna Karenina have TOCs that only list section names without chapter details.

**Solution:** Implemented `extract_two_level_structure_from_body()` as a fallback method.

**How It Works:**
1. Scans entire document for PART/BOOK/ACT markers
2. Detects chapter markers following each section
3. Builds same structure as TOC-based detection
4. Validates results (min 2 sections, min 2 chapters/section, min 10 total)

**Pattern Matching:**
```python
# Section markers (must be on their own line)
section_pattern = r'^\s*(PART|BOOK|ACT)\s+(ONE|TWO|...|[0-9]+|[IVXLCDM]+)\.?\s*$'

# Chapter markers (on own line or with short title)
chapter_pattern = r'^\s*(?:CHAPTER|Chapter)\s+([IVXLCDM]+|[0-9]+)\.?\s*(.{0,60})$'
```

**Fallback Integration:**
```python
# Try TOC-based detection first
toc_structure = self.extract_two_level_toc(text)

# If TOC fails or incomplete, try body scanning
if not toc_structure:
    print("🔍 Attempting document body scan...")
    toc_structure = self.extract_two_level_structure_from_body(text)
```

**Performance:**
- Body scanning: ~100-200ms overhead
- Only runs when TOC detection fails
- Minimal impact on successfully detected books

**Supported Books:**
- ✅ Anna Karenina: 8 PARTS with 239 chapters (now works!)
- ✅ Other books with minimal TOCs automatically supported

### Limitations & Edge Cases

**Current Limitations:**
1. ~~TOC-Dependent: Requires TOC with chapter listings~~ **FIXED** (body scanning fallback)
2. ~~Anna Karenina Issue~~ **FIXED** (body scanning detects full structure)
3. **No TOC Support:** Books without any TOC (e.g., Crime and Punishment pg2554) still not supported

**Handled Edge Cases:**
- Multi-line section titles (Treasure Island)
- Scene vs. Chapter terminology (Romeo and Juliet: "Scene I. Title")
- Epilogues and prologues (War and Peace: detected 13 of 15 books)
- Various numeral formats (Roman, Arabic, spelled-out: "ONE", "I", "1")
- Duplicate section detection (exits TOC when content starts)
- **Minimal TOCs (Anna Karenina):** Body scanning fallback detects structure
- **Section title extraction:** Checks next line if title not on same line as marker

### Test Coverage

**Unit Tests:** `tests/test_two_level_toc.py`

**Test Results (5/5 PASSING - 100% SUCCESS RATE):**
1. ✅ Treasure Island: 6 parts, 34 chapters (TOC detection)
2. ✅ War and Peace: 13 books, 298 chapters (TOC detection)
3. ✅ Anna Karenina: **8 parts, 239 chapters** (body scanning fallback)
4. ✅ Romeo and Juliet: 5 acts, 24 scenes (TOC detection)
5. ✅ Principles of Political Economy: 5 books, 50+ chapters (TOC detection)
6. ✅ White Fang: 5 parts, 26 chapters (TOC detection)

### Integration Points

**Backend Methods:**
- `Database.add_book_section()` - Insert section record
- `Database.get_book_sections()` - Retrieve sections for book
- `Database.get_chapters_by_section()` - Get chapters in section
- `Database.get_book_structure()` - Full hierarchical structure
- `Database.add_chapter()` - Updated to accept `section_id`

**API Endpoints:**
- `GET /api/books/<id>/chapters` - Returns hierarchical structure
  - `has_sections`: boolean flag
  - `sections`: array of section objects with nested chapters

**Generation Script Integration:**
- `process_book()` calls `extract_two_level_toc()` before chapter detection
- If TOC detection fails, calls `extract_two_level_structure_from_body()` as fallback
- Saves sections to database
- Creates `chapter_to_section_id` mapping
- Passes `section_id` when saving chapters

### Performance Considerations

- TOC parsing adds <100ms to book processing
- Body scanning adds 100-200ms (only when TOC fails)
- Database schema change is backward compatible (section_id nullable)
- Frontend conditional rendering has negligible performance impact
- No impact on books without hierarchical structure
- Automatic fallback ensures all supported books work without manual intervention

---

## Gemini Image Generation System

**Location:** `scripts/generate_gemini_illustrations.py` (1500+ lines)

The Gemini Image Generation System provides automated creation of book covers and chapter illustrations using Google's Gemini image generation models. This enhances the visual presentation of classic literature with AI-generated artwork.

### Overview

The system generates two types of images with support for both synchronous and asynchronous batch processing:
1. **Book Covers**: Professional cover art with title and author text (async by default, sync optional)
2. **Chapter Illustrations**: Visual storytelling for individual chapters with character and style consistency (async by default, sync optional)

**Supported Models:**
- `gemini-3-pro-image-preview`: High quality, 2K resolution (2048×3072 @ 2:3 aspect ratio)
- `gemini-2.5-flash-image`: Faster generation, lower cost, auto resolution

**Processing Modes (Updated 2025-12-13):**
- **Async Mode (DEFAULT)**: Batch API processing with 50% cost savings, completion in 1-4 hours
  - Single covers: Submitted as 1-item batch
  - Chapters: Ch1 generated sync (reference), Ch2+ as batch
  - No flag required (automatic)
- **Sync Mode (opt-in with `--sync-mode`)**: Real-time generation with immediate results, 2x cost
  - Live progress feedback
  - Immediate results
  - Useful for testing/debugging

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GeminiImageGenerator                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SYNCHRONOUS API METHODS:                                        │
│  ────────────────────────────────────────────────────────────   │
│  generate_cover_image()                                          │
│  ├── Fetches medium summary for context                         │
│  ├── Constructs professional cover prompt                        │
│  ├── Calls Gemini Image API (real-time)                         │
│  └── Returns base64 image data                                  │
│                                                                  │
│  generate_chapter_illustration()                                 │
│  ├── Fetches book summary + chapter summary                     │
│  ├── Loads previous/reference chapter illustration              │
│  ├── Constructs visual storytelling prompt                      │
│  ├── Passes reference image for character consistency           │
│  ├── Calls Gemini Image API (real-time)                         │
│  └── Returns base64 image data                                  │
│                                                                  │
│  BATCH API METHODS:                                              │
│  ────────────────────────────────────────────────────────────   │
│  create_batch_job(batch_requests)                                │
│  ├── Creates JSONL file with all chapter requests               │
│  ├── Uploads file to Gemini API                                 │
│  ├── Submits batch job                                          │
│  └── Returns job_name for tracking                              │
│                                                                  │
│  poll_batch_job(job_name)                                        │
│  ├── Polls Gemini API for job status                            │
│  ├── Shows progress updates every 30s                           │
│  └── Returns completed batch_job object                         │
│                                                                  │
│  retrieve_batch_results(batch_job)                               │
│  ├── Downloads results JSONL file (contains ALL images)         │
│  ├── Parses each line (one per chapter)                         │
│  ├── Decodes base64 image data for each chapter                 │
│  └── Returns dict: {"chapter-11": (image_bytes, None), ...}     │
│                                                                  │
│  _wait_for_rate_limit()                                          │
│  └── Enforces 30s spacing (sync mode only)                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
            │
            ├── HELPER FUNCTIONS
            │   ─────────────────────────────────────────────────
            │   build_chapter_illustration_prompt()
            │   ├── Shared by both sync and batch modes
            │   ├── Takes: book info, chapter, previous chapter
            │   └── Returns: Complete formatted prompt string
            │
            │   filter_eligible_chapters()
            │   ├── Shared chapter filtering logic
            │   ├── Removes: <200 words, preface chapters
            │   └── Applies chapter range filtering
            │
            ├── WORKFLOW FUNCTIONS
            │   ─────────────────────────────────────────────────
            │   generate_chapter_illustrations_for_book()  [SYNC]
            │   ├── Sequential chapter generation
            │   ├── Uses previous chapter as reference
            │   └── Live progress updates
            │
            │   generate_chapter_illustrations_batch()  [BATCH]
            │   ├── Generates Chapter 1 synchronously
            │   ├── Submits chapters 2-N as batch job
            │   ├── Polls for completion (hours later)
            │   ├── Downloads all results in one JSONL file
            │   └── Saves all chapter images to disk
            │
            │   resume_batch_job(state_file)  [RESUME]
            │   ├── Loads saved job metadata from disk
            │   ├── Polls Gemini API for current status
            │   ├── Downloads results when complete
            │   └── Saves all images and updates database
            │
            ├── STATE PERSISTENCE
            │   ─────────────────────────────────────────────────
            │   save_batch_job_state()
            │   └── Saves job to data/batch_jobs/*.json
            │
            │   load_batch_job_state()
            │   └── Loads job metadata from disk
            │
            │   update_batch_job_state()
            │   └── Updates job status (running/completed/failed)
            │
            │   list_pending_batch_jobs()
            │   └── Lists all active/pending jobs
            │
            ├── IMAGE PROCESSING
            │   ─────────────────────────────────────────────────
            │   save_image()
            │   ├── Decodes base64 image
            │   ├── Optimizes with PIL
            │   └── Saves to disk
            │
            └── DATABASE UPDATES
                ├── books.cover_image_url
                ├── books.cover_source = 'gemini-generated'
                └── chapters.illustration_url
```

### Key Classes and Functions

#### GeminiImageGenerator Class (lines 81-303)

**Initialization:**
```python
def __init__(self, api_key: str, model: str = DEFAULT_IMAGE_MODEL):
    self.client = genai.Client(api_key=api_key)
    self.model = model  # Default: "gemini-3-pro-image-preview"
    self.last_request_time = 0
```

**Methods:**

1. **`generate_cover_image(book_title, author, medium_summary)`** (lines 103-179)
   - **Purpose:** Generate professional book cover
   - **Inputs:**
     - `book_title`: String, book title
     - `author`: String, author name
     - `medium_summary`: String, context for visual themes
   - **Prompt Structure:**
     ```
     Generate a professional book cover for:
     Title: {book_title}
     Author: {author}

     Context: {medium_summary}

     Requirements:
     - Title at top, author at bottom
     - Visual storytelling (not literal title interpretation)
     - Edge-to-edge artwork, no borders/frames
     - 2:3 aspect ratio (portrait)
     - Professional, publishable quality
     ```
   - **Returns:** Base64-encoded image data
   - **Rate Limiting:** Waits 30s between requests

2. **`generate_chapter_illustration(chapter_num, chapter_title, chapter_summary, book_summary, previous_chapter_summary, reference_image)`** (lines 181-303)
   - **Purpose:** Generate chapter-specific illustration
   - **Inputs:**
     - `chapter_num`: Integer, chapter number
     - `chapter_title`: String, chapter title
     - `chapter_summary`: String, chapter content
     - `book_summary`: String, overall book context
     - `previous_chapter_summary`: String, narrative continuity
     - `reference_image`: Bytes, previous chapter image for consistency
   - **Prompt Structure:**
     ```
     Create visual storytelling illustration for:
     Chapter {chapter_num}: {chapter_title}

     Book Context: {book_summary}

     Previous Chapter: {previous_chapter_summary}

     This Chapter: {chapter_summary}

     Requirements:
     - Multi-panel layout option for key moments
     - Match characters/style from reference image
     - Visual narrative, no text/dialog/narration
     - Consistent art style with previous chapters
     ```
   - **Character Consistency:** Uses `reference_image` parameter to maintain consistent character appearance
   - **Returns:** Base64-encoded image data

3. **`_wait_for_rate_limit()`** (lines 95-101)
   - Enforces 30-second spacing between API calls
   - Prevents quota exhaustion
   - Conservative limit (2 requests/minute)

#### Main Processing Functions

1. **`generate_book_cover(db, generator, book_id, force_regenerate)`** (lines 375-410)
   - Checks if cover already exists
   - Skips if `cover_source = 'gemini-generated'` and not forced
   - Fetches medium summary for context
   - Generates cover image
   - Saves to `frontend/static/covers/{book_id}.png`
   - Updates database: `cover_image_url`, `cover_source`
   - Saves prompt to `{book_id}.txt`

2. **`generate_chapter_illustrations_for_book(db, generator, book_id, chapter_range, force_regenerate)`** (lines 438-586)
   - Fetches all chapters for book
   - Filters out:
     - Short chapters (<200 words)
     - Preface chapters
   - Optional chapter range filtering
   - For each chapter:
     - Loads previous chapter illustration as reference
     - Generates illustration with character consistency
     - Saves to `frontend/static/illustrations/{book_id}/{chapter_num}.png`
     - Updates database: `chapters.illustration_url`
     - Saves prompt to `{chapter_num}.txt`

3. **`find_books_without_covers(db)`** (lines 588-602)
   - Identifies books missing covers or with non-Gemini covers
   - Used for batch processing

4. **`find_books_without_chapter_illustrations(db)`** (lines 604-636)
   - Identifies books with comprehensive summaries but no illustrations
   - Filters out short chapters
   - Returns list of book IDs needing illustrations

### Image Processing

**`save_image(image_data, output_path)`** (lines 331-355)
```python
# Decode base64 image
img_bytes = base64.b64decode(image_data)

# Open with PIL
img = Image.open(io.BytesIO(img_bytes))

# Optimize and save
if output_path.suffix.lower() == '.jpg' or output_path.suffix.lower() == '.jpeg':
    img.save(output_path, 'JPEG', quality=85, optimize=True)
else:
    img.save(output_path, 'PNG', optimize=True)
```

**Features:**
- Base64 decoding
- PIL-based optimization
- Quality 85 for JPEG
- Optimize flag for PNG
- Automatic format detection

**`save_prompt(prompt, output_path)`** (lines 357-373)
- Saves generation prompt to `.txt` file
- Useful for debugging and reference
- Stored alongside images

### Batch API Mode (Added 2025-12-02)

**Purpose:** Asynchronous bulk processing for large books with 50% cost savings

**Architecture:**

1. **Submit Phase:**
   - Generate Chapter 1 synchronously (for reference)
   - Build JSONL file with chapters 2-N requests
   - Each request includes Chapter 1 as reference image
   - Upload JSONL to Gemini API
   - Submit batch job, receive `job_name`
   - Save job state to `data/batch_jobs/book_{id}_{timestamp}.json`

2. **Processing Phase** (on Google's servers):
   - Gemini processes all chapters in parallel
   - Uses Chapter 1 reference for character consistency
   - Can take 1-4 hours for typical books
   - Maximum SLA: 24 hours

3. **Retrieval Phase:**
   - Poll job status every 30s (configurable)
   - When complete, download single JSONL results file
   - Parse JSONL: each line contains one chapter's base64 image
   - Decode all images, save to disk
   - Update database with illustration URLs

**JSONL Request Format:**
```json
{
  "key": "chapter-11",
  "request": {
    "contents": [{
      "parts": [
        {"inline_data": {"mime_type": "image/png", "data": "base64_chapter1_ref..."}},
        {"text": "Chapter 11 illustration prompt..."}
      ],
      "role": "user"
    }],
    "generation_config": {
      "temperature": 1.0,
      "response_modalities": ["IMAGE"],
      "image_config": {
        "aspect_ratio": "2:3",
        "image_size": "2K"
      }
    }
  }
}
```

**JSONL Response Format:**
```json
{
  "key": "chapter-11",
  "response": {
    "candidates": [{
      "content": {
        "parts": [{
          "inlineData": {
            "mimeType": "image/png",
            "data": "base64_encoded_png_image..."
          }
        }]
      }
    }]
  }
}
```

**Resume Capability:**
- Script can be interrupted safely
- Job state saved to `data/batch_jobs/*.json`
- Resume with: `--resume data/batch_jobs/book_47_1234567890.json`
- Polls job status, downloads results when ready
- Idempotent: safe to resume multiple times

**CLI Commands:**
```bash
# Submit batch job
python scripts/generate_gemini_illustrations.py --book-id 47 --batch-mode --chapters-only

# List pending jobs
python scripts/generate_gemini_illustrations.py --list-jobs

# Resume interrupted job
python scripts/generate_gemini_illustrations.py --resume data/batch_jobs/book_47_1234567890.json
```

**Cost Comparison:**
- Sync mode: Full price × N chapters
- Batch mode: 50% price × N chapters
- Example: 100 chapters = 50% total cost savings

**Performance:**
- 10-50 chapters: 30 min - 2 hours
- 50-100 chapters: 1-4 hours
- 100-200 chapters: 2-8 hours
- Maximum: 24 hours (SLA guarantee)

### File Organization

```
frontend/static/
├── covers/
│   ├── {book_id}.png         # Book cover image
│   └── {book_id}.txt         # Cover generation prompt

data/batch_jobs/                # Batch job state persistence
└── book_{id}_{timestamp}.json  # Job metadata for resume
└── illustrations/
    └── {book_id}/
        ├── {chapter_num}.png # Chapter illustration
        └── {chapter_num}.txt # Chapter prompt

data/illustration_original/   # Original high-res (gitignored)
```

### Database Integration

**Updates to `books` table:**
```sql
UPDATE books
SET cover_image_url = '/static/covers/{book_id}.png',
    cover_source = 'gemini-generated'
WHERE id = {book_id};
```

**Updates to `chapters` table:**
```sql
UPDATE chapters
SET illustration_url = '/static/illustrations/{book_id}/{chapter_num}.png'
WHERE book_id = {book_id} AND chapter_number = {chapter_num};
```

### Command-Line Interface

**Script:** `scripts/generate_gemini_illustrations.py`

**Usage Examples:**

```bash
# Generate cover only for specific book
python scripts/generate_gemini_illustrations.py --book-id 47 --cover-only

# Generate all chapter illustrations
python scripts/generate_gemini_illustrations.py --book-id 47 --chapters-only

# Generate specific chapter range
python scripts/generate_gemini_illustrations.py --book-id 47 --chapter-range 1-10

# Generate both cover and all chapters
python scripts/generate_gemini_illustrations.py --book-id 47

# Use faster flash model (lower cost)
python scripts/generate_gemini_illustrations.py --book-id 47 --model gemini-2.5-flash-image

# Batch process all books missing illustrations
python scripts/generate_gemini_illustrations.py --batch-all

# Dry run (preview without generating)
python scripts/generate_gemini_illustrations.py --book-id 47 --dry-run

# Force regenerate existing illustrations
python scripts/generate_gemini_illustrations.py --book-id 47 --force
```

**Arguments:**
- `--book-id`: Target book ID
- `--cover-only`: Generate cover only
- `--chapters-only`: Generate chapter illustrations only
- `--chapter-range START-END`: Generate specific chapters
- `--batch-all`: Process all books
- `--model`: Choose model (`gemini-3-pro-image-preview` or `gemini-2.5-flash-image`)
- `--dry-run`: Preview without generating
- `--force`: Force regeneration of existing illustrations

### Character Consistency Implementation

**Challenge:** Maintaining consistent character appearance across multiple chapter illustrations

**Solution:** Reference image approach

```python
# Load previous chapter illustration
prev_img_path = illustrations_dir / f"{chapter_num - 1}.png"
reference_image = None

if prev_img_path.exists():
    with open(prev_img_path, 'rb') as f:
        reference_image = f.read()

# Pass to API
content_parts = []
if reference_image:
    content_parts.append({
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(reference_image).decode('utf-8')
        }
    })
content_parts.append(prompt)

# Generate with reference
response = client.models.generate_content(
    model=model,
    contents=content_parts,
    config=generation_config
)
```

**Benefits:**
1. Characters maintain consistent appearance
2. Art style continuity across chapters
3. Improved narrative flow
4. Better visual coherence

### Rate Limiting Strategy

**Configuration:**
```python
MAX_REQUESTS_PER_MINUTE = 2  # Conservative for image API
SECONDS_BETWEEN_REQUESTS = 30
```

**Implementation:**
```python
def _wait_for_rate_limit(self):
    current_time = time.time()
    time_since_last_request = current_time - self.last_request_time

    if time_since_last_request < SECONDS_BETWEEN_REQUESTS:
        wait_time = SECONDS_BETWEEN_REQUESTS - time_since_last_request
        print(f"Rate limiting: waiting {wait_time:.1f}s...")
        time.sleep(wait_time)

    self.last_request_time = time.time()
```

**Rationale:**
- Image generation is more resource-intensive than text
- Conservative limits prevent quota exhaustion
- Suitable for overnight batch processing
- 30s spacing = 2 requests/minute = 120 requests/hour

**Batch Processing Time Estimates:**
- 1 cover + 50 chapters = 51 requests × 30s = ~25 minutes
- 10 books (average) = ~4 hours
- Overnight batch: Can process 15-20 books

### Prompt Engineering

**Cover Generation Prompt Design:**
```python
prompt = f"""
Generate a professional, eye-catching book cover image for a classic book.

Title: {book_title}
Author: {author}

Context (for thematic understanding):
{medium_summary}

Requirements:
1. Include the title "{book_title}" prominently at the top
2. Include the author name "{author}" at the bottom
3. Focus on accurate visual storytelling that captures the book's essence
4. DO NOT interpret the title literally - tell the story visually
5. Create edge-to-edge artwork with no borders or frames
6. Use a color palette and mood that matches the book's content
7. Make it professional and publishable quality
8. Aspect ratio 2:3 (portrait/vertical orientation for book covers)
"""
```

**Key Elements:**
- Clear title/author placement
- Context from medium summary
- Visual storytelling emphasis
- No literal interpretation
- Professional quality requirements
- Specific aspect ratio

**Chapter Illustration Prompt Design:**
```python
prompt = f"""
Create a visual storytelling illustration for this chapter from a classic book.

Chapter {chapter_num}: {chapter_title}

Overall Book Context:
{book_summary}

Previous Chapter Context:
{previous_chapter_summary}

This Chapter's Content:
{chapter_summary}

Requirements:
1. Create accurate visual storytelling that captures key plot points
2. Consider using a multi-panel layout if there are multiple important moments
3. If there are characters, keep them visually consistent with the reference image
4. Maintain the same artistic style as previous chapters
5. Focus on visual narrative - no text, dialog, or narration
6. Use rich, detailed artwork appropriate for classic literature
"""
```

**Key Elements:**
- Multi-context (book, previous chapter, current chapter)
- Character consistency instructions
- Style continuity guidance
- Multi-panel layout option
- Pure visual storytelling (no text)
- Rich detail for quality

### Performance Characteristics

**Generation Time:**
- Cover: ~15-30 seconds per image
- Chapter illustration: ~15-30 seconds per image
- Rate limiting adds 30s between requests
- Actual throughput: ~1 image per minute

**Image Quality:**
- Pro model: 2K resolution (2048×3072)
- Flash model: Auto resolution (typically 1024×1536)
- File sizes: 200-800 KB (PNG, optimized)
- Format: PNG for illustrations, JPEG option available

**API Costs:** (approximate, varies by model)
- Pro model: Higher cost per image
- Flash model: ~75% cheaper than Pro
- Batch processing overnight recommended for cost efficiency

### Error Handling

**Common Issues:**

1. **API Quota Exceeded:**
   - Script pauses with informative message
   - Resume from last successful chapter
   - Automatic retry not implemented (manual restart)

2. **Image Decode Failure:**
   - Logs error with chapter number
   - Skips to next chapter
   - Continues processing

3. **Database Connection:**
   - Fails fast with clear error message
   - No partial state (transaction-based)

4. **Missing Summaries:**
   - Skips books/chapters without summaries
   - Logs warning
   - Continues with other content

### Testing and Validation

**Test Case: Peter Pan (Book ID 47)**
```bash
python scripts/generate_gemini_illustrations.py --book-id 47 --chapter-range 1-10
```

**Results:**
- Generated 1 cover + 10 chapter illustrations
- Total time: ~10 minutes
- All images saved successfully
- Database updated correctly
- Character consistency maintained across chapters
- Art style coherent throughout

**Validation Checklist:**
- [ ] Cover image includes title and author
- [ ] Cover aspect ratio is 2:3
- [ ] Chapter illustrations are visually coherent
- [ ] Characters maintain consistent appearance
- [ ] Art style is consistent across chapters
- [ ] File sizes are reasonable (200-800 KB)
- [ ] Database URLs are correct
- [ ] Prompts saved alongside images

### Integration with Frontend

**Book Detail Page:**
- Displays book cover from `books.cover_image_url`
- Shows chapter illustrations in chapter list
- Lightbox overlay for full-size viewing

**Chapter Lightbox:**
- Shows chapter illustration at top
- Displays chapter title and summary
- Navigation to next/previous chapters
- Close button returns to chapter list

### Future Enhancements

**Potential Improvements:**

1. **Quality Validation:**
   - Automatic quality scoring
   - Flagging low-quality generations for review
   - Automatic regeneration below threshold

2. **Style Customization:**
   - Multiple art styles (oil painting, watercolor, etc.)
   - User-selectable styles
   - Style transfer from reference images

3. **Batch Optimization:**
   - Parallel processing with multiple API keys
   - Smarter rate limiting based on quota
   - Resume from interruption

4. **Cost Optimization:**
   - Automatic model selection (Pro for covers, Flash for chapters)
   - Caching of common elements
   - Lower resolution for previews

5. **Content Safety:**
   - Automatic filtering of inappropriate content
   - Age-appropriate variations
   - Historical accuracy validation

### Deployment Considerations

**Production Deployment:**

1. **Static Files:**
   ```bash
   # Copy generated images to production server
   rsync -av frontend/static/covers/ user@server:/var/www/summra/frontend/static/covers/
   rsync -av frontend/static/illustrations/ user@server:/var/www/summra/frontend/static/illustrations/
   ```

2. **Database:**
   - Database updates included in main database deployment
   - URLs reference `/static/` path (no change needed)

3. **Monitoring:**
   - Track API usage and costs
   - Monitor image quality
   - Alert on generation failures

**Backup Strategy:**
- Original high-resolution images stored in `data/illustration_originals/`
- Gitignored to save space
- Manual backup recommended for originals
- Optimized versions in `frontend/static/` (tracked in git)

---

## Image Optimization System

**Location:** `scripts/reduce_illustration_resolution.py`

The Image Optimization System provides automated WebP/JPG conversion and size reduction for book covers and chapter illustrations, dramatically reducing page load times while maintaining visual quality.

### Overview

The system implements a two-stage workflow:
1. **Generation Stage**: High-resolution originals (2K, ~7MB each) saved to `data/` directory
2. **Optimization Stage**: Creates dual-format web-optimized versions (WebP + JPG) in `frontend/static/`

**Performance Metrics:**
- Average file size reduction: **94.5%** per image (7MB → 0.4MB)
- WebP format: ~30% smaller than JPG at equivalent quality
- Total storage savings: **89%** (331MB → 36.1MB for 48 illustrations)

### Directory Structure

```
project_root/
├── data/
│   ├── cover_originals/          # Original book cover PNGs (gitignored)
│   │   ├── 1.png                 # ~7MB per cover
│   │   ├── 47.png
│   │   └── ...
│   └── illustration_originals/   # Original chapter illustrations (gitignored)
│       ├── 1/                    # Book ID
│       │   ├── 1.png             # Chapter number
│       │   ├── 2.png             # ~7MB per illustration
│       │   └── ...
│       ├── 47/
│       └── ...
│
└── frontend/static/
    ├── covers/                   # Optimized book covers (tracked in git)
    │   ├── 1.webp                # ~0.15MB (WebP, primary format)
    │   ├── 1.jpg                 # ~0.25MB (JPG, fallback)
    │   ├── 47.webp
    │   └── 47.jpg
    └── illustrations/            # Optimized chapter illustrations (tracked in git)
        ├── 1/
        │   ├── 1.webp            # ~0.3MB (WebP)
        │   ├── 1.jpg             # ~0.4MB (JPG)
        │   └── ...
        └── 47/
            └── ...
```

### Workflow

#### Stage 1: Generation (generate_gemini_illustrations.py)

```python
# Saves to data/cover_originals/ or data/illustration_originals/
cover_path = project_root / "data" / "cover_originals" / f"{book_id}.png"
save_image(cover_data, cover_path)  # ~7MB PNG, 2048×3072

illustration_path = project_root / "data" / "illustration_originals" / str(book_id) / f"{chapter_num}.png"
save_image(image_data, illustration_path)  # ~7MB PNG, 2048×3072
```

**Key Changes from Original Design:**
- Previously saved directly to `frontend/static/` (deployment-ready location)
- Now saves to `data/` (source storage, not deployed)
- Database updates deferred until after optimization
- Script outputs reminder to run optimization

**Auto-Optimization Integration (Lines 782-836):**

The generation script automatically calls the optimization script after creating illustrations:

```python
def auto_optimize_illustrations(book_id: int, chapter_numbers: list = None, dry_run: bool = False) -> bool:
    """Automatically run optimization script after generating illustrations"""

    # Build command with optional chapter numbers and update-db flag
    cmd = [sys.executable, str(optimize_script), "--book-id", str(book_id)]
    if chapter_numbers:
        chapters_arg = ",".join(str(num) for num in sorted(chapter_numbers))
        cmd.extend(["--chapters", chapters_arg])
    cmd.append("--update-db")  # Always update database when called from generation script

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0
```

**Integration Flow:**
1. Generation script creates high-res originals in `data/illustration_originals/`
2. `auto_optimize_illustrations()` called at end of generation
3. Subprocess runs optimization script with `--update-db` flag
4. Optimization creates WebP/JPG in `frontend/static/illustrations/`
5. Database updated with illustration URLs automatically
6. User sees optimized images in frontend immediately

#### Stage 2: Optimization (reduce_illustration_resolution.py)

```bash
# Manual usage - process book illustrations
python scripts/reduce_illustration_resolution.py --book-id 47

# Manual usage with database update
python scripts/reduce_illustration_resolution.py --book-id 47 --update-db

# Process specific chapters
python scripts/reduce_illustration_resolution.py --book-id 47 --chapters 1,2,3 --update-db

# Process book covers
python scripts/reduce_illustration_resolution.py --covers --book-id 47
python scripts/reduce_illustration_resolution.py --covers --all

# Automatic usage (called from generation script)
# auto_optimize_illustrations() always passes --update-db flag
```

**Optimization Process:**

1. **Load from source:** Reads PNG from `data/illustration_originals/{book_id}/{chapter_num}.png`

2. **Resize (if needed):**
   - Target width: 1024px for illustrations, 400px for covers
   - Maintains aspect ratio (typically 2:3)
   - Uses Lanczos resampling (high-quality downscaling)
   - Example: 2048×3072 → 1024×1526

3. **Convert formats:**
   ```python
   # WebP (primary format, best compression)
   img.save(webp_path, 'WEBP', quality=85, method=6)

   # JPG (fallback for older browsers)
   img.save(jpg_path, 'JPEG', quality=85, optimize=True)
   ```

4. **Output to frontend:**
   - Saves to `frontend/static/illustrations/{book_id}/{chapter_num}.{webp,jpg}`
   - Both formats created for browser compatibility
   - Original PNG remains in `data/` directory

5. **Update database (if --update-db flag enabled):**
   ```python
   # Fetch existing chapter data
   chapter = db.get_chapter(book_id, chapter_num)

   # Create URL pattern (frontend uses this to find .webp/.jpg)
   illustration_url = f"/static/illustrations/{book_id}/{chapter_num}.png"

   # Update chapter with illustration_url (preserves all other fields)
   db.add_chapter(
       book_id=book_id,
       chapter_number=chapter_num,
       chapter_title=chapter.get('chapter_title', ''),
       summary=chapter.get('summary', ''),
       chapter_text=chapter.get('chapter_text'),
       section_id=chapter.get('section_id'),
       illustration_url=illustration_url
   )
   ```
   - URL uses `.png` extension as base (JavaScript strips and adds .webp/.jpg)
   - Preserves all existing chapter data (title, summary, text, section)
   - Only runs if `--update-db` flag passed (automatic in generation workflow)
   - Gracefully handles missing chapters or database errors

### Frontend Integration

#### HTML Structure (index.html)

Uses `<picture>` element for automatic format selection:

```html
<!-- Chapter Illustration -->
<div class="chapter-illustration-container" id="chapter-illustration-container">
    <picture id="chapter-illustration-picture">
        <source id="chapter-illustration-webp" type="image/webp" />
        <source id="chapter-illustration-jpg" type="image/jpeg" />
        <img id="chapter-illustration" class="chapter-illustration" alt="..." />
    </picture>
</div>

<!-- Lightbox (full-screen view) -->
<div class="lightbox-overlay" id="lightbox-overlay">
    <picture id="lightbox-picture">
        <source id="lightbox-webp" type="image/webp" />
        <source id="lightbox-jpg" type="image/jpeg" />
        <img class="lightbox-image" id="lightbox-image" alt="" />
    </picture>
</div>
```

#### JavaScript Logic (app.js)

**displayChapterDetail() - Lines 1024-1095:**

```javascript
// Get illustration URL from database (may be .png)
let illustrationUrl = chapter.illustration_url; // "/static/illustrations/47/1.png"

// Generate base URL by stripping extension
const baseUrl = illustrationUrl.replace(/\.(png|jpg|jpeg)$/i, '');
// Result: "/static/illustrations/47/1"

// Generate optimized URLs
const webpUrl = `${baseUrl}.webp`; // "/static/illustrations/47/1.webp"
const jpgUrl = `${baseUrl}.jpg`;   // "/static/illustrations/47/1.jpg"

// Set picture element sources
illustrationWebp.srcset = webpUrl;
illustrationJpg.srcset = jpgUrl;
illustrationImg.src = jpgUrl; // Fallback for very old browsers
```

**openLightbox() - Lines 2029-2043:**

```javascript
// Receives base URL (without extension)
const openLightbox = (imageSrc, imageAlt) => {
    const webpUrl = `${imageSrc}.webp`;
    const jpgUrl = `${imageSrc}.jpg`;

    lightboxWebp.srcset = webpUrl;
    lightboxJpg.srcset = jpgUrl;
    lightboxImage.src = jpgUrl;
    // Browser automatically selects best format
};
```

### Browser Behavior

The `<picture>` element provides native browser support for format selection:

1. **Modern Browsers** (Chrome 23+, Firefox 65+, Edge 18+, Safari 14+):
   - Automatically select WebP source
   - Load smaller, faster WebP files (~0.3MB)

2. **Older Browsers** (IE11, Safari 13-):
   - Fall back to JPG source
   - Load slightly larger JPG files (~0.4MB)

3. **Very Old Browsers** (IE9-10):
   - Ignore `<picture>` element
   - Load `<img>` src directly (JPG fallback)

**No JavaScript required** for format selection - handled by browser HTML parser.

### Code Organization

**`optimize_image()` function - Lines 42-108:**

```python
def optimize_image(input_path: Path, output_base_path: Path,
                   max_width: int = 1024, create_webp: bool = True) -> bool:
    """
    Args:
        input_path: Source PNG (e.g., data/illustration_originals/47/1.png)
        output_base_path: Output without extension (e.g., frontend/static/illustrations/47/1)
        max_width: Maximum width in pixels (default 1024 for illustrations)
        create_webp: Whether to create WebP version (default True)

    Process:
        1. Load image with PIL
        2. Convert RGBA → RGB if needed (WebP compatibility)
        3. Resize if width > max_width (maintains aspect ratio)
        4. Save WebP at quality 85, method 6 (best compression)
        5. Save JPG at quality 85, optimize=True

    Returns:
        True if both formats created successfully
    """
```

**`process_book_illustrations()` - Lines 112-219:**

```python
def process_book_illustrations(book_id: int, max_width: int = 1024,
                               dry_run: bool = False, chapter_numbers: list = None,
                               update_db: bool = False) -> bool:
    """
    Process all illustrations for a book.

    Args:
        book_id: Book ID to process
        max_width: Maximum width (default 1024px)
        dry_run: Preview without writing files
        chapter_numbers: Optional list of chapter numbers to process (e.g., [1, 2, 3])
        update_db: If True, update database with illustration URLs after optimization

    Process:
        1. Read all PNGs from data/illustration_originals/{book_id}/
        2. Filter by chapter_numbers if specified
        3. For each PNG:
           - Call optimize_image()
           - Create .webp and .jpg in frontend/static/illustrations/{book_id}/
           - If update_db: Update chapters table with illustration_url
        4. Report file size reductions

    Database Update Logic (Lines 186-208):
        if db:  # Only if update_db=True and not dry_run
            try:
                # Get existing chapter data
                chapter = db.get_chapter(book_id, int(chapter_num))
                if chapter:
                    # Create URL pattern
                    illustration_url = f"/static/illustrations/{book_id}/{chapter_num}.png"

                    # Update chapter with new illustration_url
                    # Preserves all existing fields (title, summary, text, section)
                    db.add_chapter(
                        book_id=book_id,
                        chapter_number=int(chapter_num),
                        chapter_title=chapter.get('chapter_title', ''),
                        summary=chapter.get('summary', ''),
                        chapter_text=chapter.get('chapter_text'),
                        section_id=chapter.get('section_id'),
                        illustration_url=illustration_url
                    )
                    print(f"  📝 Updated database: {illustration_url}")

    Returns:
        True if all images processed successfully
    """
```

**`process_book_covers()` - Lines 229-322:**

Similar to `process_book_illustrations()` but:
- Reads from `data/cover_originals/`
- Outputs to `frontend/static/covers/`
- Default max_width: 400px (covers displayed smaller than illustrations)

### Performance Impact

**Before Optimization:**
- Chapter page load: ~7MB per illustration
- 10-chapter book: 70MB total image data
- Slow loading on mobile/slow connections
- Higher bandwidth costs

**After Optimization:**
- Chapter page load: ~0.3MB per illustration (WebP) or ~0.4MB (JPG)
- 10-chapter book: 3-4MB total image data
- 95% reduction in data transfer
- Faster page loads, lower bandwidth costs

**Network Transfer Comparison:**

| Scenario | Before | After (WebP) | After (JPG) | Savings |
|----------|--------|--------------|-------------|---------|
| Single chapter | 7 MB | 0.3 MB | 0.4 MB | 95% / 94% |
| 10 chapters | 70 MB | 3 MB | 4 MB | 96% / 94% |
| 48 chapters (Books 1,6,47) | 331 MB | 14.4 MB | 19.2 MB | 96% / 94% |

### Database Integration

**Current Schema:**
- `chapters.illustration_url` stores path like `/static/illustrations/47/1.png`
- Database not updated during generation (deferred until optimization)
- Frontend JavaScript strips `.png` extension to generate `.webp` and `.jpg` URLs
- No database migration needed - backward compatible

**Future Consideration:**
- Could store base URL without extension: `/static/illustrations/47/1`
- Would require database migration
- Current approach works without schema changes

### Git Strategy

**Tracked in Git:**
- `frontend/static/covers/*.{webp,jpg}` - Optimized covers (~0.2MB each)
- `frontend/static/illustrations/**/*.{webp,jpg}` - Optimized illustrations (~0.35MB each)

**Gitignored:**
- `data/cover_originals/*.png` - Original covers (~7MB each)
- `data/illustration_originals/**/*.png` - Original illustrations (~7MB each)

**Rationale:**
- Optimized files small enough for git (36MB total for 48 illustrations)
- Original files too large for git (331MB for same 48 illustrations)
- Originals can be regenerated with Gemini API if needed
- Local backups of `data/` directory recommended

### Error Handling

**Missing Source Files:**
```bash
❌ Source directory not found: /path/to/data/illustration_originals/999
```

**RGBA/PNG Conversion:**
```python
# Handles PNG transparency by converting to RGB with white background
if img.mode in ('RGBA', 'LA', 'P'):
    background = Image.new('RGB', img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[-1])
    img = background
```

**Partial Failures:**
- Script continues processing remaining images
- Reports success/failure counts
- Returns non-zero exit code if any failures

### Testing

**Manual Verification:**

```bash
# Dry run to preview operations
python scripts/reduce_illustration_resolution.py --book-id 47 --dry-run

# Process single book
python scripts/reduce_illustration_resolution.py --book-id 47

# Verify output
ls -lh frontend/static/illustrations/47/
# Should show .webp and .jpg files, no .png files
```

**Size Comparison:**
```bash
# Original size
du -sh data/illustration_originals/47
# Expected: ~79M

# Optimized size
du -sh frontend/static/illustrations/47
# Expected: ~9.5M (88% reduction)
```

### Integration with Gemini System

**Workflow Integration:**

1. **Generate Illustrations:**
   ```bash
   python scripts/generate_gemini_illustrations.py --book-id 47 --chapters-only
   # Saves originals to data/illustration_originals/47/*.png
   # Outputs: "ℹ️  Run reduce_illustration_resolution.py to create optimized versions"
   ```

2. **Optimize for Web:**
   ```bash
   python scripts/reduce_illustration_resolution.py --book-id 47
   # Creates frontend/static/illustrations/47/*.{webp,jpg}
   ```

3. **Deploy:**
   - Only `frontend/static/` directory deployed
   - Optimized images (<1MB each) transferred to production
   - Original files remain local in `data/` directory

### Future Enhancements

**Potential Improvements:**
1. **Automatic Optimization:** Integrate optimization into generation script
2. **AVIF Format:** Add AVIF support (even better compression than WebP)
3. **Responsive Images:** Generate multiple sizes (srcset with different widths)
4. **Lazy Loading:** Add native lazy loading attributes
5. **CDN Integration:** Upload optimized images to CDN automatically

**Current Design Philosophy:**
- Explicit two-stage workflow (generation → optimization)
- Source-of-truth originals preserved locally
- Optimized versions committed to git
- No database schema changes required
- Gradual adoption (works with existing PNG URLs)

---

## Book Metadata Enrichment

### Overview

**Added:** 2025-12-02

The Book Metadata Enrichment system uses AI to extract comprehensive metadata about books in a single API call, including summaries, relevance, author information, and related book recommendations. This reduces API costs and improves data consistency.

### Enhanced generate_combined_summaries()

**Location:** `scripts/generate_summaries.py:281-540`

**Previous Behavior (Before 2025-12-02):**
- Generated only two summaries: concise (500 words) and medium (2000-3000 words)
- Returned tuple: `(concise_summary, medium_summary)`
- Required separate API calls for additional metadata

**New Behavior (After 2025-12-02):**
- Generates summaries + metadata in single API call
- Returns dictionary with 7 fields:
  ```python
  {
      'about_text': str,           # 150-200 words
      'concise_summary': str,      # 500 words
      'medium_summary': str,       # 2000-3000 words
      'relevance_now': str,        # 100-150 words
      'author_country': str,       # Country name only
      'similar_books': list,       # 5 books with title + author
      'other_books_by_author': list  # Max 10 book titles
  }
  ```

### Extended Prompt Template

**Location:** `scripts/generate_summaries.py:294-330`

**Sections:**

1. **ABOUT THE BOOK** (150-200 words)
   - Short, engaging summary for book overview page
   - Concise but compelling
   - No spoilers

2. **CONCISE SUMMARY** (500 words)
   - Main theme, setting, central conflict
   - Fiction: No spoilers
   - Non-fiction: Key arguments and takeaways

3. **MEDIUM SUMMARY** (2000-3000 words)
   - All major plot points, themes, character developments
   - Chronological order
   - Author's writing style analysis
   - Spoilers acceptable
   - Non-fiction: All arguments, evidence, conclusions

4. **RELEVANCE NOW** (100-150 words)
   - Why book is relevant to modern audiences
   - Contemporary themes, timeless insights
   - Connection to current issues

5. **AUTHOR COUNTRY**
   - Country name only (no additional text)
   - Used for "books from same country" recommendations

6. **SIMILAR BOOKS**
   - Exactly 5 books in `TITLE|AUTHOR` format
   - One per line
   - AI-curated recommendations

7. **OTHER BOOKS BY AUTHOR**
   - Max 10 book titles
   - Just titles, one per line
   - Comprehensive list of author's notable works

### Parsing Logic

**Location:** `scripts/generate_summaries.py:434-532`

**Regex-Based Section Extraction:**

```python
# About the Book
about_match = re.search(r'### ABOUT THE BOOK.*?\n(.*?)(?=### CONCISE SUMMARY|###|$)',
                       result, re.DOTALL | re.IGNORECASE)

# Concise Summary
concise_match = re.search(r'### CONCISE SUMMARY.*?\n(.*?)(?=### MEDIUM SUMMARY|###|$)',
                         result, re.DOTALL | re.IGNORECASE)

# Similar Books (parse TITLE|AUTHOR format)
similar_match = re.search(r'### SIMILAR BOOKS.*?\n(.*?)(?=### OTHER BOOKS|###|$)',
                         result, re.DOTALL | re.IGNORECASE)
if similar_match:
    for line in similar_text.split('\n'):
        if '|' in line:
            title, author = line.split('|')
            similar_books.append({'title': title.strip(), 'author': author.strip()})
```

**Data Cleaning:**
- Remove template text (e.g., `[Generate a summary...]`)
- Strip whitespace
- Extract first line only for author country
- Remove prefixes like "Country:" or "The author is from"
- Limit lists to max size (5 similar books, 10 other books)

### Word Count Reporting

**Location:** `scripts/generate_summaries.py:520-527`

```python
about_words = len(about_text.split()) if about_text else 0
concise_words = len(concise_summary.split())
medium_words = len(medium_summary.split())
relevance_words = len(relevance_now.split()) if relevance_now else 0
total_words = about_words + concise_words + medium_words + relevance_words

print(f"  ← Output: {total_words:,} words total")
print(f"     About: {about_words:,} words")
print(f"     Concise: {concise_words:,} words")
print(f"     Medium: {medium_words:,} words")
print(f"     Relevance: {relevance_words:,} words")
print(f"     Author Country: {author_country}")
print(f"     Similar Books: {len(similar_books)}")
print(f"     Other Books: {len(other_books_by_author)}")
```

**Example Output:**
```
  ← Output: 3,247 words total
     About: 187 words
     Concise: 512 words
     Medium: 2,398 words
     Relevance: 150 words
     Author Country: England
     Similar Books: 5
     Other Books: 6
```

### Database Integration

**Updated in:** `scripts/generate_summaries.py` (process_book method)

**New Data Flow:**

1. **Call Enhanced API:**
   ```python
   result = generator.generate_combined_summaries(text, title, author, dry_run)
   ```

2. **Store in Database:**
   ```python
   # Store summaries (existing)
   db.add_summary(book_id, 'concise', result['concise_summary'])
   db.add_summary(book_id, 'medium', result['medium_summary'])

   # Store author metadata (new)
   author_id = db.add_author(
       name=author,
       country=result['author_country']
   )

   # Update book with enriched data (new)
   db.update_book_metadata(
       book_id=book_id,
       author_id=author_id,
       about_text=result['about_text'],
       relevance_now=result['relevance_now']
   )

   # Store similar books (new)
   for rank, book_data in enumerate(result['similar_books'], 1):
       # Look up book by title+author or store for later matching
       db.add_similar_book(book_id, similar_book_id, rank)
   ```

### Cost Savings

**Before (Multiple API Calls):**
- Call 1: Concise + Medium summaries (~3,000 tokens output)
- Call 2: Author country lookup (~50 tokens output)
- Call 3: Similar books (~500 tokens output)
- Call 4: Other books by author (~300 tokens output)
- **Total:** 4 API calls, ~3,850 tokens

**After (Single API Call):**
- Call 1: All metadata in one response (~4,000 tokens output)
- **Total:** 1 API call, ~4,000 tokens

**Savings:**
- 75% reduction in API calls (4 → 1)
- ~96% reduction in request overhead
- Improved consistency (all metadata from same context)
- Faster processing (parallel API requests eliminated)

### Book Title Normalization

**Added:** 2025-12-02

**Function:** `normalize_book_title()`

**Location:** `scripts/generate_summaries.py:34-105`

**Purpose:** Standardize book titles with consistent Title Case formatting and truncate subtitles.

**Normalization Rules:**

1. **Truncate at First Colon or Semicolon:**
   ```python
   "Jane Eyre: An Autobiography" → "Jane Eyre"
   "Moby Dick; Or, The Whale" → "Moby Dick"
   ```

2. **Apply Title Case:**
   - Capitalize first word always
   - Capitalize major words (nouns, verbs, adjectives, adverbs)
   - Lowercase articles and prepositions (unless first word):
     - `a, an, and, as, at, but, by, for, from, in, into, nor, of, on, or, so, the, to, up, with, yet`

3. **Handle Hyphenated Words:**
   ```python
   "twenty-thousand" → "Twenty-Thousand"
   "Winnie-the-Pooh" → "Winnie-the-Pooh"  # Each part capitalized
   ```

**Examples:**
```python
normalize_book_title("jane eyre: an autobiography")
# → "Jane Eyre"

normalize_book_title("MOBY DICK; Or, The Whale")
# → "Moby Dick"

normalize_book_title("the great gatsby")
# → "The Great Gatsby"

normalize_book_title("Twenty Thousand Leagues under the Sea")
# → "Twenty Thousand Leagues Under the Sea"
```

**Integration:**

1. **During Book Import** (`extract_metadata()` line 552):
   ```python
   title, author = self.extract_metadata(text)
   title = normalize_book_title(title)  # Normalize on import
   ```

2. **During Manual Processing** (`process_book()` line 4151):
   ```python
   if args.title:
       title = normalize_book_title(args.title)
   ```

**Migration Script:**

**File:** `scripts/migrate_book_titles.py`

**Purpose:** Backfill existing books in database with normalized titles

**Usage:**
```bash
# Preview changes without modifying database
python scripts/migrate_book_titles.py --dry-run

# Apply changes to database
python scripts/migrate_book_titles.py
```

**Results (2025-12-02):**
- 8 out of 62 books updated
- Examples:
  - "Thus Spake Zarathustra: A Book for All and None" → "Thus Spake Zarathustra"
  - "Jane Eyre: An Autobiography" → "Jane Eyre"
  - "Twenty Thousand Leagues under the Sea" → "Twenty Thousand Leagues Under the Sea"

### Cover Image Processing Automation

**Added:** 2025-12-02

**Function:** `process_cover_image()`

**Location:** `scripts/generate_summaries.py:665-728`

**Problem:**
- Downloaded Gutenberg covers used `pg{gutenberg_id}.jpg` naming
- Website convention uses `{book_id}.jpg` naming
- WebP versions not created automatically
- Manual renaming required after each book

**Solution:**

```python
def process_cover_image(self, gutenberg_id: int, book_id: int, dry_run: bool = False) -> str:
    """
    Process cover image: rename from pg{gutenberg_id} to {book_id} and create WebP version

    1. Find original file: pg12345.jpg
    2. Rename to: 81.jpg
    3. Create optimized WebP: 81.webp (quality 85)
    4. Report file size savings
    5. Return updated cover path for database
    """
```

**Workflow:**

1. **Find Original:**
   ```python
   covers_dir = config.COVERS_DIR  # frontend/static/covers/
   original_files = list(covers_dir.glob(f"pg{gutenberg_id}.*"))
   ```

2. **Rename:**
   ```python
   original_file.rename(covers_dir / f"{book_id}.jpg")
   ```

3. **Create WebP:**
   ```python
   subprocess.run([
       'cwebp', '-q', '85',
       str(new_jpg_path),
       '-o', str(new_webp_path)
   ])
   ```

4. **Report Savings:**
   ```
   ✓ Created 81.webp (187.3 KB, 42.1% smaller than JPG)
   ```

**Integration:**

**Location:** `scripts/generate_summaries.py:4269-4275`

```python
# After book is added to database
if book_id and gutenberg_id and not dry_run:
    updated_cover_path = self.process_cover_image(gutenberg_id, book_id, dry_run)
    if updated_cover_path:
        # Update database with corrected path
        db.update_book_cover(book_id, updated_cover_path)
```

**Benefits:**
- Automatic renaming (no manual intervention)
- WebP generation included (40-50% file size reduction)
- Consistent naming convention enforced
- Database automatically updated
- Dry-run support for testing

---


## Frontend UI Components & Architecture

### Book Details Page Layout (Updated 2025-12-03)

**Component Hierarchy:**
```
book-detail-section (frontend/templates/index.html:73-155)
├── book-detail-header
│   ├── book-detail-cover (WebP with fallback)
│   └── book-detail-info (title, author)
│
├── about-section (3 stacked sections)
│   ├── About This Book (about_text)
│   ├── Why Read This Now? (relevance_now)
│   └── About the Author
│       ├── author-info-bar (name + country)
│       ├── author-bio-text (placeholder: 100 words)
│       └── author-books-carousel (scrollable carousel)
│
└── book-content
    ├── summary-tabs-section
    │   ├── summary-tabs-header-container
    │   │   ├── Tab: "Short Summary" (500-word)
    │   │   ├── Tab: "Full Summary" (2000-word)
    │   │   └── unified-tts-button (changes based on active tab)
    │   ├── tab-500-word (concise summary content)
    │   └── tab-2000-word (medium summary content)
    │
    ├── chapters-section (list of all chapters)
    └── related-books-section (carousel)
```

**Key Technical Details:**

**Summary Tabs (frontend/static/js/app.js:408-457)**
- Single-page tab switching without reload
- `setupSummaryTabs()`: Handles tab click events
- `updateSummaryTTSButton()`: Dynamically shows/hides TTS button based on:
  - Active tab (500-word vs 2000-word)
  - Audio availability for that summary type
- Stores summary content in `this.conciseSummaryContent` and `this.mediumSummaryContent`
- CSS classes: `.summary-tab.active`, `.summary-tab-content.active`

**Author Books Carousel (frontend/static/js/app.js:832-915)**
- Reuses carousel pattern from "You May Also Like"
- API call: `GET /api/books/by-author/{author}?exclude={current_book_id}`
- Left/right navigation buttons
- Smooth scroll by 3 cards at a time
- Button states update on scroll (disabled at start/end)
- CSS classes: `.carousel-container`, `.related-books-scroll`, `.related-book-card`

**Chapter Summary Box (frontend/static/js/app.js:1417-1439)**
- Yellow collapsed box with expandable content
- Entire header is clickable (not just toggle button)
- Prevents toggle when clicking TTS button
- Cursor changes to pointer on hover
- CSS class: `.chapter-summary-box.collapsed`

---

## API Endpoints

### Author Books Endpoint (Added 2025-12-03)

**Endpoint:** `GET /api/books/by-author/<author_name>`

**Location:** `backend/app_base.py:945-990`

**Query Parameters:**
- `exclude` (int, optional): Book ID to exclude from results

**Database Method:** `get_books_by_author_name()` in `backend/models.py:1072-1097`
```sql
SELECT id, title, author, filename, word_count, gutenberg_id, cover_image_url, slug
FROM books
WHERE LOWER(author) = LOWER(?) AND id != ?
ORDER BY title
LIMIT ?
```

**Response Format:**
```json
{
  "success": true,
  "author": "Charles Dickens",
  "books": [
    {
      "id": 42,
      "title": "Great Expectations",
      "author": "Charles Dickens",
      "cover_image_url": "/static/covers/42.webp"
    }
  ],
  "count": 1
}
```

**Cover Image Logic:**
1. Check `cover_image_url` in database
2. If null, check for static file at `/static/covers/{book_id}.webp`
3. Only include `cover_image_url` in response if image exists

**Performance:**
- Direct SQL query (no in-memory filtering)
- Case-insensitive author matching
- Efficient exclusion of current book
- Limit of 20 books per author

---

## Text Formatting & Rendering

### Underscore Emphasis (Added 2025-12-03)

**Function:** `formatChapterText()` in `frontend/static/js/app.js:375-389`

**Purpose:** Convert Project Gutenberg underscore emphasis to HTML `<em>` tags

**Pattern:** `_text_` → `<em>text</em>`

**Implementation:**
```javascript
formatChapterText(text) {
    const paragraphs = text.split(/\n/);
    return paragraphs
        .filter(p => p.trim().length > 0)
        .map(p => {
            let escaped = this.escapeHtml(p.trim());
            // Convert _text_ to <em>text</em>
            escaped = escaped.replace(/\b_([^_]+?)_\b/g, '<em>$1</em>');
            return `<p>${escaped}</p>`;
        })
        .join('');
}
```

**Security:** HTML escaping happens first to prevent XSS attacks

**Examples:**
- `"He _said_ something"` → `"He <em>said</em> something"`
- `"_vis-à-vis_ the text"` → `"<em>vis-à-vis</em> the text"`

**CSS Styling:** `frontend/static/css/style.css:1376-1380`
```css
.full-text-content em {
    font-style: italic;
}
```

---

## Top 10 Carousel - Responsive Layout System

### Overview (Added 2025-12-08)

The Top 10 Books carousel on the homepage uses a Netflix-inspired responsive layout that adapts between centered and left-aligned modes based on viewport width.

### HTML Structure

**Location:** `frontend/templates/index.html:85-115`

```html
<section class="hero-banner hero-discover">
    <!-- Title & Subtitle (always centered) -->
    <div class="hero-banner-content">
        <h2 class="hero-banner-heading">Discover Classics the Modern Way</h2>
        <p class="hero-banner-description">Find your next classic...</p>
    </div>

    <!-- Carousel (direct child, can break out of centered layout) -->
    <div class="top-10-carousel-wrapper">
        <div class="carousel-container top-10-carousel">
            <button class="carousel-nav-btn left">...</button>
            <div class="carousel-scroll"><!-- Books rendered by JS --></div>
            <button class="carousel-nav-btn right">...</button>
        </div>
    </div>

    <!-- CTA (always centered) -->
    <div class="hero-banner-content">
        <div class="hero-banner-ctas">...</div>
    </div>
</section>
```

### Key Design Pattern

**Direct Child Positioning:** The carousel is a direct child of `.hero-discover` (not nested in `.hero-banner-content`) to enable independent alignment while maintaining vertical stacking.

**Parent Flexbox:** `.hero-banner` uses `flex-direction: column` to stack children vertically:
```css
.hero-banner {
    display: flex;
    flex-direction: column;
    align-items: center;  /* Centers children by default */
}
```

### Responsive Behavior

**Breakpoint: 1024px**

**Desktop Mode (> 1024px):**
```css
.top-10-carousel-wrapper {
    margin: 2rem auto 1.5rem;
    max-width: 980px;
    width: 100%;
}
```
- Carousel centered with `margin: auto`
- Max-width of 980px
- Navigation buttons overlay carousel edges (absolute positioning)

**Mobile Mode (≤ 1024px):**
```css
@media (max-width: 1024px) {
    .top-10-carousel-wrapper {
        margin: 1.5rem 0 1rem 0;
        max-width: none;
        width: 100%;
        align-self: flex-start;  /* Override parent's center alignment */
    }
}
```
- `align-self: flex-start` overrides parent's `align-items: center`
- No auto margins (left-aligned)
- Full viewport width
- Navigation buttons remain visible with overlay positioning

### Breakpoint Calculation

**Why 1024px?**

The threshold accounts for:
1. Carousel max-width: 980px
2. Navigation button widths (overlaid): ~44-62px each
3. Padding and safety margin: ~40-80px

At viewports < 1024px, a centered 980px carousel would push overlay buttons partially off-screen. Switching to left-aligned mode ensures buttons remain fully visible.

### Navigation Button Positioning

**Overlay Approach:**
```css
.top-10-carousel .carousel-nav-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(0, 0, 0, 0.75);  /* Semi-transparent */
    z-index: 10;
}

.top-10-carousel .carousel-nav-btn.left {
    left: 0.5rem;  /* Small inset, overlays first book */
}

.top-10-carousel .carousel-nav-btn.right {
    right: 0.5rem;
}
```

**Mobile Adjustments:**
- Buttons maintain minimum 44px tap target (iOS/Android standards)
- Semi-transparent backgrounds ensure visibility over book covers
- Small insets (0.25-0.5rem) prevent buttons from touching screen edges

### Book Card Responsive Sizing

Cards progressively shrink to fit viewport:

```css
/* Desktop */
.top-10-book-card { width: 150px; }

/* Breakpoints */
@media (max-width: 768px) { width: 110px; }
@media (max-width: 480px) { width: 95px; }
@media (max-width: 390px) { width: 85px; }
@media (max-width: 360px) { width: 75px; }
@media (max-width: 320px) { width: 70px; }
```

Gaps between cards also reduce proportionally (1rem → 0.25rem).

### Advantages of This Approach

1. **Clean Separation:** Title/subtitle/CTA remain centered while carousel adapts independently
2. **No JavaScript Required:** Pure CSS responsive behavior
3. **Vertical Stacking:** Flexbox ensures proper layout order
4. **Button Visibility:** Left-aligned mode guarantees navigation buttons stay on-screen
5. **Netflix Pattern:** Matches industry-standard carousel UX

### Files Modified

- `frontend/templates/index.html:85-115` - HTML structure
- `frontend/static/css/style.css:2065` - Flexbox column layout
- `frontend/static/css/style.css:2173-2188` - Carousel responsive styles
- `frontend/static/css/style.css:2265-2420` - Mobile breakpoints

---

## Frontend Loading State Architecture (Added 2025-12-11)

### Overview

The loading state system provides user feedback during async operations while preventing flash-on-refresh issues. It uses a modern centered spinner design with contextual messaging.

### Core Components

#### CSS Classes

**`.loading-container`** - Centered flex container
```css
.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    min-height: 300px;
}
```

**`.loading-spinner`** - Rotating circular spinner
```css
.loading-spinner {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-left-color: var(--secondary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
```

**`.loading-text`** - Contextual loading message
```css
.loading-text {
    color: var(--text-light);
    font-size: 0.9rem;
    font-weight: 500;
    opacity: 0.8;
}
```

### Loading State Logic

#### Smart Display Pattern

Loading states only display when content is actually empty, preventing flash on page refresh:

```javascript
// Check if content exists before showing loader
if (!element.textContent.trim()) {
    element.innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <div class="loading-text">Loading...</div>
        </div>
    `;
}
```

#### SSR Compatibility

For server-side rendered pages, check `restoreScroll` flag to skip loading states:

```javascript
if (chapterFulltext && !restoreScroll) {
    chapterFulltext.innerHTML = loadingHTML;
}
```

### Implementation Locations

**Book Summary Loading:**
- `loadConciseSummary()` - "Loading summary..."
- `loadMediumSummary()` - "Loading full summary..."
- Location: `frontend/static/js/app.js:1405-1413, 1479-1487`

**Chapter Loading:**
- `loadChapters()` - "Loading chapters..."
- Chapter detail - "Loading chapter text..." and "Loading summary..."
- Location: `frontend/static/js/app.js:1520-1528, 1886-1902`

**Metadata Loading:**
- `loadBookMetadata()` - "Loading book information..." and "Loading reading guide..."
- `loadRelatedBooks()` - "Loading related books..."
- Location: `frontend/static/js/app.js:1327-1365, 1654-1661`

### Loading Dismissal

Remove loading states by selector (supports both new and legacy styles):

```javascript
// Remove both new spinner and legacy skeleton
const loadingContainer = content.querySelector('.loading-container');
if (loadingContainer) loadingContainer.remove();

const skeleton = content.querySelector('.skeleton');
if (skeleton) skeleton.remove();
```

**Critical for Reading Guide:** The `updateReadingGuide()` method must remove both `.loading-container` and `.skeleton` to properly dismiss loading states when images load.

Location: `frontend/static/js/app.js:1303-1310`

### Backward Compatibility

Legacy skeleton classes retained for backward compatibility:
- `.skeleton` - Base skeleton element
- `.skeleton-text-wide` - Wide text placeholder
- `.skeleton-text-short` - Short text placeholder
- `.skeleton-box` - Box placeholder

### Design Rationale

**Why Centered Spinner vs. Skeleton:**
1. **Cleaner Aesthetic:** Single spinner is less cluttered than multiple skeleton boxes
2. **Contextual Awareness:** Loading text tells users exactly what's happening
3. **Modern Pattern:** Matches contemporary web UX (Google, Facebook, Twitter)
4. **Simpler Markup:** Easier to maintain and update
5. **Better Performance:** Less DOM manipulation

**Why Content Check:**
1. **Prevents Flash:** No visible content → skeleton → content cycle on refresh
2. **SSR Compatible:** Works with server-side rendered pages
3. **Better UX:** Users don't see unnecessary loading states
4. **Performance:** Skips DOM manipulation when not needed

### Files Modified

- `frontend/static/css/style.css:556-641` - Loading component styles
- `frontend/static/js/app.js:1303-1310` - Loading dismissal
- `frontend/static/js/app.js:1327-1365` - Book metadata loading
- `frontend/static/js/app.js:1405-1413` - Concise summary loading
- `frontend/static/js/app.js:1479-1487` - Medium summary loading
- `frontend/static/js/app.js:1520-1528` - Chapters loading
- `frontend/static/js/app.js:1654-1661` - Related books loading
- `frontend/static/js/app.js:1886-1902` - Chapter detail loading

---

## Discover Page Architecture (Added 2025-12-11)

### Overview

The Discover page provides curated book discovery through themed carousels, with a popular books carousel added at the top for immediate access to widely-read classics.

### Page Structure

**Carousel Flow (as of 2025-12-14):**
1. **Popular Carousel** - Top 10 most downloaded classics
2. **Easy to Read** - Books for beginning readers (A2-B1 CEFR level)
3. **Books with Full Audio Summaries** - Books with complete audio narration
4. **Books You Can Read in a Day** - Shorter classics under 50,000 words (Added 2025-12-14)
5. **Adventure** - Adventure category books
6. **Children's Literature** - Children's category books
7. **Romance** - Romance category books
8. **Books by Charles Dickens** - Works by Charles Dickens

### Popular Carousel Implementation

#### Data Source

Top 10 books based on Project Gutenberg download statistics:
```javascript
const top10GutenbergIds = [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345];
```

**Book Lookup:**
```javascript
const top10Books = [];
top10GutenbergIds.forEach((gutenbergId) => {
    const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
    if (book) {
        top10Books.push(book);
    }
});
```

#### Rendering Method

**`renderTop10AsStandardCarousel(containerId, title)`**

Reuses existing carousel infrastructure for consistency:

```javascript
renderTop10AsStandardCarousel(containerId, title = 'Popular') {
    // Find top 10 books in database
    const top10Books = [];
    top10GutenbergIds.forEach((gutenbergId) => {
        const book = this.allBooks.find(b => b.gutenberg_id === gutenbergId);
        if (book) top10Books.push(book);
    });

    if (top10Books.length === 0) return;

    // Render using standard category carousel (no rank overlays)
    this.renderCategoryCarousel(
        { id: 'popular', name: title },
        top10Books,
        containerId
    );
}
```

Location: `frontend/static/js/app.js:955-980`

#### UI Consistency

The popular carousel uses the **same UI as difficulty carousels:**
- Regular book cards (cover, title, author)
- Standard carousel navigation (left/right arrows)
- No rank overlays (unlike home page version)
- No "View All" link

**Contrast with Home Page:**
- Home page uses `renderTop10Carousel()` with rank overlays and special styling
- Discover page uses `renderTop10AsStandardCarousel()` with standard styling
- Different UX contexts require different presentations

### Data Loading Flow

**Critical Sequence:**
```javascript
async showDiscoverPage(restoreScroll = false) {
    // ... setup code ...

    // MUST load books before rendering popular carousel
    await this.ensureBooksLoaded();

    // Fetch difficulty carousel data
    const response = await fetch('/api/discover/carousels');
    const data = await response.json();

    // Render page (popular carousel needs this.allBooks)
    this.renderDiscoverPage(data);
}
```

Location: `frontend/static/js/app.js:2856-2894`

**Why `ensureBooksLoaded()` is Required:**
1. Popular carousel looks up books by Gutenberg ID
2. Requires `this.allBooks` array to be populated
3. Without it, popular carousel would be empty
4. Difficulty carousels receive books from API, don't need this

### View All Link Logic

Updated to exclude popular carousel:

```javascript
// Add View All link (except for "All Books" carousel, discover page, or popular carousel)
const viewAllLink = !isDiscoverPage && category.id !== 'all' && category.id !== 'popular'
    ? `<a href="/categories/${category.id}" class="view-all-link">View All →</a>`
    : category.id === 'all' && !isDiscoverPage
        ? `<a href="/books" class="view-all-link">View All →</a>`
        : '';
```

Location: `frontend/static/js/app.js:800-805`

**Exclusion Reasons:**
- **Discover page carousels:** No category detail pages for difficulty levels
- **All Books carousel:** "View All" would link to same page
- **Popular carousel:** No dedicated page for popular books (top 10 is complete set)

### "Books You Can Read in a Day" Carousel (Added 2025-12-14)

#### Overview

Quick-read carousel featuring shorter classics (under 50,000 words) perfect for readers who want to finish a complete classic in one sitting.

#### Implementation

**Backend Filter Logic:**
Location: `backend/app_base.py:1051-1056`

```python
# Carousel 3: Books You Can Read in a Day (under 50,000 words)
quick_reads = []
for book in all_books:
    word_count = book.get('word_count')
    if word_count and word_count < 50000 and book.get('slug'):
        quick_reads.append(book)
```

**Carousel Data Structure:**
Location: `backend/app_base.py:1104-1110`

```python
if quick_reads:
    carousels.append({
        'id': 'quick-reads',
        'title': 'Books You Can Read in a Day',
        'description': 'Shorter classics under 50,000 words - perfect for a quick read',
        'books': quick_reads
    })
```

#### Books Included (17 total)

Representative examples:
- A Christmas Carol in Prose (28,541 words)
- Alice's Adventures in Wonderland (29,564 words)
- The Great Gatsby (48,208 words)
- Peter Pan (47,268 words)
- Romeo and Juliet (25,958 words)
- Metamorphosis (21,943 words)
- The Importance of Being Earnest (20,714 words)

**Word Count Range:** 20,714 - 48,500 words
**Average:** ~32,000 words (2-3 hours reading time)

#### Positioning Strategy

Placed after "Books with Full Audio Summaries" to:
1. Maintain engagement flow from audio to quick-read discovery
2. Appeal to users who prefer shorter, manageable classics
3. Create a clear differentiation between difficulty-based and length-based curation

### Component Reusability

**Shared Infrastructure:**
- `renderCategoryCarousel()` renders all carousels (popular, difficulty, category)
- Same book card HTML structure
- Same navigation button logic
- Same scroll behavior
- Same responsive breakpoints

**Benefits:**
1. **Consistency:** All carousels look and behave identically
2. **Maintainability:** One method to update, not multiple
3. **Code Efficiency:** No duplicate carousel logic
4. **Testing:** Test one method, covers all carousels

### Files Modified

**Original Implementation (2025-12-11):**
- `frontend/static/js/app.js:800-805` - View All link logic
- `frontend/static/js/app.js:955-980` - New popular carousel renderer
- `frontend/static/js/app.js:2871-2872` - Ensure books loaded
- `frontend/static/js/app.js:2895-2901` - Render popular carousel on page

**Quick-Reads Carousel Addition (2025-12-14):**
- `backend/app_base.py:1051-1056` - Filter logic for books under 50k words
- `backend/app_base.py:1104-1110` - Carousel data structure

---

## Blog Header Images & Unsplash Integration

### Overview

Blog posts feature header images automatically sourced from Unsplash API, displayed both as thumbnails in the blog index grid and full headers on individual post pages.

**Added:** 2025-12-12

### Database Schema

**Table:** `blog_posts` (added to ERD above)

**New Field:**
- `header_image_url` (TEXT, nullable): URL to Unsplash image for blog header

### Unsplash API Integration

**Configuration:** `backend/config.py:23-24`
```python
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY', '')
```

**Environment Variable:** `.env`
```
UNSPLASH_ACCESS_KEY=<your-api-key>
```

**API Limits:**
- 1,000 requests per hour (Demo tier)
- Images served from Unsplash CDN
- Attribution required per Unsplash guidelines

### Image Assignment Script

**Location:** `scripts/assign_blog_header_images.py`

**Usage:**
```bash
# Assign to all posts missing images
python scripts/assign_blog_header_images.py

# Assign to specific post by slug
python scripts/assign_blog_header_images.py --slug british-vs-american-english

# Re-assign to all posts (force)
python scripts/assign_blog_header_images.py --force
```

**Search Strategy:**

The script uses keyword-based search query mapping to find relevant images:

```python
query_mappings = {
    'british': 'british library books vintage',
    'american': 'american literature library',
    'shortest': 'reading book cozy',
    'non-native': 'reading learning education',
    'horror': 'dark atmospheric gothic',
    'romance': 'romantic vintage couple',
    'mystery': 'detective noir mystery',
    'adventure': 'adventure explore journey',
    'classics': 'classic literature vintage books',
    'english': 'english literature library'
}
```

**Selection Criteria:**
1. Keyword mapping generates smart search query from title/slug
2. Unsplash API filters for landscape orientation
3. First result selected (based on Unsplash relevance ranking)
4. Regular size image (1080px width) stored in database

**Image Properties:**
- `url`: Regular size (1080px width) for full headers
- `thumb_url`: Small size for thumbnails (not currently used)
- `photographer`: Attribution info (not currently displayed)
- `photographer_url`: Link to photographer profile

### Frontend Display

**Blog Index:** `frontend/static/js/components/BlogIndex.js:37-43`

Thumbnail display in blog grid cards:
```javascript
const thumbnailHTML = post.header_image_url ? `
    <div class="blog-card-image">
        <img src="${this.app.escapeHtml(post.header_image_url)}"
             alt="${this.app.escapeHtml(post.title)}"
             loading="lazy">
    </div>
` : '';
```

**Blog Post:** `frontend/static/js/components/BlogPost.js:46-53`

Full header image on post pages:
```javascript
const headerImageHTML = this.post.header_image_url ? `
    <div class="blog-post-header-image">
        <img src="${this.app.escapeHtml(this.post.header_image_url)}"
             alt="${this.app.escapeHtml(this.post.title)}"
             loading="eager">
    </div>
` : '';
```

### CSS Styling

**Thumbnail Cards:** `frontend/static/css/style.css:4462-4500`
- Height: 200px
- Object-fit: cover (crops to fill)
- Hover effect: 1.05x scale

**Full Headers:** `frontend/static/css/style.css:4541-4553`
- Max height: 400px
- Object-fit: cover
- Border radius: 12px
- Margin bottom: 30px

**Responsive:**
- Mobile: Single column grid
- Desktop: Multi-column grid (auto-fill, minmax 320px)

### API Endpoints

**Get Blog Posts:** `GET /api/blog`
```json
{
    "success": true,
    "posts": [
        {
            "slug": "british-vs-american-english",
            "title": "British vs American English in Classic Literature",
            "excerpt": "Exploring the differences...",
            "header_image_url": "https://images.unsplash.com/...",
            "published_date": "2025-12-11",
            ...
        }
    ]
}
```

**Get Single Post:** `GET /api/blog/{slug}`
```json
{
    "success": true,
    "post": {
        "slug": "british-vs-american-english",
        "title": "British vs American English in Classic Literature",
        "content": "# Full markdown content...",
        "header_image_url": "https://images.unsplash.com/...",
        ...
    }
}
```

### Future Improvements

**Current Limitation:** Script selects first Unsplash result automatically

**Possible Enhancements:**
1. Interactive selection tool to browse multiple image options
2. Additional filters (likes, downloads, color palette)
3. Manual image URL override capability
4. Photographer attribution display on frontend
5. Local image caching to reduce API calls

### Files Modified

**Backend:**
- `backend/models.py:278-284` - Database migration for header_image_url
- `backend/models.py:1562-1577` - Updated add_blog_post() method
- `backend/config.py:23-24` - Unsplash API key configuration

**Frontend:**
- `frontend/static/js/components/BlogIndex.js:37-43` - Thumbnail display
- `frontend/static/js/components/BlogPost.js:46-53` - Full header display
- `frontend/static/css/style.css:4462-4500` - Blog card styling
- `frontend/static/css/style.css:4541-4553` - Header image styling

**Scripts:**
- `scripts/assign_blog_header_images.py` - New script for image assignment

**Configuration:**
- `.env` - Added UNSPLASH_ACCESS_KEY

---


## Database Quality & Audit System

### Overview

Summra maintains high data integrity for chapter text extracted from Project Gutenberg sources. A comprehensive audit system verifies that chapter text stored in the database matches the original source material.

**Audit Results (2025-12-14):**
- **98.7% overall coverage** across 55 books with source files
- **0 genuine discrepancies** (2 false positives due to audit script limitations)
- **55.6% perfect matches** (<1% difference)
- **9.9% minor differences** (whitespace normalization only)

### Audit Script

**Location:** `scripts/audit_chapter_text.py`

**Purpose:**
Compares database `chapter_text` with re-extracted chapters from Gutenberg source files to identify discrepancies and verify data integrity.

**Usage:**
```bash
# Run full audit on all 81 books
python scripts/audit_chapter_text.py
```

### Coverage Metrics

**Overall Database Coverage:**
- Total books audited: 81
- Books with source files: 55 (67.9%)
- Overall coverage: 98.7%
- DB chars: 54,341,732 vs Source chars: 55,046,438
- Difference: 1.3%

**Status Distribution:**
- Perfect (<1% diff): 45 books (55.6%)
- Minor (1-10% diff): 8 books (9.9%)  
- Major (>10% diff): 0 books (2 false positives identified)
- No Source: 26 books (32.1%)

---


## Progressive Web App (PWA) Implementation

### Overview

Summra is implemented as a Progressive Web App, enabling offline reading, installation to home screen, and app-like experience on both mobile and desktop devices.

**Implementation Date:** 2025-12-18

### Core Components

#### 1. Web App Manifest

**Location:** `frontend/static/manifest.json`

**Purpose:** Defines app metadata for installation and provides app-like behavior.

**Key Properties:**
```json
{
  "name": "Summra - Classic Literature Summaries",
  "short_name": "Summra",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#1a1a1a",
  "background_color": "#ffffff",
  "icons": [
    { "src": "/static/images/icon-192.png", "sizes": "192x192" },
    { "src": "/static/images/icon-512.png", "sizes": "512x512" }
  ]
}
```

**Template Integration:**
- Linked in `frontend/templates/index.html` via `<link rel="manifest">`
- Includes Apple-specific meta tags for iOS compatibility

#### 2. Service Worker

**Location:** `frontend/static/service-worker.js`

**Technology:** Workbox 7.0.0 (Google's service worker library)

**Purpose:** Intercepts network requests to enable offline caching and improve performance.

**Caching Strategies:**

| Content Type | Strategy | Cache Duration | Max Entries |
|--------------|----------|----------------|-------------|
| App Shell (HTML, CSS, JS) | Precache | 30 days | N/A |
| Images (covers, icons) | Cache-First | 30 days | 100 |
| Book Data | Network-First | 7 days | 50 |
| Summaries | Network-First | 7 days | 50 |
| Chapters | Network-First | 7 days | 100 |
| Book Lists | Stale-While-Revalidate | 1 day | 30 |
| Categories | Stale-While-Revalidate | 1 day | 30 |
| Authors | Stale-While-Revalidate | 7 days | 50 |
| Blog Posts | Stale-While-Revalidate | 7 days | 20 |
| TTS Requests | Network-Only | Never | N/A |
| Admin Endpoints | Network-Only | Never | N/A |

**Strategy Explanations:**
- **Precache:** Cached on service worker install
- **Cache-First:** Check cache first, fallback to network (best for static assets)
- **Network-First:** Try network first, fallback to cache if offline (best for dynamic content)
- **Stale-While-Revalidate:** Serve from cache immediately, update in background
- **Network-Only:** Never cache (real-time data)

**Flask Route:**
- `/service-worker.js` - Serves service worker with correct headers
- `Service-Worker-Allowed: /` header enables service worker scope

#### 3. Service Worker Registration

**Location:** `frontend/static/js/app.js` (method: `registerServiceWorker()`)

**Features:**
- Registers on page load
- Detects service worker updates
- Logs registration status to console
- Graceful fallback for unsupported browsers

#### 4. Offline Fallback Page

**Location:** `frontend/templates/offline.html`

**Purpose:** Displayed when user navigates to uncached page while offline.

**Features:**
- Beautiful gradient design
- Auto-retry connection every 5 seconds
- Listens for `online` event to auto-redirect
- Explains offline functionality to users

**Flask Route:**
- `/offline` - Serves offline fallback page

#### 5. iOS Install Instructions

**Components:**
- iOS detection in `app.js` (`setupInstallPrompt()`)
- Install banner in `frontend/templates/index.html`
- Banner styles in `frontend/static/css/style.css`

**Detection Logic:**
```javascript
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
const isInStandaloneMode = window.navigator.standalone;

// Only show banner if:
// 1. User is on iOS
// 2. Not already installed (standalone mode)
// 3. Haven't dismissed the banner before
```

**Banner Behavior:**
- Fixed position at bottom of screen
- Slide-up animation
- Shows iOS Share icon + instructions
- Dismissible (saves to localStorage)
- Appears 2 seconds after page load
- Purple gradient design matching PWA theme

**iOS Compatibility:**
- Works on iOS 11.3+ (Safari)
- Service workers fully supported
- Manual "Add to Home Screen" required (no automatic prompt)
- Storage quota ~50MB (less than Android's ~500MB)
- No push notification support on iOS

### Browser Support

| Feature | Chrome/Edge | Safari iOS | Safari Desktop | Firefox |
|---------|-------------|------------|----------------|---------|
| Service Workers | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Offline Caching | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Install Prompt | ✅ Auto | ⚠️ Manual | ✅ Auto | ✅ Auto |
| Standalone Mode | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Push Notifications | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| Storage Quota | ~500MB | ~50MB | ~500MB | ~500MB |

### Automatic Caching Behavior

**How It Works:**
1. User visits a page (e.g., book detail, summary, chapter)
2. Service worker intercepts the request
3. Fetches from network (for fresh content)
4. Automatically saves response to cache
5. On subsequent visits (even offline), serves from cache

**Storage Limits:**
- Mobile Chrome: ~50% of available storage
- Typical: 100-500MB depending on device
- Current limits configured: 100 images, 50 books, 100 chapters

### Installation Flow

**Android Chrome:**
1. Visit summra.com
2. Chrome shows "Add to Home Screen" banner (automatic)
3. User taps "Install"
4. App icon appears on home screen
5. Tap icon → opens in standalone mode

**iOS Safari:**
1. Visit summra.com
2. iOS install banner appears after 2 seconds
3. User taps Share button (banner shows instructions)
4. Taps "Add to Home Screen"
5. App icon appears on home screen
6. Tap icon → opens in standalone mode

---

## Pagination System (Added 2025-12-19)

The pagination system transforms chapter reading from scroll-based to page-based navigation, providing a Kindle-like reading experience.

### Architecture Overview

**Core Components:**
- **Pagination State Manager** (`this.pagination` object in app.js)
- **Page Calculation Engine** (height-based algorithm)
- **Navigation System** (tap zones, swipe, keyboard, buttons)
- **Progress Tracker** (page numbers and percentage)
- **Position Persistence** (localStorage per chapter)

### State Management

**Location:** `frontend/static/js/app.js` lines 48-59

```javascript
this.pagination = {
    totalPages: 0,
    currentPage: 1,
    pages: [],              // Array of DOM elements (one per page)
    initialized: false,
    wheelTimeout: null,     // Debounce for scroll-to-turn
    swipeStartX: 0,
    swipeStartY: 0
};
```

**State Lifecycle:**
1. Reset on chapter load
2. Initialized after DOM rendering
3. Updated on page navigation
4. Recalculated on viewport/font changes
5. Cleared on chapter exit

### Page Calculation Algorithm

**Location:** `frontend/static/js/app.js` lines 4525-4801

**Key Principle:** Break content only at paragraph boundaries to prevent mid-sentence splits.

**Height Calculation:**
```javascript
// Calculate available height for content
const viewportHeight = window.innerHeight;
const stickyHeaderHeight = 50;
const backButtonHeight = 40;
const progressBarHeight = 24;
const padding = 32;

const availableHeight = viewportHeight - stickyHeaderHeight - backButtonHeight - progressBarHeight - padding;
```

**Algorithm Steps:**

1. **Clone Content for Measurement**
   - Create off-screen measurement container
   - Preserve all styles (font-size, line-height, margins)
   - Use same CSS classes as visible content

2. **Iterate Through Paragraphs**
   - Measure each paragraph's rendered height
   - Include top/bottom margins in measurement
   - Track cumulative height

3. **Apply Safety Margin (Critical Fix - v5.10)**
   ```javascript
   // Calculate lines needed, add small 0.2 line safety margin for paragraph ending
   // This accounts for margin rendering and subpixel rounding without being excessive
   const testLines = Math.ceil(testTotalHeight / lineHeight) + 0.2;
   ```

   **Why AFTER Math.ceil():**
   - Margins already included in `testTotalHeight` measurement
   - Math.ceil() rounds up line calculations
   - 0.2 line buffer accounts for rendering/rounding edge cases
   - Applied only for paragraph endings, not every line

4. **Word-Fitting for Split Paragraphs**
   - If paragraph too large, split at word boundaries
   - Measure progressively longer word sequences
   - Find maximum words that fit in remaining space
   - Create new paragraph elements for continuation

5. **Build Page Array**
   - Each page is a container div with assigned paragraphs
   - Page containers receive inline font-size from reading settings
   - Pages hidden/shown based on current position

**Edge Cases Handled:**
- Empty paragraphs (preserve spacing)
- Very long words (allow overflow rather than break)
- Margin collapse at page boundaries
- Font size changes triggering recalculation
- Window resize events

### Navigation System

**Methods Supported:**

1. **Tap Zones (Removed in v5.17)**
   - Originally 30% left/right zones
   - Removed due to blocking text selection
   - Replaced with scroll-to-turn

2. **Scroll-to-Turn** (Added after layout redesign)
   - Location: `app.js` lines 4438-4465
   - Intercepts wheel events with `preventDefault()`
   - 100ms debounce prevents rapid page flipping
   - Scroll down → next page, scroll up → previous page

3. **Keyboard Navigation**
   - Arrow Right → next page
   - Arrow Left → previous page
   - Attached to document keydown event

4. **On-Screen Buttons**
   - Previous/Next buttons overlaid on content
   - Fade in on desktop hover
   - Always visible on mobile
   - SVG chevron icons

5. **Swipe Gestures**
   - Touch event listeners for mobile
   - Swipe left → next page
   - Swipe right → previous page
   - Minimum swipe distance threshold

### Font Size Integration (Critical Fix - v5.3)

**Problem:** Font size slider had no effect on paginated content.

**Root Cause:**
- CSS had hardcoded `font-size: 1.05rem` on pagination containers
- Inline styles were being applied but overridden by CSS
- `applyFontSize()` didn't target pagination elements

**Solution (app.js lines 3721-3752):**

```javascript
applyFontSize(size) {
    const chapterSection = document.getElementById('chapter-detail-section');
    if (!chapterSection) return;

    // Apply to pagination containers (when pagination is active)
    const paginationContainers = chapterSection.querySelectorAll('.pagination-page-container');
    if (paginationContainers.length > 0) {
        paginationContainers.forEach(container => {
            container.style.fontSize = `${size}px`;
        });
    }
}
```

**CSS Changes (style.css lines 1708-2082):**
- Removed hardcoded `font-size` from `.chapter-fulltext`
- Removed hardcoded `font-size` from `.chapter-modern-english`
- Removed hardcoded `font-size` from `.pagination-page-container`
- Added comments explaining JavaScript control

**Reapplication After Pagination (app.js lines 4622-4624):**
```javascript
// Reapply saved font size to pagination container
const savedFontSize = localStorage.getItem('reading_fontSize') || '16';
this.applyFontSize(savedFontSize);
```

### Flash Prevention (Fixed v5.14)

**Problem:** Flash of unpaginated content when navigating between chapters.

**Failed Approaches:**
- v5.11: Complex loading container with spinner → broke entire layout
- v5.12: Query-based container approach → still broken
- v5.13: Simplified approach → partial fix

**Final Solution:** Simple section-level visibility control

**Hide on Chapter Load (app.js lines 2159-2163):**
```javascript
// In showChapterDetail()
const chapterSection = document.getElementById('chapter-detail-section');
if (chapterSection) {
    chapterSection.style.visibility = 'hidden';
}
```

**Show After Pagination Complete (app.js lines 4632-4636):**
```javascript
// In initializePagination()
const chapterSection = document.getElementById('chapter-detail-section');
if (chapterSection) {
    chapterSection.style.visibility = 'visible';
}
```

**Why This Works:**
- `visibility: hidden` hides content but preserves layout
- DOM remains accessible for measurement
- No complex positioning or z-index issues
- Clean transition with no flash

### Progress Integration

**Display Format:** "Page 5 of 24 • 21%"

**Update Logic (app.js):**
```javascript
updateProgress() {
    const progressText = document.getElementById('reading-progress-text');
    const progressFill = document.getElementById('reading-progress-fill');

    const percentage = Math.round((this.pagination.currentPage / this.pagination.totalPages) * 100);

    progressText.textContent = `Page ${this.pagination.currentPage} of ${this.pagination.totalPages} • ${percentage}%`;
    progressFill.style.width = `${percentage}%`;
}
```

**Progress Bar Synchronization:**
- Visual bar width matches percentage
- Updates instantly on page change
- Persists during font/theme changes

### Position Persistence

**localStorage Key Format:** `chapter_page_position_${bookId}_${chapterNumber}`

**Save on Page Change:**
```javascript
localStorage.setItem(`chapter_page_position_${bookId}_${chapterNumber}`, currentPage);
```

**Restore on Chapter Load:**
```javascript
const savedPage = localStorage.getItem(`chapter_page_position_${bookId}_${chapterNumber}`);
if (savedPage && savedPage <= totalPages) {
    this.navigateToPage(parseInt(savedPage));
}
```

**Recalculation Handling:**
- If saved page > new total pages, navigate to last page
- Maintains approximate reading position
- Not character-perfect but good enough for UX

### View Mode Integration

**Supported Modes:**
- Original Text
- Modern English
- Side-by-Side

**Pagination Recalculation on Mode Change:**
```javascript
handleViewModeChange(mode) {
    // Switch view mode
    this.switchViewMode(mode);

    // Recalculate pagination for new content
    if (this.pagination.initialized) {
        this.initializePagination();
    }
}
```

**Content-Specific Calculations:**
- Original text uses `.chapter-fulltext` elements
- Modern English uses `.chapter-modern-english` elements
- Side-by-side uses `.chapter-side-by-side` rows
- Each mode measures its own DOM structure

### Responsive Recalculation

**Triggers:**
1. Window resize (debounced 300ms)
2. Font size change (immediate)
3. Theme change (immediate)
4. View mode change (immediate)
5. Orientation change on mobile (immediate)

**Recalculation Flow:**
```javascript
// Save current position
const currentElement = getCurrentParagraphElement();

// Clear existing pagination
this.clearPagination();

// Rebuild pages with new dimensions
this.calculatePages();

// Restore approximate position
this.restorePositionToElement(currentElement);
```

### Performance Optimizations

**Measurement Container Reuse:**
- Single off-screen div created once
- Reused for all paragraph measurements
- Destroyed after calculation complete

**Debouncing:**
- Scroll-to-turn: 100ms debounce
- Window resize: 300ms debounce
- Prevents excessive recalculations

**DOM Minimization:**
- Only current page rendered in DOM
- Previous/next pages hidden with `display: none`
- Reduces paint/reflow operations

### Chapter Navigation Integration (Fixed v5.15-v5.17)

**Problem:** Navigation buttons didn't work from preface (chapter 0) to Chapter 1.

**Root Cause:**
```javascript
// WRONG - assumes chapters start at 1
const hasPrevChapter = this.currentChapter > 1;
const hasNextChapter = this.currentChapter < this.chapters.length;
```

**Solution (app.js lines 5091-5092):**
```javascript
// Explicit existence checking handles chapter 0 (preface)
const hasPrevChapter = this.chapters.some(ch => ch.chapter_number === this.currentChapter - 1);
const hasNextChapter = this.chapters.some(ch => ch.chapter_number === this.currentChapter + 1);
```

**Why This Works:**
- `.some()` explicitly checks if chapter exists
- Works for any chapter numbering scheme (0-based, 1-based, gaps)
- No assumptions about continuous numbering

### CSS Classes

**Location:** `frontend/static/css/style.css` lines 4971-5220

**Key Classes:**
- `.pagination-wrapper` - Container for all pages (height set by JS)
- `.pagination-page-container` - Individual page (receives inline font-size)
- `.pagination-nav-btn` - Previous/Next buttons
- `.pagination-progress` - Page counter display
- `.pagination-active` - Applied to body to disable normal scrolling

**Non-Scrollable Implementation:**
```css
body.pagination-active {
    overflow: hidden;
}

.pagination-wrapper {
    overflow: hidden;
    overscroll-behavior: contain;
}
```

### Files Involved

**JavaScript:**
- `frontend/static/js/app.js`:
  - Lines 48-59: State initialization
  - Lines 2159-2163: Flash prevention (hide)
  - Lines 3721-3752: Font size application
  - Lines 4438-4465: Scroll-to-turn handler
  - Lines 4498-4499: Body overflow management
  - Lines 4525-4801: Complete pagination system
  - Lines 4845-4846: Cleanup on exit
  - Lines 5091-5092: Chapter navigation fix

**CSS:**
- `frontend/static/css/style.css`:
  - Lines 1708-1710: Removed hardcoded font-size from `.chapter-fulltext`
  - Lines 1709: Removed hardcoded font-size from `.chapter-modern-english`
  - Lines 2082: Removed hardcoded font-size from `.pagination-page-container`
  - Lines 4971-5220: Complete pagination styling

**HTML:**
- `frontend/templates/index.html`:
  - Line 652: Version v5.17

### Version History

| Version | Key Changes |
|---------|-------------|
| v5.3 | Font size controls fix |
| v5.4-v5.10 | Safety margin iterations (final: 0.2 after Math.ceil) |
| v5.11-v5.14 | Flash prevention fixes (final: section visibility) |
| v5.15-v5.17 | Chapter navigation fix (explicit existence check) |

### Known Limitations

1. **Not Character-Perfect:** Position restoration after recalculation is approximate (page-level, not character-level)
2. **No Mid-Paragraph Breaks:** Very long paragraphs may result in taller pages
3. **Font Loading:** System must wait for fonts to load before accurate measurement
4. **Print Mode:** Pagination disabled for printing (uses normal scroll)

### Future Enhancements

1. **Character-Level Position:** Track exact character offset for perfect position restoration
2. **Page Turn Animations:** Optional subtle transitions between pages
3. **Keyboard Shortcuts:** Additional shortcuts (Home, End, Page Up/Down)
4. **Touch Gestures:** More sophisticated gesture recognition
5. **Reading Statistics:** Track pages read, time per page, total reading time

---
