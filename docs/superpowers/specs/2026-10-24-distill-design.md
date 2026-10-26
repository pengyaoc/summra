# Distill — Design

Date: 2026-10-24
Status: draft, awaiting approval

## 1. Intent

Distill is a private reading app for book summaries the owner writes about books they own. The owner already has 54 chapter-by-chapter summaries, made by the `book-summary` Claude Code skill, published as standalone HTML pages at `pengyaochen.com/pages/`. Those pages are hard to read on a Kindle, don't remember where you stopped, and can't show what's in progress.

Distill gives those summaries the same reading experience Plainly gives classics: Plainly's reader, saved place, progress tracking, and the Kindle e-ink mode. It lives in the Plainly repo as a second app, and it pushes the repo toward a clear split between shared code and app-only code.

Success: the owner opens `pengyaochen.com/distill` on a laptop or a Kindle, sees the books they're in the middle of with progress, opens one, and picks up where they stopped on the other device. A new summary made on their computer appears in the library after one command.

## 2. Decisions made by the owner

- **Users:** only the owner for now. Everything sits behind sign-in, signed-out visitors see only a sign-in prompt. No marketing or pitch page.
- **Summary generation stays off the server.** The owner runs the `book-summary` skill on their own computer. Distill never runs an LLM, and never accepts PDFs or EPUBs. Reason: the VM has 1 GB of RAM, and the skill uses parallel agents.
- **Import is a command run on the owner's computer.** The `book-summary` skill runs it as its last step. The web app has no upload UI.
- **The skill writes Distill's format directly.** No HTML-then-parse-back step for new books.
- **The 54 existing HTML summaries (about 53 books after a near-duplicate) get a one-time conversion**, rough edges accepted. They are not regenerated.
- **`pengyaochen.com/pages/` summaries are taken down** once Distill holds the converted versions.
- **Reading unit:** each chapter (today's `<h3>` inside a part tab) is one reader chapter. The book's parts become headings in the table of contents. The Overview is an opening section. Progress reads like "chapter 7 of 22".
- **Day-one features:** library home, reader, saved place, progress, Kindle mode. Nothing else. No audio, no study cues, no Plain English toggle, no search, no categories.
- **URL:** `pengyaochen.com/distill` for now, same pattern as `/plainly`. A move to `distill.pengyaochen.com` may come later and is out of scope here.
- **Sign-in is shared with Plainly.** Signed in to one means signed in to the other, Kindle included.
- **Repo:** one repo, folder structure split into shared, Plainly-only and Distill-only. Two deploy scripts, two services.
- **WordPress is gone from the VM.** Nothing may assume it's running.
- **Book content is stored in the database as data**, the way Plainly stores classic books. It is not kept as files.
- **The skill stops producing HTML pages.** Its Send-to-Kindle EPUB export (Phase 7, `to_kindle.py`) is dropped, because Distill's Kindle mode replaces it.
- **Images are kept on our server.** That includes the ones today's pages hotlink from other sites. The converter downloads them.

## 3. Goals, non-goals, anti-goals

**Goals**
1. Repo split into `shared` / `plainly` / `distill` with Plainly behaving exactly as before (pytest and e2e suites green before and after).
2. Distill app at `/distill`: library home with books in progress at the top, book page (table of contents), reader, synced progress, Kindle mode.
3. A defined Distill book format, an import command, and an updated `book-summary` skill that writes it.
4. A one-time converter for the 54 existing HTML summaries, with a per-book report.
5. A Distill deploy script and systemd service, separate from Plainly's.

**Non-goals (for now)**
- Server-side summarization, file upload in the browser, multiple users beyond the owner, public reading, pitch or landing page, subdomain, audio, study cues, search, highlights or notes.

**Anti-goals (failure even if it works)**
- Any regression in Plainly, at the URL, behaviour or data level.
- Copy-pasting Plainly's reader, progress or Kindle code into a Distill folder instead of sharing it.
- Book content (text or images) reachable without signing in, including through a static-file path.
- A Distill deploy or database copy that can touch Plainly's data, or the reverse.
- A summary format that is HTML with structure bolted on again.

## 4. Constraints

- **VM:** `wordpress-2-vm` (name is historical, WordPress is gone), 1 GB RAM, already running Plainly's gunicorn (1 worker, 4 threads) behind Apache. Distill adds a second small gunicorn (1 worker). Concrete identifiers are in `.prod-metadata.local.md`.
- **Apache is the sign-in layer.** mod_auth_openidc runs vhost-wide and forwards the signed-in email as `X-Remote-Email`. `pchauth` (trusted-header mode) turns that into `g.user_id`. Plainly's `<Location /plainly/>` uses `OIDCUnAuthAction pass` with `Require valid-user`. Because Distill sits on the same host, the OIDC session cookie already covers it, so shared sign-in needs no cookie work.
- **Plainly's reader index works on paragraphs.** `reader_unit` rows come from splitting chapter text on blank lines. Progress markers are `(chapter_id, paragraph_id, offset, quote)`, and completion depends on reaching the terminal paragraph. Distill's content has to give the reader the same kind of ordered units per chapter.
- **The Kindle front end is server-rendered and ES5-only** (`templates/kindle/`, `static/js/kindle.js`). Distill's richer blocks (lists, tables, images) must render there without new JS.
- TDD is required (CLAUDE.md): failing test first, full suite before claiming done.
- **The GitHub repo (`pengyaoc/summra`) is public.** Book folders, converter output and Distill DBs must never be committed. Add their paths to `.gitignore` in the same change that creates them.
- **Images (my call):** the Kindle browser is old WebKit and renders neither AVIF nor WebP. Today's pages embed ~595 AVIF images. Distill stores images as JPEG (photos) or PNG (line art). The converter transcodes everything, and the skill's image step writes JPEG/PNG instead of AVIF. The format allows `jpg|png` only, not webp.

## 5. Design

### 5.1 Repo split

Target layout (names are a proposal; the principle is what's fixed):

```
shared/            # used by both apps
  auth/            # pchauth, whoami, user models (users, reading state, mutations)
  reader/          # reader-unit index, manifest, marker resolution, progress routes
  kindle/          # UA detection, kindle blueprint pieces, kindle templates + kindle.js/css
  web/             # app factory pieces from app_base (gzip, prefix handling, error pages)
  static/, templates/  # shared reader JS/CSS, fonts
plainly/           # today's Plainly-only code: models for books/authors/categories/audio/
                   # plain English, routes, templates, scripts/content, scripts/audits
distill/           # Distill app factory, models, routes, templates, import + convert scripts
deploy/plainly/, deploy/distill/   # one deploy script, unit file, Apache snippet each
tests/shared, tests/plainly, tests/distill
```

- Do this as its own phase, before any Distill code. Plainly must be unchanged in behaviour, URLs and data. Tests are green before and after each move.
- The hard part is `backend/models.py` (2,300 lines). The reader-index methods (`ensure_reader_content`, `get_reader_manifest`, `resolve_reader_marker` and helpers) move to `shared/reader/`. They work on an interface: "give me the ordered chapters of book X, each as an ordered list of text units". Plainly's model supplies that from `chapters.chapter_text` / `modern_english_text`. Distill's supplies it from its own blocks.
- The reading-state tables in `user_models.py` are keyed by `book_id`. `book_id` means a Plainly book today, and a Distill book id would collide. See 5.3 for how that's avoided.
- The VM deploy paths (`/opt/summra`, `backend.app_prod:app`) may change. Update CLAUDE.md's deploy section and the systemd unit together with the move.

### 5.2 Distill book format

The skill and the converter both write a book as a folder. The folder is only a hand-off into the database: the import command reads it into the DB, and the DB is the master copy. The folder lives in a scratch or working directory, and is never committed to the public repo.

```
<slug>/
  book.json
  images/<file>.(jpg|png)
```

`book.json`:

```json
{
  "format": 1,
  "slug": "atomic-habits",
  "title": "Atomic Habits",
  "author": "James Clear",
  "lang": "en",
  "cover": "images/cover.jpg",
  "overview": [ ...blocks ],
  "parts": [
    { "title": "The Fundamentals",
      "chapters": [
        { "title": "1. The Surprising Power of Atomic Habits",
          "blocks": [ ...blocks ] } ] } ],
  "sources": [ ...blocks ]
}
```

- A part with a `null` title means the book has no parts. Its chapters show as a flat list.
- Block types, deliberately small:
  - `{"type":"p","text":…}`
  - `{"type":"h","text":…}` (a sub-heading inside a chapter)
  - `{"type":"ul"|"ol","items":[…]}`
  - `{"type":"quote","text":…}`
  - `{"type":"keypoints","items":[…]}` (the skill's per-chapter key-points box)
  - `{"type":"table","header":[…],"rows":[[…]]}`
  - `{"type":"image","src":"images/…","caption":…}`
- Inline formatting inside `text` and `items`: `**bold**` and `*italic*` only. No links, no raw HTML.
- `sources` remains input metadata and is exposed as a final, ungrouped `Source` chapter in the TOC and both readers when non-empty. It is not rendered separately below the TOC. Existing content chapters retain their IDs and ordinals when the Source chapter is appended. The skill's Worklog is not imported.
- **Reader units:** each top-level block in a chapter is one reader unit, the equivalent of a paragraph. The Overview is reader chapter 0. Its title is "Overview".
- **Cover delivery:** imports pre-generate 320×480-bounded AVIF, WebP and JPEG thumbnails in the content DB. Web covers use `<picture>` in that order; Kindle uses JPEG. Content-addressed cover URLs are authenticated and privately cached. Original JPEG/PNG assets and the folder format remain unchanged; no encoding runs during page/image requests. Pillow 11.3+ is required for AVIF encoding. Existing libraries can backfill with `DistillDatabase.generate_cover_thumbnails()`.

### 5.3 Data

- **Distill content DB:** its own SQLite file (e.g. `data/distill.db`). It's the master copy of all book content, as `data/database.db` is for Plainly. Tables:
  - `books` (slug, title, author, lang, cover image id, sources JSON, imported_at, content checksum)
  - `chapters` (book_id, ordinal, part_title, title, blocks JSON)
  - `images` (book_id, name, mime, bytes BLOB)

  The reader-index tables come from `shared/reader`.
- **Images live in the DB as BLOBs** (my call). So one DB copy ships everything, there's no second folder to sync, and images are served only through Flask behind sign-in. Expected size: ~600 images at under ~80 KB each, about 50 MB.
- **Users and progress:** sign-in is shared because Apache's OIDC session covers both paths. Each app keeps its own user/progress DB file: Plainly keeps `data/summra.db`, Distill gets `data/distill_user.db`, with the same schema from `shared/auth`. A user row is matched by email in each. This keeps `book_id` meaning one app's book per file, and keeps the two apps' data apart. Accepted cost: an account exists twice, once per app, which doesn't matter for one user.
- **Re-import of an existing slug** replaces that book's chapters and images. `ensure_reader_content` sees the checksum change, bumps the reader version, and saved places recover through the existing quote-based recovery.

### 5.4 Import command

The local `distill.db` is the master, and production gets a copy of it. That's the same direction as Plainly's runbook (local `database.db` → VM).

`distill/scripts/push_book.py <folder> [--dry-run] [--deploy]`:

1. **Validate** `book.json` against the format:
   - required fields
   - known block types
   - every referenced image exists and is JPEG/PNG
   - no unknown inline markup

   Print the chapter count and word counts. `--dry-run` stops here.
2. **Import** into the local `distill.db` in one transaction: book row, chapters, image BLOBs. Re-importing the same slug replaces that book.
3. **`--deploy`** copies the local `distill.db` to the VM:
   - snapshot the VM copy
   - `gcloud compute scp` to `/tmp`
   - md5 check
   - stop `distill.service`, move the file into place with the right owner and mode, start the service

   This reuses Plainly's documented DB-copy steps. It's safe because reading progress lives in the separate `distill_user.db`, which is never copied. The same flow also exists as a standalone `deploy/distill/` DB-push script.
4. Print the book's URL.

No HTTP upload endpoint, so no write API on a 1 GB box. The skill ends with `push_book.py <folder> --deploy`, replacing its current publish-page and `/pages` deploy step.

**Backup:** the local `distill.db` is the only master. It lives in gitignored `data/`, like Plainly's. The VM snapshots taken on each deploy are the off-machine copies. Any further backup is out of scope here.

### 5.5 `book-summary` skill update

- The skill still does Phases 1–3 and image sourcing as today. Images are saved as JPEG/PNG files, not AVIF data URIs.
- Assembly writes `<slug>/book.json` plus `images/` in the format above, in the scratchpad. It no longer produces an HTML page, and no longer uses `publish-page` for books.
- The rubric (`RUBRIC.md`, `scripts/score.py`) reads `book.json` instead of the assembled HTML.
- Phase 7 (Kindle EPUB, `to_kindle.py`) and its triggers in the skill description are removed.
- The skill's last step is `push_book.py <folder> --deploy`.
- New books no longer land in the vault's `03-resources/book-summaries/`. The 54 existing vault HTML files are left untouched as an archive (my call: Distill never deletes vault files). Updating `book-summaries-moc.md` to point at Distill is optional and up to the owner.
- The skill lives at `~/.claude/skills/book-summary/` outside this repo. That edit is part of this project, but committed separately (wherever the skill is versioned).

### 5.6 One-time converter for the 54 pages

`distill/scripts/convert_html_summaries.py <dir> --out <dir>`:

- Parse each page with BeautifulSoup:
  - Tabs come from `.tab-btn` and `#tab-<id>`.
  - `overview` → Overview.
  - `sources` → sources.
  - `worklog` → dropped.
  - Every other tab is a part, and each `<h3>` in it starts a chapter.
- Map HTML to blocks: `p`, `h4` → `h`, `ul/ol`, `blockquote`, key-points boxes, `table`, `img`/`figure`.
- Images:
  - Embedded `data:image/avif` images (~595) are decoded and transcoded to JPEG/PNG.
  - Hotlinked images (about a dozen pages, e.g. *The Glory and the Dream* with 66, *Abundance* with 42) are downloaded and stored, per the owner. Downloads are sequential, with a polite delay and retry/backoff on 429 (Wikimedia Commons rate-limits). Downloads are cached in the work directory, so a rerun doesn't fetch again.
  - Any image that still fails to download is dropped and listed in the report.
  - The 2 SVGs are rasterised to PNG.
- Write a report per book:
  - chapter count and word count
  - unknown elements dropped and empty chapters
  - images extracted, downloaded and failed

  Books with dropped content or zero chapters are flagged.
- Output folders go into the local DB with `push_book.py`. Their working directory is outside the repo, or gitignored. The owner spot-checks flagged books in the reader before `/pages` comes down.
- Edge cases expected:
  - pages with no part tabs
  - Chinese pages (`quanqiutongshi-zhangjie-zongjie.html`), where `lang` becomes `zh`
  - near-duplicate files (`abundance-book-summary.html` and `abundance-klein-thompson.html`). The report lists likely duplicates. The owner chooses which to keep.

### 5.7 Web app

- **Routes** (all under `/distill`, all require sign-in):
  - `/` — the library.
    - "Reading now" first: in-progress books with current chapter and progress bar, as on Plainly's Kindle home.
    - Then all books, most recently imported first.
  - `/books/<slug>` — book page: title, author, cover, progress, table of contents grouped by part, ending with Source when present.
  - `/books/<slug>/read` — the reader, at the saved place.
  - Progress API and image route. Images are served through Flask behind sign-in, not as Apache static files.
- **Installed app:** the existing drop mark supplies SVG/ICO favicons and 180/192/512px app icons, with maskable-safe padding. `/manifest.webmanifest` sets a stable app ID, start URL and scope using the live deployment prefix, and opens in standalone mode. The manifest link includes credentials because the app is private. `/sw.js` is scoped to the same prefix and returns a generic offline fallback for failed navigations; it never persists private pages, books, or progress in Cache Storage. Chromium exposes an Install app button when eligible; iPhone installation uses Share → Add to Home Screen. Installation requires HTTPS in deployment (localhost works for development).
- **Signed out:** `<Location /distill/>` uses `OIDCUnAuthAction auth`, so Apache sends anyone signed out to Google sign-in. This differs from Plainly's `pass`. Pages also check that the signed-in email is on an allow-list (`DISTILL_ALLOWED_EMAILS`) and return 403 otherwise. Without that, any Google account could sign in and read.
- **Reader code is shared, not forked (owner requirement).** Phase 1 leaves the web reader JS and Kindle templates in Plainly. The Distill web-app phase starts by extracting the common reader components from Plainly's app into `shared/`:
  - pagination and scrolling
  - progress sync and saved place
  - reader settings
  - table of contents
  - the Kindle page-turn script, CSS and generic templates

  Plainly's reader switches to the shared components in the same phase. Only app-specific pieces stay in each app: Plainly's modes and paragraph rendering, Distill's block rendering. A Distill reader that copies Plainly's reader code fails this design, even if it works.
- **Reader:** Plainly's continuous reader with a single mode. There is no mode switch. Block rendering covers the block types in 5.2. The reader settings (font, size, theme) are shared with Plainly's.
- **Kindle mode:** same detection and `?kindle=` override. The server-rendered library, book and reader templates come from `shared/kindle` with Distill's block rendering. Tables and images must page cleanly (no cut lines), checked by the e2e harness. Progress sync uses the existing Kindle progress endpoint pattern.
- **Look:** Plainly's design system with a Distill name and wordmark. No new visual language for v1.

### 5.8 Deploy

- `deploy/distill/` holds:
  - a systemd user unit (`distill.service`). Own service user or the same `summra` user is the builder's call, based on the VM.
  - a gunicorn config (1 worker, bind `127.0.0.1:<port>`)
  - an Apache snippet for `/distill`
  - a code deploy script mirroring Plainly's documented steps: pull, restart if needed, verify
  - a DB-push script (local `distill.db` → VM; see 5.4)
- Document both deploy scripts in CLAUDE.md next to Plainly's.
- Static assets for Distill's UI may be served by Apache like Plainly's. Book images may not.
- Check VM memory before and after starting the second service (`free -m`, both services' RSS) and record it.
- Taking down `/pages` summaries: remove the book-summary HTML files from the VM's `/pages/` folder (they're served by Apache). Add redirects from each old page to its Distill book where a slug matches. This is the last step, after the owner has checked the converted library.

### 5.9 Phases

1. Repo split, Plainly unchanged.
2. Distill format + import command + converter (local only), tested on all 54 pages.
3. Distill web app + Kindle mode, local.
4. Deploy Distill to the VM at `/distill`, push the local `distill.db` holding the converted library.
5. Update the `book-summary` skill: write `book.json`, drop HTML and Phase 7, end with `push_book.py --deploy`.
6. Owner checks the library, then `/pages` summaries come down with redirects.

## 6. Left to the builder

- Exact module names and how far to take the split in phase 1, as long as nothing app-specific stays in `shared/` and nothing shared is duplicated.
- How the shared reader index is parameterised (interface, base class, or callbacks).
- Ports, service user, unit names, DB file names.
- The rendering of each block type in web and Kindle, within Plainly's design system.
- Converter heuristics for odd pages, as long as every drop is reported.
