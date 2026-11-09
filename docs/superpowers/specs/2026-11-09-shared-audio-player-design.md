# Shared audio player for Distill and Plainly

Status: draft for the owner's sign-off. Nothing is built yet.
Mockups (phone and desktop) were reviewed in the session; the behaviour below is what they show, minus the removed Read button.

## Why

Three problems, all from the owner:

1. Closing the player in the reader changes the page height, so sentences move.
2. Audio stops when you leave the page. The owner wants to keep listening to one book while browsing or reading another, the way 微信读书 works.
3. The audio code is split. Distill has `shared/static/js/listen.js`; Plainly has its own `plainly/frontend/static/js/audio.js`. The goal: **if chapter recordings are added to Plainly, listening works there with no new player logic.**

## Goals

- One player implementation used by both apps: playback, position, speed, lock-screen controls, silent hold after pause, mini player, full player, sentence highlight, automatic page turns, saved reading place, and Listen from here instead.
- Reader page height never depends on the player.
- Audio continues across page changes in Distill, on phone and desktop.
- Recording storage, the audio API and the reader link are app-neutral, so Plainly needs only recordings.

## Non-goals

- Recording Plainly's book chapters. This work makes it possible; it does not do it.
- Tap-to-hide reader controls, or tap-the-text-to-pause.
- Sleep timer, voice choice, audiobook recommendations.
- Offline listening.
- Kindle: no audio, ordinary page loads, unchanged.

## Anti-goals (it fails even if it technically works)

- Sentences move when audio starts, stops or the player closes.
- Plainly needs a second copy of any player logic to add book audio.
- The reader gets slower for someone who never presses Listen.
- A saved place is lost when switching between books' audio.

## Behaviour (decided by the owner)

**Reader.** No player on the page. The top toolbar's headphones button is the only audio control.
- Nothing playing: the button is plain, and tapping it starts this book from the reading position.
- Audio going, in this book or any other: the button is accent colour, and tapping it opens the full player. One state, not two.
- If a book has no recording and nothing is playing, there is no headphones button (as today).

**Highlight and page turns.** Only when the book and page on screen match the audio. If you turn away by hand, the highlight stays behind and you are not pulled back.

**Full player.** One screen in every case: cover, chapter title, book title and chapter position, scrub bar with times, previous chapter, back 15, play/pause, forward 30, next chapter, speed, Chapters. A down arrow closes it and returns to the same page. There is no Read button.
- **Listen from here instead** shows only when the book on screen is not the one playing. It saves the current book's place, then starts the on-screen book from its reading position.
- Phone: full screen. Desktop: a panel along the right edge, full window height, with no dimming, so the page stays readable and the panel can stay open while reading. When open, the reader column slides left at its same width, so line breaks and page cuts do not change. Below about 1,060 px wide, where column and panel cannot sit side by side, the panel lies over the page instead.

**Mini player.** On non-reader pages only: cover, chapter title, book title, time, pause, close. Tapping it opens the full player. Phone: slim row along the bottom edge. Desktop: floating card at the bottom right. Closing stops audio and ends the silent hold.

## Architecture

### Frontend: three layers in `shared/static/js/`

1. **`AudioPlayer`** (one per browsing session). Owns the `<audio>` element, tracks, position, rate, silent hold, Media Session, and sign-in-expiry handling. Knows nothing about pages. Emits state changes. This is `listen.js` minus everything touching the reader.
2. **`ReaderAudioLink`** (one per on-screen reader). Connects an `AudioPlayer` to the shared continuous reader: the headphones button, highlight, automatic page turns, manual-paging detection, reading-position start, and saved place. Decides highlight and page turns with the book-and-page rule above. Contains no app-specific code.
3. **Player UI**: mini and full player templates in `shared/templates/shared/reader/` and `shared/static/css/listen.css`, rendered from `AudioPlayer` state.

Controls with nothing behind them are hidden by the track data, not by app checks. A track without timings has no highlight or page turns; a book with one track has no chapter buttons.

**Audio sources** are the only per-kind code. A source returns tracks: `{id, book, chapter title, urls[], duration_ms?, timings?}`.
- `RecordedBookSource`: reads the shared audio API. Used by Distill now and by Plainly once recordings exist.
- `GeneratedSpeechSource`: Plainly's existing generated summary speech, including chunked URLs and waiting for chunks. No timings.

**Saved place without a reader on screen.** The stand-in in `distill/static/js/listen_page.js` becomes a shared class using the reader manifest and `shared/progress`, which both apps already have.

### Keeping audio alive

Both apps use the same model: one page that never reloads while you browse, holding one `AudioPlayer`. Plainly already works this way.

Distill moves to in-place loading. Flask still renders each page as HTML, as it does today. A small script intercepts in-app links, fetches that HTML, and swaps the page's main content, title and body class, keeping the address bar and Back button correct. CSS, shared JS and the player are loaded once and stay. Page scripts (home filters, book page, reader) get a start and stop step, so each swap starts clean. The reader uses the same open and close path Plainly uses. A direct link, refresh or failed fetch falls back to an ordinary page load. Kindle requests keep ordinary page loads.

**Performance.** Reading and browsing must not get slower.
- Measure today's full-page timings first, in the browser tests with phone-like network throttling: tap to content for home, book page and reader open, and time for a page turn. These become the budget: every in-place load must be at or below its baseline.
- Saved work: no re-download or re-parse of CSS and JS on each page, and no reader start-up beyond what opening a book needs.
- Fetch the next page on `pointerdown` or link hover, so the request starts before the tap ends. Only fetch GET pages, with one in flight per link.
- Show the old page until the new one is ready, with a thin progress line only after 150 ms, so fast loads don't flash.
- A fetch started by an earlier tap is cancelled when a new one starts, so taps can't land out of order.
- Stop steps remove listeners and timers. A test opens and closes the reader 20 times and checks listener count and memory don't grow.
- Audio stays on-demand: no audio data loads until Listen is pressed, apart from the small track list needed for the iPhone tap rule.

### Page height

Move the player out of `.continuous-reader-footer` and delete the resize event from `showBar`. Nothing about audio may affect the reader's page measurement.

### Backend: new `shared/audio/`

- The `chapter_audio` table, its migration and its queries move out of `distill/models.py` into a mixin both databases use, the same way `shared/reader/index.py` works.
- The key becomes `(chapter_id, mode)`, because Plainly can record Original and Plain English separately. Existing Distill rows migrate to mode `summary`. `distill/scripts/db_patch.py` keeps working, and needs a test with the new key.
- `/api/books/<slug>/audio` and the chapter file route move to a shared blueprint, taking the app's access check. Distill stays signed-in and private. Plainly follows its own public rules.
- `distill/audio/` (engines, spoken text, assembly) and `make_audio` move to shared code so Plainly can record with the same pipeline. Deploying Plainly's recordings is left to the work that adds them.
- Timings keep using reader unit ids, which both apps already share.

## Build order

1. Record baseline timings. Quick iPhone check that audio keeps playing across an in-place swap (throwaway).
2. Fix page height. Split `listen.js` into `AudioPlayer` and `ReaderAudioLink` with Distill unchanged in appearance.
3. New mini player, full player and headphones behaviour.
4. Distill in-place page loading with the performance work.
5. Move the backend to `shared/audio/`, with the Distill migration.
6. Move Plainly to the shared player, delete `audio.js`'s player logic, rebuild its bundle.

Each step ends with tests passing. Deploy only when the owner asks.

## Acceptance

- In-place loads meet the baseline budget for home, book page and reader open.
- Reader page text stays pixel-identical when audio starts, pauses and closes (browser test measuring text positions).
- Audio continues with no gap across home, book page, another book's reader, and browser Back in Distill.
- Highlight shows only when book and page match; turning away by hand doesn't pull you back.
- Headphones open the full player for audio in this book or another. Listen from here instead appears only for another book, and the previous book's place is saved.
- Lock-screen play and pause still work, including after a pause.
- A test gives a Plainly book a recorded chapter fixture and shows the headphones, highlight, page turns and saved place working with no Plainly-specific player code.
- Plainly's summary audio still plays, in the new player.
- All pytest, Distill browser tests, and the 14 Plainly browser scripts pass. iPhone behaviour is confirmed by the owner on a device.

## Calls made while writing (not yet confirmed by the owner)

- Plainly's players get the new look too, since the UI is shared.
- Recordings are keyed per reading mode. Side-by-side plays the Plain English recording if there is one, otherwise Original, and highlights the matching column.
- Previous chapter and a chapter list were added to the full player.
- Forward stays 30 seconds; back stays 15.
- Listen from here instead uses the same start-point rule as the headphones button.
