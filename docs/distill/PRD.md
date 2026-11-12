# Distill — Product Requirements

> Split out of `docs/PRD.md` on 2026-11-11. Distill only. Platform features (reader, Kindle, sign-in, audio player) are in [`docs/shared/`](../shared/). Newest dated entries are at the top; the reference sections follow.

## 2026-11-03 — Release synchronization

The published NVIDIA entry, research-table behavior and Kindle rendering fixes
above are included in the GitHub/VM synchronization requested by the owner.
This release step introduces no additional product behavior or requirements.
Browser and production checks pass; physical Kindle confirmation is pending.
Code release `575447d` is pushed to GitHub and synchronized on the VM. All
committed files match, both apps are active, and live/privacy/catalog checks
pass. CI run 41667479715 passed. Final evidence is recorded in WORK_LOG.md.

## 2026-11-02 — Equity research documents and readable tables

Distill supports publishing complete research documents without summarizing.
The NVIDIA company research and valuation analysis dated October 31, 2026 form
one library entry tagged `Equity research`, with both documents available in
order from the contents page. All prose, figures, tables and source URLs remain.

Research tables retain their row/column grids in the web reader. Readers can
scroll within wide or tall tables on desktop and phones without turning the
page. Kindle presents each row as labeled cells with repeated row/column context,
so every value remains readable across e-ink pages without tiny ten-column text
or clipped rows. This also works in the server-rendered no-JavaScript view.
Existing book table presentation is unchanged. Published and production-verified
as book 63 on November 2, 2026; all 21 tables and sections pass live checks.
Detailed evidence is in WORK_LOG.md.

## Distill image migration deployed (2026-10-28)

Existing original images and cover thumbnails now serve from private files,
with their previous URLs, appearance, sign-in protection and reading state
preserved. Production migration and live image checks passed; Plainly remained
available. Distill's content database shrank from159.6MB to10.0MB and its current
database backup from about148MB to3.5MB. Images remain intact on the VM, with
no reauthentication or image regeneration required. The Mac authoring database
uses the same storage so future book imports/deploys retain this behavior.

## Distill image storage outside the database (2026-10-27)

Original Distill images and generated cover thumbnails now live as private
files outside SQLite and Git. The reading experience, image URLs, sign-in
protection, book/chapter identity, cover appearance and saved reading places
remain unchanged. This reduces the content database and metadata backup size;
it does not discard images or reduce their quality.

Imports and book deployment carry media separately from metadata, with verified
file installation before activating a new content database. Existing books can
be migrated without reimporting or regenerating images. Account/progress and
Kindle pairing data are not replaced. Operators retain one latest metadata
backup per app and must preserve/back up its separate media files as well.
Plainly's existing media storage and reader behavior are unchanged.

Since 2026-11-11 each Distill content deploy also removes media files that
neither the live library nor its one metadata backup uses (for example narration
replaced by a re-recording), so restoring that backup still works and the VM
does not accumulate superseded audio. The first manual run freed 654 MB.

## Distill Kindle text size and Chinese fonts (2026-10-27)

The Kindle reader offers ten text sizes, extending the old30px maximum to72px. New readers start at36px; saved valid sizes are preserved. The top-tap menu shows the current size level and maximum, with inactive controls at either end. Font choices are 默认 (existing fallback), 宋体 (Song) and 黑体 (Hei); the reader saves the choice and repaginates around the current paragraph. Fonts use installed Kindle faces, keeping downloads light. Song/Hei are confirmed installed on the tested PW3, but the user confirmed larger text works and 黑体 looks good on the physical stock-browser Kindle. Plainly's original size limits and font UI are retained.

## Distill book actions (2026-10-27)

Continue/Start reading, Read from beginning and Mark unfinished/Mark as read use consistent typography, spacing and touch target sizes. Continue/Start reading remains the filled primary action; the secondary actions share one understated link treatment. Actions wrap without horizontal overflow on phone screens, retain visible keyboard focus and preserve their existing destinations and status behavior.

## 17. Distill (Private Book-Summary Reader, 2026-10-25; updated 2026-10-26)

Distill is a private app for the owner's book summaries, the second app on the shared reader platform (see ERD "Reader platform"). It is served at `/distill`, apart from Plainly's data and URLs. Design: `docs/superpowers/specs/2026-10-24-distill-design.md`.

### 17.1 Access

**User story:** As the owner, I want my summaries visible only to explicitly authorized accounts, so that I can share private book notes with invited readers.

- Book content and account data are behind sign-in. The content-free launch screen, manifest, favicon and allow-listed app branding icons are public for installation and sign-in. Content access is restricted to explicitly authorized accounts through an allow-list of email addresses (`DISTILL_ALLOWED_EMAILS`). A signed-in email that is not on the list gets 403 on a page, an image and the reader API. Invited readers share the content catalog while keeping their account and reading progress separate. On 2026-11-07 the owner authorized cassyheng@gmail.com across Distill and the site's other apps; access remains app-specific and does not grant administrative privileges.
- Signed-out visitors see only a sign-in prompt. There is no marketing or pitch page. The prompt comes from Apache OIDC (`OIDCUnAuthAction auth` redirects to Google); the app itself returns 401 (signed out) or 403 (email not on the allow-list) as JSON.
- Sign-in is shared with Plainly: signed in to one means signed in to the other, Kindle included.
- Book text and images are never publicly cacheable and images are not served from a static path.

### 17.2 Library

**User story:** As the owner, I can see my saved reading places, explicitly completed books and the full collection.

- **Reading now**: started books most recent first, with cover, progress and saved location. Show six cards initially, with an expandable remainder.
- Clicking anywhere on a Reading now or Finished card opens the reader at its saved position, including the cover, title, progress bar and empty card space. The whole card is also a keyboard-accessible link. Deployed and verified on 2026-10-26.
- **Home (web, 2026-11-08):** no tabs. One page: the last-read book first (cover, author, progress, current chapter, minutes left) with **Continue** and **Listen** as equal buttons side by side, then any other books in progress under *Also reading*, then the whole library on the same page. Desktop (1000 px and wider) has no bar across the page: the logo sits at the top of a full-height left panel with the book, and the library starts at the top of the window on the right; phones scroll straight through, with a Search link that jumps to the library. Library keeps search, All / Unread / Finished, and language, category and sort filters (visible on desktop, behind a Filters button on phones); while a book is in progress, applying one on a phone returns to the library section. With nothing in progress, home is a normal header and the library.
- **Listen outside the reader (2026-11-08):** Listen on home and on a book page plays right there, starting at the saved reading place, with the player along the bottom of the page. The button becomes Pause while playing. Listening saves the place to the account like listening in the reader. Going to another page stops the audio. Book pages use the same two buttons (Start or Continue, and Listen); Listen is removed for a book with no audio.
- **All books**: status badges, language/category/status filters and newest/title/author/shortest sorting. Preserve filters and scroll position when returning from a book; refresh server progress when returning through the browser's back-forward cache.
- Show approximate reading times using 220 English words or 400 CJK characters per minute.

### 17.3 Book page

- Show cover, title, author, progress and saved chapter, including for Finished books. **Start reading** or **Continue reading** opens the saved place; **Read from beginning** is a separate action.
- **Mark as read** explicitly moves a book to Finished; **Mark unfinished** moves it back to Reading now. Neither action discards current/furthest positions or accumulated reading time. A book can be marked Read before reading begins.
- Contents start with the Overview, retain meaningful chapter numbering and part headings, and avoid duplicated number prefixes. Section overviews have concise distinct labels. Source material appears as the final ordinary **Source** chapter, with the same reading/navigation behavior as other chapters, rather than a separate section below Contents.
- An unknown book shows a not-found page.

### 17.4 Reader

- Summary is the only mode; no mode selector. Font, size and theme settings are shared with Plainly. Tap, swipe and keyboard page navigation preserve headings, lists, key points, quotes, tables and images; oversized blocks scroll within their page.
- Current place and furthest progress are separate account-backed values. Reopening resumes the current paragraph across devices. Locations show Overview, Chapter n of m (excluding the Overview), or Source.
- **Distill never moves a book to Finished merely because its last page/chapter was reached.** Only an explicit Read action finishes it, on web and Kindle. Plainly retains its automatic completion behavior.
- Existing automatically finished Distill books return to Reading now unless an accepted explicit Read action exists. Preserve all saved mode positions, reading time and mutation history during this conversion.
- Show Saving, Saved, Not saved or Updated on another device feedback. Loading failures provide retry and reload/sign-in recovery. Contents retains part headings and highlights the current chapter; contents/settings dialogs support keyboard focus, Tab and Escape.
- Back navigation remains responsive: a final save can continue during navigation, with at most 250ms waiting for it. Preserve the validated library return URL and filters through the book page. A failed content-cache operation falls back to the network.

### 17.5 Kindle mode

When the browser is an e-ink Kindle, the same URLs serve the e-ink pages (see 12), signed in as the same account:
- **Library**: Reading now (up to 3, with "See all") then All books, 4 per page, with text and controls at twice the size of the other Kindle pages. A page with long titles or books in progress may need a short scroll.
- **Book**: cover, saved-place resume, separate Read from beginning, Mark as read / Mark unfinished controls, and contents 8 per page with part headings and a "You are here" mark.
- **Reader**: fixed pages, tap to turn, resumes at the saved place, and the page you reach is saved to your account, so the web reader picks up where the Kindle stopped.
- There is one text (the summary), so no Text switch. Tables and figures are never split across pages.

### 17.6 Non-goals (for now)

Server-side summarization, file upload in the browser, multiple users beyond the owner, public reading, a pitch or landing page, a subdomain, offline audio, study cues, search, highlights or notes. Books are added by running an import command on the owner's computer; the web app has no upload UI.

### 17.7 Acceptance criteria

- A signed-in allow-listed owner sees the library, can open a book and read it, and the reload restores the same paragraph.
- A non-allow-listed account, or a signed-out visitor, sees no book text, image or reader data.
- The reader has no mode selector and loads no Plainly cache (IndexedDB `distill-reader-v1`, never `summra-reader-v2`).
- On a 375x667 phone no block is clipped; on a Kindle no table row or figure spans two columns.
- Reaching the final page on web or Kindle leaves a Distill book in progress. Explicit Read/unfinished actions survive reloads and preserve current/furthest positions; Finished defaults to resume.
- Import and repair preserve meaningful numbering. Source is the final chapter; title repairs and Source append operations retain existing chapter identities and reading positions.
- Library/book covers use precomputed AVIF, then WebP, then JPEG fallbacks; Kindle uses JPEG. Reader illustrations retain their originals. Requests do not encode images or recompile unchanged reader content.
- Deployed to the VM on 2026-10-26 with public launch/manifest, private-route authentication boundaries and authenticated library-return checks verified. Existing installations may retain their old launch URL until the manifest refreshes.
- A signed-out PWA launch shows a working Sign in action without private asset dependencies; successful authentication returns to the library, while a valid session opens it automatically.
- Installing Distill uses the drop icon even when the OS fetches metadata without sign-in. Signed-out access to book content and progress remains blocked.

---

### 17.8 Listen (2026-11-07)

**User story:** As the owner, I want to listen to a summary on my iPhone and switch between listening and reading at the same spot, so that I can keep going while walking or driving, and still find my place after iOS closes the app.

- **Audio:** made ahead of time on the owner's Mac.
  - English uses the Mac's system voice (`say`, Siri Voice 2). Chinese uses Mandarin Siri Voice 4 at rate 1.0.
  - Each chapter reads its title, then paragraphs, headings, quotes, lists and key points. Tables and images (captions included) are skipped.
- **Listen:** a headphones button in the reader toolbar starts at the paragraph at the top of the page. If audio was paused in that paragraph, it resumes at the paused second instead. The button appears only when the book has audio.
- **Audio follows you (2026-11-09):** audio keeps playing while you browse the library, open a book page or read another book, on phone and desktop. Distill pages load in place, and Back and direct links still work.
- **Reader:** there is no player on the page, so audio never moves the text. The headphones button is plain when nothing is playing and starts this book from your reading position. When audio is going, in this book or any other, it is accent coloured and opens the full player.
- **Full player:** cover, chapter and book title, scrub bar with times, previous chapter, back 15 s, play/pause, forward 30 s, next chapter, speed, Chapters and Stop listening. A down arrow closes it. **Stop listening** ends the audio, removes the highlight and page following, saves your place and leaves the page where it is. **Listen from here instead** appears only when the book on screen is not the one playing; it saves the playing book's place and starts this one. Phone: full screen. Desktop: a panel along the right edge, with the reading column sliding left at the same width; below about 1,060 px the panel lies over the page.
- **Mini player:** on non-reader pages only, with cover, chapter, book, time, pause and close. Tapping it opens the full player. Closing it stops the audio.
- **Following the text:** only when the book and page on screen match the audio. Hands off, the spoken paragraph is highlighted and the page turns by itself as the audio moves on, including partway through a paragraph that runs onto the next page.
- **Turning pages while listening:** turning away by hand leaves the highlight behind and never pulls you back. Paging back to the spoken page, or starting a chapter from the player, resumes following.
- **Recording:** both apps record on the owner's Mac with the same command and voices, in English or Chinese. Plainly no longer uses Gemini for speech.
- **Shared platform:** Plainly and Distill use the same player, highlight, page following and saved place. Plainly gets all of it as soon as a book has chapter recordings. Its summary speech already plays in this player.
- **Lock screen:** shows the chapter, book and author, with play/pause, skip and seek. At the end of a chapter the next one plays, including while locked.
- **Kill-safe resume:** the place is kept on the device every 5 s and on pause or leaving the app. Pressing Listen in the same paragraph resumes at the saved second.
- **Shared position:** listening saves the summary's reading position (on pause, chapter change and every 30 s), so the text opens where the audio stopped, on any device.
- **Failures:** a failed load, such as an expired sign-in, pauses and asks to sign in again. It never stops silently.
- **Text edits:** audio for a chapter whose text has changed is hidden until it is re-rendered.
