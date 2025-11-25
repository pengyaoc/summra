# Summra - Product Requirements Document

## Product Vision

Summra is a web application that makes classic literature accessible through AI-generated summaries of varying lengths. It helps readers explore public domain books quickly with concise overviews, comprehensive summaries, or detailed chapter-by-chapter analyses, enhanced with text-to-speech capabilities.

**Mission:** Democratize access to classic literature by providing high-quality, AI-generated summaries that help readers discover, understand, and appreciate great books.

## Target Users

### Primary Personas

**1. The Curious Reader**
- Wants to explore classic literature but has limited time
- Needs quick overviews to decide what to read in full
- Values spoiler-free summaries for fiction

**2. The Student**
- Studying classic literature for courses
- Needs comprehensive understanding of themes and plot
- Benefits from chapter-by-chapter breakdowns
- Uses summaries to supplement reading, not replace it

**3. The Lifelong Learner**
- Interested in classic non-fiction (philosophy, economics, history)
- Wants to understand key arguments and ideas
- Appreciates detailed analysis and context

**4. The Accessibility-Focused User**
- Benefits from text-to-speech for learning on-the-go
- May have visual impairments or reading difficulties
- Prefers audio summaries during commutes or exercise

## Core Features

### 1. Three Summary Lengths

**Feature Description:**
Users can choose from three different summary lengths to match their needs and available time.

**User Stories:**
- As a curious reader, I want a 500-word spoiler-free overview so I can decide if I want to read the full book
- As a student, I want a comprehensive 2000-3000 word summary so I can understand all major plot points and themes
- As a thorough learner, I want chapter-by-chapter summaries so I can deeply understand the structure and progression of the book

**Specifications:**

#### Concise Summary (500 words)
- **Length:** ~500 words
- **Content:** Main themes, setting, central conflict
- **Fiction:** No spoilers (no plot twists, endings, or major reveals)
- **Non-fiction:** Key arguments and main takeaways
- **Tone:** Engaging and accessible
- **Generation Time:** 30-60 seconds

#### Medium Summary (2000-3000 words)
- **Length:** 2000-3000 words
- **Content:** All major plot points, themes, character developments
- **Fiction:** Full spoilers acceptable
- **Non-fiction:** All main arguments, evidence, conclusions
- **Analysis:** Author's writing style and major themes
- **Generation Time:** 1-2 minutes

#### Comprehensive Summary (Chapter-by-Chapter)
- **Structure:** Individual summary for each chapter + overall analysis
- **Chapter Length:** Dynamic (min 200, max 2000 words per chapter)
- **Content per Chapter:**
  - Important events and dialogues
  - Character development and relationships
  - Key themes and symbols
  - Important quotes
  - How chapter advances narrative
- **Overall Analysis:** Connects all chapters and analyzes book as a whole
- **Generation Time:** 5-30 minutes (full book)

**UI Requirements:**
- Three clearly labeled option cards on book detail page
- Visual distinction between summary types
- Clear indication of which summary is currently selected
- Smooth transition when switching between summary types

**Acceptance Criteria:**
- [ ] User can select any of three summary types
- [ ] Selected summary type is visually highlighted
- [ ] Summary content updates immediately when selection changes
- [ ] Concise summaries contain no spoilers for fiction works
- [ ] Medium summaries are between 1800-3500 words
- [ ] Comprehensive view shows expandable chapter list

### 2. Text-to-Speech (TTS)

**Feature Description:**
Users can listen to any summary using high-quality text-to-speech conversion, enabling hands-free consumption and accessibility.

**User Stories:**
- As a commuter, I want to listen to summaries while driving so I can learn during my commute
- As a user with visual impairment, I want audio versions of summaries so I can access the content
- As a multitasker, I want to listen to summaries while doing other activities

**Specifications:**

**Audio Generation:**
- **Technology:** VITS open-source TTS model
- **Voice:** Female English speaker (default: p226)
- **Quality:** 22050 Hz, 16-bit WAV
- **Format:** Standard HTML5 audio playback
- **Caching:** Generated audio is cached permanently for instant replay
- **Limit:** First 5000 characters of summary

**Playback Controls:**
- Play/Pause button
- Audio progress bar
- Volume control (browser native)
- Speed control (planned)
- Download option (planned)

**UI Requirements:**
- "Listen to Summary" button prominently displayed
- Audio player appears when TTS is generated
- Loading indicator during audio generation
- Clear error messages if generation fails
- Player persists across page navigation (planned)

**Acceptance Criteria:**
- [ ] User can click "Listen" on any summary
- [ ] Audio generation starts within 2 seconds
- [ ] First-time generation completes within 30 seconds
- [ ] Cached audio loads instantly (<1 second)
- [ ] Audio player has play/pause controls
- [ ] User can see audio progress
- [ ] Audio quality is clear and natural-sounding
- [ ] System handles long summaries (>5000 chars) gracefully

### 3. Book Discovery and Browsing

**Feature Description:**
Users can browse a curated collection of classic books with cover images and metadata.

**User Stories:**
- As a reader, I want to see book covers so I can visually browse the collection
- As a user, I want to see author names and titles so I can find books I'm interested in
- As a browser, I want an attractive interface so browsing feels enjoyable

**Specifications:**

**Book Grid:**
- **Layout:** Responsive card-based grid
- **Cards Include:**
  - Cover image (Project Gutenberg or custom)
  - Book title
  - Author name
  - Word count (optional)
- **Interaction:** Click card to open book details
- **Responsive:** Adapts to mobile, tablet, desktop

**Book Detail Page (Redesigned 2025-11-25):**
- **Minimal Header:** Smaller cover image (120px) with title and author side-by-side
- **Quick Summary:** Concise summary shown by default with inline Listen button
- **Detailed Overview Preview:** Medium summary with fade effect (300px max height)
  - Shows full formatted text with gradient fade at bottom
  - "Read Full Summary →" link navigates to dedicated page
  - No layout shift when expanding
- **Chapter Navigation:** Full-width chapter boxes (one per row)
  - 4px blue left border for visual accent
  - Hover effects (slide right, light blue background)
  - Click to navigate to dedicated chapter page
- **No Option Cards:** Removed to reduce visual clutter

**UI Requirements:**
- Professional, clean design
- High-quality cover images
- Clear typography
- Smooth animations
- Loading states for images

**Acceptance Criteria:**
- [ ] All books display with cover images
- [ ] Cover images load progressively
- [ ] Missing covers show placeholder
- [ ] Grid is responsive on all screen sizes
- [ ] Click on book opens detail view
- [ ] Back button returns to library

### 4. URL Routing and Navigation

**Feature Description:**
Each book and summary type has a unique URL that can be bookmarked and shared.

**User Stories:**
- As a user, I want to bookmark a specific summary so I can return to it later
- As a student, I want to share a book summary URL with classmates
- As a browser, I want the back button to work intuitively

**Specifications:**

**URL Structure:**
```
/                                    → Home page (book library)
/#/book/alice-in-wonderland          → Book overview (concise + medium preview + chapters)
/#/book/alice-in-wonderland/medium   → Full medium summary page
/#/book/alice-in-wonderland/chapter/3 → Individual chapter page (chapter 3)
```

**Navigation:**
- Hash-based routing (no server-side routing needed)
- Browser back/forward buttons work correctly
- Page refresh preserves current view
- URL updates when user navigates

**Acceptance Criteria:**
- [ ] Each book has a unique URL slug
- [ ] URL includes selected summary type
- [ ] Refreshing page loads correct book and summary
- [ ] Back button navigates through history correctly
- [ ] Forward button works as expected
- [ ] URLs can be bookmarked
- [ ] URLs can be shared and open correctly

### 5. Chapter Navigation (Redesigned 2025-11-25)

**Feature Description:**
Users can navigate to dedicated pages for each chapter, with full text displayed and summary protected from spoilers.

**User Stories:**
- As a student, I want to jump to specific chapters so I can focus on relevant sections
- As a reader, I want to avoid spoilers, so chapter summaries should be hidden by default
- As a learner, I want to see chapter titles so I can understand book structure
- As a user, I want to read full chapter text while having summary available if needed

**Specifications:**

**Chapter List (Book Overview):**
- **Structure:** Vertical list of full-width chapter boxes (one per row)
- **Styling:** White background, 4px blue left border, subtle hover effects
- **Chapter Box Includes:**
  - Chapter number and title combined (e.g., "3. The Time Traveller Returns")
  - Hover: Light blue background, slide right animation, subtle shadow
- **Spacing:** 12px gap between boxes
- **Interaction:** Click box to navigate to dedicated chapter page

**Chapter Detail Page:**
- **Navigation:** Accessible via `#/book/{slug}/chapter/{num}`
- **Auto-scroll:** Page scrolls to top on navigation
- **Layout:**
  - White background card with 32px padding
  - Collapsed chapter summary box (yellow/beige, "may contain spoilers" warning)
  - Full chapter text section below summary
  - Inline TTS buttons for both summary and full text
- **Summary Toggle:**
  - Default: Collapsed to protect from spoilers
  - Click "Show Summary" to expand
  - Click "Hide Summary" to collapse again

**UI Requirements:**
- Clear visual hierarchy
- Consistent spacing and typography (1.75 line-height)
- Mobile-friendly tap targets (44x44 minimum)
- Smooth page transitions
- White reading background for better readability
- Automatic scroll to top on chapter navigation

**Acceptance Criteria:**
- [✅] Chapter boxes displayed one per row
- [✅] Click chapter box navigates to dedicated page
- [✅] Page scrolls to top on navigation
- [✅] Chapter summary collapsed by default
- [✅] User can toggle summary visibility
- [✅] Full chapter text always visible
- [✅] Individual TTS buttons for summary and full text
- [✅] Back button returns to book overview
- [✅] Browser back/forward work correctly

## User Workflows

### Workflow 1: Discovering a New Book (Updated 2025-11-25)

```
1. User lands on home page
2. User browses book grid with cover images
3. User clicks on interesting book cover
4. User arrives at book overview page showing:
   - Quick Summary (concise, 500 words, no spoilers)
   - Detailed Overview preview (first ~300px of medium summary with fade)
   - Chapter boxes (one per row, full width)
5. User reads concise summary
6. User scrolls to see medium preview (first ~200 words visible with fade)
7. User decides:
   - Want more detail → clicks "Read Full Summary →" (navigates to medium page)
   - Want specific chapter → clicks chapter box (navigates to chapter page)
   - Not interested → back to library
```

### Workflow 2: Studying a Book in Depth (Updated 2025-11-25)

```
1. User searches for specific book in library
2. User opens book overview page
3. User scrolls to chapters section
4. User clicks "Chapter 1" box to navigate to dedicated chapter page
5. Page scrolls to top automatically
6. User sees:
   - Collapsed chapter summary box (yellow warning: may contain spoilers)
   - Full chapter text displayed below
7. User reads full chapter text
8. If needed, user clicks "Show Summary" to reveal chapter summary
9. User clicks "Listen" to hear either summary or full text
10. User clicks "Back to Book" to return to overview
11. User clicks next chapter box to continue
12. Browser back/forward buttons work correctly
```

### Workflow 3: Quick Reference

```
1. User has bookmarked URL to specific book/summary
2. User clicks bookmark
3. App loads directly to bookmarked view
4. User reads/listens to summary
5. User closes tab when done
```

### Workflow 4: Listening While Commuting

```
1. User opens saved book on mobile device
2. User selects medium summary
3. User clicks "Listen to Summary"
4. User waits ~10 seconds for audio generation
5. User presses play on audio player
6. User listens while driving/walking
7. User pauses when needed
8. Audio player persists across page navigation (planned)
```

## Non-Functional Requirements

### Performance
- **Page Load:** < 2 seconds on 3G connection
- **Summary Switch:** < 500ms to switch between summary types
- **TTS Generation:** < 30 seconds for first generation
- **Cached TTS:** < 1 second to load
- **Image Loading:** Progressive with lazy loading

### Accessibility
- **ARIA Labels:** All interactive elements properly labeled
- **Keyboard Navigation:** Full keyboard support
- **Screen Readers:** Compatible with major screen readers
- **Color Contrast:** WCAG AA compliant
- **Text-to-Speech:** Core accessibility feature
- **Responsive Text:** Scales appropriately on mobile

### Usability
- **Learning Curve:** < 2 minutes for new users
- **Error Messages:** Clear, actionable, non-technical
- **Loading States:** Clear feedback during async operations
- **Mobile-Friendly:** Touch targets ≥ 44x44 pixels

### Browser Support
- **Chrome:** Last 2 versions
- **Firefox:** Last 2 versions
- **Safari:** Last 2 versions
- **Edge:** Last 2 versions
- **Mobile Safari:** iOS 13+
- **Chrome Mobile:** Android 8+

## Feature Roadmap

### Phase 1: Core Features (COMPLETED)
- ✅ Three summary lengths
- ✅ Book library with covers
- ✅ Text-to-speech generation
- ✅ Chapter-by-chapter summaries
- ✅ Project Gutenberg integration
- ✅ Responsive web design

### Phase 2: Enhanced UX (COMPLETED - 2025-11-25)
- ✅ URL routing for books, summaries, and chapters
- ✅ BeFreed-inspired minimal UI redesign
- ✅ Removed unnecessary bounding boxes
- ✅ Content-first presentation
- ✅ Separate pages for medium summary and chapters
- ✅ Chapter summary collapsed by default (spoiler protection)
- ✅ Scroll to top on page navigation
- ⏳ Persistent audio player (stays across navigation) - PARTIAL (player exists but resets on navigation)

### Phase 3: Full-Length Option (PLANNED)
- 📋 Display full chapter text (collapsible)
- 📋 Summary + full text side-by-side option
- 📋 Search within full text
- 📋 Highlighting and annotations

### Phase 4: Advanced Features (FUTURE)
- 📋 User accounts and authentication
- 📋 Favorites and reading lists
- 📋 Reading progress tracking
- 📋 Search across all books
- 📋 Book recommendations
- 📋 Multiple TTS voices
- 📋 Playback speed control
- 📋 Download summaries as PDF
- 📋 Export to EPUB for e-readers
- 📋 Offline mode support
- 📋 Social sharing features
- 📋 Comments and discussions

### Phase 5: Content Expansion (FUTURE)
- 📋 Multi-language support
- 📋 Author biographies
- 📋 Historical context sections
- 📋 Character analysis
- 📋 Theme exploration
- 📋 Related book suggestions
- 📋 Custom book uploads (user-provided)

## Success Metrics

### User Engagement
- **Daily Active Users (DAU)**
- **Average Session Duration:** Target > 10 minutes
- **Books per User:** Target > 3 books browsed per session
- **Return Rate:** Target > 40% weekly return

### Feature Usage
- **Summary Type Distribution:**
  - Concise: 40-50% of views
  - Medium: 30-40% of views
  - Comprehensive: 20-30% of views
- **TTS Usage:** Target > 25% of summaries listened to
- **Chapter Expansion:** Average 5+ chapters expanded per comprehensive view

### Performance
- **Page Load Time:** < 2 seconds (90th percentile)
- **TTS Success Rate:** > 95% successful generations
- **Error Rate:** < 1% of requests

### Quality
- **User Satisfaction:** Target > 4.0/5.0 rating
- **Summary Accuracy:** No factual errors reported
- **Audio Quality:** > 90% users rate audio as "good" or "excellent"

## Design Principles

### 1. Simplicity First
- Minimize clicks to access content
- Clear visual hierarchy
- No unnecessary features or options
- Progressive disclosure of complexity

### 2. Content-Focused
- Text is the hero
- Minimal distractions
- Clean, readable typography
- Ample white space

### 3. Accessibility by Default
- TTS as core feature, not afterthought
- Keyboard navigation throughout
- Screen reader friendly
- High contrast, readable fonts

### 4. Fast and Responsive
- Instant feedback on interactions
- Progressive loading
- Cached content for speed
- Mobile-first responsive design

### 5. Trustworthy
- Accurate summaries
- Clear attribution
- No misleading information
- Transparent about AI generation

## Open Questions

### Content Quality
- Q: How do we measure summary quality?
- A: User feedback, spot-checks, comparison with professional summaries

### Monetization
- Q: Will this be a free or paid service?
- A: Free for personal use; potential premium tier for features like bulk downloads, API access

### Content Rights
- Q: Are we sure all books are public domain?
- A: Only use Project Gutenberg books (verified public domain in US)

### User Accounts
- Q: Do we need user accounts?
- A: Phase 4 feature; start with local bookmarks/favorites using localStorage

## Dependencies

### External Services
- **Google Gemini API:** Required for summary generation
  - Rate limits: 10 req/min, 250k tokens/min
  - Cost: ~$0.05-0.15 per book
- **Project Gutenberg:** Source for books and cover images
  - Free, public domain
  - No API key required

### Technical Stack
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Backend:** Python Flask
- **Database:** SQLite
- **TTS:** Coqui TTS (VITS model)
- **Hosting:** Self-hosted or cloud (TBD)

## Risk Assessment

### Technical Risks
- **API Rate Limits:** Mitigated by intelligent rate limiting
- **TTS Model Size:** ~100MB download on first use
- **Database Scaling:** SQLite handles thousands of books; migrate to PostgreSQL if needed

### Content Risks
- **Summary Quality:** Mitigated by using advanced models and spot-checking
- **Copyright Issues:** Mitigated by using only verified public domain books
- **Offensive Content:** Classic books may contain outdated/offensive language

### User Experience Risks
- **Slow TTS Generation:** Mitigated by caching and background generation
- **Missing Book Covers:** Mitigated by fallback to custom covers
- **Complex Books:** Some structures may not parse correctly; manual review needed

## Appendix

### Glossary
- **Concise Summary:** 500-word overview without spoilers
- **Medium Summary:** 2000-3000 word comprehensive summary
- **Comprehensive Summary:** Chapter-by-chapter analysis
- **TTS:** Text-to-Speech conversion to audio
- **Project Gutenberg:** Digital library of public domain books
- **VITS:** Variational Inference Text-to-Speech model

### References
- Project Gutenberg: https://www.gutenberg.org/
- WCAG Accessibility Guidelines: https://www.w3.org/WAI/WCAG21/quickref/
- Google Gemini API: https://ai.google.dev/
- Coqui TTS: https://github.com/coqui-ai/TTS

---

**Document Version:** 1.1
**Last Updated:** 2025-11-25
**Author:** Summra Team
**Status:** Living Document
