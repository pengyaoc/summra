# Reading Progress Integration Guide

This document explains how to integrate the user authentication and reading progress tracking features into the existing app.js code.

## Overview

The reading progress system tracks:
- Which chapter the user is currently reading
- What page they're on (for paginated views)
- Which chapters have been completed
- Works offline and syncs when user logs in

## API Integration Points

### 1. Track Chapter Views

When a user navigates to a chapter, track their progress:

```javascript
// In showChapterDetail() or similar function
async showChapterDetail(book, chapterNum) {
    // ... existing code to render chapter ...

    // Track that user viewed this chapter
    if (window.authModule && book.id) {
        await window.authModule.trackChapterView(book.id, chapterNum, 0);
    }

    // ... rest of code ...
}
```

### 2. Track Page Changes (Pagination)

When using the pagination system and the page changes:

```javascript
// In pagination page change handler
function changePage(newPage) {
    currentPage = newPage;

    // Track page change
    if (window.authModule && currentBook && currentChapter) {
        window.authModule.trackPageChange(
            currentBook.id,
            currentChapter,
            currentPage
        );
    }

    // ... render new page ...
}
```

### 3. Mark Chapter as Complete

When user reaches the last page of a chapter or reads to the end:

```javascript
// In pagination or scroll handler
if (isLastPage || hasReachedEnd) {
    if (window.authModule && currentBook && currentChapter) {
        await window.authModule.onChapterComplete(
            currentBook.id,
            currentChapter
        );
    }
}
```

### 4. Resume Reading Position

When loading a book or chapter, restore the last read position:

```javascript
// When loading book detail page
async loadBookDetail(bookId) {
    // ... fetch book data ...

    // Get last read position
    if (window.authModule) {
        const progress = await window.authModule.getLastReadPosition(bookId);

        if (progress) {
            console.log(`Last read: Chapter ${progress.chapter_number}, Page ${progress.page_number}`);

            // Optionally auto-navigate to last chapter
            // navigateToChapter(progress.chapter_number);
        }
    }
}
```

### 5. Display Completed Chapters

When rendering chapter list, mark completed chapters:

```javascript
// When rendering chapter list
async renderChapterList(bookId, chapters) {
    // Get completed chapters
    let completedChapters = [];
    if (window.authModule) {
        completedChapters = await window.authModule.getCompletedChaptersForBook(bookId);
    }

    chapters.forEach(chapter => {
        const isCompleted = completedChapters.includes(chapter.chapter_number);

        // Add 'completed' class to chapter box
        const chapterBox = document.createElement('div');
        chapterBox.className = 'chapter-box' + (isCompleted ? ' completed' : '');

        // ... render chapter content ...
    });
}
```

### 6. Auto-scroll to Last Position

After rendering chapter content, scroll to last read position:

```javascript
// After chapter content is rendered
async showChapterDetail(book, chapterNum) {
    // ... render chapter content ...

    // Get progress and scroll to last position
    if (window.authModule) {
        const progress = await window.authModule.getReadingProgress(book.id);

        if (progress && progress.chapter_number === chapterNum) {
            window.authModule.scrollToLastPosition(progress.scroll_position);
        }
    }
}
```

## User Authentication

### Check if User is Logged In

```javascript
// Check auth status
if (window.authModule) {
    const user = window.authModule.currentUser();

    if (user) {
        console.log('Logged in as:', user.username);
        // Progress will be saved to server
    } else {
        console.log('Not logged in');
        // Progress will be saved to local storage
    }
}
```

### Force Sync

When user logs in, progress is automatically synced. You can also manually trigger sync:

```javascript
if (window.authModule) {
    await window.authModule.syncOfflineProgress();
}
```

## CSS Classes

The following CSS classes are available:

- `.completed` - Add to `.chapter-box` to mark as completed
- `.reading-progress-summary` - Progress summary card
- `.chapter-progress-badge` - Small badge showing "Completed" or progress

## Example: Complete Integration

```javascript
// Complete example of integrating progress tracking

class BookReader {
    constructor() {
        this.currentBook = null;
        this.currentChapter = null;
        this.currentPage = 0;
    }

    async loadBook(bookId) {
        // Fetch book data
        const book = await this.fetchBook(bookId);
        this.currentBook = book;

        // Get last read position
        if (window.authModule) {
            const progress = await window.authModule.getLastReadPosition(bookId);

            if (progress) {
                // Auto-navigate to last chapter
                await this.loadChapter(progress.chapter_number, progress.page_number);
            }
        }

        // Render chapter list with completed indicators
        await this.renderChapterList();
    }

    async loadChapter(chapterNum, pageNum = 0) {
        // Fetch chapter data
        const chapter = await this.fetchChapter(this.currentBook.id, chapterNum);
        this.currentChapter = chapterNum;
        this.currentPage = pageNum;

        // Render chapter
        this.renderChapter(chapter);

        // Track chapter view
        if (window.authModule && this.currentBook) {
            await window.authModule.trackChapterView(
                this.currentBook.id,
                chapterNum,
                pageNum
            );
        }
    }

    async changePage(newPage) {
        this.currentPage = newPage;
        this.renderPage(newPage);

        // Track page change
        if (window.authModule && this.currentBook && this.currentChapter !== null) {
            await window.authModule.trackPageChange(
                this.currentBook.id,
                this.currentChapter,
                newPage
            );
        }

        // Check if last page
        if (this.isLastPage(newPage)) {
            await this.onChapterComplete();
        }
    }

    async onChapterComplete() {
        if (window.authModule && this.currentBook && this.currentChapter !== null) {
            await window.authModule.onChapterComplete(
                this.currentBook.id,
                this.currentChapter
            );

            // Update UI to show chapter as completed
            this.markChapterCompleted(this.currentChapter);
        }
    }

    async renderChapterList() {
        // Get completed chapters
        let completedChapters = [];
        if (window.authModule && this.currentBook) {
            completedChapters = await window.authModule.getCompletedChaptersForBook(
                this.currentBook.id
            );
        }

        // Render chapters with completed indicators
        this.chapters.forEach(chapter => {
            const isCompleted = completedChapters.includes(chapter.chapter_number);

            const element = this.createChapterElement(chapter, isCompleted);
            this.chapterListContainer.appendChild(element);
        });
    }

    createChapterElement(chapter, isCompleted) {
        const box = document.createElement('div');
        box.className = 'chapter-box' + (isCompleted ? ' completed' : '');
        box.innerHTML = `
            <h3 class="chapter-title">${chapter.chapter_number}. ${chapter.title}</h3>
        `;
        return box;
    }

    markChapterCompleted(chapterNum) {
        const chapterBox = document.querySelector(`[data-chapter="${chapterNum}"]`);
        if (chapterBox) {
            chapterBox.classList.add('completed');
        }
    }
}
```

## Testing

### Test User Registration and Login

1. Click "Account" button in header
2. Click "Create one" to register
3. Enter username (min 3 chars) and password (min 6 chars)
4. Click "Create Account"
5. Should be logged in automatically

### Test Progress Tracking

1. Log in as a user
2. Navigate to a book
3. Open a chapter
4. Read to the end or manually trigger completion
5. Go back to book detail page
6. Chapter should show as completed with checkmark

### Test Offline Mode

1. Open a book while logged in
2. Read some chapters
3. Log out
4. Continue reading (progress saved to local storage)
5. Log back in
6. Progress should sync automatically

### Test Cross-Device Sync

1. Log in on device A
2. Read some chapters
3. Log in on device B with same account
4. Should see same progress (completed chapters, last read position)

## Troubleshooting

### Progress not saving

- Check browser console for errors
- Verify user is logged in or local storage is enabled
- Check network tab for failed API calls

### Completed chapters not showing

- Verify `getCompletedChaptersForBook()` is called
- Check that chapter numbers match between tracking and rendering
- Inspect CSS classes applied to chapter elements

### Sync not working

- Check that user is authenticated
- Verify `/api/progress/sync` endpoint is accessible
- Check for CORS issues if frontend/backend on different domains

## Database Schema Reference

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

### Reading Progress Table
```sql
CREATE TABLE reading_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    page_number INTEGER DEFAULT 0,
    scroll_position INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id)
);
```

### Chapter Completion Table
```sql
CREATE TABLE chapter_completion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    completed INTEGER DEFAULT 0,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id, chapter_number)
);
```

## API Endpoints

All endpoints require authentication (session cookie) except where noted.

### Authentication
- `POST /api/auth/register` - Create new user account
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/check` - Check auth status (no auth required)
- `GET /api/auth/me` - Get current user info

### Reading Progress
- `POST /api/progress/save` - Save reading progress
- `GET /api/progress/get/<book_id>` - Get progress for book
- `GET /api/progress/all` - Get all progress for user
- `POST /api/progress/chapter/complete` - Mark chapter complete/incomplete
- `GET /api/progress/chapters/<book_id>` - Get completed chapters
- `POST /api/progress/sync` - Sync offline progress

## Security Notes

- Passwords are hashed with SHA-256 + salt
- Sessions use secure cookies with HttpOnly flag
- CORS is enabled with credentials support
- In production, set SESSION_COOKIE_SECURE=True for HTTPS

## Future Enhancements

- Reading statistics (total time, pages read, etc.)
- Reading streaks and achievements
- Social features (share progress, reading lists)
- Export reading history
- Reading goals and reminders
