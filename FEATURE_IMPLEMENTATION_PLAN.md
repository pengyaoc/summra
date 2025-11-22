# Feature Implementation Plan

## 1. Persistent Playback Control ⭐ HIGH PRIORITY

### Requirements:
- Fixed audio player at bottom of page
- Persists across book/summary navigation
- Pause/Play controls
- Stop button (cancels TTS generation)
- Shows current playing track

### Implementation:
**Frontend** (`app.js`):
- Move audio player outside summary-content (fixed position)
- Add global playback state management
- Pause/Play/Stop controls
- Display current book/chapter being played

**Backend** (`app.py`):
- Add `/api/tts/stop` endpoint
- Kill background TTS generation threads
- Return success status

**CSS** (`style.css`):
- Fixed position bottom: 0
- z-index to stay on top
- Slide-up animation

## 2. URL Routing for Books ⭐ HIGH PRIORITY

### Requirements:
- Each book has URL: `/#/book/{slug}/summary/{type}`
- Refresh preserves state
- Browser back/forward works

### Implementation:
**Frontend** (`app.js`):
- Use hash-based routing (`#/book/alice-in-wonderland`)
- Parse URL on page load
- Update URL on navigation
- Handle browser back/forward

**URL Format**:
```
/                           → Home page (book list)
/#/book/alice-in-wonderland → Book page (default: concise)
/#/book/alice-in-wonderland/medium → Specific summary
```

## 3. Comprehensive Summary UX Improvements

### Requirements:
- Overview same level as chapters (same font/styling)
- Overview default collapsed
- Remove "Chapter Summaries" header
- Individual "Listen" button per section

### Changes:
**HTML Template** (`index.html`):
- Remove separate `.overall-summary` class
- Make overview a chapter-item
- Remove "Chapter Summaries" heading

**JavaScript** (`app.js`):
- Overview default collapsed (not expanded)
- Add TTS button to each chapter
- Each section plays independently

**CSS** (`style.css`):
- Unified chapter styling
- No special `.overall-summary` rules

## 4. Full-Length Option

### Requirements:
- New option: "Full Length"
- Shows actual chapter text (collapsable)
- Summary above full text (collapsed by default)
- Like comprehensive view structure

### Implementation:
**Backend**:
- Store full chapter text in DB
- New API endpoint for full-length view
- Return chapter summaries + full text

**Frontend**:
- New option card: "Full Length"
- Display format:
  ```
  Chapter 1: Title
    [▼] Summary (collapsed)
    [▼] Full Text (expanded)
  ```

**Database**:
- Add `full_text` column to chapters table
- Populate during summary generation

## Implementation Order

1. ✅ **Persistent Playback Control** (1-2 hours)
   - Critical for UX
   - Fixes current TTS issues

2. ✅ **URL Routing** (1 hour)
   - Important for usability
   - Relatively simple

3. ✅ **Comprehensive UX** (30 min)
   - Quick CSS/HTML changes
   - Big UX improvement

4. ✅ **Full-Length Option** (2 hours)
   - Requires DB changes
   - Most complex feature

## Files to Modify

### Frontend:
- `frontend/templates/index.html` - Add persistent player, full-length option
- `frontend/static/js/app.js` - Routing, playback control, full-length display
- `frontend/static/css/style.css` - Fixed player, unified chapter styling

### Backend:
- `backend/app.py` - Stop endpoint, full-length API
- `backend/models.py` - Chapter full text storage
- `scripts/generate_summaries.py` - Store full chapter text

### Database:
- Migration to add `full_text` to chapters table

## Testing Checklist

- [ ] Audio player persists across navigation
- [ ] Pause/Play/Stop controls work
- [ ] Stop cancels TTS generation
- [ ] URLs work on refresh
- [ ] Browser back/forward works
- [ ] Overview collapsed by default
- [ ] Each section has own Listen button
- [ ] Full-length option displays
- [ ] Chapter text is collapsable
- [ ] Summary collapsed by default in full-length
