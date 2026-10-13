# Summra redesign — "Quiet library + study cues" (A + C)

## Context

The live site (pengyaochen.com/summrabook) works but has no single visual language: a dark cinematic hero, a grey-gradient carousel band, and white flat-UI sections with 2014 flat-palette buttons (`#3498db`), mixing Amazon Ember / Arial Black / New York / Open Sans. The home page never shows Summra's actual differentiator (original sentence → plain-English sentence). Discover and Categories are the same carousel-row layout (Discover rendered blank for ~3s, plus a 404 in console). The book page's chapter list is bare grey "Chapter N" bars with no summary, time, or progress. The reader is the strongest page (serif paper, calm side-by-side) and becomes the anchor for the whole system.

User chose **Mix A + C**: A's editorial look (warm paper, serif, oxblood accent) plus C's study cues (difficulty level, reading time, progress) on Discover and book pages. Audience: general (curious adults, students, English learners).

Assumptions: URLs, routes, SSR fast paths, and the single-template SPA (`frontend/templates/index.html` + `frontend/static/css/style.css` + `frontend/static/js/app.js` → esbuild `app.min.js`) stay. No framework migration. No web fonts (keep first-paint wins from b4359b9) — system serif/sans stacks only. Site-wide dark mode is out of scope (reader keeps its existing dark/sepia themes).

## Design system

Tokens on `:root` in `style.css` (replace the current ad-hoc set; alias old names to new ones first so nothing breaks mid-migration):

| Token | Value | Use |
|---|---|---|
| `--paper` | `#F6F1E7` | page background |
| `--surface` | `#FBF8F1` | cards, reader page |
| `--ink` | `#2B2622` | body text |
| `--ink-muted` | `#6B5F55` | secondary text |
| `--rule` | `#E8DFCF` | hairlines, progress track |
| `--accent` | `#8A2E2E` (oxblood) | links, primary button, progress fill, quote rule |
| `--level-easy-bg/fg` | `#E3EBDD` / `#3E5A36` | level tag |
| `--level-moderate-bg/fg` | `#F3E6CC` / `#7A5A1E` | level tag |
| `--level-challenging-bg/fg` | `#F1DEDA` / `#7A2828` | level tag |

- Type: headings + reading = existing `--reading-font-serif` stack; UI chrome = system sans. One weight scale (400/600), sentence case.
- One primary button style (oxblood fill), one secondary (ink outline). Radius 6px; cards 10px; hairline borders, no gradients.
- Cover placeholder: 2:3 box tinted `--rule` with the title set in serif, so loading never shows grey blobs and card heights stay uniform.

**Study cues (from C)**, derived server-side so SSR and JS agree (DRY):
- Level label from `books.cefr_level`: A1–B1 → Easy, B1-B2/B2 → Moderate, B2-C1 and up → Challenging, NULL → no tag (29 of 90 books). Reuse/extract the CEFR grouping already in `backend/routes/discover.py`.
- Reading time from `word_count` at 230 wpm (book: hours; chapter: minutes).

## Pages

1. **Global header/footer** — serif wordmark; nav: Discover · Books · Library; search icon expanding to field. Footer simplified to one line + links.
2. **Home** — hero on paper: "Read the classics in plain English." + an original→plain sentence pair (oxblood left rule, original in muted italic), server-rendered from a few curated chapter openings, rotating client-side; search + "Start reading" CTA. Then: "Start here" shelf (existing top-10 SSR, drop the big 1–6 numerals, add level tag + time); "Choose by level" three cards → Discover filtered; "How it works" as a real mini side-by-side snippet replacing the clipart illustrations; "Continue reading" row when progress exists. The cover-wall hero is retired.
3. **Discover** — one filterable grid instead of carousel rows: level chips (All/Easy/Moderate/Challenging) + length chips (Short/Medium/Long by word_count) + sort. Server-render the first grid to kill the blank state; fix the 404.
4. **Books / Categories / Author / Library** — share one book-card component (cover, title, author, level tag, reading time) in a uniform grid; Categories keeps shelves but uses the same card.
5. **Book page** — two-column header: cover | title, author, meta row (level · N chapters · ~X hrs · "Plain English" badge when modern text exists), primary "Start reading" / "Continue ch. N", secondary "Read side by side". Below: About this book (short summary, expand) → Chapters as a table of contents (number, title, one-line summary excerpt, minutes, read checkmark from progress) → guides (characters/timeline/themes) as cards → About the author (moved down from above the summary).
6. **Reader** — based on the continuous reader on `main` (not prod's older chapter view). Keep its structure: header = back · chapter / book title · contents · reading settings, and the reading mode (Summary / Original / Plain English / Side-by-Side) stays inside the reading settings panel — no mode toggle in the header (user decision, 2026-10-12). Restyle only: header and panels on the new tokens, paper theme, oxblood progress, side-by-side rows get a hairline between aligned paragraphs.

## Implementation phases (each = own PR-sized commit, worktree per CLAUDE.md)

**Before any change — capture the baseline.** Add `tests/e2e/capture_pages.mjs` (Playwright, reusing `smoke.mjs`'s `BASE_URL` handling). It takes full-page screenshots at desktop (1280×900) and mobile (375×812) of: `/`, `/discover`, `/books`, `/categories`, `/library`, `/books/frankenstein`, `/books/frankenstein/chapters/1` (Plain English), the same chapter in Side by side, and one author page. It waits for covers and catalog to load (network idle plus image `complete`) so we don't capture placeholders. `OUT_DIR` selects the output folder. Run it on unmodified `main`, once against local Flask on :5001 and once against prod (`BASE_URL=https://pengyaochen.com/summrabook`), saving to `docs/redesign/before/{local,prod}/`. Commit these before touching any UI code. After each phase, re-run into `docs/redesign/after/`. At the end, generate `docs/redesign/compare.html`, a page showing each screen's before and after side by side at both widths, and send it to you.

0. **Spec + docs** — copy this design to `docs/superpowers/specs/2026-10-12-site-redesign-design.md`; add WORK_LOG entry; update `docs/PRD.md` (page specs) and `docs/ERD.md` (tokens, level/reading-time helpers).
1. **Tokens + global chrome** — new `:root` tokens with old-name aliases; header, footer, buttons. Remove dead vars as each is migrated.
2. **Study-cue helpers** — Python helper (`backend/` near `routes/discover.py`) for `level_label(cefr)` and `reading_time(words)`; expose `level`, `reading_minutes` on `/api/books` and SSR `initial_data`; chapter `reading_minutes` + summary excerpt on book API.
3. **Book card component + listing pages** (Books, Categories, Author, Library) with cover placeholder.
4. **Discover** filter grid (SSR first page, client filtering on catalog already fetched once — see `tests/e2e/catalog_fetch_once.mjs`).
5. **Book page** header + TOC.
6. **Home** hero/sentence pair + shelves; remove cover-wall CSS/assets references.
7. **Reader** restyle (header, contents and settings panels, paper theme) — modes stay in reading settings.
8. **Build + deploy** — `npm run build`, `npm run build:check`; deploy per CLAUDE.md (templates/static need no restart; backend helper change does → restart).

## Tests (TDD, failing first)

- pytest `tests/test_study_cues.py`: CEFR → label incl. ranges (`B1-B2`, `C1-C2`), NULL/unknown → None; reading time boundaries (0 words, 229/230 words).
- pytest: `/api/books` and book API include `level` / `reading_minutes`.
- Playwright (new `tests/e2e/redesign_*.mjs`): home SSR HTML contains the sentence pair and level tags; Discover renders cards before JS catalog fetch and level chip filters count; book page TOC rows show minutes + summary excerpt; no console errors/404s on `/`, `/discover`, `/books`, `/books/frankenstein`, `/books/frankenstein/chapters/1` at desktop and 375px widths.
- Existing e2e suite (`smoke.mjs`, `reader_opens_at_chapter.mjs`, `sxs_*`, `sticky_overlap*`, `top10_ssr.mjs`, `perf.mjs`) must stay green; update `top10_ssr` only if its numeral assertion conflicts — flag rather than silently edit.

## Verification

- `pytest tests/ -v` (show pass count).
- `python backend/app.py` then `cd tests/e2e && PATHS=/,/discover,/books,/books/frankenstein,/books/frankenstein/chapters/1 node smoke.mjs` + new scenarios; Read screenshots in `tests/e2e/screenshots/` at desktop and mobile.
- `perf.mjs` first-paint numbers no worse than before the redesign.
- After deploy: CLAUDE.md "Verify public site" curls + visual check in the built-in browser.
