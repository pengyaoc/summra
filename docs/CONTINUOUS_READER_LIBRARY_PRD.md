# Summra Library and Continuous Reader

**Product requirements document**

- **Status:** Implemented; pending VM acceptance test
- **Owner:** Product and Engineering
- **Last updated:** 2026-09-07
- **Target:** Web and installable PWA

## 1. Summary

Summra will move from a chapter-centric reading experience to this product model:

> Library -> continuous book reader -> automatic per-mode resume

A book is one uninterrupted reading destination. Chapters and parts remain visible structural landmarks, table-of-contents targets, and stable location context; they are not separate cards or chapter destinations. The book itself still renders as turnable pages.

Signed-in readers land on a personal Library after login. Selecting a book anywhere opens the continuous reader directly. Signed-out visitors continue to land on the Home page and may discover and read without an account; their progress is saved on the device and merged into their account after sign-in.

The reader preserves Summra's existing book-like, viewport-based pagination and page-turn interaction. “Continuous” describes the logical book session: page turns proceed across chapter boundaries without a chapter destination or loading screen. The reader saves a durable text anchor for each reading mode instead of treating a rendered page number as the reading location. Content is delivered progressively in bounded paragraph segments so opening a large book is fast without downloading or paginating the whole book at once.

## 2. Problem

The current implementation has useful foundations but exposes the storage model in the product experience:

- Cloud progress is one row per user and book in `backend/user_models.py`.
- `/api/progress` saves chapter, rendered page, and pixel scroll position.
- The book page may show a chapter/page-based Continue Reading action.
- Pagination saves page changes and treats reaching a chapter's last rendered page as chapter completion.
- Book detail presents chapters as separate destinations.
- The account experience shows aggregate counts rather than a useful reading library.

This creates five product problems:

1. Reading stops at artificial chapter page boundaries.
2. Resume locations move when font, viewport, pagination, or mode changes.
3. One book-level progress record cannot remember a location for each mode.
4. Going backward can incorrectly reduce apparent progress, while jumping ahead can incorrectly imply completion.
5. Opening a chapter records its opening position before restore completes, which can overwrite the location the reader intended to resume.

The current backend is therefore migration input, not a contract the new experience must preserve.

## 3. Goals

- Make Library the signed-in reader's primary home and the post-login destination.
- Make every book a single, continuously paginated reading experience with the existing book-like page-turn behavior.
- Restore the same logical passage across font, viewport, device, and layout changes.
- Remember current location and furthest genuine reading extent independently for every mode.
- Keep first content latency low while progressively loading large books.
- Preserve signed-out reading and merge device progress safely after sign-in.
- Sync quietly across devices without unexpectedly moving an active reader.
- Make completion book-centric and resistant to false completion from TOC jumps.

## 4. Non-goals

- Generating new summaries, translations, paragraph alignments, illustrations, or audio.
- Replacing the Discover catalog or recommendation system beyond its navigation and book-opening behavior.
- Durable audio-playback resume. Audio may remain available in reader chrome, but audio position is a separate future marker.
- Annotations, highlights, bookmarks, social reading, streaks, goals, or reading-speed estimates.
- Native mobile applications.
- Removing chapter-level data needed for content generation, analytics, URLs, or internal operations.
- Replacing the existing book-like paginated reader with a continuous vertical-scroll presentation.

## 5. Product principles

- **The book is the destination.** A chapter URL opens the same book reader at a chapter anchor.
- **Paging remains the reading model.** The change removes chapter destinations, not book-like pages or page-turn interaction.
- **Resume is automatic.** A reader should not have to choose a chapter or confirm a saved location.
- **Location is semantic.** Paragraph anchors survive presentation changes; page numbers and pixels do not.
- **Modes are independent views.** Each mode retains its own current marker and furthest extent.
- **Structure remains useful.** Parts and chapters organize navigation without fragmenting the reading flow.
- **Progress is earned.** Opening, previewing, searching, or jumping does not count as reading.
- **Sync does not seize control.** Remote progress may be suggested, never used to move an active reader unexpectedly.
- **Progressive loading is invisible.** Network chunking must not look like chapter-by-chapter navigation.

## 6. Users and key jobs

### Returning reader

“Take me directly back to the passage and mode where I stopped, regardless of which device or reading settings I use.”

### Exploring reader

“Let me open a classic immediately, understand what it is when I need context, and keep my place without creating an account.”

### Mode-switching reader

“Let me alternate between the original, plain-English, summary, and paired text without losing my separate place in any of them.”

### Student or reference reader

“Let me move quickly through a long book's structure without those jumps being mistaken for completed reading.”

## 7. Information architecture and navigation

### 7.1 Signed-in navigation

The primary navigation order is:

1. Library
2. Discover

Account and sign-out controls remain utilities, not primary destinations. Successful login always completes the local-progress merge and then lands on `/library`. If authentication began while opening a protected deep link, Library may offer a one-time “Return to [book]” notice, but the automatic post-login destination remains Library.

### 7.2 Signed-out navigation

- `/` remains the default Home page and signed-out landing page.
- Discover remains accessible from Home and primary navigation.
- Library is not presented as a signed-out account destination.
- Opening a book shows its editorial detail page without requiring login. The explicit **Read book** action opens the continuous reader.
- Progress and mode preference are saved locally on the device.
- Sign-in returns to Library after merging local activity.

### 7.3 Canonical destinations

| Destination | Canonical behavior |
| --- | --- |
| `/` | Home; signed-out default |
| `/library` | Personal Library; authentication required |
| `/discover` | Catalog and recommendations |
| `/books/{slug}` | Editorial book page: author context, summary, and the explicit **Read book** entry point |
| `/books/{slug}/read` | Continuous reader, automatically resumed |
| `/books/{slug}/read?chapter={chapter_id}` | Same reader anchored to a chapter |
| Existing `/books/{slug}/chapters/{number}` | Same reader anchored to that chapter; no separate chapter UI |

Legacy chapter URLs retain their server-rendered metadata and crawlability. They may redirect to the canonical reader only after SEO impact is assessed; either way, the visible experience is the continuous reader.

### 7.4 Book selection

Selecting a book card from Library, Home, Discover, search, categories, author pages, or related books opens that book's editorial detail page. There is no intermediate chapter grid or confirmation screen. Description, full-book overview, author, categories, and related books remain on that page; **Read book** is the explicit reader entry point.

## 8. Personal Library

Library is a reading surface, not an account dashboard.

### 8.1 Continue Reading

Continue Reading is the first and most prominent section. It is a horizontal shelf ordered by descending `last_meaningful_read_at`.

Each card shows:

- Cover, title, and author
- Most recently used mode, with user-facing labels: Summary, Original, Plain English, or Side-by-Side
- Whole-book furthest-read percentage in that mode
- Current chapter as secondary context
- Human-readable last-read recency, such as “Yesterday”
- A Continue action

The entire card is the primary action and opens the active mode at that mode's current marker. The explicit Continue control has the same destination and exists for clarity and keyboard access. The most recently read book receives greater visual weight without preventing at least the next several books from being visible or horizontally reachable.

#### Meaningful engagement rule

A book enters Continue Reading after the first of these **sequential-reading** events:

- forward page turns advance the current marker across two paragraph boundaries from the mode's opening marker; or
- the reader accumulates 60 seconds of active reading and stops beyond the opening paragraph.

Active reading time counts only while the document is visible and the reader has interacted within the preceding 30 seconds. An initial open, restore, mode mapping, TOC jump, browser find/search jump, or programmatic page change does not satisfy the rule by itself.

Once a book has meaningfully started, later backward reading may update its current marker and recency without removing it from Continue Reading. Finished books are excluded from Continue Reading until marked unfinished or genuinely resumed before the end.

### 8.2 Finished

- Shows books with status `finished`, ordered by `finished_at` descending.
- Cards show cover, title, author, last-used mode, completion date, and a read-again action.
- The overflow menu provides **Mark as unfinished**.
- Mark as unfinished changes the book status to `in_progress`, clears `finished_at`, and keeps all per-mode markers and furthest extents.
- Auto-completion is suppressed until the reader subsequently performs a new sequential traversal into the true end; merely reopening the end does not instantly reverse the manual action.

### 8.3 Recently opened

Recently opened is deferred for the first release. Add it only if analytics show a meaningful population of previewed-but-unstarted books and user research shows value. Preview-only activity is retained for analytics for 30 days but does not appear in Continue Reading.

### 8.4 Empty Library

When no book is in progress or finished, show:

- A short explanation: “Books you start will appear here, with your place saved automatically.”
- Primary action: **Find your first classic** -> Discover

Do not show account counts, chapter checklists, empty shelves, or setup tasks.

### 8.5 Library states

- Render a skeleton for the shelf rather than shifting completed card layouts.
- If cloud data fails but cached library data exists, show cached data with a quiet offline indicator.
- If neither cloud nor cache is available, preserve the page and offer Retry plus Discover.
- Card cover failure must fall back to the existing generated/default cover treatment.

## 9. Continuous reader

### 9.1 Reader presentation

- Preserve the current viewport-responsive pagination, book-like page presentation, page-turn controls, navigation zones, typography/layout settings, and established click/tap/swipe/keyboard behavior.
- Do not replace the primary reading experience with a vertically scrolling document.
- Treat the active mode as one logical paginated book. Parts and chapters appear as restrained headings within the page flow and may include existing illustrations.
- A visual page remains a presentation artifact that may change with font, viewport, mode, or settings. It may be shown in the live UI but is never the durable or synced location.
- A forward page turn from the final page of one chapter opens the first page containing the next chapter in the same reader session, with the same interaction and animation as any other page turn.
- Crossing a chapter boundary requires no route change, book landing page, chapter selection, or full-screen loading state.
- Pagination may run incrementally over fetched segments; it must not require all book text to be downloaded or laid out before the first page is readable.
- The document URL may update its chapter query or history state as the active chapter changes, without causing navigation.
- Browser Back from the reader returns to the prior product surface. The visible Back control always returns to that book's editorial detail page, preserving the book context and explicit re-entry point.

### 9.2 Reader chrome

The reader uses a persistent, single-row dark toolbar. It must remain one content row at iPhone widths (safe-area inset may increase its outer height) and must not steal page-turn gestures or text selection.

Header controls, in order:

- Back to the editorial book page
- Current chapter and book title (book title may truncate or be omitted on narrow screens)
- Compact Contents icon, opening a chapter-picker drawer/sheet
- Matching compact Reading Settings icon

Reading Settings contains the four reading-mode controls as well as typography and theme. The full author, summary, and related-book context remains on the editorial book page rather than competing with the focused reader toolbar.

Slim footer:

- Whole-book furthest-read percentage for the active mode
- Current chapter name

Future reading-time estimates are not shown until there is enough reliable, consent-appropriate reading-speed data.

### 9.3 Entry and restoration sequence

The reader must use this order:

1. Resolve the requested book, optional chapter deep link, identity, local state, and remote state.
2. Select the entry mode: explicit mode in a valid deep link, otherwise last-used mode, otherwise Plain English when available, otherwise Original.
3. Select the entry marker: explicit chapter deep link, otherwise that mode's current marker, otherwise map from the last-used mode, otherwise the book opening.
4. Fetch the manifest and bounded segment containing the marker.
5. Paginate the target segment and display the rendered page containing the marker without a page-turn animation.
6. Enable observation and progress writes only after restoration has completed.
7. Prefetch adjacent segments.

No default marker, page zero, chapter opening, scroll position, or mode change may be persisted before step 6. This invariant fixes the current resume-overwrite defect and applies to initial load, reload, mode changes, history navigation, and error retries.

### 9.4 Loading and error behavior

- Show title/chapter skeletons only for the initial unresolved segment.
- Never show a chapter loading screen between already adjacent content.
- If content required for the next page is slow, retain the current page and show a small, non-blocking loading indicator in the page-turn affordance.
- Retry transient segment failures automatically with capped exponential backoff, then expose an inline Retry action.
- A failed future segment must not discard rendered content or the current marker.
- If the exact saved paragraph no longer exists, use the anchor-recovery rules in section 12.4 and disclose only if recovery falls back beyond the saved chapter.

## 10. Reading modes

Reading Settings exposes the four modes in this order:

1. Summary
2. Original
3. Plain English
4. Side-by-Side

Unavailable content remains visible but disabled with an explanation. Side-by-Side is available only at **1024 CSS px or wider**; an open Side-by-Side reader that becomes narrower automatically returns to Plain English (or Original when Plain English is unavailable), preserving the semantic anchor. A book with partial Plain English coverage permits the mode and shows a restrained “Plain English unavailable for this section” gap with an Original fallback action; it does not silently mix modes.

### 10.1 Summary

- Concatenate the existing chapter summaries into one logical book sequence and paginate it with the same reader.
- Retain part/chapter headings, illustrations where appropriate, and TOC navigation.
- The existing full-book summary remains on the editorial book page, not in the Summary reading sequence.
- Summary progress has its own denominator and marker.

### 10.2 Original

Render the canonical original paragraphs in book order.

### 10.3 Plain English

Render aligned plain-English paragraphs in book order. Its marker is independent after first entry.

### 10.4 Side-by-Side

- Screens at or above 1024 CSS px: synchronized paragraph rows with Original and Plain English columns.
- Narrow screens and portrait layouts: the mode is disabled rather than stacked; Plain English or Original remains available as the single-column alternative.
- Each aligned pair has one logical position. Changing responsive layout does not change the marker.
- When one side lacks a paragraph, preserve the logical row and show an explicit unavailable state rather than shifting later alignment.

The first release enables Side-by-Side only at a 1024 CSS px viewport threshold; device type is not used.

### 10.5 First-use mapping and independent resume

- Returning to a mode with a saved marker restores that marker.
- Entering Original, Plain English, or Side-by-Side for the first time maps to the aligned logical paragraph nearest the current visible anchor.
- Entering Summary for the first time maps to the current anchor's chapter heading, because summary paragraphs do not align with full text.
- Entering a full-text mode from Summary maps to the first paragraph of the corresponding chapter.
- The mapped marker is an entry position, not meaningful engagement or furthest-read progress.
- After entry, each mode advances and resumes independently.
- A mode change saves the departing mode's settled current marker before resolving the destination marker.

## 11. Table of contents

The TOC is a drawer/sheet, never a chapter grid.

It shows:

- Existing part and chapter hierarchy
- Current chapter highlight
- Per-chapter progress through the active mode, derived from furthest extent
- Search when a book has more than 40 TOC entries

Search matches part and chapter titles, is case-insensitive, and does not search full book text.

Selecting an entry:

1. closes the drawer;
2. progressively fetches the target segment if necessary;
3. paginates and displays the page containing the chapter heading without reloading the reader;
4. updates the active current marker and URL/history state;
5. does **not** advance furthest extent, meaningful-engagement counters, or completion.

The current marker may subsequently advance normally if the user begins sequential reading from the selected location.

## 12. Durable position and progress semantics

### 12.1 Stable anchor

A marker is represented conceptually as:

```json
{
  "book_id": 123,
  "mode": "plain",
  "content_version": 7,
  "chapter_id": 456,
  "paragraph_id": "p_01J...",
  "offset": 0.42,
  "quote": "short normalized recovery excerpt",
  "updated_at": "2026-09-07T20:15:00Z"
}
```

- `chapter_id` and `paragraph_id` are stable content identifiers, not array indexes.
- `offset` is a clamped 0..1 fraction through the logical paragraph, not a pixel or rendered line.
- `quote` is a normalized, privacy-safe excerpt from public-domain content used only for recovery.
- `content_version` identifies the paragraph/alignment manifest used to create the marker.
- Side-by-Side uses the aligned pair's logical paragraph ID.
- Summary uses summary-specific paragraph IDs.

Paragraph identifiers are persisted in content data. They must not be regenerated on every request or derived solely from mutable paragraph text.

### 12.2 Current marker versus furthest extent

For each `(user or device, book, mode)` retain:

- `current_marker`: the most recently settled reading location, including intentional backward reading and TOC navigation.
- `furthest_marker`: the greatest position reached through qualified sequential reading.

Current marker may move in either direction. Furthest marker is monotonic within a content version and never decreases because of backward reading, a TOC jump, mode mapping, or remote merge. A content-version update may remap it but must preserve the closest equivalent extent and an audit record. This is content recovery within v2, not migration of the removed legacy progress database.

### 12.3 Percentage

- Calculate percentage against ordered logical units for the active mode, weighted by canonical word count with paragraph offset interpolation.
- Chapter/part headings and illustrations have zero weight.
- Summary uses summary word count; Original and Plain English use their own mode word counts; Side-by-Side uses the shared alignment sequence once, not the sum of both columns.
- Display a whole number from 0% through 100%.
- Library and reader chrome display the furthest-read percentage, not current-marker percentage.
- 100% is displayed only when the book is finished. Pre-completion rounding is capped at 99%.

### 12.4 Anchor recovery after content changes

Resolve an old marker in this order:

1. same paragraph ID in the current manifest;
2. explicit old-to-new paragraph mapping generated with the content revision;
3. unique normalized quote match within the same chapter;
4. nearest surviving paragraph before/after the old ordinal within the same chapter;
5. chapter opening;
6. book opening if the chapter no longer exists.

Record the recovery level for diagnostics. Do not overwrite the stored marker until restoration succeeds. If recovery falls back to another chapter or the book opening, tell the reader that the text changed and their place was restored approximately.

### 12.5 Settled marker

The current marker is the first logical reading position visible on the displayed page: its paragraph ID plus the paragraph-relative offset of the first visible text fragment. If a paragraph spans multiple rendered pages, each page therefore restores to the correct portion of that paragraph. A marker becomes settled 600 ms after a completed page turn or target-page restoration. Build this mapping as part of pagination; never scan or reprocess the entire book on every page turn.

### 12.6 Save triggers

Queue a silent save:

- after a page turn settles;
- before a mode change;
- after a TOC navigation settles;
- when `visibilitychange` makes the document hidden;
- on `pagehide`;
- before in-app navigation away from the reader; and
- at most every 15 seconds during sustained reading.

Coalesce saves per book/mode. Use `sendBeacon` or `fetch(..., {keepalive: true})` for lifecycle saves where supported, while always writing the same mutation to the local durable queue first.

## 13. Progressive content delivery

The user experiences a whole book; the client and server exchange bounded segments.

### 13.1 Manifest-first protocol

`GET /api/reader/books/{book_id}/manifest`

Returns metadata only:

- book identity, title, author, cover, content version
- ordered parts and chapters with stable IDs and titles
- mode availability and partial-coverage flags
- ordered segment descriptors and word-count ranges per mode
- paragraph-alignment version for the three full-text modes
- illustration and audio availability metadata
- total logical word count per mode

The manifest must not contain chapter prose, chapter summaries, or full-book descriptions.

### 13.2 Segment protocol

`GET /api/reader/books/{book_id}/segments/{segment_id}?mode={mode}`

Returns:

- stable segment, chapter, and content-version identifiers
- ordered paragraphs or aligned pairs with stable paragraph IDs
- structural headings that begin within the segment
- previous and next segment IDs
- word-range metadata needed for progress
- optional illustration references, never large inline image payloads

Segment boundaries are independent of visual pages and may cross neither a chapter heading nor an alignment row. Generation targets 24 KiB of uncompressed text and must cap a response at 64 KiB or 80 logical paragraphs, whichever occurs first. An unusually large single paragraph may exceed the byte cap as one paragraph and is flagged in metadata.

Responses support Brotli/gzip, ETag revalidation, immutable caching by `(book, mode, content_version, segment_id)`, and cancellation through `AbortController`.

### 13.3 Initial and adjacent loading

- Fetch the manifest and the segment containing the entry marker in parallel when a cached manifest can resolve the marker; otherwise fetch the manifest first.
- Paginate and render the target page as soon as its segment arrives.
- Prefetch two segments ahead and one behind on normal networks.
- On `Save-Data`, 2G, or repeated high latency, prefetch one ahead and none behind.
- Begin the next fetch when the current page is within two rendered pages of the end of buffered content.
- Fetch backward content when the current page is within one rendered page of the beginning of buffered content.
- Abort obsolete target/prefetch requests after a mode change or distant TOC jump.
- Deduplicate concurrent requests and limit content fetch concurrency to three.

### 13.4 Continuous pagination

- Feed fetched segments into one logical pagination sequence in book order.
- Preserve the existing page renderer and page-turn interaction; the new content layer supplies more book content to it incrementally.
- Segment boundaries never become visual page boundaries. Withhold a nonterminal trailing partial page until enough of the next segment has arrived to compose that page completely; if it is not ready, keep the current page visible with the loading affordance rather than exposing a short page that later reflows.
- Maintain a stable mapping from each rendered page's first visible text fragment to its semantic paragraph anchor.
- When settings, mode, or viewport change, repaginate around the semantic current marker and display the new page containing that marker. Never restore by the old rendered page index.
- Adding a preceding segment or evicting distant layout data must not change the visible passage. Re-resolve the same semantic anchor after pagination indexes update.
- Keep target, current, immediately previous, and immediately next pages laid out. Distant segments may retain content without live page DOM; under memory pressure, refetch immutable cached segments and repaginate from their anchors.
- Chapter boundaries do not control the visible experience: a prefetched next segment should make the boundary page turn indistinguishable from an ordinary page turn.

### 13.5 Performance budgets

Measured at the 75th percentile on a mid-tier mobile device and a warm application shell:

- Reader shell visible: <= 1.0 s
- Resume target text visible on broadband/Wi-Fi: <= 1.5 s
- Resume target text visible on simulated Fast 3G: <= 2.5 s
- No request for reading prose exceeds the segment response cap, except a flagged single paragraph
- No blank inter-chapter frame during sequential reading when the network meets Fast 3G
- Reader interaction long tasks: none over 100 ms during an ordinary page turn
- Cumulative layout shift after target positioning: <= 0.1
- Initial reader text payload, excluding images/audio: <= 150 KiB transferred

The client records manifest, target-segment, first-text, next-segment-ready, restore-complete, and inter-chapter-stall timings.

## 14. Completion

Completion is stored once per user/device and book, independent of the active mode.

A book is automatically marked Finished only when all are true:

1. the terminal segment for the active mode is loaded;
2. the reader advances sequentially into the final logical paragraph from an immediately preceding logical position;
3. the page containing the terminal reading position remains displayed for at least two seconds while the document is active; and
4. the event is not attributed to restore, TOC, search, deep link, mode mapping, browser find, or a programmatic page change.

Jumping to the last chapter, selecting the last TOC entry, opening an end deep link, or dragging directly to the end does not finish the book. Those actions may update current marker but not furthest extent.

On completion:

- set status to `finished` and `finished_at` once;
- set the active mode's furthest extent to its terminal marker;
- display 100% for that mode;
- keep other modes' independent furthest extents unchanged;
- move the book from Continue Reading to Finished on the next Library update; and
- offer **Keep reading** and **Back to Library** without a blocking celebration.

Chapter checkmarks disappear from the primary UI. The disposable legacy progress database is removed at cutover, so its chapter-completion data is neither retained nor migrated; it is not a source of book completion.

## 15. Local reading, offline queue, and cross-device sync

### 15.1 Device storage

Use IndexedDB, not only `localStorage`, for:

- per-mode current/furthest marker state
- book status and meaningful-engagement state
- last-used mode
- monotonic device sequence
- pending idempotent mutations
- cached Library projection
- cached manifests and reader segments coordinated with the service worker

Every progress mutation is committed locally first and then sent to the server when signed in and online. A server failure never prevents local resume.

### 15.2 Identity and device identifiers

- Generate a random, non-fingerprinting `device_id` per browser profile.
- Give each mutation a unique `mutation_id`, `device_id`, `device_sequence`, client occurrence time, and last-known server revision.
- The server deduplicates mutation IDs and assigns authoritative receipt time and revision.
- Signing out removes cached identity but does not delete anonymous reading progress unless the user explicitly clears device data.

### 15.3 Save API

`POST /api/progress/v2/mutations`

A mutation includes:

- book, mode, content version
- current marker
- optional qualified furthest marker
- event cause: `page_turn`, `mode_exit`, `toc`, `hidden`, `pagehide`, `navigation`, `completion`, or `manual_unfinish`
- meaningful-engagement counters/flags
- completion transition when applicable
- idempotency and revision fields

The response returns:

- accepted server revision and canonical projection;
- duplicate acknowledgement; or
- conflict details with both local and remote candidates.

`GET /api/progress/v2/books/{book_id}` returns all mode states, book status, revisions, and server timestamps. `GET /api/library` returns denormalized cards and mode projections needed to render Library without N+1 requests.

### 15.4 Merge rules

For both sign-in merge and normal sync:

- Furthest extent is the maximum qualified logical extent per mode after content-version mapping.
- Meaningful engagement is additive/idempotent and cannot be created by a jump event.
- Finished status wins over ordinary reading mutations.
- A later explicit **Mark as unfinished** transition wins over earlier completion and is revisioned separately.
- Current marker uses optimistic revision. If the incoming mutation is based on the canonical revision, accept it. If not, retain both candidates until the conflict policy resolves them; never silently discard an unsynced marker.
- Local-only books and mode states are added to the account.
- Successfully acknowledged mutations are removed from the local queue; failed or conflicting mutations remain durable.

The merge finishes before post-login navigation to Library. If the network is unavailable, Library loads its local projection, shows “Sync pending,” and retries after reconnection.

### 15.5 Remote-position prompt

Never move an open reader merely because a remote marker arrives.

Treat a remote marker as meaningfully farther when it is in the forward direction and is either at least 2% of the mode or 10 logical paragraphs ahead. If it is also from a newer accepted server revision than the reader's last synchronized base, show a non-modal prompt:

> You read further on another device — go to 42%?

Actions:

- **Go to 42%**: save/retain the local current candidate, fetch the target segment, move to the remote marker, and adopt it as current after restore succeeds.
- **Stay here**: dismiss for that remote revision and retain the local current marker; furthest extent still merges by maximum.

Do not prompt for tiny differences, backward remote markers, changes created only by content-anchor remapping, or the same dismissed revision. An active device never auto-jumps, including during background sync.

### 15.6 Offline reading

- Already cached segments remain readable offline.
- Sequential reading continues across cached chapter boundaries.
- At an uncached boundary, keep existing text visible and clearly state that the next section needs a connection.
- The existing explicit offline-book feature may cache every manifest/segment, but it must use the same bounded segment protocol and report completion accurately.
- Offline progress queues without data loss and syncs on reconnect, app launch, and successful login.

## 16. Proposed data model

Names are illustrative; the invariants are required.

### `book_reading_state`

One row per user and book:

- `user_id`, `book_id`
- `last_mode`
- `status`: `preview`, `in_progress`, `finished`
- `meaningfully_started_at`, `last_meaningful_read_at`
- `finished_at`, `completion_revision`
- `manual_unfinished_at`
- `revision`, `created_at`, `updated_at`

Unique: `(user_id, book_id)`. Index: `(user_id, status, last_meaningful_read_at DESC)`.

### `mode_reading_state`

One row per user, book, and mode:

- `user_id`, `book_id`, `mode`
- current marker fields
- furthest marker fields
- `content_version`
- active-reading seconds and sequential-boundary count needed for meaningful engagement
- current/furthest update timestamps
- `revision`, `last_device_id`

Unique: `(user_id, book_id, mode)`.

### `progress_mutation`

- `mutation_id` primary key
- `user_id`, `device_id`, `device_sequence`
- book/mode/event cause and marker payload
- base and accepted revisions
- client occurrence and server receipt times

Retain enough history for idempotency, sync diagnostics, and content-version recovery; establish a retention policy before launch.

### Content anchors

Persist stable paragraph IDs, ordered logical positions, mode, content version, chapter relationship, word weights, segment relationship, and cross-mode alignment IDs in content storage. These records are content metadata and do not contain user data.

## 17. Direct replacement and backward compatibility

Existing `data/summra.db` progress is disposable test data. The release removes that database and creates the v2 user-state schema directly; it does not migrate page numbers, dual-write legacy fields, or gate readers by account/device. Git rollback is the rollback mechanism.

### 17.1 Cutover

- Stop the application, remove the old `data/summra.db`, and let `UserDatabase.init_db()` create the v2 tables.
- V2 is the only source of truth for Library, resume, percentage, and completion from the first restart.
- Remove legacy page/scroll writes and chapter-checkmark UI in the same change.

### 17.2 Deep links and cached clients

- Existing chapter links continue to resolve.
- Old service-worker caches use a new cache namespace and cannot serve obsolete all-chapter payloads to v2 routes.
- API versioning prevents an older client from sending page numbers into the v2 anchor fields.

## 18. Accessibility and responsive requirements

- Meet WCAG 2.2 AA for the Library and reader flows.
- Use semantic headings in book order and a main reading landmark.
- All chrome, cards, drawers, mode options, and TOC entries are keyboard operable with visible focus.
- Drawers trap focus while open, close on Escape, and restore focus to the invoking control.
- Announce mode changes, approximate anchor recovery, offline boundaries, sync prompts, and loading failures without announcing routine silent saves.
- Do not make center-tap chrome toggling the only way to reveal controls.
- Respect reduced motion; resume and programmatic anchor restoration are instant by default.
- Reader text supports browser zoom to 200% without unintended horizontal overflow; pagination recomputes around the same semantic marker, and Side-by-Side becomes unavailable when the effective viewport is too narrow.
- Side-by-Side reading order is Original then Plain English in the wide-screen two-column DOM presentation.
- Touch targets are at least 44 by 44 CSS pixels.
- Progress is conveyed as text as well as visually.

## 19. Privacy, security, and reliability

- Progress endpoints require the existing authenticated identity and validate book, mode, content version, chapter, paragraph, and offset against the manifest.
- Use parameterized queries and enforce ownership at every read/write.
- Do not accept client-supplied percentage, completion, or furthest ordering without server validation.
- Quote recovery excerpts contain only book text and are length-limited; no surrounding user data is stored.
- Rate-limit malformed or excessive mutation traffic while allowing ordinary page-turn save coalescing.
- Logs include mutation ID, user-safe internal IDs, revision result, and recovery level; never log email, full paragraph text, auth headers, or cookies.
- A progress-write outage degrades to the durable local queue and must not block reading.
- Deleting an account removes cloud reading state and mutation history according to the product's deletion policy; device-only data remains under browser storage controls and receives a separate clear-data action.

## 20. Analytics and success measures

### 20.1 Events

Instrument at minimum:

- `library_viewed`
- `library_book_opened`
- `reader_opened`
- `reader_restore_completed`
- `reader_restore_recovered`
- `reader_segment_requested` / `reader_segment_failed`
- `reader_interchapter_stall`
- `reading_meaningfully_started`
- `reading_mode_changed`
- `toc_opened` / `toc_entry_selected`
- `about_book_opened`
- `progress_saved_local` / `progress_synced`
- `progress_conflict_prompted` / `accepted` / `dismissed`
- `book_finished` / `book_marked_unfinished`

Use pseudonymous internal IDs and coarse timing/position buckets. Do not send paragraph text.

### 20.2 Launch metrics

Compare with the pre-launch cohort:

- Increase the share of returning signed-in readers who resume a book within 30 seconds of landing.
- Increase chapter-boundary continuation rate.
- Reduce exits on chapter-transition surfaces.
- At least 99.5% of accepted progress mutations eventually synchronize or remain durably queued.
- Fewer than 0.5% of reader opens report anchor recovery below the saved chapter.
- Fewer than 1% of sessions encounter a visible inter-chapter loading stall on broadband/Wi-Fi.
- Fewer than 0.1% of completions are reversed within five minutes without intervening reading, as a false-completion guardrail.

Set numeric growth targets after one week of baseline instrumentation; reliability guardrails apply at launch.

## 21. Release plan

### Phase 0: Content and measurement foundations

- Assign stable paragraph IDs and content versions.
- Produce Original/Plain English alignment metadata.
- Add segment manifest generation and validate every book/mode.
- Instrument current reader latency, chapter exits, mode use, and resume success.

### Phase 1: Progress v2 and continuous reader

- Add new tables, APIs, IndexedDB queue, and anchor recovery.
- Build continuous-book Original and Plain English modes with existing pagination plus progressive loading.
- Preserve old routes through the new reader.
- Replace the disposable progress database directly; no migration or dual-write period is required.

### Phase 2: All modes and TOC

- Add Summary and responsive Side-by-Side.
- Add TOC drawer, single-row reader chrome, completion, and sync prompt.
- Validate offline segment behavior and lifecycle saves.

### Phase 3: Library and navigation

- Launch Library, post-login merge/redirect, signed-in navigation order, Finished, and empty state.
- Keep all book-card destinations on editorial detail pages, with explicit Read book controls entering the reader.
- Remove chapters as primary cards and legacy chapter-completion counts; the account utility may show v2 in-progress and finished book totals.

### Phase 4: VM acceptance and cleanup

- Expand cohorts while monitoring resume recovery, false completion, stalls, queue age, and conflicts.
- Verify the direct replacement on the VM; Git revert remains available if a serious regression is found.
- Decide whether Recently opened is warranted from observed behavior.

No new feature flags or compatibility switches are introduced for this release.

## 22. QA and acceptance scenarios

### Navigation and Library

- [ ] A signed-out visit to `/` stays on Home.
- [ ] A signed-in visit and successful login land on Library.
- [ ] Library is the first signed-in navigation item; Discover is second.
- [ ] Continue Reading is ordered by most recent meaningful reading activity.
- [ ] An accidental open does not add a book to Continue Reading.
- [ ] The first Library card opens its book directly at the exact mode and paragraph.
- [ ] Finished books are ordered by `finished_at` and can be marked unfinished without losing markers.
- [ ] Empty Library links to Discover.
- [ ] Selecting a book anywhere opens the continuous reader, not a chapter-card page.

### Continuous reading and modes

- [ ] The current book-like paging and page-turn controls, gestures, keyboard behavior, and animation remain unchanged.
- [ ] Moving across a chapter boundary uses an ordinary page turn and does not navigate or show a chapter loading screen under the performance test network.
- [ ] Only a bounded initial text payload is sent; adjacent content loads progressively.
- [ ] TOC navigation works without leaving or reloading the reader.
- [ ] TOC and deep-link jumps update current marker but not furthest extent or completion.
- [ ] Summary is the continuous sequence of chapter summaries; full-book summary appears only as About/Overview.
- [ ] Original, Plain English, and Side-by-Side map to the same logical paragraph on first use.
- [ ] Summary maps by nearest chapter.
- [ ] Every mode restores its own later independent location.
- [ ] Side-by-Side is two columns only at 1024 CSS px or wider and is unavailable on narrower screens.
- [ ] A desktop Side-by-Side session falls back to Plain English (or Original) with the same semantic anchor after narrowing the viewport.

### Resume and progress

- [ ] Changing font, zoom, theme, viewport, responsive Side-by-Side layout, or device restores the same paragraph and approximate intra-paragraph offset.
- [ ] Repagination may change the displayed page count/index but does not change the semantic current marker.
- [ ] Initial reader load never writes an opening marker before restoration completes.
- [ ] Backward reading changes current marker without reducing furthest-read percentage.
- [ ] A TOC jump forward does not increase furthest-read percentage until sequential reading occurs.
- [ ] Lifecycle saves survive immediate tab close where the browser supports beacon/keepalive and always remain in the local queue otherwise.
- [ ] A removed paragraph restores through the documented recovery order.

### Completion and sync

- [ ] Sequentially reaching the true end marks the book Finished.
- [ ] Opening or jumping to the final chapter/end does not mark it Finished.
- [ ] Mark as unfinished moves the book to Continue Reading and does not immediately re-complete on an end-position reopen.
- [ ] Signed-out activity merges after login and is visible in Library.
- [ ] Offline activity queues and synchronizes after reconnection.
- [ ] Reading on two devices merges furthest extent monotonically.
- [ ] A meaningfully farther remote current marker produces the prompt with the correct percentage.
- [ ] Sync never silently moves an active reader or discards an unacknowledged local marker.
- [ ] Duplicate mutation delivery is idempotent.

### Accessibility and failure handling

- [ ] All primary flows pass keyboard-only and screen-reader testing.
- [ ] Chrome can be revealed without pointer center-tap.
- [ ] Failed future-segment requests retain current content and expose Retry.
- [ ] Cached segments remain readable offline; uncached boundaries fail in place without losing progress.
- [ ] Library and reader meet the performance and WCAG targets in this document.

## 23. Definition of done

The change is complete when:

- all acceptance scenarios pass in supported desktop and mobile browsers;
- every production book has a valid versioned manifest, stable paragraph IDs, and segments for each advertised mode;
- automated tests cover marker validation, mapping, recovery, conflict, meaningful engagement, completion, API bounds, and route compatibility;
- end-to-end tests cover the cross-device, offline, font/viewport change, mode resume, TOC, chapter boundary, mobile Side-by-Side unavailability, completion, and manual-unfinish scenarios;
- dashboards and alerts exist for restore failures, segment latency/error rate, inter-chapter stalls, sync queue age, mutation conflicts, and false-completion signals;
- direct replacement has been exercised against a fresh progress database, and Git rollback is documented; and
- legacy page-number resume and chapter-checkmark UI are no longer primary product behavior.

## 24. Dependencies and risks

| Dependency or risk | Mitigation |
| --- | --- |
| Content changes can alter persisted paragraph identities | Use versioned paragraph mappings and the quote/ordinal recovery ladder |
| Original and Plain English paragraphs may not align perfectly | Persist explicit alignment rows, including one-sided gaps; validate every advertised book |
| Progressive fetch can expose boundary stalls | Manifest-first loading, two-ahead prefetch, inline retry, latency telemetry |
| Incremental content or repagination can move rendered page boundaries | Restore the same semantic anchor after pagination-index updates; regression-test fonts and viewports |
| Offline and multi-device writes can race | Local-first idempotent queue, optimistic revisions, monotonic furthest merge, explicit current conflict prompt |
| Legacy page numbers cannot map exactly | Do not carry them over: the disposable test progress database is reset at cutover |
| Content edits can invalidate locations | Content versions, old-to-new maps, quote/ordinal recovery ladder |
| TOC/end jumps can create false completion | Cause-tagged programmatic page-change suppression and sequential end qualification |
| Long books can grow DOM/memory | Bounded segments and a small live pagination window around the current page |
| SEO relies on chapter URLs | Preserve routes and SSR chapter metadata while rendering the unified reader |

## 25. Open implementation decisions

These decisions do not change the product contract and should be resolved in technical design:

- Whether stable paragraph and segment metadata lives in normalized SQLite tables or a versioned generated artifact referenced by SQLite.
- IndexedDB implementation: use the browser-native API with no schema-migration library; the local stores are created fresh or upgraded in place.
- Supported-browser memory threshold that triggers distant-segment placeholders.
- Retention duration for accepted progress mutations after the idempotency and diagnostics window.
- Canonical reader URL: `/books/{slug}/read`; legacy chapter URLs retain server-rendered metadata and enter the same reader experience.

## 26. References

- Existing product PRD: `docs/PRD.md`
- Existing reading-progress implementation: `backend/user_models.py`, `backend/progress_routes.py`, `frontend/static/js/auth.js`
- Existing reader and pagination: `frontend/static/js/reader.js`, `frontend/static/js/pagination.js`
- [Kindle User's Guide](https://kindle.s3.amazonaws.com/Kindle_User%27s_Guide_English.pdf) — reading progress/location and adjustable presentation precedents
- [Amazon: Update Your Sync Settings for Kindle](https://digprjsurvey.amazon.com/csad/help/node/GGFEXXS8Z7DPJSTN)
- [Amazon: Sync Your Kindle E-Reader](https://digprjsurvey.amazon.com/csad/help/node/GDCAMDFMC2LZP6BR)
