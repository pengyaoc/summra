# Summra - Product Requirements Document

## Product Vision

Summra makes public-domain classics easier to read. The headline feature is a **sentence-by-sentence rewrite of every chapter into modern English**, displayed side-by-side with the original. Summaries (short and full), chapter-by-chapter breakdowns, AI illustrations, and audio narration round out the experience.

**Mission:** Democratize access to classic literature by removing the language barrier — translating Victorian, Romantic, and Enlightenment-era prose into the English a modern reader actually speaks, while preserving the original.

**Positioning (as it appears on the site):** *"Read the Classics in Plain English — every classic, rewritten sentence-by-sentence into modern English. Read side-by-side with the original, or just the plain version. Free."*

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
- **Narrative Continuity (Added 2025-11-28):**
  - Each batch of chapters receives context from the previous batch's last chapter
  - Improves plot thread tracking across batch boundaries
  - Better character arc continuity in sequential narratives
  - Example: When summarizing Chapters 6-10, AI receives Chapter 5 text for context
- **Overall Analysis:** Connects all chapters and analyzes book as a whole
- **Generation Time:** 5-30 minutes (full book)

**UI Requirements:**
- Tab interface for Short Summary and Full Summary on book detail page (Updated 2025-12-03)
- Tab labels: "Short Summary" and "Full Summary" (formerly "500-word Summary" and "2000-word Summary")
- "Read more" expand button for both summary previews (Updated 2025-12-03)
- Visual distinction between summary types
- Clear indication of which summary is currently selected
- Smooth transition when switching between summary types
- Short Summary preview collapsed at 300px height with expand/collapse toggle
- Full Summary preview with fade effect and "Read more" button to full page view

**Acceptance Criteria:**
- [✅] User can select between Short Summary and Full Summary tabs
- [✅] Selected summary type is visually highlighted
- [✅] Summary content updates immediately when selection changes
- [✅] Concise summaries contain no spoilers for fiction works
- [✅] Medium summaries are between 1800-3500 words
- [✅] Comprehensive view shows expandable chapter list
- [✅] "Read more" button text consistent across all summary views (2025-12-03)
- [✅] Short Summary expand/collapse toggles with consistent button text (2025-12-03)

### 2. Text-to-Speech (TTS)

**Feature Description:**
Users can listen to any summary using high-quality text-to-speech conversion, enabling hands-free consumption and accessibility.

**User Stories:**
- As a commuter, I want to listen to summaries while driving so I can learn during my commute
- As a user with visual impairment, I want audio versions of summaries so I can access the content
- As a multitasker, I want to listen to summaries while doing other activities

**Specifications:**

**Audio Generation:**
- **Technology:** Google Gemini 2.5 Flash TTS API (the original local Coqui/VITS handler was removed)
- **Voice:** Configurable in `backend/config.py` — `GEMINI_TTS_VOICE` (default: `Kore`; options: Puck, Charon, Kore, Fenrir, Aoede, Sulafat)
- **Quality:** 24 kHz WAV (Gemini default), stitched from chunked requests
- **Format:** Standard HTML5 audio playback
- **Caching:** Generated audio is cached on disk under `frontend/static/audio/` and reused indefinitely
- **Dev vs prod split:**
  - Dev (`backend/app.py`) generates audio on demand via the Gemini API
  - Prod (`backend/app_prod.py`) only **serves** pre-generated audio — TTS generation is disabled to keep the production VM small
  - Bulk pre-generation lives in `scripts/audio/` (`batch_generate_concise_audio.py`, `batch_generate_medium_audio.py`, `generate_gemini_audio_batch_offline.py`)
- **Limit:** Long inputs are chunked (~900 words per request) and the WAVs are stitched together

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
Users can browse a curated collection of classic books with cover images and metadata using category-based carousels and grid views.

**User Stories:**
- As a reader, I want to see book covers so I can visually browse the collection
- As a user, I want to see author names and titles so I can find books I'm interested in
- As a browser, I want an attractive interface so browsing feels enjoyable
- As a curious reader, I want to explore books by category so I can discover books in genres I enjoy
- As a user, I want to navigate between carousel and grid views so I can choose my preferred browsing style

**Specifications:**

**Home Page Layout (Redesigned 2025-11-28, Updated 2025-12-06):**
- **Hero Section (Added 2025-12-06):**
  - Full-width gradient background (purple to violet: #667eea to #764ba2)
  - Large headline: "Classic Literature, Made Easy"
  - Subtitle: "Everything you need to discover, learn, and read the classics — completely free"
  - **Three Vertically Stacked Section Cards:**

    **1. Discover** 🔍 (Focus: Quick Preview & Audio)
    - Find your next classic in minutes with quick summaries and audio narration
    - Features:
      - Quick summaries to preview any book
      - Audio narration for on-the-go listening
      - Browse by genre, era, and author
    - CTA: "Explore Categories →" (navigates to #/categories)

    **2. Learn** 📚 (Focus: Deep Understanding)
    - Deep dive into classics with comprehensive summaries and visual guides
    - Features:
      - Comprehensive summaries with deep analysis
      - Visual guides for themes, characters & timeline
      - Chapter-by-chapter breakdowns
    - CTA: "See Example: Great Expectations →" (navigates to Great Expectations book page)

    **3. Read** 📖 (Focus: Premium Reading Experience)
    - Enjoy a premium Kindle-like reading experience with modern features
    - Features:
      - Plain English translations side-by-side with original
      - Customizable fonts, sizes & color themes
      - Distraction-free reading mode
    - CTA: "Try Reading: Jane Eyre Chapter 1 →" (navigates to Jane Eyre Chapter 1)
      - Desktop: Opens in side-by-side view (original + modern English)
      - Mobile: Opens in modern English view (screen too narrow for side-by-side)

  - **Design Elements:**
    - Vertical stack layout (not horizontal grid)
    - Large icon (3rem) on left, content on right
    - Glass-morphism cards with backdrop blur and subtle border
    - Checkmark bullet points (✓) for feature lists
    - Individual CTA buttons for each section (aligned with content)
    - Hover effects: cards slide right with background brightening
  - Responsive design: smaller fonts and tighter spacing on mobile
  - Only visible on home page (hidden on book detail and other pages)

- **Top 10 Books Carousel (Added 2025-12-08):**
  - **Location:** Embedded in the "Discover" hero banner section
  - **Design:** Netflix-style horizontal carousel with overlay navigation
  - **Purpose:** Showcase the most popular/featured classic books to drive discovery

  **Responsive Layout:**
  - **Desktop (>1024px):** Carousel centered with max-width 980px
    - Navigation buttons positioned inside carousel area (overlaid on scroll container)
    - Books displayed in horizontal scrollable row
    - Smooth scroll behavior on button click
  - **Mobile (≤1024px):** Carousel left-aligned to viewport edge
    - Breaks free from centered hero content container
    - Navigation buttons overlaid on left/right edges
    - Touch-swipeable horizontal scrolling

  **Book Cards:**
  - **Width:** 150px per card (110px on mobile <768px)
  - **Cover Image:** Full book cover with 2:3 aspect ratio
  - **Rank Overlay:** Large bold number (1-10) overlaid on bottom-left
    - White text with black outline and shadow for contrast
    - Font: Arial Black, 3.5rem on desktop, 2rem on mobile
  - **Hover Effect:** Scale to 1.05x
  - **Click Action:** Navigate to book detail page

  **Navigation Controls:**
  - **Left/Right Buttons:**
    - Circular buttons (44px diameter) with chevron icons
    - Semi-transparent black background (rgba(0,0,0,0.75))
    - White icons from inline SVG
    - Hover: darker background, scale 1.1x
    - Disabled state: 30% opacity when at start/end
  - **Position:** Absolutely positioned, vertically centered
    - Desktop: Inside carousel container (0.5rem from edges)
    - Mobile: Same positioning, scales to 2.5-2.75rem on smallest screens
  - **Behavior:**
    - Click scrolls carousel by ~600px (approximately 3-4 books)
    - Smooth scroll animation
    - Buttons auto-disable at scroll boundaries

  **Technical Implementation:**
  - **HTML Structure:**
    - Carousel is direct child of `.hero-discover` section (not nested in `.hero-banner-content`)
    - This allows carousel to break free from centered wrapper on mobile
    - Three `.hero-banner-content` wrappers: title/subtitle, carousel wrapper, CTA
  - **CSS Architecture:**
    - `.hero-banner` uses `display: flex; flex-direction: column` for vertical stacking
    - `.top-10-carousel-wrapper` uses `align-self: flex-start` below 1024px breakpoint
    - Preserves centered title/subtitle while allowing left-aligned carousel
  - **Breakpoint Threshold:** 1024px chosen to prevent button clipping
    - Calculation: 980px max-width + 44px buttons + padding = requires 1024px+ viewport
  - **Data Loading:** Books fetched from `/api/books?limit=10` on page load

  **User Experience:**
  - **Discovery:** Immediately showcases top classics to new visitors
  - **Visual Hierarchy:** Rank numbers create clear priority ordering
  - **Touch-Friendly:** Swipeable on mobile devices (native overflow scroll)
  - **Performance:** Lazy-loaded images with skeleton loading states
  - **Accessibility:** Keyboard navigation support (arrow keys work in scroll container)

- **White Background:** Clean, minimal design inspired by Amazon
- **Category Carousels:** Horizontal scrolling rows organized by category
  - **Top 10 Categories:** Displayed first, sorted by book count (most popular first)
  - **All Books Carousel:** Displayed last, shows entire collection
  - **Each Carousel Includes:**
    - Category title on left (e.g., "Victorian Literature")
    - "View All →" link on right (navigates to category detail page)
    - Left/right navigation arrows (circular, white background, shadow)
    - Horizontal scrolling book cards (no scrollbar visible)
  - **Book Cards:** Larger format (200px wide x 280px cover)
    - Cover image with subtle shadow (lazy-loaded for performance)
    - Title (2 lines max, truncated)
    - Author name (1 line, truncated)
    - No background card - transparent design
    - Hover: Scale to 1.05x
  - **Book Order (Added 2025-11-28):**
    - Books displayed in randomized order within each carousel
    - Order is cached in-memory after first load
    - Refreshing page preserves the same randomized order
    - Improves discovery while maintaining consistency
  - **Vertical Spacing:**
    - 2.5rem gap after blue header
    - 1.5rem gap between carousel rows
    - 0.75rem gap between books in carousel

**Header Navigation (Added 2025-11-28, Updated 2025-11-28):**
- **Logo and Home Link:** Left side (Summra icon + text)
- **Navigation Menu Items:** Right side (left-aligned, 20px from logo)
  - "Categories" → All Categories page
  - "All Books" → All Books grid page
- **Menu Style:** Transparent background, minimal text-only design
  - No borders or button backgrounds
  - Hover: opacity change + underline
  - Appears as integrated menu items, not separate buttons

**Book Grid:**
- **Layout:** Responsive card-based grid
- **Cards Include:**
  - Cover image (Project Gutenberg or custom, lazy-loaded)
  - Book title
  - Author name
  - Word count (optional)
- **Interaction:** Click card to open book details
- **Responsive:** Adapts to mobile, tablet, desktop
- **Usage:**
  - "All Books" page (grid view of entire collection)
  - Category detail pages (grid view filtered by category)
- **Data Caching (Added 2025-11-28):**
  - Category data cached in-memory after first fetch
  - Eliminates flash/reload when returning to category pages
  - Improves navigation performance and user experience

**Book Detail Page (Redesigned 2025-11-25, Enhanced 2025-12-03):**
- **Minimal Header:** Smaller cover image (120px) with title and author side-by-side
- **About This Book Section (Added 2025-12-03):**
  - Displays AI-generated editorial metadata about the book
  - Two-column layout on desktop (stacks on mobile):
    - **Left:** "About This Book" (150-200 word engaging summary)
    - **Right:** "Why Read This Now?" (100-150 word relevance statement)
  - **Author Metadata Bar:**
    - Author's country of origin displayed
    - "More by [Author]" expandable dropdown showing author's other notable works
  - **Design:** Light gray card with subtle border, placed between header and summaries
  - **Backward Compatible:** Section hidden for books without metadata
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
- [✅] All books display with cover images
- [✅] Cover images load progressively
- [✅] Missing covers show placeholder
- [✅] Grid is responsive on all screen sizes
- [✅] Click on book opens detail view
- [✅] Back button returns to home
- [✅] Category carousels display on home page (2025-11-28)
- [✅] Carousels sorted by book count (most popular first) (2025-11-28)
- [✅] Navigation arrows scroll carousel left/right (2025-11-28)
- [✅] "View All" links navigate to category detail pages (2025-11-28)
- [✅] Header navigation buttons work (Categories, All Books) (2025-11-28)
- [✅] Category detail page shows grid of books (2025-11-28)
- [✅] All Categories page shows all category carousels (2025-11-28)
- [✅] Categories section hidden when viewing book details (2025-11-28)
- [✅] "About This Book" section displays when metadata exists (2025-12-03)
- [✅] Section hidden for books without metadata (backward compatible) (2025-12-03)
- [✅] Top 10 Carousel displays in Discover hero banner (2025-12-08)
- [✅] Carousel centered on desktop (>1024px), left-aligned on mobile (≤1024px) (2025-12-08)
- [✅] Rank numbers (1-10) overlaid on book covers with high contrast (2025-12-08)
- [✅] Navigation buttons scroll carousel smoothly (2025-12-08)
- [✅] Navigation buttons disable at scroll boundaries (2025-12-08)
- [✅] Books clickable to navigate to detail page (2025-12-08)
- [✅] Carousel touch-swipeable on mobile devices (2025-12-08)
- [✅] Title/subtitle remain centered while carousel breaks out on mobile (2025-12-08)
- [✅] Two-column layout on desktop, stacked on mobile (2025-12-03)
- [✅] Author country displays when available (2025-12-03)
- [✅] "More by Author" dropdown toggles correctly (2025-12-03)

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
/                                    → Home page (category carousels + all books grid)
/#/book/alice-in-wonderland          → Book overview (concise + medium preview + chapters)
/#/book/alice-in-wonderland/medium   → Full medium summary page
/#/book/alice-in-wonderland/chapter/3 → Individual chapter page (chapter 3)
/#/category/5                        → Category detail page (grid of books in category 5)
/#/categories                        → All categories page (all category carousels)
/#/all-books                         → All books grid page
```

**Navigation (Updated 2025-11-28):**
- Hash-based routing (no server-side routing needed)
- Browser back/forward buttons work correctly
- Page refresh preserves current view
- URL updates when user navigates
- **Consistent Back Behavior:** "Back to Home" buttons always navigate to home page (not browser history)
  - Applied to: Category detail pages, All Categories page, All Books page
  - Ensures predictable navigation for users

**Acceptance Criteria:**
- [ ] Each book has a unique URL slug
- [ ] URL includes selected summary type
- [ ] Refreshing page loads correct book and summary
- [ ] Back button navigates through history correctly
- [ ] Forward button works as expected
- [ ] URLs can be bookmarked
- [ ] URLs can be shared and open correctly

### 5. Chapter Navigation (Redesigned 2025-11-25, Updated 2025-12-01)

**Feature Description:**
Users can navigate to dedicated pages for each chapter, with full text displayed, optional illustrations, and summary protected from spoilers.

**User Stories:**
- As a student, I want to jump to specific chapters so I can focus on relevant sections
- As a reader, I want to avoid spoilers, so chapter summaries should be hidden by default
- As a learner, I want to see chapter titles so I can understand book structure
- As a user, I want to read full chapter text while having summary available if needed
- As a visual learner, I want to see illustrations for chapters to enhance my reading experience

**Specifications:**

**Chapter List (Book Overview):**
- **Structure:** Vertical list of full-width chapter boxes (one per row)
- **Hierarchical Display (Added 2025-11-27):**
  - **Two-Level Structure:** Books with PART/BOOK/ACT organization show section headers
    - Section headers: Uppercase text with border separator (e.g., "PART ONE: The Old Buccaneer")
    - Chapters indented 20px under their respective sections
    - Examples: Treasure Island (6 Parts), War and Peace (15 Books), Romeo and Juliet (5 Acts)
  - **Single-Level Structure:** Traditional books show flat chapter list (no indentation)
    - Example: Alice in Wonderland (numbered chapters only)
- **Styling:** White background, 4px blue left border, subtle hover effects
- **Chapter Box Includes:**
  - Chapter number and title combined (e.g., "3. The Time Traveller Returns")
  - **Title Formatting (Added 2025-12-02):** All chapter titles use consistent title case:
    - First word and major words capitalized
    - Articles/prepositions lowercase (a, an, the, of, in, etc.) unless first word
    - Words after em-dashes (—), colons (:), and periods (.) capitalized
    - First word inside quotes always capitalized
    - Examples: "Of the Division of Labour", "Huck.—Miss Watson.—Tom Sawyer", "It Is The Child!"
  - Hover: Light blue background, slide right animation, subtle shadow
- **Spacing:** 12px gap between boxes, 24px gap before section headers
- **Interaction:** Click box to navigate to dedicated chapter page

**Chapter Detail Page (Updated 2025-12-01):**
- **Navigation:** Accessible via `#/book/{slug}/chapter/{num}`
- **Auto-scroll:** Page scrolls to top on navigation
- **Layout:**
  - White background card with 32px padding
  - Chapter illustration (optional, centered between header and summary)
  - Collapsed chapter summary box (yellow/beige, "may contain spoilers" warning)
  - Full chapter text section below summary
  - Inline TTS buttons for both summary and full text
- **Chapter Illustrations (Added 2025-12-01, Enhanced 2025-12-02):**
  - Display AI-generated artwork specific to each chapter
  - Generated via Gemini API (sync or batch mode)
  - Responsive sizing (max 600px desktop, 400px mobile)
  - Hidden when no illustration available
  - Supports local files (illustrations/) or external URLs
  - Character consistency maintained across chapters via reference images
  - **Generation Modes:**
    - **Synchronous:** Real-time generation with live progress (default)
    - **Batch:** Asynchronous bulk processing with 50% cost savings (for 50+ chapters)
- **Summary Header (Polished 2025-11-25):**
  - Summary title with spoiler warning on left
  - Button group on right: "🔊 Listen" + chevron toggle
  - Flexbox layout with 12px gap between buttons
  - Minimal chevron-only toggle (no border or background)
  - Listen button simplified: "🔊 Listen" (not "Listen to Summary")
- **Summary Toggle:**
  - Default: Collapsed to protect from spoilers
  - Click "▼" chevron to expand, shows "▲" when expanded
  - Transparent design with hover effects (color change + scale)

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
- [✅] Back button properly aligned with text content (2025-11-25)
- [✅] Listen button in summary header alongside toggle (2025-11-25)
- [✅] Toggle button simplified to chevron-only design (2025-11-25)

### 6. Reading Experience Customization (Added 2025-11-30)

**Feature Description:**
Kindle-inspired reading experience with customizable fonts, sizes, and color schemes, plus progress tracking and sequential navigation for distraction-free long-form reading.

**User Stories:**
- As a reader, I want to customize font family and size so I can read comfortably
- As a user with visual impairments, I want adjustable text size and high-contrast themes
- As a reader, I want to see my reading progress so I know how much content remains
- As a student, I want to quickly move to the next chapter without returning to the book overview
- As a user, I want my reading preferences to persist across sessions

**Specifications:**

**6a. Reading Settings Panel:**
- **Access:** Gear icon (⚙️) button on chapter and medium summary pages
- **Panel Design:**
  - Slides in from right edge of screen
  - 320px wide on desktop, full-width on mobile
  - White background with shadow overlay
  - Close button (✕) in header
- **Settings Persistence:** All preferences saved to browser localStorage
- **Availability:** Both chapter detail and medium summary pages

**6b. Font Family Selection:**
- **Options:**
  1. **Georgia** (default) - Classic serif font, traditional book feel
  2. **System** - Native system font stack, familiar to user's OS
  3. **Open Sans** - Modern sans-serif, clean and readable
- **UI:** Radio-style buttons with font preview ("Aa")
- **Labels:** Font names displayed below preview buttons
- **Application:** Applies to chapter summaries, chapter full text, and medium summaries
- **Persistence:** Saved as `reading_font` in localStorage

**6c. Font Size Adjustment:**
- **Range:** 12px (minimum) to 24px (maximum)
- **Default:** 16px
- **Controls:**
  - **Slider:** Continuous adjustment across full range
  - **A- Button:** Decrease by 1px (minimum 12px)
  - **A+ Button:** Increase by 1px (maximum 24px)
  - **Size Display:** Shows current size (e.g., "16px")
- **Application:** Applies to reading text only (summaries and chapters)
- **Exclusion:** Does NOT affect next chapter button, headers, or UI elements
- **Persistence:** Saved as `reading_fontSize` in localStorage

**6d. Color Scheme (Theme):**
- **Light Theme** (default):
  - Background: White (#FFFFFF)
  - Text: Dark gray (#2c3e50)
  - Use case: Bright environments, daytime reading
- **Dark Theme:**
  - Background: Dark gray (#1a1a1a)
  - Text: Light gray (#e0e0e0)
  - Use case: Low-light environments, night reading, reduced eye strain
- **Sepia Theme:**
  - Background: Beige/cream (#f4ecd8)
  - Text: Warm brown (#5c4f3d)
  - Use case: Kindle-like warm tones, reduced blue light, comfortable long reading sessions
- **UI:** Visual theme preview squares with labels
- **Application:**
  - Applies to all reading content (summaries, chapters)
  - Applies to next chapter button area background
  - Does NOT affect navigation elements outside reading area
- **Persistence:** Saved as `reading_theme` in localStorage

**6e. Reading Progress Indicator:**
- **Design:** Kindle-style thin progress bar (2px height, not thick web-style)
- **Position:** Fixed to bottom of screen
- **Components:**
  - Visual fill bar showing progress percentage
  - Text percentage display (e.g., "42%")
- **Calculation:** Based on scroll position relative to total scrollable height
- **Formula:** `progress = (scrollTop / scrollableHeight) * 100`
- **Updates:** Real-time as user scrolls
- **Theme Adaptation:** Colors match selected theme
- **Mobile:** Taller bar (32px) for better visibility and touch interaction

**6f. Sticky Reading Header:**
- **Trigger:** Appears when user scrolls past book/chapter title
- **Content:**
  - Chapter number (e.g., "Chapter 8")
  - Book title
  - Gear icon for quick settings access
- **Position:** Fixed to top, edge-to-edge width
- **Behavior:**
  - Smooth slide-down animation when triggered
  - Smooth slide-up when scrolled back to top
  - Always accessible for settings
- **Dual Implementation:** Separate headers for chapter and medium summary pages

**6g. Next Chapter Navigation:**
- **Location:** End of chapter full text section
- **Display Logic:** Only shown when a next chapter exists
- **Button Text:** "Next Chapter →"
- **Functionality:** Navigates directly to next sequential chapter
- **Styling:**
  - Transparent background with border
  - Theme-aware colors (adapts to light/dark/sepia)
  - Hover: Border color changes to accent color, subtle background tint
- **Margin:** 48px top, 80px bottom (space above and below button)
- **Font Behavior:** Does NOT change size or family with reading settings

**6h. Navigation Improvements:**
- **Back Button:** "← Back to Book" always returns to book detail page (not browser history)
- **Top Spacing:** Proper margin above back button + gear icon row (not stuck to top edge)
- **Route Persistence:** Page refresh on chapter URL maintains chapter view (no redirect to home)
- **Scroll Behavior:** Page scrolls to top on chapter navigation

**UI Requirements:**
- Settings panel accessible at all times during reading
- Clear visual feedback for selected options (active state)
- Smooth transitions when changing settings
- Keyboard navigation support for accessibility
- Touch-friendly controls on mobile devices
- Preferences restore on page load
- No jarring visual changes when switching themes

**Acceptance Criteria:**
- [✅] Gear icon opens settings panel from both fixed and sticky headers
- [✅] Settings panel slides in from right with smooth animation
- [✅] Font family changes apply immediately to reading content
- [✅] Font size changes apply immediately with live preview
- [✅] Theme changes apply immediately with smooth color transitions
- [✅] All settings persist in localStorage across sessions
- [✅] Settings restore automatically on page load
- [✅] Progress bar updates in real-time as user scrolls
- [✅] Progress percentage displayed accurately
- [✅] Sticky header appears when scrolling past title
- [✅] Sticky header hides when scrolled back to top
- [✅] Next chapter button only shown when next chapter exists
- [✅] Next chapter button navigates to correct sequential chapter
- [✅] Next chapter button respects theme colors
- [✅] Back button always returns to book detail page
- [✅] Page refresh on chapter URL maintains chapter view
- [✅] Settings panel works identically on chapter and medium pages
- [✅] Mobile: Settings panel goes full-width
- [✅] Mobile: Progress bar taller for better visibility

**Design Inspiration:**
- Amazon Kindle reading interface for customization options
- E-reader design principles for distraction-free reading
- Thin progress indicators like Kindle (not thick web-style bars)
- Minimal, unobtrusive UI elements during reading
- Professional typography and spacing

### 7. User Authentication & Reading Progress (Added 2025-12-20; **rebuilt 2026-09-06 on `pchauth`/trusted-header, no app-level login**)

**Status:** `FEATURE_AUTH = True` by default (`backend/config.py`) — the progress-tracking and whoami blueprints are always registered on this deployment. What varies per host is `SUMMRA_AUTH_MODE` (`off` / `optional` / `required`, read from `SUMMRA_AUTH_MODE` env — unset means `off`, matching pre-pchauth no-login behavior for local dev/test). Production (`wordpress-2-vm`) runs `optional` with `SUMMRA_ALLOWED_EMAILS` set.

> **Superseded (2026-09-06):** everything below this note through §7a as originally written — username/password registration, SHA-256+salt hashing, a Login/Register account modal, `/api/auth/register`, `/api/auth/login`, `backend/auth_routes.py`/`auth_utils.py` — **no longer exists**. There is no registration or login *form* anywhere in this app. Full incident/design history: `WORK_LOG.md`, 2026-09-05/09-06 entries; design spec in the `pchauth` repo's `docs/superpowers/specs/2026-09-05-consolidated-login-design.md`.

**Feature Description:**
Reading-progress tracking that persists across devices *for a signed-in visitor*, where "signed in" is decided entirely outside this app: a shared Apache reverse-proxy vhost on `wordpress-2-vm` runs `mod_auth_openidc` against Google, and — when a session already exists (e.g. because you signed in at `pengyaochen.com/pages`) — forwards a trusted `X-Remote-Email` header to this app on every request. This app never runs an OAuth flow, never asks for a password, and offers no sign-in button of its own (see 2026-09-06 UI decision below). Anonymous visitors read fine; their progress just stays local to the device instead of syncing.

**User Stories:**
- As a reader, I want my progress synced across devices *if* I'm already signed in elsewhere on the site — without this app asking me to log in separately
- As an anonymous visitor, I want the app to work normally without being nagged to create an account
- As a reader, I want to resume where I left off so I don't lose my place in a book
- As a reader, I want to see which chapters I've completed so I can track my progress through a book

**Specifications:**

**7a. Identity (no login flow in this app):**
- **Source of truth:** `X-Remote-Email`, set by the shared Apache vhost's `mod_auth_openidc` (`AuthType openid-connect`, `Require valid-user`, `OIDCUnAuthAction pass` so anonymous requests still reach the app). This app trusts the header unconditionally — it only works because gunicorn binds `127.0.0.1` and is reachable *only* through that Apache proxy.
- **Allowlist:** `pchauth.core.is_allowed()` checks the header's email against `SUMMRA_ALLOWED_EMAILS` (comma-separated, `service.env`) and fails closed — an empty allowlist in a non-`off` mode refuses to start.
- **Per-request resolution (`pchauth/flask_adapter.py`'s `init_pchauth`, a `before_request` hook):** no header + `optional` → anonymous (`g.user_id = None`, request proceeds); no header + `required` → 401; header present but not allowlisted → 403; header present and allowlisted → `user_db.upsert_user_by_email()` creates/updates the row and sets `g.user_id`.
- **`GET /api/auth/check`** (`backend/whoami.py`): the frontend's only sign-in-state probe — `{"authenticated": false}` for anonymous, else `{"authenticated": true, "user": {...}}`. No `/api/auth/login`, `/api/auth/register`, or `/api/auth/logout` exist; "logging out" is the shared gateway's own logout, not something this app can do.
- **Account button (`#user-account-btn`, header):** hidden by default (`.hidden` utility class — the bare `hidden` HTML attribute doesn't work here since `.header-nav-btn`'s own `display: flex` author style wins the cascade over the UA stylesheet's `[hidden]` default; see `WORK_LOG.md`, 2026-09-06 final entry). `auth.js`'s `updateAuthUI()` removes `.hidden` only once `/api/auth/check` confirms a real signed-in user; an anonymous visitor never sees it at all — there's no sign-in action to offer them, so a visible dead-end button was judged worse than no button.
- **Account modal, signed-out view:** no CTA. Just "Reading Progress — Saved on this device." — the shared-gateway sign-in path is deliberately not named anywhere in the UI (it should stay unadvertised, not something a curious visitor discovers by inspecting the page).

**7b. Reading Progress Tracking:**
- **Granular Progress Storage:**
  - Book ID
  - Chapter number (0 for preface)
  - Page number (for paginated reading)
  - Scroll position (for non-paginated views)
  - Timestamp of last update
- **Auto-Tracking:**
  - Progress saved automatically when viewing chapters
  - Updates on page navigation
  - No manual save action required
- **Chapter Completion:**
  - Auto-marked complete when user reaches last page
  - Visual indicator: greyed out with checkmark
  - Persists across sessions

**7c. Continue Reading Button:**
- **Location:** Top of book detail page in book-detail-info section
- **Display Logic:** Only shown when user has reading progress for the book
- **Button Text:** "Continue Reading: [Chapter Name], Page [Number]"
  - Example: "Continue Reading: Chapter 5, Page 3"
  - Preface displayed as "Preface" instead of "Chapter 0"
- **Functionality:**
  - Clicking navigates directly to saved chapter
  - Auto-scrolls to saved page after chapter loads
- **Icon:** 📖 book emoji for visual recognition

**7d. Identity Persistence:** no session cookie of this app's own to persist — identity is re-derived from `X-Remote-Email` on every request, confirmed against `/api/auth/check`. There is no offline mode: the app assumes an internet connection is always available (offline support — service worker caching, IndexedDB progress caching — was removed 2026-09-07; see `WORK_LOG.md`). Reading progress is tracked only in the server-side database, keyed by account, so it follows the reader across devices. An earlier IndexedDB-backed local mutation queue let a device trust and restore its own unsynced progress before/without a server round-trip; that per-device local copy was removed 2026-09-07 (see `WORK_LOG.md`) — progress reads and writes now always go through `/api/progress/v2/*`.

**7e. Reading History & Statistics:**
- **Account View:**
  - Books started count
  - Chapters completed count
  - Member since date
  - Last login timestamp
- **Future Enhancement:** Detailed reading statistics dashboard

**Database Schema:**
- **Separate Database:** `summra.db` (not `database.db`)
- **Tables:**
  - `users`: identity (`email` unique, `subject`/`name` reserved for a future direct-OIDC source, unused today) + `created_at`/`last_login` — no password column
  - `reading_progress`: Chapter and page tracking
  - `chapter_completion`: Completion tracking per chapter

**UI Requirements:**
- Account modal with clean, modern design
- Form validation with inline error messages
- Loading states for async operations
- Mobile-responsive design
- Clear visual feedback for logged-in state
- Completed chapters marked with checkmark and grey styling
- Continue Reading button prominent and easily accessible

**Acceptance Criteria:**
- [✅] Identity resolves from `X-Remote-Email` when present and allowlisted; anonymous otherwise (no error, no forced login)
- [✅] No registration/login form exists anywhere in this app
- [✅] Account button hidden for anonymous visitors; shown, with email, once `/api/auth/check` confirms a real signed-in user
- [✅] Reading progress auto-saves on chapter view (server-side if signed in, else localStorage)
- [✅] Chapter completion auto-marked on last page
- [✅] Completed chapters show visual indicator (grey + checkmark)
- [✅] Continue Reading button appears on book page when progress exists
- [✅] Clicking Continue Reading navigates to saved chapter and page
- [✅] Account stats show books started and chapters completed
- [✅] Anonymous visitor never sees the shared-gateway sign-in path named in the UI

**Design Inspiration:**
- Goodreads for reading progress tracking
- Kindle for seamless reading continuation
- Trusted-header SSO (identity owned entirely by the reverse proxy, app never sees a credential)

### 8. Breadcrumb Navigation (Added 2025-12-02)

**Feature Description:**
Context-aware breadcrumb navigation replaces traditional back buttons, showing users their location in the site hierarchy and providing quick access to parent pages.

**User Stories:**
- As a user, I want to see where I am in the site structure so I can navigate back to any parent page
- As a reader exploring categories, I want breadcrumbs that reflect how I got to the current book
- As a user, I want breadcrumbs on all pages so navigation is consistent

**Specifications:**

**Breadcrumb Trails:**
```
Home
Home → All Books
Home → Categories
Home → Categories → Victorian Literature
Home → All Books → Pride and Prejudice
Home → All Books → Pride and Prejudice → Summary
Home → All Books → Pride and Prejudice → Chapter 1
```

**Context-Aware Behavior:**
- When book selected from category page: `Home → Categories → Romance → Pride and Prejudice`
- When book selected from All Books: `Home → All Books → Pride and Prejudice`
- Context tracked automatically based on navigation path

**Visual Design:**
- First breadcrumb has back arrow (`← Home`)
- Breadcrumbs separated by `›` symbol
- Current page shown in plain text (not clickable)
- Links use secondary color (#3498db)
- Hover effect: darker blue
- Responsive: wraps on mobile

**Placement:**
- Replaces all "Back" buttons throughout site
- Appears at top of every page (below header, above content)
- Consistent position across all routes
- Margin: 16px top, 24px bottom

**SEO Benefits:**
- Structured data (Schema.org BreadcrumbList)
- Search engines understand site hierarchy
- Rich snippets in search results
- Improved crawlability

**Accessibility:**
- Semantic HTML (`<nav>`, `<ol>`, `<li>`)
- ARIA label: `aria-label="Breadcrumb"`
- Keyboard navigable (all links focusable)
- Screen reader friendly

**UI Requirements:**
- Clean, minimal design (no borders or backgrounds)
- Touch-friendly tap targets on mobile
- Text-only design (no icons except back arrow)
- Consistent with site's minimal aesthetic

**Acceptance Criteria:**
- [✅] Breadcrumbs shown on all pages except home
- [✅] First breadcrumb always goes to home with back arrow
- [✅] Current page shown as plain text
- [✅] Links navigate correctly via hash routing
- [✅] Context-aware trails based on navigation path
- [✅] Breadcrumbs wrap gracefully on mobile
- [✅] Structured data included for SEO
- [✅] Accessible to keyboard and screen readers

### 8. Related Books Recommendations (Added 2025-12-02)

**Feature Description:**
Personalized book recommendations displayed as a carousel at the bottom of each book detail page, helping readers discover similar works based on author, category, and country.

**User Stories:**
- As a reader who enjoyed a book, I want to see similar books so I can continue reading in the same genre
- As a fan of an author, I want to see their other works so I can read more by them
- As a user exploring literature, I want to discover books by authors from the same country

**Specifications:**

**Recommendation Algorithm:**

1. **By Author** (Priority 1):
   - All other books by the same author
   - Excludes current book
   - Random order for variety

2. **By Category** (Priority 2):
   - Books in same categories (Romance, Victorian Literature, etc.)
   - Excludes books by same author (already shown)
   - Random order

3. **By Country** (Priority 3):
   - Books by authors from same country
   - Excludes books already shown
   - Random order

**Deduplication:**
- Frontend merges all three lists
- Removes duplicate books (may appear in multiple categories)
- Limits to 10 total recommendations

**Visual Design:**

**Carousel Style:**
- Horizontal scrolling row (same as category carousels on home page)
- Left/right navigation arrows
- Smooth scroll animation (3 cards at a time)
- No visible scrollbar
- Touch-friendly horizontal scrolling

**Book Cards:**
- Cover image (200px wide × 300px high on desktop)
- Book title (2 lines max, truncated)
- Author name (1 line, truncated)
- Hover: scale to 1.05x
- Click: navigate to book detail page

**Responsive Sizing:**
- Desktop: 200px wide, 300px cover
- Tablet: 150px wide, 200px cover
- Mobile: 130px wide, 180px cover

**Section Header:**
- "You May Also Like"
- Same styling as "Chapters" header
- Border-top separator (1px, #e0e0e0)
- Margin-top: 48px (space above section)

**Placement:**
- Bottom of book detail page
- After chapters section
- Before footer
- Hidden if no related books found

**Navigation Arrows:**
- Circular white buttons with shadow
- Left/right chevrons (‹ and ›)
- Disabled at carousel edges
- Smooth scroll by 3 cards
- Touch-friendly (44×44px minimum)

**Loading Behavior:**
- Lazy loaded (fetched when book detail page opens)
- Separate API call: `GET /api/books/<id>/related`
- Graceful failure (section hidden on error)
- No loading skeleton (instant display)

**API Response:**
```json
{
  "success": true,
  "related": {
    "by_author": [...],
    "by_category": [...],
    "by_country": [...]
  }
}
```

**UI Requirements:**
- Consistent styling with home page carousels
- Smooth animations and transitions
- Mobile-friendly scrolling
- Clear visual hierarchy
- Professional, clean design

**Acceptance Criteria:**
- [✅] Section appears at bottom of book detail page
- [✅] Up to 10 related books shown
- [✅] Books prioritized by author → category → country
- [✅] Duplicates removed automatically
- [✅] Carousel scrolls smoothly left/right
- [✅] Navigation arrows work correctly
- [✅] Arrows disabled at edges
- [✅] Books clickable (navigate to detail page)
- [✅] Section hidden if no related books
- [✅] Responsive on mobile/tablet/desktop
- [✅] Touch-friendly horizontal scrolling
- [✅] Cover images lazy-loaded

### 9. Chapter Illustration Lightbox (Added 2025-12-01)

**Feature Overview:**

Full-screen image viewer for chapter illustrations, allowing readers to view high-quality artwork without leaving the chapter page. Provides a distraction-free viewing experience with smooth transitions and multiple interaction methods.

**User Story:**

> "As a reader exploring illustrated classics like 'The Wonderful Wizard of Oz', I want to view chapter illustrations in full-screen quality so that I can appreciate the artwork without navigating away from my current reading position."

**Key Capabilities:**

1. **Click-to-Expand:** Click any chapter illustration to open in full-screen overlay
2. **High-Quality Display:** Illustrations displayed at optimal size (up to 90% of viewport)
3. **Dark Background:** Near-black overlay (95% opacity) focuses attention on artwork
4. **Multiple Close Methods:** Close button, background click, or Escape key
5. **Scroll Lock:** Page scroll disabled while viewing (prevents disorientation)
6. **Smooth Transitions:** Fade in/out animations (300ms) for polished feel
7. **Responsive Sizing:** Adapts to mobile and desktop viewports

**User Interface Elements:**

**Illustration Display (in Chapter):**
- Chapter illustration shown inline within chapter content
- Pointer cursor on hover indicates interactivity
- Subtle opacity change on hover (visual feedback)

**Lightbox Overlay:**
- Full-screen dark background (rgba(0, 0, 0, 0.95))
- Centered illustration with proportional scaling
- Circular close button (✕) in top-right corner
  - Semi-transparent white background
  - Glowing effect on hover
  - 50x50px on desktop, 44x44px on mobile (touch-friendly)

**Interaction Flow:**

```
1. User reads chapter with illustration
2. User hovers over illustration
   → Cursor changes to pointer
   → Image opacity reduces slightly
3. User clicks illustration
   → Lightbox fades in (300ms)
   → Page scroll locked
   → Illustration displayed full-screen
4. User views high-quality image
5. User closes via:
   Option A: Click ✕ button (top-right)
   Option B: Click dark background area
   Option C: Press Escape key
6. Lightbox fades out (300ms)
   → Page scroll restored
   → User returns to exact scroll position
```

**Accessibility Features:**

- **Keyboard Support:** Escape key closes overlay
- **Aria Labels:** Close button has descriptive label ("Close lightbox")
- **Focus Management:** No keyboard traps (Escape always works)
- **Screen Reader:** Alt text from illustration passed to overlay image
- **Touch-Friendly:** Larger close button on mobile (44x44px minimum)

**Edge Cases Handled:**

- **Missing Illustrations:** Lightbox only enabled when illustration exists
- **Rapid Clicking:** CSS transitions handle rapid open/close smoothly
- **Mobile Touch:** Tap on background closes overlay (not just button)
- **Very Large Images:** Max dimensions prevent overflow (90vh/90vw)
- **Very Small Images:** Displayed at natural size (no upscaling/blurriness)
- **Keyboard Users:** Escape key always accessible (no modal trap)

**Visual Design:**

**Color Scheme:**
- Overlay background: `rgba(0, 0, 0, 0.95)` (near-black, high contrast)
- Close button background: `rgba(255, 255, 255, 0.1)` (semi-transparent white)
- Close button border: `rgba(255, 255, 255, 0.3)` (subtle outline)
- Close button text: `white` (high contrast)

**Layout:**
- Z-index: 10000 (above all other content including reading settings)
- Image sizing: `max-width: 90vw; max-height: 90vh` (desktop)
- Image sizing: `max-width: 95vw; max-height: 95vh` (mobile - more space)
- Image scaling: `object-fit: contain` (maintains aspect ratio)
- Close button position: `top: 24px; right: 24px` (desktop)
- Close button position: `top: 16px; right: 16px` (mobile)

**Typography:**
- Close button: 2rem font size (desktop), 1.5rem (mobile)
- Close character: ✕ (multiplication sign, clean appearance)

**Animations:**
- Overlay fade: 0.3s ease (opacity transition)
- Close button hover: 0.2s ease (transform scale 1.1)
- Cursor: `zoom-out` on background (visual affordance)

**Performance Characteristics:**

- **Image Loading:** Instant (images already loaded in chapter view)
- **Animation Performance:** GPU-accelerated opacity transitions
- **Memory Footprint:** Minimal (~1-2 KB for event handlers)
- **Reusability:** Single overlay instance reused for all images

**Browser Compatibility:**

- Modern browsers: Full functionality
- IE11: Works (may lack smooth transitions)

---

### 10. Optimized Image Loading (Added 2025-12-02)

**Feature Description:**
Chapter illustrations use modern image formats (WebP/JPG) with automatic browser selection for optimal loading performance, reducing page load times by ~95% compared to original high-resolution images.

**User Stories:**
- As a mobile user, I want illustrations to load quickly even on slow connections so I can read without waiting
- As any user, I want high-quality images without large file downloads so pages load instantly
- As a user on metered data, I want minimal data usage when viewing illustrated chapters

**User Value:**
- **Faster Page Loads:** Illustrations load 95% faster than unoptimized versions
- **Lower Data Usage:** WebP format uses ~30% less data than JPG for same quality
- **Better Mobile Experience:** Smaller files ideal for cellular connections
- **Automatic Optimization:** Browser selects best format without user intervention
- **High Visual Quality:** Optimized images maintain crisp, professional appearance

**Technical Implementation:**

**Image Format Strategy:**
```html
<!-- Picture element provides multiple format options -->
<picture>
    <source srcset="/static/illustrations/47/1.webp" type="image/webp" />
    <source srcset="/static/illustrations/47/1.jpg" type="image/jpeg" />
    <img src="/static/illustrations/47/1.jpg" alt="Chapter illustration" />
</picture>
```

**Browser Behavior:**
- **Modern Browsers (Chrome 23+, Firefox 65+, Edge 18+, Safari 14+):**
  - Automatically load WebP format (~0.3MB per illustration)
  - Benefit from superior compression and quality

- **Older Browsers (IE11, Safari 13-):**
  - Fall back to JPG format (~0.4MB per illustration)
  - Still optimized, just slightly larger than WebP

- **Legacy Browsers (IE9-10):**
  - Use `<img>` src as final fallback
  - Guaranteed to work on all browsers

**File Size Comparison:**

| Format | Size | Quality | Browser Support |
|--------|------|---------|-----------------|
| Original PNG | ~7 MB | Maximum | All |
| Optimized JPG | ~0.4 MB | High | All |
| Optimized WebP | ~0.3 MB | High | Modern (95%+) |

**Performance Impact:**

**Before Optimization:**
- Single chapter: 7MB download
- 10-chapter book: 70MB total
- Mobile load time: 10-30 seconds on 4G
- Data cost: Significant on metered connections

**After Optimization:**
- Single chapter: 0.3-0.4MB download
- 10-chapter book: 3-4MB total
- Mobile load time: <1 second on 4G
- Data cost: 95% reduction

**Real-World Metrics (48 illustrations across Books 1, 6, 47):**
- Total original size: 331 MB
- Total optimized size: 36.1 MB (WebP + JPG combined)
- Average reduction: **89%**
- Page load improvement: **~20x faster**

**UI/UX Specifications:**

**Visual Quality:**
- Resolution: 1024px width (sufficient for desktop displays)
- Aspect ratio: Maintained from original (typically 2:3 portrait)
- Quality setting: 85% (imperceptible quality loss vs. original)
- Sharpness: Preserved through Lanczos resampling

**Loading Behavior:**
- **No Loading Skeleton:** Images load instantly (cached or fast network)
- **Progressive Display:** Browser native progressive rendering
- **Instant Click-to-Zoom:** Lightbox uses same optimized images
- **Cache-Friendly:** Browser caches both formats independently

**Accessibility:**
- Alt text preserved across all formats
- Format selection transparent to screen readers
- No JavaScript required for format selection
- Keyboard navigation unaffected

**Lightbox Integration:**
- Optimized images also used in full-screen lightbox
- Same WebP/JPG dual-format approach
- No additional downloads when zooming
- Consistent quality between inline and lightbox views

**Acceptance Criteria:**

- [x] Modern browsers automatically load WebP format
- [x] Older browsers fall back to JPG format seamlessly
- [x] All browsers display illustrations without errors
- [x] File sizes reduced by >90% compared to originals
- [x] Visual quality indistinguishable from originals at display size
- [x] Lightbox uses same optimized images (no duplicate downloads)
- [x] No JavaScript errors related to image format selection
- [x] Page load time improved by >10x for illustrated chapters

**Future Enhancements:**

**Potential Improvements:**
1. **AVIF Format:** Even better compression than WebP (when browser support improves)
2. **Responsive Images:** Multiple sizes for different screen widths (srcset)
3. **Lazy Loading:** Only load images as they scroll into view
4. **Blur-up Loading:** Show low-res placeholder while full image loads
5. **CDN Integration:** Serve images from global CDN for faster delivery

**Automated Database Updates:**
- Optimization script automatically updates database with illustration URLs
- Triggered when running from generation workflow (`auto_optimize_illustrations`)
- Can be manually enabled with `--update-db` flag
- Updates `chapters.illustration_url` field after successful optimization
- Uses URL pattern: `/static/illustrations/{book_id}/{chapter_num}.png`
- Preserves existing chapter data (title, summary, full text, section)
- Gracefully handles missing chapters or database errors
- Only updates database when optimization succeeds

**Current Design Philosophy:**
- Simple dual-format strategy (WebP + JPG)
- No build-time complexity
- Works with existing database schema
- Automated database sync after optimization
- Gradual degradation for older browsers
- Zero user intervention required
- Mobile browsers: Full support (iOS, Android)
- Touch devices: Tap-to-close works as expected

**Acceptance Criteria:**

- [✅] Clicking chapter illustration opens full-screen lightbox
- [✅] Lightbox displays illustration at optimal size (up to 90% viewport)
- [✅] Dark background (95% black) focuses attention on image
- [✅] Close button (✕) visible in top-right corner
- [✅] Clicking close button closes lightbox
- [✅] Clicking dark background (not image) closes lightbox
- [✅] Pressing Escape key closes lightbox
- [✅] Page scroll locked while lightbox is open
- [✅] Page scroll restored to exact position when closing
- [✅] Smooth fade in/out animations (300ms)
- [✅] Pointer cursor on illustration hover
- [✅] Opacity feedback on illustration hover
- [✅] Mobile: Close button is touch-friendly (44x44px minimum)
- [✅] Mobile: Illustration uses more screen space (95% viewport)
- [✅] Keyboard accessible (Escape key always works)
- [✅] Screen reader friendly (aria labels present)
- [✅] No errors if illustration missing (graceful degradation)
- [✅] Works on both chapter and medium summary pages
- [✅] Close button has hover effect (glow + scale)

**Design Inspiration:**
- Google Photos lightbox (dark background, click-to-close)
- Medium image viewer (clean, minimal UI)
- iOS Photos app (swipe gestures, minimal chrome)
- Kindle book covers (full-screen focus on artwork)

**Future Enhancements:**

- **Navigation Arrows:** Previous/Next buttons to cycle through chapter illustrations
- **Image Zoom:** Pinch-to-zoom or click-to-zoom for very large illustrations
- **Download Button:** Allow users to save illustrations locally
- **Image Metadata:** Display caption/description if available
- **Touch Gestures:** Swipe down to close on mobile (iOS Photos-style)
- **Fullscreen API:** Native browser fullscreen mode option

### 11. Analytics and Tracking (Added 2025-12-12)

**Feature Description:**
Google Analytics 4 (GA4) tracking installed site-wide to measure user engagement, traffic sources, and content performance.

**User Stories:**
- As a product owner, I want to understand which books are most popular so I can prioritize content
- As a developer, I want to see traffic sources so I can optimize marketing efforts
- As a team, I want engagement metrics so we can improve user experience

**Specifications:**

**Implementation:**
- **Tracking ID:** G-6XGTPLPMG0
- **Technology:** Google tag (gtag.js)
- **Installation:** Added to `<head>` section of main template
- **Placement:** Immediately after opening `<head>` tag (before other scripts)
- **Coverage:** All pages (single-page application tracks initial page load)

**Data Collected:**
- Page views and navigation patterns
- User demographics and interests
- Traffic sources (organic, direct, referral, social)
- User engagement metrics (time on site, pages per session)
- Device and browser information
- Geographic data (country, region, city)

**Privacy Considerations:**
- Anonymous data collection (no PII stored)
- Standard Google Analytics privacy policy
- No custom user identification
- Cookie-based tracking (browser defaults)

**Acceptance Criteria:**
- [✅] GA4 tag installed in HTML template
- [✅] Tracking ID configured correctly
- [✅] Script loads asynchronously (no page blocking)
- [✅] dataLayer initialized properly
- [ ] Real-time data visible in GA4 dashboard (24-48h delay expected)
- [ ] Pageviews tracked for initial page load
- [ ] Device and browser data collected
- [ ] Geographic data captured

**Future Enhancements:**
- **Custom Events:**
  - Book detail page views
  - Summary type selection (concise, medium, comprehensive)
  - TTS audio playback
  - Chapter navigation
  - Search queries
- **SPA Tracking:** Manual pageview tracking for client-side navigation
- **Content Grouping:** Group by category (fiction, non-fiction, poetry)
- **E-commerce Tracking:** Premium features conversion (if added)
- **User Privacy:** Cookie consent banner (GDPR/CCPA compliance)

**Files Modified:**
- `frontend/templates/index.html:4-12` - Google Analytics script tag

## User Workflows

### Workflow 1: Browsing by Category (Added 2025-11-28)

```
1. User lands on home page
2. User sees category carousels (e.g., "Victorian Literature", "Philosophy", "Romance")
3. User browses carousel by:
   - Clicking left/right arrows to scroll through books in category
   - Scrolling horizontally on touchscreen devices
4. User sees book cover, title, and author in each carousel card
5. User decides:
   Option A: Click book cover → navigate to book detail page
   Option B: Click "View All →" → navigate to category detail page (grid view)
   Option C: Click "Categories" in header → see all categories page
6. If viewing category detail page:
   - See all books in category in grid layout
   - Click any book to view details
   - Click "Back to Home" to return (always returns to home, not previous page)
7. If viewing All Categories page:
   - See all category carousels (not just top 10)
   - Sorted by popularity
   - Click "Back to Home" to return (always returns to home, not previous page)
8. Navigation behavior (Added 2025-11-28):
   - Carousel book order is randomized but cached - order stays consistent on refresh
   - Category data is cached - no flash/reload when returning to pages
   - Book cover images lazy-load for better performance
```

### Workflow 2: Discovering a New Book (Updated 2025-11-28)

```
1. User lands on home page
2. User browses category carousels or clicks "All Books" in header
3. User clicks on interesting book cover
4. User arrives at book overview page showing:
   - Quick Summary (concise, 500 words, no spoilers)
   - Detailed Overview preview (first ~300px of medium summary with fade)
   - Chapter boxes (one per row, full width)
   - NOTE: Category carousels hidden on book detail pages
5. User reads concise summary
6. User scrolls to see medium preview (first ~200 words visible with fade)
7. User decides:
   - Want more detail → clicks "Read Full Summary →" (navigates to medium page)
   - Want specific chapter → clicks chapter box (navigates to chapter page)
   - Not interested → back button returns to previous page (home, category, or all books)
```

### Workflow 3: Studying a Book in Depth (Updated 2025-11-25)

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

### Workflow 4: Quick Reference

```
1. User has bookmarked URL to specific book/summary/category
2. User clicks bookmark
3. App loads directly to bookmarked view
4. User reads/listens to summary
5. User closes tab when done
```

### Workflow 5: Listening While Commuting

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
- **Image Loading:** Progressive with lazy loading (Added 2025-11-28)
  - All carousel and grid book cover images use `loading="lazy"` attribute
  - Reduces initial page load by deferring off-screen images
  - Improves performance on slower connections
- **Data Caching:** In-memory caching for category data and carousel order (Added 2025-11-28)
  - Eliminates redundant API calls when navigating back to pages
  - Preserves carousel book order across page refreshes
  - Instant page loads for previously visited categories

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

### Phase 2: Enhanced UX (COMPLETED - 2025-11-28)
- ✅ URL routing for books, summaries, and chapters
- ✅ BeFreed-inspired minimal UI redesign
- ✅ Removed unnecessary bounding boxes
- ✅ Content-first presentation
- ✅ Separate pages for medium summary and chapters
- ✅ Chapter summary collapsed by default (spoiler protection)
- ✅ Scroll to top on page navigation
- ✅ Chapter summary UI polish (button reorganization, minimal toggle design)
- ✅ Back button alignment fix (container-based layout)
- ✅ Two-level book structure support (PART/BOOK/ACT → Chapters)
  - ✅ Hierarchical TOC detection
  - ✅ Document body scanning fallback (for books like Anna Karenina)
  - ✅ Database schema for sections
  - ✅ API returns structured data
  - ✅ Frontend displays section headers with indented chapters
  - ✅ All 5 test books passing (Treasure Island, War and Peace, Anna Karenina, Romeo and Juliet, Principles of Political Economy)
- ✅ Category-based discovery (Amazon-inspired carousel UX) - 2025-11-28
  - ✅ Home page with category carousels (horizontal scrolling rows)
  - ✅ Categories sorted by book count (top 10 displayed)
  - ✅ Left/right navigation arrows for each carousel
  - ✅ "View All →" links to category detail pages
  - ✅ Header navigation menu items (Categories, All Books) - minimal text-only design
  - ✅ Category detail page (grid view of books in category)
  - ✅ All Categories page (all carousels, no limit)
  - ✅ All Books grid page
  - ✅ White background, clean minimal design
  - ✅ Category carousels hidden on book detail pages
  - ✅ URL routing for categories (#/category/5, #/categories, #/all-books)
- ✅ Navigation UX Improvements - 2025-11-28
  - ✅ Carousel book order randomization with caching (consistent across refreshes)
  - ✅ Category data caching (eliminates flash/reload)
  - ✅ Lazy loading for all book cover images (performance optimization)
  - ✅ Consistent "Back to Home" behavior (always returns to home, not browser history)
- ⏳ Persistent audio player (stays across navigation) - PARTIAL (player exists but resets on navigation)

### Phase 3: Full-Length Option (PLANNED)
- 📋 Display full chapter text (collapsible)
- 📋 Summary + full text side-by-side option
- 📋 Search within full text
- 📋 Highlighting and annotations

### Phase 4: Advanced Features (FUTURE)
- [✅] User identity and reading progress tracking — shipped (§7), trusted-header SSO not a standalone login system
- 📋 Favorites and reading lists
- 📋 Search across all books
- 📋 Book recommendations
- 📋 Multiple TTS voices
- 📋 Playback speed control
- 📋 Download summaries as PDF
- 📋 Export to EPUB for e-readers
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

### Data Quality (Added 2025-12-02)
- **Chapter Title Consistency:** All chapter titles use proper title case formatting
  - Automated normalization applied during import and backfilled for existing data
  - Handles edge cases: em-dashes, quoted text, punctuation
  - Result: Professional, consistent presentation across all 80 books
- **Implementation:**
  - `normalize_chapter_title()` function in `scripts/content/generate_summaries.py`
  - Backfill script: `scripts/backfills/backfill_chapter_title_case.py`
  - 1,013 titles updated out of 2,965 total chapters

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
- Q: Do we need user accounts / our own login system?
- A: No — decided 2026-09-06. Identity comes entirely from a shared Apache reverse-proxy gateway (`mod_auth_openidc` against Google) that also fronts `/pages/` and OpenReader; this app just reads a trusted `X-Remote-Email` header when present (`SUMMRA_AUTH_MODE=optional` in production). No registration/login form, no password, no session cookie of this app's own. Full history in §7 above and `WORK_LOG.md`. `users` / `reading_progress` / `chapter_completion` tables in `summra.db` still exist and are always active (`FEATURE_AUTH = True` by default) — what's gone is the standalone credential/login layer, not the progress tracking itself.

## Dependencies

### External Services
- **Google Gemini API:** Required for summary generation
  - Rate limits: 10 req/min, 250k tokens/min
  - Cost: ~$0.05-0.15 per book
- **Project Gutenberg:** Source for books and cover images
  - Free, public domain
  - No API key required

### Technical Stack
- **Frontend:** Vanilla HTML/CSS/JavaScript (single-page app, hash routing), installable PWA (no offline support)
- **Backend:** Python Flask (`backend/app_base.py` for shared routes, `app.py` for dev, `app_prod.py` for prod)
- **Databases:** SQLite — `data/database.db` for content, `summra.db` (project root) for users + reading progress
- **Summary / metadata / illustration generation:** Google Gemini (3.5 Flash + fallbacks; 2.5 Flash Image / batch for chapter illustrations)
- **Modern-English rewrite:** Google Gemini 3.1 Flash-Lite (`PLAIN_TEXT_MODEL`)
- **TTS:** Google Gemini 2.5 Flash TTS API (offline batch in prod, on-demand in dev)
- **Hosting:** GCP (e2-micro free tier, no on-demand TTS; or e2-small ~$13/mo with full TTS) — see `deploy/`

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
- **Concise / Short Summary:** ~500-word overview, spoiler-free for fiction
- **Medium / Full Summary:** 2000–3000 word comprehensive summary
- **Comprehensive Summary:** Chapter-by-chapter analysis
- **Modern English Rewrite (Plain English):** Sentence-by-sentence rewrite of the original chapter text into contemporary English, viewable side-by-side with the original
- **TTS:** Text-to-Speech conversion to audio (Google Gemini 2.5 Flash TTS)
- **Project Gutenberg:** Digital library of public domain books
- **Feature flag:** A boolean in `backend/config.py` that gates an entire subsystem (e.g. `FEATURE_AUTH`, `FEATURE_BLOG`)

### References
- Project Gutenberg: https://www.gutenberg.org/
- WCAG Accessibility Guidelines: https://www.w3.org/WAI/WCAG21/quickref/
- Google Gemini API: https://ai.google.dev/
- Gemini TTS docs: https://ai.google.dev/gemini-api/docs/speech-generation

---


## Recent Feature Updates (2025-12-03)

### Summary Tabs with Unified Listen Button

**Feature Description:**
Book summaries are now presented in a tabbed interface with "Short Summary" and "Full Summary" tabs, making it easier to switch between summary lengths.

**User Experience:**
- **Tab Navigation:** Click between "Short Summary" (500-word) and "Full Summary" (2000-word) without page reload
- **Unified Listen Button:** Single listen button positioned to the right of tabs
  - Automatically updates to play audio for the currently active tab
  - Shows/hides based on audio availability for each summary type
  - Consistent position regardless of which tab is active
- **Read More:** Expandable summaries with "Read more" button for longer content

**User Benefits:**
- Cleaner, more organized interface
- Easier comparison between summary lengths
- Consistent audio playback controls
- Better visual hierarchy

### About the Author Section

**Feature Description:**
Each book details page now includes an "About the Author" section with author information and related books.

**User Experience:**
- **Author Information:**
  - Author name displayed prominently
  - Country of origin shown inline with name
  - Author biography (placeholder: 100 words, ready for AI-generated content)

- **Books by This Author:**
  - Scrollable carousel of other books by the same author available on Summra
  - Book covers displayed when available
  - Left/right navigation arrows for browsing
  - Click any book to navigate to its details page

**User Stories:**
- As a reader who enjoys an author's style, I want to discover other books by the same author so I can continue reading their work
- As a student researching an author, I want quick access to their other works so I can understand their writing evolution
- As a curious reader, I want to learn about the author's background so I can better understand the context of their writing

**Specifications:**
- Shows up to 20 books by the same author
- Excludes the current book from the carousel
- Automatically hides section if author has no other books on Summra
- Reuses carousel design from "You May Also Like" for consistency

### Enhanced Chapter Experience

**Chapter Summary Box:**
- **Clickable Header:** Entire yellow summary box header is now clickable to expand/collapse
- **Visual Feedback:** Cursor changes to pointer when hovering over header
- **Smart Clicking:** TTS button within header doesn't trigger expansion (isolated click target)
- **Collapsed State:** Summary box starts collapsed to reduce page clutter
- **Short Chapters:** Summary box hidden entirely for short chapters (below MIN_CHAPTER_WORDS threshold) to avoid confusing "processing" messages

**Text Formatting:**
- **Italic Emphasis:** Project Gutenberg's underscore emphasis (`_word_`) now renders as proper italic text
- **Examples:**
  - `"He _said_ something"` displays as "He *said* something"
  - Preserves original formatting intent from classic texts
- **Security:** HTML escaping prevents XSS attacks while preserving emphasis

**User Benefits:**
- More intuitive interaction with chapter summaries
- Better reading experience with proper text formatting
- Reduced visual clutter with collapsed summaries
- Consistent with original book formatting conventions

### Reorganized Book Information

**Layout Updates:**
The "About This Book" section has been reorganized for better information flow:

1. **About This Book** - What the book is about
2. **Why Read This Now?** - Contemporary relevance and context
3. **About the Author** - Author biography and related works

**Previous Layout:**
- Two-column layout with "About This Book" and "Why Read This Now?" side by side
- Author information in a metadata bar below

**Current Layout:**
- Stacked single-column sections for better readability
- Author section includes biography and book discovery
- More scannable on mobile devices

**User Benefits:**
- Better information hierarchy
- Easier to read on all screen sizes
- Author discovery integrated naturally into the flow
- More engaging with carousel of related books

---

## Recent Feature Updates (2025-12-11)

### Modern Loading States

**Feature Description:**
Replaced skeleton loading states with a modern centered spinner design for a cleaner, more polished loading experience across all async operations.

**User Experience:**
- **Centered Spinner:** Single 48px rotating circular spinner with smooth animation
- **Contextual Messages:** Clear loading text indicates what's being loaded
  - "Loading summary..."
  - "Loading full summary..."
  - "Loading chapters..."
  - "Loading related books..."
  - "Loading book information..."
  - "Loading reading guide..."
  - "Loading chapter text..."
- **Smart Display:** Loading states only appear when content is actually empty (prevents flash on page refresh)
- **Fast Dismissal:** Spinner removed immediately when content loads

**Technical Implementation:**
- `.loading-container`: Centered flex container with padding
- `.loading-spinner`: Rotating border animation with CSS keyframes
- `.loading-text`: Subtle text below spinner
- Content check before displaying: `if (!element.textContent.trim())`
- SSR-compatible: Skips loading state when restoring from server-rendered content

**User Benefits:**
- Cleaner, more modern aesthetic
- Better understanding of what's loading
- No jarring flash when refreshing pages
- Consistent experience across all loading scenarios
- Professional, polished feel

**Acceptance Criteria:**
- [✅] Loading spinner displays for all async content operations
- [✅] Contextual message describes what's being loaded
- [✅] No flash when refreshing pages with existing content
- [✅] Spinner dismissed immediately when content loads
- [✅] Reading guide images properly dismiss loading state

### Discover Page Carousels

**Feature Description:**
The Discover page features multiple curated carousels to help users find books based on different criteria: popularity, difficulty level, audio availability, reading time, and thematic categories.

**User Experience:**
- **Multiple Discovery Paths:** Users can find books through various lenses
- **UI Consistency:** All carousels use standard carousel design
  - Regular book cards with cover, title, and author
  - Left/right navigation arrows
  - No rank overlays
  - No "View All" links
- **Clear Descriptions:** Each carousel includes a helpful subtitle explaining its criteria

**Page Flow (Updated 2025-12-14):**
1. **Popular** - Top 10 most downloaded books from Project Gutenberg
   - Based on Gutenberg IDs: [84, 2701, 1342, 46, 1513, 43, 11, 2641, 98, 345]
2. **Easy to Read** - Books for beginning readers (A2-B1 CEFR level)
3. **Books with Full Audio Summaries** - Books with complete audio narration
4. **Books You Can Read in a Day** - Shorter classics under 50,000 words (Added 2025-12-14)
5. **Adventure** - Adventure category books
6. **Children's Literature** - Children's category books
7. **Romance** - Romance category books
8. **Books by Charles Dickens** - Works by Charles Dickens

**User Stories:**
- As a new visitor, I want to see the most popular classics first so I can start with widely-loved books
- As a curious reader, I want quick access to popular books without searching
- As a literature explorer, I want popular books presented alongside difficulty levels
- As a busy reader, I want to find shorter classics that I can finish in one sitting
- As someone new to classics, I want audio summaries to help me understand books before reading them

**Technical Implementation:**

*Popular Carousel:*
- New method: `renderTop10AsStandardCarousel()`
- Reuses existing `renderCategoryCarousel()` for consistent UI
- Books loaded via `ensureBooksLoaded()` before rendering
- Popular carousel ID: 'popular' (excluded from "View All" link logic)

*Books You Can Read in a Day Carousel (Added 2025-12-14):*
- Backend filter: Books with `word_count < 50000`
- Carousel ID: 'quick-reads'
- Location: `backend/app_base.py:1051-1110`
- Returns 17 books ranging from 20,714 to 48,500 words
- Average reading time: 2-3 hours

*Other Carousels:*
- Backend endpoint: `/api/discover/carousels`
- Dynamic filtering based on CEFR level, audio availability, categories, and authors
- Location: `backend/app_base.py:1020-1138`

**User Benefits:**
- Multiple discovery paths for different user needs
- Quick identification of books by reading time
- Immediate access to popular books on Discover page
- Consistent UI with all carousels (no learning curve)
- Better discovery of widely-read classics
- Audio learners can find books with summaries

**Acceptance Criteria:**
- [✅] Popular carousel displays at top of Discover page
- [✅] Contains top 10 books based on Gutenberg download statistics
- [✅] Easy to Read carousel shows A2-B1 CEFR level books
- [✅] Books with Full Audio Summaries carousel shows only books with audio files
- [✅] Books You Can Read in a Day shows books under 50,000 words (Added 2025-12-14)
- [✅] All carousels use standard carousel UI (no rank overlays)
- [✅] No "View All" links displayed on any discover carousels
- [✅] Books load before carousel renders (no empty carousel)

---

### 11. Blog Header Images

**Feature Description:**
Blog posts feature visually engaging header images automatically sourced from Unsplash API. Images display as thumbnails in the blog index grid and as full headers on individual blog post pages.

**Added:** 2025-12-12

**User Stories:**
- As a reader browsing the blog, I want to see attractive thumbnails for each post so I can quickly identify topics of interest
- As a reader viewing a blog post, I want a visually appealing header image so the reading experience feels polished and professional
- As a blog administrator, I want header images to be automatically assigned so I don't have to manually source images

**Image Source:**
- **API:** Unsplash (https://unsplash.com/developers)
- **Selection:** Keyword-based smart search queries
- **Orientation:** Landscape (optimized for blog headers)
- **Size:** Regular (1080px width) for quality and performance balance
- **Rate Limit:** 1,000 requests/hour (Demo tier)

**Specifications:**

#### Blog Index (Thumbnail View)
- **Display Location:** Blog grid cards on `/blog` page
- **Image Size:** 200px height × full card width
- **Image Treatment:** Cover (cropped to fill)
- **Hover Effect:** 1.05x scale with smooth transition
- **Loading:** Lazy loading (loading="lazy") for performance
- **Fallback:** No image shown if header_image_url is null

#### Blog Post (Full Header View)
- **Display Location:** Top of blog post page (before title)
- **Image Size:** 400px max height × full width
- **Image Treatment:** Cover (cropped to fill)
- **Border Radius:** 12px for visual consistency
- **Loading:** Eager loading (loading="eager") for immediate display
- **Margin:** 30px bottom spacing before title
- **Fallback:** No image shown if header_image_url is null

#### Image Assignment Script
- **Script:** `scripts/blog/assign_blog_header_images.py`
- **Automated:** Run manually when new blog posts are added
- **Search Strategy:** Keyword mapping for relevant results
  - Example: "british" → "british library books vintage"
  - Example: "horror" → "dark atmospheric gothic"
  - Example: "romance" → "romantic vintage couple"
- **Selection:** First result from Unsplash (ranked by relevance)
- **Storage:** URL stored in `blog_posts.header_image_url` field

**UI Requirements:**
- Blog index grid displays thumbnail images above post titles
- Blog post pages display full header images with proper aspect ratio
- Images are responsive and scale appropriately on mobile devices
- Images maintain visual quality across all screen sizes
- Alt text includes blog post title for accessibility

**Acceptance Criteria:**
- [✅] Blog index shows thumbnail images for all posts with header_image_url
- [✅] Blog post pages show full header images at top of content
- [✅] Images load efficiently with appropriate lazy/eager loading
- [✅] Image assignment script successfully assigns relevant images
- [✅] Images maintain good quality without being too large (performance)
- [✅] Responsive design: images scale properly on mobile, tablet, desktop
- [✅] Graceful degradation: posts without images still display correctly

**Future Enhancements:**
- Interactive image selection tool (browse multiple Unsplash options)
- Manual URL override capability for custom images
- Photographer attribution display on frontend
- Additional filters (color palette, likes, downloads)
- Local image caching to reduce API calls

---

### 12. Page-Based Reading Experience (Pagination)

**Feature Description:**
Transform chapter reading from traditional scroll-based navigation to a page-based experience, mimicking Kindle's e-ink reading interface where users "turn pages" instead of scrolling.

**Added:** 2025-12-18
**Updated:** 2025-12-19 (v5.3-v5.17 bug fixes)

**User Stories:**
- As a reader, I want to navigate chapters by turning pages instead of scrolling so I get a more book-like reading experience
- As a reader on mobile, I want to swipe to turn pages so the interaction feels natural like a physical book
- As a reader, I want to see my progress as page numbers (e.g., "Page 5 of 24") so I know exactly how much I've read
- As a reader using a trackpad, I want to scroll to turn pages so navigation feels intuitive
- As a reader, I want the text to fit perfectly on each page so I never see partial sentences or awkward breaks

**Specifications:**

#### Page Calculation
- **Algorithm:** Height-based calculation that breaks content only at paragraph boundaries
- **Viewport Awareness:** Pages dynamically calculated based on window height minus fixed UI elements
- **Safety Margin:** 0.2 line buffer applied AFTER Math.ceil() to prevent text cutoff at paragraph endings
- **Responsive:** Automatic recalculation on window resize, font change, theme change, view mode change
- **Word Fitting:** When paragraphs exceed page height, split at word boundaries (never mid-word)

#### Navigation Methods (All Supported)
1. **Scroll-to-Turn** (Desktop)
   - Mouse wheel scroll down → next page
   - Mouse wheel scroll up → previous page
   - Trackpad scroll gestures supported
   - 100ms debounce to prevent rapid page flipping

2. **Swipe Gestures** (Mobile)
   - Swipe left → next page
   - Swipe right → previous page
   - Minimum swipe distance threshold

3. **Keyboard Shortcuts**
   - Arrow Right → next page
   - Arrow Left → previous page

4. **On-Screen Buttons**
   - Previous/Next buttons overlaid on content
   - Fade in on hover (desktop)
   - Always visible (mobile)
   - SVG chevron icons

#### Progress Display
- **Format:** "Page X of Y • Z%"
- **Location:** Bottom progress bar
- **Updates:** Instant on page change
- **Synchronization:** Progress bar width matches percentage
- **Example:** "Page 5 of 24 • 21%"

#### Reading Settings Integration
- **Font Size:** Slider controls text size (12-24px)
  - Triggers immediate pagination recalculation
  - Inline styles applied to pagination containers
  - No hardcoded CSS overrides

- **Font Family:** Georgia, System, Open Sans
  - Affects line height and word wrapping
  - Triggers recalculation on change

- **Theme:** Light, Dark, Sepia
  - Theme switching maintains pagination
  - Colors updated without recalculation

#### View Mode Support
- **Original Text:** Pagination of classic text
- **Modern English:** Pagination of simplified text
- **Side-by-Side:** Pagination of parallel columns
- **Mode switching:** Triggers automatic recalculation for new content

#### Position Persistence
- **Storage:** localStorage per chapter (`chapter_page_position_${bookId}_${chapterNumber}`)
- **Save Trigger:** Every page change
- **Restore:** On chapter load
- **Recalculation:** Maintains approximate position (page-level, not character-level)

#### Flash Prevention
- **Problem:** Unpaginated content briefly visible before pagination completes
- **Solution:** Section-level visibility control
  - Hide: `visibility: hidden` on chapter load
  - Show: `visibility: visible` after pagination complete
  - Preserves DOM layout for measurement
  - No complex positioning or z-index issues

#### Chapter Navigation Integration
- **Between Chapters:** "Previous Chapter" / "Next Chapter" buttons
- **Preface Support:** Handles chapter 0 (preface) correctly
- **Explicit Existence Checking:** Uses `.some()` to verify adjacent chapters exist
- **Works with:** Any chapter numbering scheme (0-based, 1-based, gaps)

#### Non-Scrollable Pages
- **Implementation:** `body.pagination-active { overflow: hidden }`
- **Wrapper:** Fixed height set by JavaScript
- **Overscroll:** `overscroll-behavior: contain` prevents bounce
- **Result:** Page never scrolls, content always fits viewport exactly

**UI Requirements:**
- Pages must fit exactly in viewport (no scrolling)
- Text selection must work everywhere (no blocking zones)
- Progress indicator updates instantly on page change
- Page turns must be instant (no animations as per user preference)
- Reading settings must apply immediately to paginated content
- Visual buttons must be accessible but not intrusive

**Acceptance Criteria:**
- [✅] Pages calculated based on viewport height
- [✅] Content breaks only at paragraph boundaries (no mid-sentence splits)
- [✅] All 4 navigation methods work (scroll, swipe, keyboard, buttons)
- [✅] Progress displayed as "Page X of Y • Z%"
- [✅] Page transitions are instant (no animations)
- [✅] Font size controls work with pagination (v5.3 fix)
- [✅] No text cutoff at page boundaries (v5.10 safety margin fix)
- [✅] No flash of unpaginated content during navigation (v5.14 fix)
- [✅] Navigation works from preface to Chapter 1 (v5.17 fix)
- [✅] Text selection works everywhere (tap zones removed)
- [✅] Pages never scroll (body overflow hidden)
- [✅] Position persists when returning to chapter
- [✅] Responsive: recalculates on window resize
- [✅] Theme/font changes trigger recalculation
- [✅] Works with all view modes (Original, Modern, Side-by-Side)

**Known Limitations:**
1. Position restoration after recalculation is approximate (page-level, not character-level)
2. Very long paragraphs may result in taller pages
3. Font loading must complete before accurate measurement
4. Pagination disabled for printing (uses normal scroll)

**Version History:**

| Version | Date | Changes |
|---------|------|---------|
| v5.3 | 2025-12-19 | Font size controls fix - removed CSS overrides, target pagination containers |
| v5.4-v5.10 | 2025-12-19 | Safety margin iterations - final: 0.2 line AFTER Math.ceil() |
| v5.11-v5.14 | 2025-12-19 | Flash prevention fixes - final: section visibility control |
| v5.15-v5.17 | 2025-12-19 | Chapter navigation fix - explicit existence checking for chapter 0 |

**Future Enhancements:**
- Character-level position tracking for perfect restoration after recalculation
- Optional subtle page turn animations (user preference toggle)
- Additional keyboard shortcuts (Home, End, Page Up/Down)
- More sophisticated touch gesture recognition
- Reading statistics tracking (pages read, time per page, total reading time)
- Book progress persistence across chapters ("You're on page 145 of 520 total")

---

**Document Version:** 2.0
**Last Updated:** 2025-12-19
**Author:** Summra Team
**Status:** Living Document


## 13. Data Quality & Integrity

### Database Audit System

**Feature Owner:** Engineering Team
**Priority:** High
**Status:** ✅ Implemented (2025-12-14)

#### Overview

Automated audit system to verify data integrity of chapter text stored in the database against original Project Gutenberg source files.

#### Current Quality Metrics

**As of 2025-12-14:**
- **98.7% overall coverage** across 55 books with source files
- **0 genuine discrepancies** (2 false positives due to audit limitations)
- **55.6% perfect matches** (<1% character difference)
- **9.9% minor differences** (whitespace normalization only)

#### Audit Process

1. Compare database `chapter_text` with re-extracted source chapters
2. Calculate character and word count discrepancies
3. Identify missing or extra chapters
4. Generate comprehensive metrics report
5. Flag books requiring investigation (>10% difference)

#### Acceptance Criteria

- [✅] Audit all 81 books in database
- [✅] Generate detailed CSV report with metrics
- [✅] Identify discrepancies >10% (requires investigation)
- [✅] Verify database integrity (98.7% coverage achieved)
- [✅] Document known edge cases (em-dash format, poems, etc.)

#### Future Enhancements

- Improve audit script chapter detection patterns
- Add source files for 26 books currently missing
- Automated verification after book processing
- Coverage metrics in admin interface
- Alert system for <95% coverage

---

**Document Version:** 2.0
**Last Updated:** 2025-12-14
**Author:** Summra Team
**Status:** Living Document


---

## Progressive Web App (PWA) Installability

**Feature Owner:** Engineering Team
**Priority:** Medium
**Status:** ✅ Implemented — installability only (offline support removed 2026-09-07)

### Overview

Summra can be installed to a device's home screen for a native, browser-chrome-free launch experience. It has no offline mode: the app assumes an internet connection is always available. The previous "Progressive Web App" offering (service worker, automatic page caching, "Save for Offline" book downloads, an offline fallback page) was removed — it caused more problems (stale-cache bugs, iOS cache-eviction workarounds, sync complexity) than it solved. See `WORK_LOG.md` for the removal entry.

### User Stories

**As a mobile user**, I want to:
- Install Summra as an app on my home screen
- Have the app feel native without browser chrome

**As an iOS user**, I want to:
- See clear instructions on how to install the app (since iOS doesn't show automatic prompts)
- Install via Share → "Add to Home Screen"

**As an Android user**, I want to:
- See automatic install prompts from Chrome
- Install with one tap

### Features

#### Installable App

**What:**
- Users can install Summra as a standalone app
- App icon appears on device home screen
- Opens in full-screen mode (no browser UI)

**How:**
- Web App Manifest (`frontend/templates/manifest.json`, served at `/manifest.json`) defines app metadata
- Android: Automatic install prompt (`beforeinstallprompt`)
- iOS: Custom install instructions banner (`#ios-install-banner`)

**Acceptance Criteria:**
- [✅] Manifest.json with app metadata
- [✅] Icons (192x192, 512x512 PNG)
- [✅] Standalone display mode
- [✅] Theme color (#1a1a1a)
- [✅] App opens full-screen when launched from home screen
- [✅] iOS install banner, dismissible (`localStorage.installBannerDismissed`), doesn't reappear once dismissed or once installed

### Technical Implementation

**Files:**
- `frontend/templates/manifest.json` - Web app manifest (Jinja-rendered for `base_path`/asset versioning)
- `frontend/templates/index.html` - Manifest link, iOS meta tags, install banner
- `frontend/static/js/app.js` - `setupInstallPrompt()` (iOS banner + Android `beforeinstallprompt`)
- `frontend/static/css/style.css` - iOS banner styles

**Flask Route:**
- `/manifest.json` - Serves the manifest with correct content type (`backend/routes/system.py`)

---

## 14. Plain English Rewrites (Headline Feature)

**Feature Owner:** Engineering + Content Team
**Priority:** Critical — current site headline ("Read the Classics in Plain English") is built around this feature
**Status:** ✅ Implemented (ongoing — rolled out per-book as chapters are generated)

### Overview

Every chapter has a **modern-English rewrite** generated from the original text. The rewrite preserves the meaning, structure, and paragraph boundaries of the source but renders it in the English a contemporary reader actually speaks — short sentences, modern vocabulary, no archaic syntax. Users read this side-by-side with the original (desktop) or by itself (mobile).

This is not a summary. The rewrite is the same scene, chapter by chapter, sentence by sentence — just in plain English.

### User Stories

- As a reader put off by Victorian or Romantic-era prose, I want a version of the actual chapter in modern English so I can enjoy the story without parsing every sentence twice
- As a student, I want the original and the plain version side-by-side so I can build comprehension
- As an ESL reader, I want plain English versions so the language doesn't get in the way of the story
- As a long-form reader, I want the option to read only the plain version on my phone, because side-by-side doesn't fit on a small screen

### Specifications

**Storage:**
- Stored per chapter in `chapters.modern_english_text` (TEXT, nullable; column added by migration in `models.py`)
- Generated independently from the chapter summary; books can have summaries without modern English, or vice versa

**Generation:**
- Script: `scripts/content/generate_modern_english.py`
- Model: `PLAIN_TEXT_MODEL` in `backend/config.py` (currently `gemini-3.1-flash-lite`)
- Per-chapter prompt; output is plain text matching paragraph structure of the original
- Subject to the same Gemini rate limiter as summary generation

**Reading view:**
- Three view modes on the chapter page:
  1. **Original** — original Project Gutenberg text only
  2. **Modern** — plain English only
  3. **Side-by-Side** — two columns, original on the left, modern on the right, paragraph-aligned (desktop only; mobile falls back to Modern)
- Reading settings (font family, size, theme, pagination) apply across all three view modes
- Page-based pagination recalculates when view mode changes

**Hero-page CTA:**
- The Read section card on the home page links directly to **Jane Eyre, Chapter 1** as a demo
  - Desktop CTA opens side-by-side view
  - Mobile CTA opens modern-only view (side-by-side doesn't fit on small screens)

### Acceptance Criteria

- [✅] `modern_english_text` column present in `chapters` table
- [✅] `scripts/content/generate_modern_english.py` generates and persists rewrites
- [✅] Chapter API (`GET /api/books/<id>/chapters/<n>`) returns `modern_english_text` when present
- [✅] Frontend offers Original / Modern / Side-by-Side view modes
- [✅] Side-by-Side view paragraph-aligns the two columns
- [✅] Mobile falls back to Modern when user picks Side-by-Side
- [✅] Pagination recalculates when view mode changes (PRD §12)
- [✅] Reading settings (font, size, theme) apply to all three view modes
- [✅] Chapters without a generated rewrite degrade gracefully (Modern + Side-by-Side hidden or disabled)

### Future Enhancements

- Backfill modern-English for the remaining chapters that don't have it yet
- Per-book quality regen (regenerate any chapter where the rewrite was flagged as low quality)
- Reader-controlled "translation level" (lighter vs. heavier modernization)
- Surface a per-chapter language-difficulty indicator on the chapter list so readers know which chapters most benefit from the plain version

---

## 15. Editorial Blog (Feature-Flagged)

**Feature Owner:** Content Team
**Status:** Implemented but **dark by default** — gated behind `FEATURE_BLOG` in `backend/config.py` (default `False`)

### Overview

A long-form editorial blog for essays, book deep-dives, and topical pieces (e.g. AI-and-classics commentary). Lives in the `blog_posts` table and is rendered through dedicated routes when the flag is on. Header images come from Unsplash.

### Specifications

- **Routes (gated):**
  - `GET /blog` — Blog index (cards with header image, title, excerpt)
  - `GET /blog/<slug>` — Individual blog post (full header image, body)
  - `GET /api/blog` — JSON list
  - `GET /api/blog/<slug>` — JSON post
- **Storage:** `blog_posts(id, slug UNIQUE, title, content, excerpt, author, published_date, updated_date, header_image_url, created_at)`
- **Header images:** Unsplash API via `scripts/blog/assign_blog_header_images.py` (requires `UNSPLASH_ACCESS_KEY` env var). Search terms are mapped per blog topic (e.g. "british" → "british library books vintage")
- **Sitemap integration:** When `FEATURE_BLOG=True`, blog URLs are included in `sitemap.xml`
- **Frontend:** Server-rendered HTML pages, not part of the SPA shell

### Acceptance Criteria

- [✅] Schema present in `models.py`
- [✅] Blog routes registered under `if config.FEATURE_BLOG:`
- [✅] Routes return clean 404s when flag is off
- [✅] Sitemap omits blog URLs when flag is off
- [✅] Header-image assignment script works against the Unsplash Demo tier (1,000 req/hr cap)

### Future Enhancements

- Tag and category system for blog posts
- Author profiles linked to author hub pages
- RSS feed
- Comments / discussion (would require auth — see Feature 7)

---

## Feature Flag Bundle

The following subsystems are **implemented in code but dark by default**, gated by flags in `backend/config.py`. The flags exist so the production deployment can stay focused on the core reading experience while heavier or less-polished subsystems are wired through but inert.

| Flag | Default | What it gates |
|------|---------|---------------|
| `FEATURE_AUTH` | `True` (changed 2026-09-06; was `False`) | Registers the progress-tracking and whoami blueprints (identity + reading-progress tracking, Continue-Reading button — PRD §7). No longer a registration/login system — see §7's superseded note. Per-host reach of identity is separately controlled by `SUMMRA_AUTH_MODE` (`off`/`optional`/`required`), not this flag. |
| `FEATURE_BLOG` | `False` | Editorial blog routes, blog API endpoints, blog entries in `sitemap.xml` (PRD §15) |

**Convention:**
- Backend: blueprints are conditionally registered (`if config.FEATURE_AUTH: init_pchauth(...); app.register_blueprint(progress_routes.progress_bp); app.register_blueprint(whoami.whoami_bp)`); routes return 404 when the flag is off
- Frontend: the flag values are injected into the SPA shell as `window.FEATURE_AUTH` / `window.FEATURE_BLOG`, and the gated button markup is server-stripped from `index.html` when off
- Tests: feature flags are exercised by `tests/test_feature_flags.py`

When updating the PRD or ERD for a feature-flagged subsystem, always note the flag status — the section can otherwise read as if the feature is live to all users.

---

**Document Version:** 2.2
**Last Updated:** 2026-05-30
**Author:** Summra Team
**Status:** Living Document
