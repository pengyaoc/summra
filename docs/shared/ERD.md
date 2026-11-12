# Shared platform — Engineering Reference

> Split out of `docs/ERD.md` on 2026-11-11. The reader, Kindle e-ink mode, sign-in and progress, audio player, media policy and repository layout that both apps use. Newest dated entries are at the top; the reference sections follow.

## 2026-11-07: Native Kindle viewport stabilization

The native fullscreen launcher embeds an ES5 policy loaded through Mesquite's
app-local test-script hook into its privileged browser context. It disables
native auto/double-tap zoom on HTTPS Distill/Plainly book-reader URLs, fits the
existing body width to the physical window, and resets native viewport position
after clicks, document loads and app activation; native reader scrollbars are
hidden and return to automatic outside the reader. Delayed reassertion runs after
native input handling; webpage DOM dimensions and pagination remain unchanged.
Listeners/timers are replaced idempotently and removed on unload; native zoom
controls are re-enabled on pause or navigation outside reader URLs (including
kindle=0). No web-to-device bridge, schema/auth change or stock browser patch.

The launcher atomically installs its marked sidecar inside Mesquite's writable
app jail and requires a token-specific native readiness log before hiding bars.
Unsupported native APIs leave the toolbar visible. Physical PW3 touch cycles and
user finger testing confirm stable full-size pages; emulation alone is not proof
for this hardware-only bug. Website geometry experiments were reverted.

## 2026-11-03: Kindle reader chrome sizing and overflow

Shared `shared/static/css/kindle.css` scales reader chrome typography 2.5×,
reserves 90px top/bottom pagination insets, and lays out settings panels in normal
flow inside an independently scrollable menu. Existing viewport measurements
repaginate prose into the reduced reading rectangle without changing kfs/font
cookies, anchors or body-text size. The ES5 scroll guard in `kindle.js` permits
input within an overflowing open menu while continuing to suppress document
panning; non-overflowing menus and the reader keep their prior drag protection.
Distill figures use atomic inline-block boxes so illustrations and captions stay
together in the shorter reading columns. Native launcher gestures, authentication
and database schemas are unchanged. The three static assets are deployed with
content-hashed URLs; both services remain active without a restart. Source
release `7b78211` is synchronized to the VM with clean tracked files and matching
live asset hashes. Release synchronization adds no architectural/schema change.

## 2026-11-03 — Physical PW3 image painting correction

Physical testing reproduced a legacy WebKit multicolumn painting defect after
font-size 8→9: the figure reserved its complete footprint but only the image's
lower region painted. For the existing native PW3 profile only, preserve the
original image's layout footprint and progress unit while hiding its painting.
Paint a cached image copy in a separate clipped viewport layer outside columns,
positioned from the original rectangle on each page turn or relayout. Captions
remain in the normal flow; display copies carry no progress indices. Other
browser profiles and no-JavaScript rendering retain their existing images.
No schema, content, authentication or progress-model changes. Deployed and
physically verified on the owner’s PW3 at sizes 8 and 9, including paging away
and back and a second illustrated chapter. Browser projection/readiness tests
and 303 Python regressions pass. This supersedes the earlier pending physical
image verification; detailed evidence and limitations are in WORK_LOG.md.

## 2026-11-02 — Kindle startup and illustration layout repair

The shared Kindle reader now hides its body before the first body paint when
JavaScript is enabled, waits for chapter image load/error completion, and reveals
the requested page only after pagination and the existing native PW3 shell's
200 ms geometry settlement. A 15-second head-script recovery preserves access
if the reader script fails; the image wait is capped at 10 seconds. Failed or
stalled images are hidden before pagination, retain their captions, and cannot
shift an already displayed page when a late request completes. No-JavaScript
reading retains the existing visible scrolling chapter.

Loaded illustrations receive explicit proportional dimensions before column
pagination. The image plus caption and figure margins are constrained to the
reading viewport; figures and images explicitly use block layout, avoiding
reliance on an old browser's HTML5 figure defaults and inline-image baselines.
Resize notifications with unchanged geometry do not repaginate. Existing native
PW3 shell setup ordering, fullscreen polling/reload behavior, startup fragments,
font controls, authentication and progress coordinates remain. No DB/schema or
content changes. Deployed and live-verified November 2, 2026; physical Kindle
paint/drag confirmation remains pending because the device is unreachable.
Validation details are in WORK_LOG.md.

## Shared audio player (2026-11-09)

Supersedes the Player notes in the two Listen sections below. Design: `docs/superpowers/specs/2026-11-09-shared-audio-player-design.md`.

**Frontend (`shared/static/js/`).**
- `audio_player.js`: `AudioPlayer`, one per browsing session. Owns the `<audio>` element, tracks (multi-part allowed), position, rate, silent hold and Media Session. Knows nothing about pages. `subscribe` emits `state`, `time`, `track`, `error`. The only `new MediaMetadata` is here.
- `audio_sources.js`: `RecordedBookSource` (shared audio API) and `PlaceKeeper` (saved place with or without a reader on screen). `plainly/frontend/static/js/generated_speech_source.js` adapts Plainly's summary speech, using book id `speech-<id>`.
- `reader_audio_link.js`: `ReaderAudioLink`, one per on-screen reader: headphones button, highlight, page following, turning away, Listen from here instead. Highlight and page turns need the screen's book and page to match the audio. Paging back to the spoken page, or starting a track from the player, resumes following.
- `player_ui.js` with `shared/templates/shared/reader/_player.html` and `listen.css`: mini player and full player. Controls hide from track data, not app checks. The player floats, so audio cannot change where reader pages are cut.
- `page_swap.js` (Distill): fetches same-origin pages from an allow-list, parses them and swaps `#page-root`. Prefetches on hover and pointerdown, keeps scroll in history state, and falls back to a full load (saving audio first) on 401, redirect or failure. The reader DOM stays in `#reader-shell`, outside `#page-root`. `distill_shell.js` owns the player and exposes `window.distillAudio`; Plainly exposes `window.plainlyAudio`.

**Backend (`shared/audio/`).** `store.py` (`AudioStoreMixin`, table `chapter_audio`, key `(chapter_id, mode)`, default mode `summary`), `routes.py` (`audio_blueprint(get_db, access_check)`), `engines.py`, `spoken.py`, `assemble.py`. An app supplies the hook `audio_spoken_units`. Plainly stores media under `data/plainly-media`. Recording is one shared command, `python -m shared.audio.make_audio --app {distill,plainly}`; each app describes itself in `<app>/audio_app.py` (database, reading modes, deploy). A book's `lang` picks the voice, English when it has none. Plainly's summaries are recorded by `plainly/scripts/audio/record_summaries.py` to `static/audio/book_<id>_<type>.m4a`, which `tts_utils.check_cached_audio` prefers over older Gemini files. Plainly no longer calls Gemini for speech: `/api/tts/generate` lives in `app_base.py` and, in dev as in production, only finds recordings. Shipping Plainly's recordings to the VM is not built yet.

**Deploy order.** Run `deploy_code` before `deploy_db`, so the VM migrates `chapter_audio` to the two-column key before rows arrive.

**Tests.** `tests/e2e/`: `reader_audio_stable`, `player_ui`, `player_reader`, `distill_in_place`, `plainly_player`, `distill_page_timing` (budget in `perf/distill_baseline.json`, measured through a local delay proxy because `page.route` disables the HTTP cache).

## Generated media lives outside Git (2026-10-27)

Verified on production: generated media stayed in place with all 634 hashes
unchanged; Plainly audio/images and authenticated Distill library/book/cover
requests pass. Both services remain active. Published main and remaining local
branch/stash/checkpoint references are cleaned; non-media saved work is preserved.
CI passed for the rewrite. This is a storage/deployment policy change only.

Generated Plainly audio, covers, chapter illustrations and guide images are
runtime/deployment assets, not source-controlled blobs. Their existing paths
under `plainly/frontend/static/{audio,covers,illustrations,guides}/` and all
application/database URL references remain unchanged. Historical paths under
`frontend/static/` and generated redesign/e2e screenshots were removed from Git
history too. Ignore rules prevent reintroduction. Branding/UI icons and Kindle
shortcut covers remain source-controlled; Distill's image blobs remain in its
separately managed content SQLite database.

Deployment supplies these assets separately, preserving ignored files during
code updates. A fresh clone contains source and branding, not a complete media
library. Git history rewrite changes commit identities, not database schema,
API contracts or reader/auth logic. Existing clones must be explicitly migrated
or recloned; merging old history would reintroduce the removed objects. VM
transition preserves media paths/bytes and can update HEAD/index without deleting
the working media. See `deploy/README.md` for operational requirements.

## Shared Kindle pairing and launcher source (2026-10-27)

Deployment verified: `eb89c5f` is live for both apps. Apache syntax, service health,
Kindle QR/bootstrap, normal Google login, phone-only route challenges and
public/private library boundaries pass live HTTPS checks. Complete approval and
revocation flows pass integration tests; on-device phone approval remains a user check.

`shared/auth/device_pairing.py` now owns the existing SQLite pairing request,
CSRF and device-session model plus request identity middleware for both apps.
App configuration supplies id/name, environment prefix, library/login endpoints,
public exceptions and optional launch endpoint. Required mode keeps Distill
private; optional mode preserves Plainly's anonymous content and existing
login-required progress APIs. Only e-reader Kindle UAs can redeem device cookies.
Google's trusted header identity is always required for approval/revocation;
paired credentials cannot authorize another device. Cookie paths and names and
SQLite stores remain app-isolated; Distill's existing `distill_pairing.db` and
`distill_*` cookies are compatible, Plainly uses `plainly_pairing.db` beside its
user DB and `plainly_*` cookies. No existing table/schema migration is required.

Pairing HTML is shared at `shared/templates/shared/kindle/pairing.html` with
app branding. Plainly `/login` has a real Flask redirect route rather than an
Apache remapping to `/`; Kindle sign-in links go directly to `/pair`, while
normal browsers retain Google OIDC. Apache explicitly challenges the phone-only
`/pair/approve` and `/pair/devices` endpoints for both apps.

`deploy/kindle/` is the authoritative version-controlled native launcher and
cover source; runtime state remains in Kindle RAM and scripts remain under
`/mnt/us/distill-fullscreen/native/`. The imported scripts retain the verified
Home handoff, single-browser lock, title ownership checks and recovery behavior.
SSH keys and experimental images stay outside Git. This is a browser-window
launcher, not an alternate engine. Disk audit in `deploy/README.md` attributes
most avoidable VM usage to retained deployment DB backups; live DBs have almost
no free pages, so no schema/VACUUM or deletion is justified by this audit alone.

## Native browser gestures and sleep lifecycle (2026-11-03)

Supersedes the power-event termination/four-hour default below. The existing
`deploy/kindle/session.sh` embeds a LuaJIT/FFI X11 helper with input-only,
override-redirect edge/corner windows, restacked directly above the browser
every 500 ms to survive browser raises while leaving native dialogs above them.
A top-edge downward swipe restores the recorded browser title (`PC:TS`); a reserved bottom-left corner tap toggles
`PC:N`/`PC:TS`. While bars show, an input-only page-area window consumes the first
outside tap to dismiss them. Ordinary page input outside reserved zones remains
with the browser. Native controls stay outside the website; no web/device bridge,
web code, authentication, database or data model changes.

Startup waits for helper readiness before hiding bars. X11 automatically destroys
input windows when the helper connection closes; cleanup records/kills the actual
Lua child PID as well as its shell wrapper and restores only the owned title.
The supervisor tolerates non-active power states, hides gesture windows while
asleep, restores fullscreen on wake, and grants a bounded app-focus settling
period. Browser/window replacement exits safely. Default session duration is
unlimited; an optional bounded recovery timer and manual restore remain.
Existing reader paragraph-preserving reload on toolbar restoration is unchanged.
Physical swipe operation was confirmed after periodic stacking. Corner reveal
was subsequently reported inconsistent: touches outside the former 101px zone
led to expanding it to 11% of screen height (159px on PW3). The controller now
regression-tests those physical coordinates; user retesting confirmed improved
corner reliability after the expansion. Validation/deployment status is recorded
in WORK_LOG.md; native dialog stacking and physical power-button/cover checks remain separate.

## Verified native fullscreen architecture (2026-10-27)

The installed jailbroken-Kindle launcher uses normal appmgr browser startup and the existing native X11 window; PC:TS→PC:N hides the status/search chrome without a custom engine or browser-file changes. Record the exact original window title and restore only the matching owned fullscreen title. A separate power/sleep-event waiter restores it independently of the main loop, with a four-hour ceiling; app exit, process traps and the restore shortcut use the same restoration routine. State is in `/tmp/distill-native-fullscreen`, persistent scripts in `/mnt/us/distill-fullscreen/native/`, source backup on the Mac in `~/.local/share/distill-kindle/native-fullscreen/`. No autostart or sleep-prevention setting is installed.

The verified PW3 reports outerHeight1232 normally and1448 fullscreen, but retains1268 for innerHeight/clientHeight. Its existing native-only layout adds216px to body/shell in fullscreen and checks outer-height changes at1Hz, with no reflow when unchanged. Returning native chrome retains an otherwise uncontrollable pan offset, so replace the fragment with the current paragraph and reload the reader. Current font/login/paragraph persist. Other device profiles retain the existing layout. Manual/timeout restoration and physical drag containment in fullscreen/menu/normal-exit all pass; power-event subscription is installed but no physical power cycle was performed in this run. No auth, data or schema change. Earlier viewport-height assumptions below are superseded.

## 2026-10-27: Clear native pan on fullscreen exit

Fullscreen/full-height menu drags and installed timeout restoration physically pass. Returning native chrome retains a pan offset outside DOM scroll coordinates even after remeasurement. On the matched PW3's fullscreen→normal outer-height transition, replace the current fragment with the current paragraph and reload the reader to reset native pan. Fullscreen entry still repaginates locally. The current URL/history entry, font, login and paragraph are retained; exiting fullscreen now requires a page reload. No schema/auth changes. Physical exit verification pending.

## 2026-10-27: Detect measured fullscreen outer height

Physical geometry proves that fullscreen changes outerHeight1232→1448 while innerHeight/clientHeight stay1268. Use the matched PW3's outerHeight equal to screen.height to add216px to the native body/shell. A once-per-second native-only check repaginates only when outerHeight changes, covering builds that omit DOM resize. Regression emulates the real fixed-inner-height behavior. Restore shortcut now validates the exact standard browser title as well as titles with extra fields; manual restoration returns1232px and removes session state. Normal Home scriptlet launch successfully opens the authenticated fullscreen library. Direct browser LIPC `go` caused a Mesquite crash and is excluded; recovery dismissed its dialog and reopened via normal launch. Temporary geometry diagnostic will be removed during clean deployment. No native browser/root-filesystem edits or auth/data changes.

## 2026-10-27: Use native fullscreen browser space

A reversible X11 window-title request (`PC:N` versus normal `PC:TS`) hides the PW3's native status/URL bars without replacing the authenticated browser or editing its files. Physical screenshot confirms1072×1448 at y0 instead of1072×1232 at y216. The native reader now adds any reported viewport-height increase above1268px to its measured1260px body/1279px scroll shell; reversing fullscreen restores normal height. Only the existing matched legacy PW3 profile uses this correction. Added enter/exit height regression coverage. No data/auth/progress schema changes. Launcher and full-height physical verification pending.

## Verified native PW3 implementation (2026-10-27)

This final implementation supersedes the trial architecture entries below. Only no-touch WebKit531–534 on a1072×1448 screen with portrait document proportions receives `native-pw3`, selected once during startup. Finish ordinary pagination first, then move the existing header/viewport/footer/menu nodes into a dynamically created shell with explicit inline native geometry:104% relative body,1260px body height,1279px scrolling shell. Repaginate after200ms, preserving explicit startup anchors. The native browser requires this initialization/style sequence; class-only geometry and extra reflows did not reliably constrain fresh-load panning. Font relayout does not reevaluate/remove the profile. Other browsers retain the original unwrapped layout; no-JS fallback is untouched. No schema/auth/content changes. Final deployed62e3f39 physically passes all four drag directions after load/reload, size changes, Song→Hei and menu close. Temporary geometry probes removed; normal device sleep restored.

## 2026-10-27: Match measured native surface initialization

Use the physically successful trial sequence directly: finish normal pagination, wrap only the matched PW3 reader nodes, explicitly set native shell/body styles, then repaginate after 200ms. The profile is selected once, so font relayout cannot remove it. Other browsers retain their original unwrapped layout. Earlier class-based/extra-reflow attempts did not pass fresh-load drags and are superseded. No content/auth/storage changes. Final physical verification pending.

## 2026-10-27: Reconcile native scroll range after load

Startup geometry confirms the PW3 profile is selected, but its native scroll range settles later than synchronous DOM layout. Remeasure only this profile one second after window load. Preserve explicit end-of-chapter startup across wrapping/remeasurement. Temporary startup metrics excluded from release. Physical reload verification pending.

## 2026-10-27: Initialize native scroll surface after pagination

Font adjustment/closed-menu drags passed, but a fresh native load retained its initial root pan range. Defer wrapping existing reader nodes until after the first pagination/reflow, then remeasure at the current paragraph, matching the successful physical trial initialization order. No content/auth/storage changes. Fresh-load verification pending.

## 2026-10-27: Preserve native profile after font relayout

The physical PW3 passed settled-load/menu drags but changing size exposed an unstable exact document-width check: native auto-fit can change CSS document width. Keep the legacy no-touch 1072×1448 device match, using portrait document proportions instead of exact width during relayout. This retains the workaround across font changes. No data or authentication changes. Final on-device adjustment/close verification pending.

## Native PW3 viewport profile (2026-10-27)

`kindle.js` places the existing reading nodes inside a dynamic `reader-shell`. The general browser path keeps its100% clipped shell. A narrow runtime profile detects no-touch legacy WebKit, a1072×1448 screen and1072px document width, then enables `native-pw3`: a104%-wide,1260px relative body contains a1279px native scroll shell. The inner scrollbar gutter is clipped and the native view stops panning into blank space. Exact dimensions were derived/tested on PW3 firmware5.16.2.1.1; this is a portrait-only profile, not a generic screen-size formula. DOM touch listeners cannot constrain this browser because it exposes no touch events; they remain useful on modern engines. Root scroll-reset logic does not control the PW3's separate native pan. Dynamic wrapping leaves the no-JavaScript fallback unchanged. No persistence, content or auth changes. Temporary geometry beacons are diagnostic only and excluded from the clean release.

## Kindle gesture scroll containment (2026-10-27)

The paginated reader cancels touchmove and wheel default actions on the body in capture phase, explicitly non-passive on modern browsers and capture=true on legacy boolean-listener APIs. This covers reading text, gutters and font banners; click/tap navigation is retained. A guarded window scroll listener resets nonzero root/body offsets, and menu open/close also clears stale offsets. The font menu is a clipped, absolutely positioned overlay whose banners are positioned within it, preventing fixed descendants from adding a native blank document range. Modern touch-action/overscroll declarations supplement the legacy JavaScript guard. No persistence schema, auth or progress-format changes.

## Kindle viewport sizing (2026-10-27)

JavaScript-enabled Kindle reading uses a fixed CSS body anchored to the viewport edges, absolutely positioned header/footer and an inset clipped reading rectangle. Pagination measures that rectangle's clientWidth/clientHeight instead of window.innerWidth/innerHeight, which may include chrome or overflowing content on legacy WebKit. The vertical fallback clears its old explicit height before remeasurement. Tap zones use body dimensions; layout resets document scroll offsets. Legacy WebKit scrollbar styling is limited to paginated reading. Without JavaScript the existing scrolling chapter remains available. No architecture, database or progress-format change. The regression reproduces the prior oversized rectangle with inflated window metrics and verifies the bounded rectangle after the fix.

## Kindle typography configuration (2026-10-27)

`KindleOptions` now declares `font_size_max`, `font_size_default`, `font_choices` and `font_default`, with bounded/allowlisted validation. Shared cookie readers use the installed app configuration. Distill selects ten sizes through72px, default36px, and system/Song/Hei font choices; Plainly retains five sizes and its21px default. The existing `kfs` cookie preserves levels1–5 and accepts larger levels only in configured apps; `kff` stores a validated font key. Distill's CSS requests local STSong/STHeiti CJK fallback families after the Latin face, with generic fallbacks. Both families were verified via fontconfig on the actual PW3. No webfonts, database schema changes or system font installation. The shared ES5 reader consumes maximum/default data attributes, parses multi-digit size classes, repaginates after size/font changes, updates the level indicator and disables controls at bounds. Existing cookies remain prefix-scoped and expire after a year.

## Distill Kindle device authentication (2026-10-27)

`distill/device_pairing.py` resolves trusted Apache OIDC identity first, then an allowlisted Kindle-only device cookie. It runs before Kindle dispatch. Apache `OIDCUnAuthAction pass` is conditional on the shared e-reader UA definition; false matches retain Google auth. Public `/pair` and `/pair/qr.png` contain no private content and reject non-Kindle clients; `/pair/approve` and `/pair/devices` always require genuine OIDC, independent of device cookies. UA is a routing signal, never an identity. Explicit display-mode overrides do not enable device authentication.

Separate SQLite `distill_pairing.db`, alongside the configured user DB (override `DISTILL_PAIRING_DB`): `pairing_requests(secret_hash PK, code UNIQUE, created, expires, email, consumed)`, `device_sessions(token_hash PK, id UNIQUE, email, created, expires)` and `pairing_csrf(token_hash PK, email, scope, expires)`. Request and session secrets have 256 bits of randomness and only SHA-256 hashes are stored. Approval identifiers expire after ten minutes; the originating browser secret is required for an atomic, one-time redemption into a 30-day session. `BEGIN IMMEDIATE` serializes concurrent redemption. Request creation is globally bounded to 40 per ten minutes; creation purges expired records. Approval/revocation require one-time email/scope-bound CSRF tokens plus a matching HttpOnly cookie and reject foreign Origin headers. Allowlist checks apply on every authenticated request, including redeemed sessions. Session revocation deletes its hash. Cookies are Secure/HttpOnly/SameSite=Lax and scoped to the mounted app. Pairing responses are no-store, deny framing and restrict external resources. QR codes are generated locally (`qrcode`); the canonical origin defaults to `https://pengyaochen.com` (`DISTILL_PAIRING_ORIGIN` override), never the client Host header. No Google token is copied to a Kindle. Existing content/progress schemas and Plainly authentication are unchanged.

This document provides in-depth technical documentation for the Summra project, including entity relationship diagrams, detailed algorithm implementations, and code-level architecture. This is intended for developers and for providing context to future Claude Code sessions.

## Reader section boundary navigation (2026-10-27)

The shared web reader uses the first/last IDs in `continuousReader.segmentIds` as its rendered window edges. Backward section navigation opens the previous section's final page (`shouldGoToLastPage`); forward navigation opens the section after the last rendered section on its first page (`shouldResetToPage1`). Navigation replaces the window IDs, and button availability uses the same edges. In-flight section turns ignore repeated input, release their lock on every exit, and discard responses after reader exit, replacement or mode change. This fixes multi-chapter backward skips such as the reported 细胞传 jump and prevents replaying a prefetched section going forward. No architecture, schema, content, marker or API changes; Plainly and Distill share the behavior, with Plainly's bundle rebuilt.

Deployment verification: both the reader continuity and Distill book-action styling shipped in e6cb60f. Both apps are active; live served assets match the tested files. No database migration.

## Repository layout (post repo split, 2026-10-24)

```text
shared/                  Code both apps use (must not import plainly/ or distill/)
  auth/                  pchauth (trusted-header identity), user_models.py, whoami.py
  progress/routes.py     Reading-progress blueprint
  reader/                config.py (ReaderConfig), modes.py, platform.py, routes.py, blocks.py, index.py
  kindle/                UA detection, page dispatch and helpers, progress recording
  static/, templates/    static/{css,fonts,js} (reader platform), templates/shared/
  web.py                 Prefix middleware, gzip, asset versioning, install_shared_ui
plainly/                 The Plainly app (package `plainly`)
  app_base.py, app.py, app_prod.py, config.py, models.py, routes/, tts_utils.py, ...
  frontend/              Flask static_folder / template_folder (relative to plainly/)
    static/              css/, js/ (app.min.js is built), covers/, illustrations/, audio/, shared -> ../../../shared/static
    templates/
  scripts/               Ingestion, audits, audio, images (run as `python -m plainly.scripts.<group>.<name>`)
distill/                 Distill, the second app (see "Distill app")
  app_base.py, routes.py, kindle_routes.py, models.py, book_format.py, reader_config.py, scripts/
  static/ (shared -> ../../shared/static), templates/
tests/{shared,plainly,distill}/  Tests mirror the package layout; tests/e2e is the Playwright harness
deploy/                  gunicorn_config.py (every service), hardening checks, kindle/ launchers
  plainly/               install.sh, summra.service, override.example.conf, summra.conf (Apache), service.env.example, requirements-prod.txt
  distill/               distill.service, distill.conf (Apache), env and deploy.local templates
  archive/               Superseded: dedicated-VM DEPLOY.md, unused nginx configs
docs/                    PRD.md, ERD.md (indexes); shared/, plainly/, distill/ (each PRD.md + ERD.md, plus app docs); superpowers/ (specs, plans), archive/
```

Each of `shared/`, `plainly/` and `distill/` has a README; the root README presents Summra as the platform plus the two apps (2026-11-11). Plainly's deploy files moved from `deploy/{apache,systemd}/` and the repo root into `deploy/plainly/` the same day. The VM's installed copies (`/etc/apache2/service-locations/`, the user unit) are copies, so the move needs no VM change; reinstall from the new paths next time. Also on 2026-11-11: PRD and ERD were split into `docs/{shared,plainly,distill}/` (`docs/PRD.md` and `docs/ERD.md` became indexes), and the ingestion, Plain English and deploy runbooks moved out of `CLAUDE.md` into `docs/plainly/` and `deploy/{plainly,distill}/RUNBOOK.md`.

`plainly.config.BASE_DIR` is the repository root, so `data/` stays at the top level while
`COVERS_DIR`, `ILLUSTRATIONS_DIR` and `TTS_OUTPUT_DIR` live under `plainly/frontend/static/`.
Scripts compute repo-relative paths from `Path(__file__)` with one extra `.parent` level
(`plainly/scripts/<group>/x.py` is four levels below the root). The production Apache `Alias` and
nginx `alias` point at `/opt/summra/plainly/frontend/static/`, and the esbuild paths in
`package.json` use the same prefix. `tests/test_layering_names.py` fails if any file still refers
to the old top-level `backend`, `scripts` or `frontend/static` locations.

## User Authentication & Progress Tracking (Added 2025-12-20; **auth rebuilt 2026-09-06 — see note**)

> **Superseded 2026-09-06:** the username/password registration+login system originally documented in this section — `shared/auth/`, `plainly/auth_utils.py`, SHA-256+salt password hashing, Flask server-side sessions — was deleted outright, not deprecated. Identity is now supplied entirely by a shared Apache reverse-proxy gateway via a trusted `X-Remote-Email` header (the `pchauth` package, `shared/auth/pchauth/`). This app has never run its own OAuth flow and has no login form of any kind. Full history: `WORK_LOG.md` (2026-09-05/06 entries); design spec in the `pchauth` repo's `docs/superpowers/specs/2026-09-05-consolidated-login-design.md`.

### Overview

Reading-progress tracking stored in a separate database (`summra.db`), keyed by an identity this app never authenticates itself — it trusts whatever `X-Remote-Email` the Apache gateway in front of it supplies (or none, for an anonymous visitor). The app assumes an internet connection is always available; there is no offline-mode fallback for progress or identity.

> **Note:** this section (Progress Tracking Flow / Frontend Integration below) predates the 2026-09-06 auth rebuild and the 2026-09-07 offline-support removal — some method names and localStorage keys described here no longer match `plainly/frontend/static/js/auth.js`. Needs a refresh; out of scope for the offline-removal pass that touched it.
>
> **Further update, 2026-09-07:** `plainly/frontend/static/js/auth.js` also dropped its IndexedDB-backed local mutation queue (`device_profile`, `local_book_state`, `local_mode_state`, `pending_mutation`, `cached_library` object stores) that let a device write and restore its own progress ahead of / without a server round-trip. Progress is now single-source-of-truth in `summra.db` (`mode_reading_state`/`book_reading_state`/`progress_mutation`, described below) — `queueReaderMutation` posts straight to `/api/progress/v2/mutations` and `getReaderState`/`getLibrary` always read from `/api/progress/v2/books/<id>` and `/api/library`, so progress still follows the reader across devices via the server DB, it's just no longer cached or trusted locally per device. `plainly/frontend/static/js/auth.js` still uses IndexedDB for one unrelated thing: `cached_manifest`/`cached_segment` object stores, a pure content cache (already-fetched chapter manifests/segments) so a mid-session network hiccup doesn't lose a page already loaded — not progress persistence.

### Identity: pchauth (`shared/auth/pchauth/`)

**Purpose:** framework-agnostic trusted-header identity resolution, shared with OpenReader (each app has its own copy of the same small package — no cross-repo dependency).

| File | Purpose |
|---|---|
| `core.py` | `Identity` dataclass (`email`, plus `subject`/`name` reserved for a deferred direct-OIDC source, unused today) and `is_allowed(email, config)` — the allowlist check, fails closed. |
| `config.py` | `AuthConfig` (`mode`: `off`/`optional`/`required`, `allowed_emails`) and `load_pchauth_config(environ, prefix)`, which reads `{PREFIX}_AUTH_MODE` / `{PREFIX}_ALLOWED_EMAILS`. |
| `trusted_header.py` | Extracts an `Identity` from `X-Remote-Email` (and, if present, `X-Remote-User`/`X-Remote-Name` for the reserved fields) — no verification of its own; the whole security model rests on this header being unforgeable, which is only true because the app binds `127.0.0.1` and is reachable exclusively through the trusted Apache proxy. |
| `flask_adapter.py` | `init_pchauth(app, config, upsert_user)` — a `before_request` hook resolving `g.user_id` every request; `login_required` decorator matching `auth_utils.py`'s old error shape (`{'error': 'Authentication required'}`, 401) so replacing it needed no call-site changes in `progress_routes.py`. |

**Per-request resolution (`init_pchauth`'s hook):**
- `mode == 'off'`: every request resolves to one fixed default identity (`upsert_user(Identity(email=""))`) — reproduces pre-pchauth no-login behavior for local dev/test, where there's no Apache gateway to supply anything.
- No `X-Remote-Email` + `optional`: `g.user_id = None`, request proceeds anonymously.
- No `X-Remote-Email` + `required`: 401 immediately.
- Header present but email not in `allowed_emails`: 403.
- Header present and allowed: `upsert_user(identity)` creates/updates the `users` row by email and sets `g.user_id`.

### Database: summra.db

**Location:** `summra.db` (root directory, separate from content database)

**Purpose:** Store user accounts, authentication data, and reading progress. Separation from `database.db` keeps user data isolated from book content.

### Entity Relationship Diagram

```
┌─────────────────────────┐
│       users             │
├─────────────────────────┤
│ id (PK)                 │
│ email (UNIQUE)          │
│ subject (UNIQUE, unused)│
│ name (unused)           │
│ created_at              │
│ last_login              │
└─────────────────────────┘
         │
         │ 1:N
         ├──────────────────────────┬──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  reading_progress   │    │ chapter_completion  │    │  (future tables)    │
├─────────────────────┤    ├─────────────────────┤    │                     │
│ id (PK)             │    │ id (PK)             │    │ - bookmarks         │
│ user_id (FK)        │    │ user_id (FK)        │    │ - notes             │
│ book_id             │    │ book_id             │    │ - highlights        │
│ chapter_number      │    │ chapter_number      │    └─────────────────────┘
│ page_number         │    │ completed           │
│ scroll_position     │    │ completed_at        │
│ updated_at          │    │ created_at          │
└─────────────────────┘    └─────────────────────┘

UNIQUE(user_id, book_id)   UNIQUE(user_id, book_id, chapter_number)
```

### Database Schema

#### users table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    subject TEXT UNIQUE,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `email`: From the trusted `X-Remote-Email` header — the only identity source this round; unique
- `subject`, `name`: reserved for a deferred direct-OIDC identity source (`self_oidc` in the pchauth design), never populated by `trusted_header.py` today — don't assume either is set
- `created_at`: Account (row) creation timestamp
- `last_login`: Last request timestamp that resolved this identity

**No credential of any kind is stored here.** This table exists to key reading-progress rows to an email, not to authenticate anyone — authentication happens entirely upstream, in Apache. A pre-2026-09-06 `users` table (`username`/`password_hash`/`salt`) is dropped and recreated on first run after upgrade (`UserDatabase._migrate_password_schema`) — safe because every known deployment had 0 rows in it; that migration refuses to run (rather than silently drop data) if it ever finds otherwise.

#### reading_progress table

```sql
CREATE TABLE reading_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER,
    page_number INTEGER DEFAULT 0,
    scroll_position REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id)
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table (cascading delete)
- `book_id`: Book ID (references books.id in database.db conceptually)
- `chapter_number`: Current chapter (0 = preface, NULL = no progress)
- `page_number`: Current page in paginated view (0-indexed)
- `scroll_position`: Scroll position in non-paginated view (0.0-1.0)
- `updated_at`: Last update timestamp

**Constraints:**
- UNIQUE(user_id, book_id): One progress record per user per book
- Uses `INSERT OR REPLACE` to update existing progress

#### chapter_completion table

```sql
CREATE TABLE chapter_completion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    completed INTEGER DEFAULT 1,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, book_id, chapter_number)
)
```

**Fields:**
- `id`: Auto-incrementing primary key
- `user_id`: Foreign key to users table (cascading delete)
- `book_id`: Book ID (references books.id conceptually)
- `chapter_number`: Completed chapter number
- `completed`: Boolean flag (1 = completed, 0 = reset)
- `completed_at`: Completion timestamp
- `created_at`: First completion timestamp

**Constraints:**
- UNIQUE(user_id, book_id, chapter_number): One completion record per chapter per user
- Uses `INSERT OR REPLACE` to toggle completion status

### UserDatabase Class

**Location:** `shared/auth/user_models.py`

**Purpose:** Abstraction layer for all user and progress operations.

#### Key Methods

**Identity:**
```python
def upsert_user_by_email(self, email: str) -> int
    """Create the users row for this email if it doesn't exist, update
    last_login either way, and return its id. Called from pchauth's
    before_request hook on every request that carries a trusted,
    allowlisted identity — this is the only way a users row is ever
    created; there is no separate "register" step."""

def get_user_by_id(self, user_id: int) -> Optional[Dict]
    """Used by GET /api/auth/check to render {authenticated, user}."""
```

**Reading Progress:**
```python
def save_reading_progress(self, user_id: int, book_id: int,
                         chapter_number: int, page_number: int = 0,
                         scroll_position: float = 0.0) -> None
    """Save or update reading position."""

def get_reading_progress(self, user_id: int, book_id: int) -> Optional[Dict]
    """Get current reading position."""

def mark_chapter_complete(self, user_id: int, book_id: int,
                         chapter_number: int, completed: bool = True) -> None
    """Mark chapter as completed or reset."""

def get_completed_chapters(self, user_id: int, book_id: int) -> List[int]
    """Get list of completed chapter numbers."""
```

**Statistics:**
```python
def get_user_stats(self, user_id: int) -> Dict
    """Get reading statistics:
    - books_started: Count of books with progress
    - chapters_completed: Total completed chapters
    """
```

### Authentication Flow

There is no registration or login flow in this app — see `init_pchauth`'s per-request resolution above. Every request either arrives with a trusted `X-Remote-Email` (checked against the allowlist, then upserted) or without one (anonymous under `optional`, rejected under `required`). No client ever POSTs credentials to this app.

#### Session Management
- No session of this app's own — no cookie is set, no server-side session store exists here. Identity is re-derived from the request header every single time.
- Persistence lives entirely in the shared Apache gateway's `mod_auth_openidc` session (out of this app's control) plus the frontend's own `localStorage` cache of the last-known user (`auth.js`'s `summra_current_user` key) for instant offline UI.

### Progress Tracking Flow

#### Auto-Save Reading Position
1. User views chapter → `showChapterDetail()` called
2. Track initial view: `trackChapterView(book_id, chapter_num, page=0)`
3. User navigates pages → `displayCurrentPage()` called
4. Track page change: `trackPageChange(book_id, chapter_num, page_num)`
5. On last page: Auto-mark complete via `onChapterComplete()`

**Debouncing:** Progress saves are debounced (500ms) to avoid excessive API calls.

#### Chapter Completion Logic
```javascript
// In displayCurrentPage()
const isLastPage = this.pagination.currentPage === this.pagination.totalPages - 1;
if (isLastPage) {
    window.authModule.onChapterComplete(this.currentBook.id, this.currentChapter);
}
```

**Backend:** Uses `INSERT OR REPLACE` to handle completion toggle.

### Frontend Integration

#### auth.js Module
**Location:** `plainly/frontend/static/js/auth.js`

**Initialization:**
```javascript
window.authModule = {
    initAuth(),                                    // Initialize on page load
    checkAuthStatus(),                             // Ask /api/auth/check who (if anyone) the gateway says we are
    trackChapterView(book_id, chapter_num, page),  // Save progress
    trackPageChange(book_id, chapter_num, page),   // Update page position
    onChapterComplete(book_id, chapter_num),       // Mark complete
    getCompletedChaptersForBook(book_id),          // Fetch completions
    getReadingProgress(book_id)                    // Fetch current position
}
```

No `login()`/`register()`/`logout()` — there's nothing for this module to call for any of those; signing in happens, if at all, entirely outside this app.

#### UI Integration Points

**Header Account Button:** (`index.html`, `plainly/frontend/static/js/auth.js`'s `updateAuthUI()`)
```html
<button class="header-nav-btn user-account-btn hidden" id="user-account-btn">
    <span class="user-icon">👤</span>
    <span class="user-name" id="header-user-name">Account</span>
</button>
```
- Ships with the `.hidden` class server-rendered (most visitors are anonymous, and there's no sign-in action to offer them — see the Superseded note above). `updateAuthUI()` removes `.hidden` only once `/api/auth/check` confirms a real signed-in user, and shows their email.
- **Not** the bare `hidden` HTML attribute: `.header-nav-btn`'s own `display: flex` author style beats the UA stylesheet's `[hidden] { display: none }` regardless of specificity (author styles always win over UA defaults) — that was tried first and silently did nothing. `.hidden`'s `display: none !important` is what actually works; see `WORK_LOG.md`, 2026-09-06 final entry, for the live debugging story (including that reproducing the bug required clearing the PWA's service-worker cache, not just a same-tab hard reload).
- Opens the account modal on click; the modal's signed-out view (unreachable for a genuinely anonymous visitor, since the button itself is hidden) has no sign-in CTA and does not name the gateway's sign-in path.

**Continue Reading Button:** (`app.js:showResumeReadingButton()`)
- Created dynamically in `book-detail-info` section
- Only shown when user has progress for book
- Button text: "Continue Reading: Chapter X, Page Y"

**Completed Chapters:** (`app.js:loadChapters()`)
```javascript
const completedChapters = await window.authModule.getCompletedChaptersForBook(book_id);
// Apply .completed class to chapter boxes
box.className = 'chapter-box' + (isCompleted ? ' completed' : '');
```
- Chapters marked with grey styling + checkmark
- Visual indicator persists across sessions

### API Endpoints

#### Identity
- `GET /api/auth/check` - `{authenticated, user}` for the current request's resolved identity (or `{authenticated: false}`). No `/register`, `/login`, `/logout`, or `/me` — see the Superseded note.

#### Progress Tracking
- `POST /api/progress/save` - Save reading position
- `GET /api/progress/get/<book_id>` - Get reading position
- `GET /api/progress/all` - All progress rows for the current user (used to compute account-view stats client-side — there's no dedicated stats endpoint)
- `POST /api/progress/chapter/complete` - Mark chapter complete
- `GET /api/progress/chapters/<book_id>` - Completed chapter numbers for a book
- `POST /api/progress/sync` - Sync offline progress

**Authentication Required:** every progress endpoint above (`@login_required`, pchauth's Flask adapter) 401s an anonymous request. Plainly uses the trusted Apache identity; Distill additionally accepts browser-bound Kindle sessions as described above. Pairing approval/revocation has its own one-time CSRF protection.

### Security Considerations

**Identity trust boundary:** this app trusts `X-Remote-Email` unconditionally and performs no verification of its own. That's only safe because (a) gunicorn binds `127.0.0.1`, never a public interface, and (b) Apache is the only thing that can reach it — see `deploy/plainly/summra.conf` and the shared vhost documented in the vault's `wordpress-vm-pages-setup.md`. If either of those ever changes, this becomes a header-spoofing vulnerability instantly. A header-spoofing test against a comparable trusted-header endpoint is documented in OpenReader's `docs/WORKLOG.md` (2026-09-06) as part of verifying this design.

**No credential storage:** nothing to hash, salt, rotate, or leak — the `users` table holds only an email and timestamps.

**Allowlist fails closed:** `is_allowed()` denies by default; `load_pchauth_config` refuses to start in a non-`off` mode with an empty allowlist.

---

## Reader platform (shared reader, 2026-10-25; updated 2026-10-26)

The continuous reader, its settings, the reader API, progress and the Kindle mode are one **platform** in `shared/`. An app plugs in with a `ReaderConfig` plus two JS hooks. Plainly and Distill are the two apps. Nothing under `shared/` imports from either, and `shared/static` and `shared/templates` never contain an app's name (`tests/shared/test_layering.py`). Labels and copy that differ come from config.

### Config (`shared/reader/config.py`)

One frozen `ReaderConfig` per app, declared in `<app>/reader_config.py` (`PLAINLY_READER`, `DISTILL_READER`). `__post_init__` validates it (`tests/shared/test_reader_config.py`). `to_client()` is the JSON of `window.READER_CONFIG`, rendered by `shared/templates/shared/reader/_config_script.html`; its shape is pinned by a test.

| Field | What it drives |
|---|---|
| `app_name` | `app_name` in the template context (page titles, wordmark). |
| `cache_db_name` | IndexedDB name for cached segments (`summra-reader-v2`, `distill-reader-v1`). Two apps on one origin must differ, because book ids collide. |
| `cache_visibility` | `public` or `private`: the `Cache-Control` prefix on the manifest and segment responses (blueprint). Distill is `private`. |
| `modes` | Tuple of `ReaderMode`: the modes the app offers. Every id must be in `ALL_MODES`, no duplicates. |
| `default_modes` | Mode ids tried in order when the saved `last_mode` is not configured or not in the book's manifest. Must be configured modes. |
| `features` | `ReaderFeatures`, below. |
| `settings` | `ReaderSettings`, below. Defaults to `DEFAULT_SETTINGS`. |
| `kindle` | `KindleOptions`, required when `features.kindle` is on. |
| `api_base` | Prefix of the reader and progress APIs (`/api`). `platform.js` sets `this.apiBase = withBasePath(api_base)` and `reader_state.js` builds its URLs from it. |
| `extra_page_blocks` | CSS selector list of extra elements pagination treats as page blocks (Distill: `table.reader-table, figure.reader-figure`). |
| `hint_keys` | The one-time hints the app's `UserDatabase(valid_hints=...)` accepts. Distill passes `reader_swipe_mobile`, `reader_nav_desktop`. |
| `inline` | `markdown` (marked when loaded, else regexes; Plainly) or `strict` (escape, then only `**bold**` and `*italic*`; Distill). |
| `image_base` | Prefix put before an `image` block's `src` (Distill: `''`, so `images/x.jpg` resolves against `/books/<slug>/read`). |

- `ReaderMode(id, label, layout='single', members=(), library_label=None, min_width=None, narrow_fallback=())`. `label` is the selector button and help text. `library_label` is the Library card's mode suffix (falls back to `label`). `layout` is `single` or `side_by_side`. `members` are the `ReaderMember(id, label, cell_class)` columns of a side-by-side mode (they must be `original`, `plain`; `cell_class` is what the row splitter selects). `min_width` is the viewport width a wide mode needs, and `narrow_fallback` lists the modes to use below it. The layout `side_by_side` and the id `side_by_side` go together.
- `ReaderFeatures(progress=True, illustrations=False, page_turn_hint=True, kindle=True, automatic_completion=True)`. `automatic_completion=False` disables terminal-page completion in web, Kindle and the server mutation handler; Distill opts out, Plainly retains the default. Explicit Read actions are independent of this flag. `progress=False` leaves `/api/progress/*` and `/api/auth/check` as 404. `illustrations=False` renders no chapter figure. `page_turn_hint=False` shows no hint. `kindle=False` makes a Kindle user agent get the web page and `/api/kindle/progress` 404 (`tests/distill/test_kindle.py`).
- `ReaderSettings(fonts, font_default, size_min, size_max, size_default, themes, theme_default)`: the font, size and theme controls the settings panel renders, and what `settings.js` validates a saved choice against.
- `KindleOptions(text_modes, default_text)`: the Kindle `Text` row and the values `/api/kindle/progress` accepts. Every text mode must be a configured mode, and `default_text` must be one of them.

### Mode registry (`shared/reader/modes.py`)

`ALL_MODES = ('summary', 'original', 'plain', 'side_by_side')` is the one registry. The ids are **storage vocabulary**: the SQL `CHECK` lists on `reader_unit`, `mode_reading_state` and `progress_mutation` spell the same strings, and `ReaderIndexMixin._READER_MODES` and `user_models.VALID_MODES` derive from it. A test pins the `CHECK` strings to the registry, and the stored schema is byte-identical to before. An app picks a subset (Plainly all four, Distill only `summary`). It cannot invent an id without a schema migration.

The mode selector shows only when the book's manifest offers at least two modes that the app also configures. A saved `last_mode` outside that set falls through to `default_modes`, and a mode the manifest offers but config omits is never chosen. For Plainly this hides the selector on 3 of the 90 local books (108, 110 and 114, original text only), a deliberate change (see the PRD). For Distill it is always hidden. Node tests: `tests/js/reader_modes.test.mjs`.

### Plug-in surface

**Python**
- `ReaderConfig`, declared once in `<app>/reader_config.py`.
- `install_reader_platform(app, config, get_content_db, user_db)` (`shared/reader/platform.py`). It stores the config in `app.extensions`, adds `reader_config` and `app_name` to the template context, and registers the reader blueprint (manifest, segment, map, recover; the content DB is looked up per request) with the config's cache visibility. When `user_db` is given it points `shared.progress.routes` and `shared.auth.whoami` at it, and registers their blueprints only if `features.progress`. Those two modules' globals are last-install-wins (production runs one app per process), so Distill's tests isolate them with a fixture.
- A content DB implementing the `ReaderIndexMixin` hooks (`get_connection`, `get_book`, `_reader_load_book`, `_reader_load_chapters`, `_reader_chapter_units`, `_reader_plain_coverage`, `_reader_source_checksum`, `_reader_structure`) and the `shared.progress` library hooks (`library_books`, `chapter_titles`).
- Kindle page handlers, registered with `register_kindle_pages(bp, handlers, config)`, only when `features.kindle` is on.
- Kindle progress. The app's `POST /api/kindle/progress` route is a few lines calling `shared.kindle.progress.save_progress(config, user_db, content_db, user_id, position)`. `position(content_db, book_id, ch, p, text) -> (unit_id, quote) | None` is a hook on the content-DB side: it maps the Kindle's chapter key and unit index to a reader-index unit id and a quote, or returns `None` for an unknown book or chapter. `save_progress` does the feature and `user_db` 404, the 401, the validation (`book_id`, `ch`, `p` ints, `p >= 0`, `text` in `kindle.text_modes`) and `record_page`. So the progress endpoint is a shared function plus a thin route per app, not a route registered from config.
- Kindle reader template: extend `shared/templates/shared/kindle/reader_base.html`. Its header comment lists the context variables: `book`, `chapter`, `text`, `text_urls`, `start`, `chars_before`, `chapter_chars`, `total_chars`, `font_size`, `cookie_path`, `sync_url`, `prev_url`, `next_url`, `next_title`. It also uses `base_path`, `asset_v` and `reader_config` from the platform context, and offers the blocks `flow_body`, `flow_class` and `lang`.

**JS hooks**, methods on the host class passed to `applyReaderPlatform(Host)` (`shared/static/js/platform.js`; it is the only shared file that imports, because the mixin files are loaded alone in tests from a `data:` URL):
- `classifyUnit(text) -> block` turns one stored unit into a render-vocabulary block. Plainly: text heuristics in `plainly/frontend/static/js/app.js`. Distill: `JSON.parse`. The shared `blocksMixin` supplies `continuousReaderBlock` from it.
- `selectBook(book)` is where the reader's back button goes.

**Platform defaults**, applied only if the host lacks them: `showOnlySections()` (no-op) and `initReaderPlatform()` (sets `apiBase` and `pagination = createPaginationState()`).

**What the host page must provide**
- `.hidden { display: none }` and `.main-content` CSS. The shared reader CSS uses `.hidden` to close its panels but never defines it. Plainly gets both from `style.css` and Distill from `distill.css`. Without `.hidden` the settings and contents panels show open.
- `window.APP_BASE_PATH` (the deploy prefix, `''` at the root) and `window.READER_CONFIG`, both set before any reader script.
- Script order: `shared/js/base_path.js` first (a classic script that defines the globals `withBasePath` and `summraBasePath`), then `shared/js/reader_state.js` (`window.readerState`; it also defaults `window.authModule` to `{...readerState, initAuth}`), then the app's module. A host with its own auth UI sets a fuller `window.authModule` after `reader_state.js` (Plainly's `auth.js`). Distill uses the default.
- The reader-shell DOM ids the shared JS looks up. The partials `_continuous_reader.html` and `_settings_panel.html` render them: `continuous-reader-section`, `continuous-reader-content`, `reader-status`, `reader-book-title`, `reader-chapter-title`, `reader-back-button`, `reader-toc-button`, `reader-toc-panel`, `reader-toc-list`, `reader-settings-button`, `reading-settings-panel`, `reader-mode-settings` (with `[data-reader-settings-mode]` buttons), `reader-mode-help`, `continuous-reader-progress`, `reader-progress-fill`, the `[data-reader-close]` buttons, the controls `font-size-slider`, `size-value`, `decrease-size`, `increase-size`, `.font-choice` and `.theme-choice`, and the `.continuous-reader-chrome` and `.continuous-reader-footer` wrappers that pagination measures.
- Optional: `window.summraApp.openLightbox(src, alt)`. Illustration clicks call it through `?.`, so without it a click does nothing.

### Render vocabulary

The block types, one renderer per language: `shared/static/js/blocks.js` (web reader) and `shared/reader/blocks.py` (Kindle pages, `block_element`). `tests/shared/test_block_parity.py` renders every type in both and requires identical markup (the JS↔Python parity rule), so change one and you change the other.

| Block | Fields | Renders as |
|---|---|---|
| `p` (default) | `text` | `<p>` |
| `h` | `text` | `<h3 class="reader-section-heading">` |
| `verse` | `lines` | `<p class="reader-verse">`, lines joined with `<br>` |
| `li` | `text` | `<p class="reader-list-item">` |
| `quote` | `text` | `<blockquote class="reader-quote">` |
| `ul`, `ol` | `items` | `<ul>` or `<ol class="reader-list">` of `<li>` |
| `keypoints` | `items` | `<ul class="reader-keypoints">` (the "Key points" label comes from CSS `::before` in `distill.css`, since it is app copy) |
| `table` | `header`?, `rows` | `<table class="reader-table">` with `thead` and `tbody`; cells are inline text |
| `image` | `src`, `caption`? | `<figure class="reader-figure"><img src="{image_base}{src}" alt="">` plus `figcaption` |

Distill books use `p h ul ol quote keypoints table image` (format v1). `verse` and `li` exist for Plainly's classifier. Inline text is escaped first (spaces become `&nbsp;`) and then formatted per `inline`; `image_base` and `src` are attribute-escaped. A block's content never contains an element the paginator selects as a page block, except a list's own `<li>`. `block_text` (Python) is the text a block shows, used for word counts and quote recovery. The rendered DOM text must equal it, which a test checks for every type including CJK.

Plainly's Kindle pages keep their own `kindle_inline` filter instead of `block_element`, because routing them through the shared renderer would change Plainly's markup. A possible later step is to turn Plainly's chapter illustration into an `image` block.

### Serving and bundling

Shared assets live in `shared/static/` (`css/base.css`, `reader.css`, `kindle.css`; `fonts/`; `js/`). Each app exposes them at `/static/shared/...` through a symlink inside its static folder (`plainly/frontend/static/shared` -> `../../../shared/static`, `distill/static/shared` -> `../../shared/static`; the depth differs because Plainly's static folder is one level deeper). `shared/templates/shared/` is a fallback template root added by `install_shared_ui(app)`; an app's own template at the same path wins.

**Apache follows that symlink only with `Options -Indexes +FollowSymLinks` on the static `<Directory>`.** Keep that option when installing `deploy/plainly/summra.conf` and confirm `/plainly/static/shared/css/base.css` returns 200 (the static Alias serves it, so Apache gzip applies).

Segment URLs carry the manifest's content version (`.../segments/<id>?mode=<m>&v=<content_version>`). The server ignores `v`; it exists so a re-imported book (same book id, bumped `reader_version.version`) misses the 1-year `immutable` HTTP cache. The IndexedDB cache is keyed on `[book_id, content_version, mode, segment_id]`, so it is invalidated by the same version bump.

Plainly's `app.min.js` is built by esbuild from `app.js`, which imports `shared/static/js/platform.js`; `npm run build:check` fails if the bundle is stale. Distill loads `platform.js` as a native module and has no bundle.

### Adding a third app

`distill/app_base.py` is the reference factory; copy its order.

1. Write the content DB: a class with `ReaderIndexMixin` and the library hooks (`library_books`, `chapter_titles`).
2. Declare a `ReaderConfig` in `<app>/reader_config.py` with a unique `cache_db_name`. Choose modes from `ALL_MODES`.
3. In the app factory, in this order:
   1. Install authentication **first, before any blueprint is registered** (`init_pchauth` for Plainly; `install_pairing` for Distill). The Kindle dispatch is a `before_app_request` that skips `@login_required`, so if a Kindle blueprint is registered before pchauth's `before_request`, Flask runs the Kindle hook first and serves Kindle pages to anyone. `test_kindle_pages_and_progress_need_the_allow_list` (Distill) guards this order.
   2. `install_reader_platform(app, config, get_content_db, user_db)`, then the app's blueprints.
   3. For a private app, an `after_request` hook that gives every non-static response without a `Cache-Control` the value `private, no-cache` (as `distill/app_base.py` does).
   4. `install_web_basics(app, '<APP>_STATIC_DIR_OVERRIDE')`: it installs `PrefixMiddleware` (the `X-Forwarded-Prefix` deploy prefix, without which every URL breaks under `/prefix`), gzip, and the `asset_v` template helper that the shared templates call.
   5. `install_shared_ui(app)`.
4. Add the `static/shared` symlink with the right depth for the app: `ln -s "$(realpath --relative-to=<app static dir> shared/static)" <app static dir>/shared` (Plainly's is `../../../shared/static`, Distill's `../../shared/static`).
5. Write the host class with `classifyUnit` and `selectBook` so its units map onto the shared block vocabulary, call `applyReaderPlatform(Host)`, and provide everything under "What the host page must provide" (render the shell with the `_continuous_reader.html` and `_settings_panel.html` partials).
6. If Kindle is on: write the page handlers and register them with `register_kindle_pages` (use `shared.kindle.pages.render_page`, `not_found_page`, `account_user_id` and the page-size constants rather than copying them), add the thin `/api/kindle/progress` route with a `position` hook, and extend `reader_base.html`.
7. Add an e2e script under `tests/e2e/`.

**One app per process.** `shared.progress.routes` (`user_db`, `content_db`) and `shared.auth.whoami` are module globals set by `install_reader_platform`, so a process serves one app. Run each app in its own gunicorn. Tests that build both apps pin these globals per app (`pin_platform_globals` in `tests/distill/conftest.py`).

**Shared origin.** Apps cohosted on one origin share `localStorage`: reading preferences (`reading_font`, `reading_fontSize`, `reading_theme`) and dismissed hints (`summra-hint-*`) are common to Plainly and Distill. That is intended: one reader, one set of display preferences. IndexedDB is namespaced per app by `cache_db_name`, because book ids collide between apps.

### Plainly-only reader code that stays in shared

`pagination.js` and `settings.js` moved to `shared/` whole, including Plainly's legacy chapter-page branches (the paged chapter view that predates the continuous reader). They are dead for Distill. The legacy chapter page also calls `authModule.trackPageChange` and `authModule.onChapterComplete` without a guard. That works only because Plainly's `auth.js` defines them, so it is a Plainly-only path.

### Known gaps (backlog)

- A "Key points:" lead paragraph can be left alone at the bottom of a page, apart from its list (shared pagination).
- The Kindle contents repeat the part heading on a page that starts mid-part.
- The shared partials hold fixed English UI copy (both apps have an English UI).
- Library card markup is still duplicated in `renderLibraryCards` (pre-existing).

---
