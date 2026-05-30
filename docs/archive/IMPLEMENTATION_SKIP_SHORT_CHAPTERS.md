# Implementation: Skip Summary for Short Chapters (<200 words)

## Changes Required

### 1. Backend: scripts/content/generate_summaries.py

**In `generate_comprehensive_summary` method (line ~2040):**

Add filtering logic BEFORE bulk/single processing:

```python
# Filter chapters by word count - separate long and short chapters
MIN_WORDS_FOR_SUMMARY = 200
chapters_needing_summary = []
short_chapters = []

for chapter_num, chapter_title, chapter_text in chapters_to_process:
    word_count = len(chapter_text.split())
    if word_count >= MIN_WORDS_FOR_SUMMARY:
        chapters_needing_summary.append((chapter_num, chapter_title, chapter_text))
    else:
        short_chapters.append((chapter_num, chapter_title, chapter_text, word_count))
        print(f"  Skipping summary for Chapter {chapter_num}: {chapter_title} ({word_count} words - too short)")

# Process chapters needing summaries (existing bulk/single logic)
if chapters_needing_summary:
    use_bulk = config.BULK_SUMMARY_CONFIG['enabled'] and not partial_run
    # ... existing processing code uses chapters_needing_summary instead of chapters_to_process

# Save short chapters to DB with NULL/empty summary
for chapter_num, chapter_title, chapter_text, word_count in short_chapters:
    chapter_summaries.append({
        'chapter_number': chapter_num,
        'chapter_title': chapter_title,
        'summary': '',  # Empty summary
        'word_count': 0
    })

    # Save to database with empty summary
    if not dry_run and not partial_run and book_id is not None:
        self.db.add_chapter(
            book_id,
            chapter_num,
            chapter_title,
            '',  # Empty summary - frontend will show full text instead
            chapter_text  # Still save full chapter text
        )
        print(f"  ✓ Saved Chapter {chapter_num} to database (no summary - {word_count} words)")
```

### 2. Frontend: frontend/static/js/app.js

**In `displayChapterDetail` method (line ~684):**

Add check for empty/null summary and hide summary block:

```javascript
// Load summary (collapsed by default) - or hide if empty
const summaryText = document.getElementById('chapter-summary-text');
const summarySection = document.getElementById('chapter-summary-section');  // Add wrapper ID to HTML
const summaryToggleBtn = document.getElementById('toggle-summary-btn');
const summaryTtsBtn = document.getElementById('chapter-summary-tts-button');

if (!chapter.summary || chapter.summary.trim() === '') {
    // No summary available - hide entire summary section
    if (summarySection) {
        summarySection.style.display = 'none';
    }
} else {
    // Summary available - show and populate
    if (summarySection) {
        summarySection.style.display = '';
    }
    summaryText.innerHTML = this.renderMarkdown(chapter.summary);

    // Setup toggle button (existing code)
    const summaryContent = document.getElementById('chapter-summary-content');
    let isSummaryExpanded = false;

    summaryToggleBtn.onclick = () => {
        if (isSummaryExpanded) {
            summaryContent.classList.add('hidden');
            summaryToggleBtn.textContent = '▼ Show Summary';
            isSummaryExpanded = false;
        } else {
            summaryContent.classList.remove('hidden');
            summaryToggleBtn.textContent = '▲ Hide Summary';
            isSummaryExpanded = true;
        }
    };

    // Setup summary TTS button
    summaryTtsBtn.onclick = () => {
        this.generateChapterTTS(chapter.chapter_number, chapter.summary, summaryTtsBtn, 'summary');
    };
}
```

### 3. Frontend: HTML Template Update

**In frontend/templates/index.html:**

Wrap the summary section in a container with ID:

```html
<!-- Add wrapper div with ID -->
<div id="chapter-summary-section">
    <!-- Chapter Summary (collapsible) -->
    <div class="mb-4">
        <button id="toggle-summary-btn" class="text-blue-600 hover:text-blue-800 flex items-center gap-2 mb-2">
            <span>▼ Show Summary</span>
        </button>
        <div id="chapter-summary-content" class="hidden bg-gray-50 p-4 rounded">
            <div id="chapter-summary-text" class="text-gray-700 whitespace-pre-wrap"></div>
        </div>
    </div>
</div>
```

## Testing

Run dry-run on Peter Pan (has short preface chapter of 63 words):

```bash
source venv/bin/activate && python scripts/content/generate_summaries.py /tmp/pg16.txt --title "Peter Pan" --author "J. M. Barrie" --dry-run
```

Expected output should show:
```
Skipping summary for Chapter 0: Preface (63 words - too short)
```

## Summary

- Backend: Filter chapters < 200 words before summarization
- Save filtered chapters to DB with empty summary
- Frontend: Check for empty summary and hide entire summary block
- Full chapter text still displayed as usual
- No API calls wasted on very short chapters
