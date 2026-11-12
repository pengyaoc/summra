# Summra Work Log

> Entries dated before 2026-10-01 moved to [`docs/archive/WORK_LOG-2025-2026.md`](docs/archive/WORK_LOG-2025-2026.md) on 2026-11-11.

## 2026-11-11: Root file cleanup and work log split

- Status: done.
- Deleted `setup.sh` and `setup.bat`; the README quick start lists the same steps.
- Moved the pytest settings from `pytest.ini` into `[tool.pytest.ini_options]` in `pyproject.toml`. Collection is unchanged (1,388 of 1,390, 2 deselected).
- Moved the 66 entries dated before 2026-10-01 (8,200 lines) to `docs/archive/WORK_LOG-2025-2026.md`, in their original order. This file keeps the 159 entries from 2026-10 on (about 3,470 lines). A line-by-line comparison showed nothing lost.

## 2026-11-11: README restructure for the shared platform + two apps

- Status: done locally, not committed.
- Root `README.md` now presents Summra as a codename: shared platform plus Plainly and Distill, with a diagram, repo map, quick start, tests, deploy and docs index.
- Plainly-specific content moved to new `plainly/README.md` and was corrected: `summra.db` lives in `data/`, `FEATURE_AUTH` is on, there is no Gemini TTS any more (audio is recorded on the Mac), and the old batch audio scripts are gone.
- New `distill/README.md` and `shared/README.md` (package table: what each one does and how an app plugs in).
- Structural cleanup applied (owner approved):
  - `deploy/plainly/` now holds Plainly's `install.sh` (repo root is now `../..`), `summra.service`, `override.example.conf`, `summra.conf`, `service.env.example` and `requirements-prod.txt` (moved from the repo root). `deploy/archive/` holds `DEPLOY.md` and the unused nginx configs. `deploy/README.md` now opens with a map of the folder.
  - `docs/archive/` gets `PROJECT_OVERVIEW.md`, `SYSTEM_ARCHITECTURE.md`, `USAGE.md` and `tests/{TEST,COVERAGE}_SUMMARY.md`. `docs/plainly/` gets the two Plain English workflows, the learnings, the Moby-Dick log and `marketing/`. References updated in CLAUDE.md, AGENTS.md, ERD, `passage_rewrite.py`, e2e and memory.
  - `setup.sh` / `setup.bat` install both apps plus `pip install -e .` and print both ports. `pyproject.toml` description updated.
  - GitHub: repo description and topics updated.
  - Tests: `test_apache_conf.py` and `test_layout_paths.py` follow the moved `summra.conf`; `test_layering_names.py` also scans `docs/plainly/`. Full pytest: 1,388 passed.
  - The VM is unaffected: its Apache fragment and unit are installed copies, and gunicorn still uses `deploy/gunicorn_config.py`.
- Second cleanup round (owner approved items 1–6):
  - `docs/tts/` → `docs/archive/tts/` (describes Coqui/Gemini speech, both gone). `tests/README.md` rewritten as a short map of the suites.
  - `docs/CONTINUOUS_READER_LIBRARY_{PRD,ERD}.md` → `docs/shared/`.
  - Local only, moved to `~/.Trash/summra-cleanup-20261111/`: `backend/`, `scripts/` (both just `__pycache__`), the unused uv `.venv/`, and `data/database.pre-bleak-house-plain-20261018.db` (174 MB). Root `node_modules/` stays (esbuild).
  - `CLAUDE.md` 45 KB → 13 KB. Runbooks moved verbatim to `docs/plainly/ingestion_workflow.md`, `docs/plainly/plain_english_checklist.md`, `deploy/plainly/RUNBOOK.md` and `deploy/distill/RUNBOOK.md`, leaving short pointers with the key rules. References repointed.
  - PRD/ERD split by top-level section into `docs/{shared,plainly,distill}/{PRD,ERD}.md` (PRD 21/20/7 sections, ERD 26/33/8). `docs/PRD.md` and `docs/ERD.md` are now indexes that list every section and its new file. A line-count check against HEAD shows no content lost. `CLAUDE.md` and `AGENTS.md` now say to update the part you changed.
  - `test_layering_names.py` scans `docs/{shared,plainly,distill}/` and no longer reads the archived `docs/tts/`.
  - Tests: full pytest 1,388 passed. `node --test tests/js/*.test.mjs` 63/65: 2 failures in `resolve_view_mode.test.mjs` (`document is not defined`) are pre-existing; no JS changed and they are not in CI.

## 2026-11-08: Distill home page tabs (Option B)

- Status: built and tested locally; not committed or deployed.
- Home is now Reading and Library tabs (`?tab=`), in the header beside the icon on all web sizes; banner and Finished shelf removed. Reading: last-read book as a large card. Library: All / Unread / Finished switch, search, filters visible on desktop and behind a Filters button on phones, applied on change.
- `tests/distill/test_pages.py` assertions on the removed shelf and All books heading were changed because the requested layout changed.
- Checked phone and desktop screenshots with a local test user.

## 2026-11-08: `deploy_code` script

- Added `distill/scripts/deploy_code.py`: one reviewed command for Distill code deploys, replacing hand-built SSH commands. Tests: `tests/distill/test_deploy_code.py`.

## 2026-11-08: Distill Kindle library size, install button, icons

- Status: done locally, not committed or deployed.
- Kindle library text and controls are 2x (scoped to `.library` in `distill_kindle.css`), 4 books per page instead of 7. Pages with 2-line titles or a Reading now section scroll a little; two rows would be the most that always fits one screen.
- Removed the Install app button and its prompt code; the dismissible iOS install guide stays.
- Favicon SVG, ICO and 32 px PNG now have transparent backgrounds. App icons stay opaque, as iOS requires.
- iOS icon: `icon-512.png` is sharp, so the artwork is not the cause. The page now offers the exact 180 px file. Best explanation, unconfirmed on a device; iOS keeps the icon from install time, so it must be removed and re-added.
- Tests: full pytest 1,316 passed; `distill.mjs` passed. `test_kindle.py` page size and `test_app.py` install and icon assertions changed because the requested behaviour changed.
- Design decision: Distill home becomes two tabs, Reading and Library, with All / Unread / Finished inside Library and tabs on top on mobile and desktop web. Not built.

## 2026-11-08: Siri cut-off fix and incremental Distill deploys

- Status: built and tested locally; not committed, VM code not updated. Chinese re-recording in progress, nothing deployed from it.
- Bug: Chinese audio skipped text. Siri stops at about 26 s per sentence (flat from about 140 characters up) and reports success. Evidence: paragraph 1186.5 was 24.5 s whole and 39.4 s in pieces. Not a playback seek: audio position only changes on seeks, chapter changes and resume (from reading the code).
- Fix: `split_for_siri` records pieces of at most 90 characters; a piece of 25.5 s or more fails the chapter. Real paragraphs now 41.2 s, 34.3 s, 51.9 s (were 24.5, 23.2, 32.5). Old Siri audio is marked stale by its voice id and keeps playing until replaced.
- Deploys: `deploy_db` no longer swaps the whole DB or restarts the service. New `distill/scripts/db_patch.py` sends changed rows only and never touches books that exist only on the VM. `tests/distill/test_deploy_db.py` was rewritten for this behaviour because it asserted the file swap.
- Tests: full pytest 1,313 passed, including `test_db_patch.py` (11).

## 2026-11-08: Listen highlight goes away when the player closes

- Status: done locally, not committed or deployed.
- Bug: closing the player left the spoken paragraph highlighted, and paging redrew it.
- Fix (`shared/static/js/listen.js`): the highlight shows only while the bar is open; `showBar` redraws it, so listening again brings it back.
- Tests: `listen_follow.mjs` gained close, paging, late time update and reopen checks (3 failed before the fix). `listen_follow`, `distill_listen`, `distill.mjs` and the 14 Plainly scripts pass. Not tried on a real iPhone.

## 2026-11-07: Distill Listen (audio for summaries)

- Goal: listen to Distill summaries on the iPhone PWA and switch between
  listening and reading at the same spot, with a position that survives an app
  kill. Volume: 64 books (56 en, 8 zh), 1,816 chapters, ~120–140 h of speech.
- Voices picked by the owner from test clips:
  - Chinese: Mandarin Siri Voice 4 (`zh-CN-D`) at rate 1.0, via InkChinese's
    private SiriTTSService exporter. About 5× real time; returns timings for
    each spoken stretch.
  - English: macOS `say` with the system voice. About 2× real time.
- Rejected: on-device `speechSynthesis` (stops on lock, loses its place on
  kill), and a private podcast feed (would lose reading/listening sync).
- Design: `docs/superpowers/specs/2026-11-07-distill-listen-design.md`.
  - Chapter audio is made on the Mac, one reader unit at a time, and stored in
    MediaStore.
  - The timing of each unit (`chapter_id.ordinal`) is known when the units are
    joined.
  - Playback uses one `<audio>` element plus Media Session.
  - Position is saved to localStorage and synced as the summary-mode progress
    marker.
- 2026-11-07 tests:
  - Asking the private Siri route for "Nora" returns the same bytes as a
    made-up name, so it quietly falls back for unknown voices.
  - `say` uses the system voice (Siri Voice 2), which `-v` can't name, and its
    output is byte-for-byte repeatable.
  - So English stays on `say`, guarded by an exact reference-clip check.
- Owner decisions: the VM disk has room; when sign-in expires, playback pauses
  and asks to sign in again.
- Spec approved. Plan: `docs/superpowers/plans/2026-11-07-distill-listen.md`
  (8 tasks). Built on branch `feat/distill-listen`, in a worktree.
- Built:
  - `distill/audio/` (spoken units, engines with voice guard, assembly);
  - the `chapter_audio` table;
  - deploys that upload only the media the VM lacks;
  - the Range audio route and timings API;
  - `make_audio`;
  - `listen.js` (player bar in the reader footer, text following, Media
    Session, local and server position).
- Measured:
  - `say` renders at about 3.7× real time per process; Siri at about 5×.
  - Siri output is not byte-repeatable (3,500 vs 3,520 ms for the reference
    sentence), so its voice check matches duration within ±2%.
- Tests:
  - full pytest: 1,275 passed;
  - `distill_listen.mjs` (WebKit) and `distill.mjs` pass;
  - all 14 Plainly e2e scripts pass (`shared/` changed: the `listen` progress
    cause).
- Rollout: audio for `abundance-klein-thompson`, `the-vital-question` and
  `silent-spring` (the owner's three requested books, already imported
  2026-10-25).

## 2026-11-07: Kindle back/forward scale correction

- Reproduced on the physical PW3: direction reversal could shrink the whole
  fullscreen page to about 5/6 size despite unchanged DOM geometry. Normal
  toolbar mode was stable. Initial frontend geometry/scroll/repaint trials passed
  emulation but failed hardware; matching root dimensions introduced scrollbars.
  All website trials and geometry beacons were reverted. Live kindle.js remains
  the committed SHA256
  89b96413802ddea581ed9026c4e2b2862a848147d1c8afa5f52b10e6e1d8d267.
- Native privileged viewport control resolves the observed failure. Embedded an
  ES5 policy in the existing session.sh; the launcher atomically installs its
  marked app-local sidecar and invokes the stock Mesquite test-script hook.
  Disable native auto/double-tap zoom, fit body width, reset native pan after
  clicks/documents/activation, and hide native reader scrollbars. URL-scoped to
  HTTPS Distill/Plainly book readers, excluding kindle=0; pause/navigation/unload
  restore controls and remove callbacks. No website bridge, stock source patch,
  schema/auth/content/progress changes or sleep prevention.
- Startup waits for token-specific readiness before hiding bars. The first
  packaged attempt correctly retained bars: chmod 600 prevented uid9000 Mesquite
  from reading the root-written sidecar. Corrected to 644 (no secrets), verified
  real readiness/fullscreen startup, and added an installer regression covering
  readability, owned replacement and refusal of symlinks/unmarked files.
- Owner finger testing confirms “Stays full size.” Repeated physical raw-touch
  back/forward cycles and toolbar-toggle/reload checks retain the same title
  rectangle (109,33)-(945,65), without right/bottom shrink. Earlier one-shot
  auto-zoom trials were insufficient; the installed policy reasserts after input
  and document navigation. Physical fixtures/captures remain under /tmp; old
  native test sidecar removed. Website diagnostic code is absent.
- Installed the launcher on the owner's PW3 firmware 5.16.2.1.1; rollback copy:
  /mnt/us/distill-fullscreen/native/session.sh.before-viewport-20261107.
  Existing native corner/swipe controls remain separate from web UI.
- Validation: focused native/shared suite (23 cases), shell syntax and whitespace
  checks; mocked native API lifecycle/URL/click/document tests plus real device
  acceptance. The earlier 460 backend and browser suites did not prove this
  hardware-only fix and are not represented as its physical evidence. ERD, PRD
  and Kindle runbook updated. Source release 049a8fc is committed/pushed and
  fast-forwarded on the VM. Device/local/VM launcher SHA256 matches
  160b9a5377180a462915d953eb0bfe240de0b0896322df0eadf96b8ee9613fd7.
  Live reader JS retains the baseline hash above; distill and summra (Plainly)
  user services are active, without a restart. VM-local files and unrelated
  documentation edits from other sessions are preserved outside this release.

## 2026-11-03: Commit and synchronize Kindle release

- At the user's request, reviewed the11 pending Kindle launcher/UI/test/documentation
  files together. ERD and PRD reflect the final native159px corner, sleep lifecycle,
  2.5× reader chrome and caption-safe pagination; worklog records physical feedback,
  validation and deployment limits. No media, credentials or environment files
  are included.
- Existing validation remains applicable:412 shared/Distill Python cases,66 focused
  shared/Plainly cases,14 Plainly browser scenarios, Distill desktop/mobile/Kindle
  and dedicated Chromium/WebKit illustration runs pass; shell syntax and whitespace
  checks pass. No further code edits since those checks.
- VM preflight: same base commit as local, with only the three deliberately
  predeployed Kindle assets modified. Their SHA256 hashes match this release.
  Preserve VM-local backend/environment files and reconcile only the verified
  asset changes before a fast-forward pull.
- Committed/pushed implementation as `7b78211`; VM fast-forwarded to that exact
  commit after verifying every predeployed asset byte against origin/main. VM
  tracked files are clean; existing untracked backend/environment files preserved.
  Both user services are active; Plainly loopback and authenticated Distill Kindle
  reader return200. Live HTTPS CSS/JS SHA256 hashes match the committed files.
  Static-only runtime deployment needs no service restart.
- Release CI: https://github.com/pengyaoc/summra/actions/runs/41767043107.
  This documentation-only follow-up records the completed deployment; no further
  architecture, product, source-code or data changes.


## 2026-11-03: Enlarge Kindle reader UI 2.5×

- Increased book title/time/percentage 14→35px, navigation and regular control
  text 18→45px, A+22→55px, menu labels/position16→40px and font status20→50px.
  Expanded header/footer allocation36→90px, retaining existing saved prose size.
- Replaced anchored settings banners with flowing/wrapping panels to prevent
  large controls overlapping. Short viewports scroll the menu internally;
  document panning stays blocked and ordinary menus retain drag protection.
- Focused Python checks:66 passed. Initial Kindle browser regression passes;
  inspected 1072×1448 and758×950 menus with no horizontal overflow, plus640×400
  scroll overflow. Added browser regression for scroll/reachable font and Close.
- All14 required Plainly browser scenarios pass. Added short-screen scroll,
  2.5× typography and reachable font/Close checks. Distill's reduced reading area
  exposed figure fragmentation: atomic inline-block figures keep image/caption
  together. Corrected stale Distill card selector and page-turn assertion (rounded
  percentages need not change on every page); added enlarged font-family/status
  checks. Final Distill desktop/mobile/Kindle run passes when run serially;
  dedicated image tests pass in Chromium/WebKit, including font changes and
  native fullscreen transitions. Shared/Distill Python suite:412 passed; initial
  shared/Plainly Kindle and markup suite:66 passed. Concurrent Distill browser
  runs produced expected progress-session409 conflicts; serial rerun is clean.
- Deployed only the three reviewed CSS/JS assets to the existing VM after checking
  original hashes; rollback archive `/tmp/summra-kindle-ui-before-20261103.tgz`.
  Live public Plainly asset hashes and Kindle HTML content-hash references match;
  authenticated Distill styles and Kindle reader return200. Both services active,
  no restart required. Website changes are live; an existing Kindle page must be
  refreshed/reopened. Physical on-device visual acceptance remains pending.
  No native launcher or data/schema/auth changes in this UI update. Assets were
  deployed ahead of Git release synchronization, recorded below.


## 2026-11-03: Native Kindle gesture controls and sleep-aware session

- Implemented browser control entirely in the existing Kindle launcher: top-edge
  swipe reveals native bars, reserved bottom-left corner taps toggle on/off, and
  page-area taps dismiss visible bars without reaching the webpage. Added an
  embedded LuaJIT controller self-test; no website or schema/auth changes.
- Initial passive-grab trial encountered a native input-grab conflict and retained
  normal bars. Replaced it with X11 input-only windows; corrected title handling
  to use the browser's `_NET_WM_NAME` UTF-8 property. On-device XTest checks passed
  corner on/off, top-edge reveal and outside dismissal against the real browser.
- Sleep now suspends gesture zones and wake restores fullscreen; normal sleep
  stays enabled. Removed default four-hour expiration, kept optional timeout,
  title ownership/manual restoration, and actual Lua-child cleanup on failure.
- Validation: all launcher shell syntax checks and embedded on-device controller
  tests pass; 20 focused pytest cases pass, including mocked Home exit, sleep/wake
  and helper-failure cleanup. Installed-device XTest passes all four interactions;
  killing the actual Lua child restores bars and removes session state. Powerd
  entered screenSaver with gesture zones suspended, then returned active with
  the same helper PID and fullscreen restored. The advertised wakeUp write was
  rejected by firmware; wake was observed rather than attributed to that write.
- User reported intermittent physical swipe/corner behavior in the initial trial.
  Added periodic stacking directly above the browser (below native UI), enlarged
  the corner target to 101 × 101 pixels, and added native gesture-coordinate logs.
  Reinstalled and reran controller/XTest checks successfully. The user then confirmed
  both physical top-edge swipes and bottom-left toggles work consistently.
- Installed on the reachable PW3, with original launcher preserved as
  `/mnt/us/distill-fullscreen/native/session.sh.before-gestures`. Current session
  is active without a timeout. Initial physical acceptance was subsequently
  corrected: corner reveal still missed some taps; the later expansion is recorded
  below. Native menu/keyboard stacking and physical power-button/cover operation
  remain unverified separately from power-service tests. Launcher files are
  installed on the Kindle; Git release synchronization is recorded below.

## 2026-10-28: Distill file-media migration verified in production and authoring DB

- Deployed `ca07abe`; GitHub CI passed: https://github.com/pengyaoc/summra/actions/runs/40647364065. All1,225 local regression cases passed,2 opt-in cases deselected. Rehearsal migrated a production copy and checked all886 original/162 thumbnail authenticated HTTP bodies against their original SHA256 hashes, anonymous rejection and unchanged non-image records.
- Supervised live migration stopped only Distill, kept a consistent rollback copy and the current verified app archive, extracted/verified files, rebuilt metadata tables atomically and compacted SQLite. A one-off systemd job provided a300s ceiling and service-start cleanup independent of SSH; normal exception handling restores old content/code. The job completed normally and Plainly stayed active. Temporary rehearsal media/DBs, rollback copy and runner were removed only after verification.
- Live content DB159,563,776→9,986,048 bytes;886 original and162 thumbnail metadata records retained,1,043 unique private files/146,541,246 bytes in `/opt/summra/data/distill-media/`. Every file hash matched; books/chapters/reader records, IDs/sequences, cover tokens and account/pairing files remained unchanged.11 live authenticated image/variant byte checks and anonymous401 checks passed; Distill/Plainly services and Plainly public library healthy. Existing URL/cache/auth behavior preserved, data directory ignored by Git.
- Refreshed the single Distill metadata backup only after live validation:147,581,980→3,520,797 bytes at `data/backups/distill-latest.tar.gz` (content/accounts/pairing plus manifest). Plainly's single archive remains54,065,818 bytes. Static/private media is separate from these DB archives and must be copied for complete recovery.
- Migrated the Mac authoring DB too after checking no local port5003 server was running:159,551,488→9,986,048 bytes; all1,043 file hashes/non-image records verified, one local current metadata archive3,422,405 bytes. Future imports/deploys use file storage. No user content or image quality was discarded.


## 2026-10-27: File-backed private Distill images

- Replaced original-image and cover-thumbnail BLOB storage with hash-keyed private files under `data/distill-media/<sha-prefix>/<sha256>` (or `DISTILL_MEDIA_DIR`); SQLite keeps MIME, IDs, names, cover tokens/source checksums and `storage_key` references. Existing authenticated image URLs, response bodies, ETags/cache rules and chapter/reader coordinates remain unchanged. New imports/backfills write verified, durable, atomic files before metadata commits; identical bytes deduplicate and old files are retained for rollback snapshots.
- Legacy migration writes/verifies all files before rebuilding both image tables in one transaction, preserving IDs, AUTOINCREMENT sequence, thumbnail tokens and foreign keys. File failures roll back the original BLOB schema/data. `distill.scripts.migrate_media --compact` explicitly verifies and VACUUMs with writers stopped; no automatic compaction on normal startup. Production inventory before migration:886 originals/145,079,672 bytes,162 thumbnails/3,578,072 bytes.
- Content deploy now takes an online SQLite snapshot, packages/verifies referenced files separately, verifies transfer hashes and installs media before activating metadata. Missing/corrupt local media or failed remote media install aborts before stopping the service. Account/progress/pairing DBs are backed up but never replaced. Deployment refreshes the one verified `backups/distill-latest.tar.gz` archive instead of accumulating raw full-DB snapshots. Generated media remains ignored through existing `data/` rules and must be backed up separately from metadata.
- Focused migration/store/transfer/deploy/push tests:36 passed. Full regression: 1,225 passed, 2 opt-in cases deselected. Production-copy rehearsal passed all 886 original and 162 thumbnail authenticated HTTP byte hashes and verified anonymous rejection, unchanged non-image tables/IDs and valid foreign keys. Deduplicated 1,043 files/146,541,246 bytes; compacted DB 159,563,776→9,986,048 bytes. Live migration completed2026-10-28; verified results above. Existing Plainly files and its service are unaffected.


## 2026-10-27: Remove generated media from published Git history

- At the user's explicit request, rewrote the sole published branch (`main`; no tags or open PRs) using git-filter-repo. Removed generated audio, book covers, chapter illustrations and guide images under both historical `frontend/static/` and current `plainly/frontend/static/` roots, plus generated redesign/e2e screenshot directories. App branding/icons and Kindle launcher covers remain versioned.
- Removed 634 currently tracked generated files. Before documentation edits, all 516 remaining current files matched their original Git modes/blob IDs exactly. Verified no targeted paths remain in any rewritten reachable commit. Fresh mirror packed history shrank from 624.71MiB to 11.50MiB. GitHub may update its storage statistics asynchronously; commit IDs change throughout rewritten history.
- Added matching ignore rules. Generated content is deployment data, transferred separately from source. The code and media URLs are unchanged. A fresh clone needs separately supplied content DBs and generated media; deployment must not delete ignored media. Current VM media is preserved in place, with 634 files/509,981,225 bytes hash-verified in a temporary independent snapshot before transition.
- Full regression: 1,211 cases passed; one layout assertion required a generated covers directory to exist in a fresh clone. Updated that characterization to require its versioned static parent while retaining the exact configured media path; targeted layout checks pass (3 cases), yielding 1,212 passing cases across the suite and rerun, 2 opt-in cases deselected. Published rewritten main as `9cca549` using an exact old-SHA lease. GitHub CI passed: https://github.com/pengyaoc/summra/actions/runs/40632374603. VM and all three Mac task checkouts migrated without deleting media; all 634 VM hashes and 729/634/634 local media hashes remained unchanged. Also rewrote media out of the VM-only branch/stash and Mac stash/tree checkpoints, preserving every non-media ref tree and stash parent; saved stash descriptions remain available. Expired obsolete reflogs and garbage-collected: VM packed Git 11.24MiB, Mac 11.29MiB. Live Plainly audio/cover/illustration/guide URLs pass HTTP 206 byte checks; authenticated Distill library/book/cover return 200; both services active. Temporary VM safety snapshot and isolated Git mirror removed only after final hash verification. No application schema/auth/reader behavior changes. Existing archives in `data/backups/` continue to hold one verified content/accounts/pairing backup set per app; those database archives do not include static media.


## 2026-10-27: Version Kindle launchers, share pairing with Plainly, audit VM disk

- Added `deploy/kindle/` as authoritative source for the installed Distill/Plainly fullscreen launchers, shared restore/runtime, embedded covers and PNG/SVG source assets. README covers prerequisites, USB installation, startup handoff, recovery, known limitations and QR login. Copied current working device sources without modifying runtime behavior. Private SSH material, logs and retired browser images excluded.
- Moved Distill's pairing store/routes to `shared/auth/device_pairing.py` and its screen to `shared/templates/shared/kindle/pairing.html`. Both apps use the same auth boundary with explicit app configuration. Distill's cookie/DB names and records remain unchanged; Plainly has isolated `plainly_*` cookies and `plainly_pairing.db`. No content/progress schema change. Google header identity and allowlist still govern approval and revocation.
- Plainly keeps public reading; Kindle Sign in and `/login` enter QR pairing. Non-Kindle sign-in keeps Apache Google authentication. Removed Plainly's Location-level proxy remapping so `/login` reaches Flask, and protected phone-only approval/device-management with explicit OIDC. Added QR runtime dependency for Plainly/production.
- Validation: 75 focused pairing/auth/Kindle tests pass, including real Plainly phone approval, CSRF/origin rejection, single-use approval, QR, cookie flags, prefixes, app isolation, desktop rejection and revocation. Full regression: 1,204 passed in the sandbox; all 8 network-dependent failures passed when rerun with network access (5 Gutenberg TOC + 3 cover URLs), for 1,212 passing cases total; 2 opt-in cases deselected. All copied shell scripts pass `sh -n`; installer leaves device state untouched. Existing device launchers/covers were physically verified before copying; no fresh device installation needed for unchanged scripts.
- Read-only VM audit: root 37% used (11/30 GB, 18 GB free), `/opt/summra` 3.6 GB. 26 top-level backup files total 2,146,037,760 bytes; live content databases 174 MB Plainly/160 MB Distill; Git 676 MB; static audio 332 MB. Plainly chapters are 138 MB and Distill image blobs 146 MB. Only 4/1 free SQLite pages: VACUUM will not meaningfully shrink them. Detailed audit and retention recommendations in `deploy/README.md`. No backups, media, data or history deleted.
- Implementation committed/pushed to main as `eb89c5f` and deployed to `/opt/summra`. Apache configtest passes; summra/distill user services active. Live HTTPS checks pass for both apps: QR HTML/PNG, Secure app-scoped cookie, Kindle `/login`→`/pair`, Google challenges for normal login and phone-only approval/devices, Plainly public library and Distill private redirect. Final pairing/auth/reader-markup regression: 77 passed. No secrets or unrelated changes included. Physical phone approval on the user’s Kindle was not repeated; the complete approval/redeem/revoke flows passed HTTP integration tests. GitHub CI passed: https://github.com/pengyaoc/summra/actions/runs/40626680775.


## 2026-10-27: Native fullscreen installed and physically verified

- Installed Kindle library entries **Distill Fullscreen** (existing documents/distill.sh, prior disabled version preserved) and **Restore Distill Toolbar**. Normal appmgr launch opens the authenticated library, then changes only the existing browser window's PC:TS title to PC:N. It hides status/URL bars and expands1072×1232 at y216 to1072×1448 at y0. No browser/root-filesystem edits, alternate browser, remount, disabled sleep or autostart.
- Device scripts/logs: `/mnt/us/distill-fullscreen/native/`; Mac source backup: `/Users/pengyao/.local/share/distill-kindle/native-fullscreen/`. Exact original window title is recorded and checked before restoration. Independent power/sleep-event listener or four-hour ceiling restores bars; leaving the browser and an explicit restore shortcut also restore them. Manual restoration and shortened installed timeout were physically verified and remove session state; actual physical power press was not exercised in this run. Initial restore title validation bug fixed and verified. Normal sleep remains0.
- Final reader implementation1ecb275 uses measured outerHeight1232↔1448 (innerHeight/clientHeight remain1268). Fullscreen adds216px to the measured native body/shell. A native-only1Hz check reflows only on outer-height changes. On fullscreen exit, replace the fragment with the current paragraph and reload to clear the native pan offset; verified same chapter/paragraph and normal bounded layout afterward.
- Physical clean-release tests: fullscreen reading and open font banners pass real up/down/left/right drags; after the final installed timeout, normal mode reloads and all four drags pass. Actual Home shortcut opens signed-in Distill, and normal library link opens the book. Size8/Hei retained, menu closed; final screenshot/window geometry confirm fullscreen reader ready. Chromium/WebKit native selection, fixed-inner-height enter/exit/reload, viewport and gesture checks pass. Public asset hashes match production; no data/auth/schema change. Temporary geometry probes removed. Failed direct LIPC go path is excluded; its generated crash report is preserved under existing device diagnostics, outside the library.

## 2026-10-27: Clear native pan on fullscreen exit

Fullscreen/full-height menu drags and installed timeout restoration physically pass. Returning native chrome retains a pan offset outside DOM scroll coordinates even after remeasurement. On the matched PW3's fullscreen→normal outer-height transition, replace the current fragment with the current paragraph and reload the reader to reset native pan. Fullscreen entry still repaginates locally. The current URL/history entry, font, login and paragraph are retained; exiting fullscreen now requires a page reload. No schema/auth changes. Physical exit verification pending.

## 2026-10-27: Detect measured fullscreen outer height

Physical geometry proves that fullscreen changes outerHeight1232→1448 while innerHeight/clientHeight stay1268. Use the matched PW3's outerHeight equal to screen.height to add216px to the native body/shell. A once-per-second native-only check repaginates only when outerHeight changes, covering builds that omit DOM resize. Regression emulates the real fixed-inner-height behavior. Restore shortcut now validates the exact standard browser title as well as titles with extra fields; manual restoration returns1232px and removes session state. Normal Home scriptlet launch successfully opens the authenticated fullscreen library. Direct browser LIPC `go` caused a Mesquite crash and is excluded; recovery dismissed its dialog and reopened via normal launch. Temporary geometry diagnostic will be removed during clean deployment. No native browser/root-filesystem edits or auth/data changes.

## 2026-10-27: Use native fullscreen browser space

A reversible X11 window-title request (`PC:N` versus normal `PC:TS`) hides the PW3's native status/URL bars without replacing the authenticated browser or editing its files. Physical screenshot confirms1072×1448 at y0 instead of1072×1232 at y216. The native reader now adds any reported viewport-height increase above1268px to its measured1260px body/1279px scroll shell; reversing fullscreen restores normal height. Only the existing matched legacy PW3 profile uses this correction. Added enter/exit height regression coverage. No data/auth/progress schema changes. Launcher and full-height physical verification pending.

## 2026-10-27: Final physical Kindle verification complete

- Deployed reader implementation62e3f39 passes real evdev up/down/left/right drags after fresh load, repeat refresh, open font banners with size8→9, size9→8 with Song→Hei, and closed banners. Each phase's reading-region framebuffer is pixel-identical before/after every drag. Restored size8/10+Hei, menu closed, original chapter/page and normal sleep behavior (`preventScreenSaver=0`). All synthetic touch contacts were released. Removed unused native diagnostic file; no website geometry beacons remain.
- Final architecture supersedes earlier trial implementations below: only the matched no-touch legacy WebKit1072×1448 portrait PW3 gets a wrapper after normal pagination, explicit104%/1260px body styles and1279px native scroll shell, followed by200ms repagination. Select the profile once; font/resize layout cannot remove it. Other devices retain the original unwrapped layout. Native fit slightly scales the view. Preserve explicit #end/#fwd/paragraph startup.
- Chromium/WebKit profile and auto-fit retention checks, viewport/72px/font/tap/resize checks, and load/menu/adjust/close gesture regressions all pass. Earlier38 focused backend cases passed; final changes are JS/CSS only. Public served asset hashes match the deployed release. No database, auth, Apache or native browser-file change. Unrelated local iOS icon edits remain outside this release.

## 2026-10-27: Match measured native surface initialization

Use the physically successful trial sequence directly: finish normal pagination, wrap only the matched PW3 reader nodes, explicitly set native shell/body styles, then repaginate after 200ms. The profile is selected once, so font relayout cannot remove it. Other browsers retain their original unwrapped layout. Earlier class-based/extra-reflow attempts did not pass fresh-load drags and are superseded. No content/auth/storage changes. Final physical verification pending.

## 2026-10-27: Reconcile native scroll range after load

Startup geometry confirms the PW3 profile is selected, but its native scroll range settles later than synchronous DOM layout. Remeasure only this profile one second after window load. Preserve explicit end-of-chapter startup across wrapping/remeasurement. Temporary startup metrics excluded from release. Physical reload verification pending.

## 2026-10-27: Initialize native scroll surface after pagination

Font adjustment/closed-menu drags passed, but a fresh native load retained its initial root pan range. Defer wrapping existing reader nodes until after the first pagination/reflow, then remeasure at the current paragraph, matching the successful physical trial initialization order. No content/auth/storage changes. Fresh-load verification pending.

## 2026-10-27: Preserve native profile after font relayout

The physical PW3 passed settled-load/menu drags but changing size exposed an unstable exact document-width check: native auto-fit can change CSS document width. Keep the legacy no-touch 1072×1448 device match, using portrait document proportions instead of exact width during relayout. This retains the workaround across font changes. No data or authentication changes. Final on-device adjustment/close verification pending.

## 2026-10-27: Native PW3 blank-pan workaround (physical verification)

- Actual-device tests showed that24376cd's DOM touch prevention did not stop native panning. The real page reports1072×1268, while only1072×1231 is visible below the toolbar, and exposes no DOM touch events. Root DOM offsets remain zero while the native view pans. Related first-party empirical research on the same model/firmware: https://thorgalle.me/notes/documentation-for-the-kindle-browser and its linked scrollbar tests. Used the behavior as a reference, without copying application code.
- Added a dynamic reader-shell containing the existing header/page/footer/menu. Only the legacy, no-touch PW3 portrait profile (old WebKit,1072×1448 screen,1072px document width) uses a104% relative body of1260px with a1279px nested scroll container; the scrollbar gutter is clipped. Other browsers retain the normal fitted shell. No-JavaScript pages are untouched. The selected font/size is retained; native auto-fit slightly scales the view.
- On-device temporary variant: real up/down/left/right drags after fresh load and with font banners open all leave the reading region pixel-identical. Size/font adjustments and closed-banner verification remain pending because the Kindle slept again during that step; the first size increase completed and the original size8/Hei must be restored. Modern Chromium/WebKit viewport/large-font/menu/touch regression checks pass on the clean implementation. Added native-profile selection coverage to the existing e2e script. No content, progress schema or authentication changes.
- Temporary diagnostic sent only geometry/offsets, no book text, URLs or cookies, through favicon requests; it will be removed before clean deployment. A built-in legacy Mesquite test entry did not work with the active browser and returned Home; reopened the stock browser normally and resumed the saved page. No browser files changed. Test sleep prevention had a ten-minute automatic restore to its original0 setting; final device cleanup must restore0 again after remaining tests.

## 2026-10-27: Prevent blank-space dragging before/after font banners

- User clarified that the text fits but a touch drag can reveal blank space, including after toggling the font banners. The prior CSS fit fix was insufficient on the physical browser. Added capture-phase, non-passive touchmove/wheel cancellation across the paginated body (including gutters and banners), plus a guarded reset of stale window/document scroll offsets. Ordinary taps remain available. Modern touch-action/overscroll hints supplement legacy event prevention. Font banners are absolute children of a clipped overlay instead of viewport-fixed descendants; opening/closing clears retained offsets, and tapping the backdrop closes the menu.
- Added touch-drag assertions to the existing Kindle e2e test on initial load, in gutters, with banners open, after A+, and after closing. Previous release fails initial touch-cancellation regression. Chromium/WebKit tests pass those phases, size/Hei changes, repeated toggles, wheel cancellation, simulated legacy blank scroll range and retained-offset correction; Chromium also runs CDP touch drags. Tap navigation still works. All38 focused Distill/shared Kindle backend tests pass. On-device interaction verification and deployment pending at this checkpoint. No database, authentication or saved-preference changes.

## 2026-10-27: Fit Kindle reading pages to the browser viewport

- User reported horizontal and vertical scrollbars after the typography update. Read-only framebuffer capture confirmed chapter content extending below the actual stock-browser reading area. Replaced window-dimension-based pagination with a fixed CSS reading shell, anchored header/footer and an inset clipped page rectangle measured via clientWidth/clientHeight. Tap zones use the same fitted body dimensions; layout clears retained document scroll offsets. Kindle-only scrollbar styling suppresses legacy scrollbar painting. No font-size reduction, authentication, data or progress-format changes; no-JavaScript scrolling remains available.
- Added a viewport regression to the existing Kindle browser test. Against the prior files, a synthetic legacy window.innerWidth=9000/innerHeight=4000 produced a3928px reading rectangle and footer at4000px in a1224px window. Corrected Chromium/WebKit checks pass with those metrics, at72px/Hei, through resizing/orientation changes and wheel/tap input. Distill/shared backend tests pass; Plainly Kindle tests run separately because combined collection can shadow the app package with tests/plainly after module purging. Physical refresh verification pending deployment.

## 2026-10-27: Larger Kindle text and Chinese font choices

- User reported the existing maximum remained too small. Confirmed a shared client/server five-level cap, topping out at 30px. Distill now opts into ten levels (16/18/21/25/30/36/42/50/60/72px), defaulting to36px for unset/invalid preferences. Existing valid size cookies retain their meaning. Plainly keeps its original five-level range/default.
- Added Distill-only 默认 / 宋体 / 黑体 reader controls. Song uses installed STSong-family glyph fallbacks; Hei requests STHeiti-family fallbacks. Latin retains the standard Kindle faces. Preferences use validated app-scoped year-long cookies. ES5 handlers repaginate at the current paragraph, handle two-digit size classes, show the current level/maximum and mark limits inactive. No font downloads or Kindle system modifications.
- Read-only SSH inspection on the actual PW3 confirmed STSong and STHeiti (also traditional Chinese variants) in fontconfig. User previously confirmed the deployed phone-assisted stock-browser reading flow works. Backend validation: 387 Distill/shared tests passed. Chromium and WebKit synthetic Chinese-page checks pass for36→72px, limit enforcement, decreasing from level10, font changes, reload persistence, no document overflow and page turns. Screenshots visually inspected. The user subsequently confirmed larger text works and 黑体 looks good on the physical Kindle. Typography release497f761 is deployed; both services are active and live served assets match the tested files.

## 2026-10-27: Kindle-only phone-assisted Google sign-in

- Implemented in an isolated worktree from production 87a6afb, preserving unrelated uncommitted iOS icon changes in the primary checkout. User authorized implementation, deployment and a stock-Kindle trial; latest scope limits automatic pairing to Kindle devices.
- Added a JavaScript-free QR/code page, explicit Google-authenticated phone approval, browser-bound one-time redemption, independent 30-day Distill sessions and phone-based revocation. Added separate hashed-secret SQLite storage, short expiry, global request cap, CSRF protection and security headers. Apache routes only e-reader Kindle UAs through app device authentication; phones/desktops retain Google login and phone approval always forces real OIDC. No existing content/progress schema changes or Plainly changes.
- Final full Distill/shared backend run: 386 passed, including 17 new pairing cases covering prefixes, CSRF, concurrent one-time redemption, expired secrets/sessions, revocation, forged cookies, approval permissions and excluded UAs. Allowlist-removal and API fail-closed regressions also pass. QR dependency installed locally. Deployed and pushed a22a42b to main. Production user DB backed up online to `/opt/summra/data/backups/kindle-pairing-20261027T152650Z/distill_user.db`, with the previous Apache fragment alongside it. Apache configtest passed; graceful reload and Distill-only restart completed; Distill and Plainly remain active. Public HTTP checks confirm Kindle→pair (302), pairing HTML/QR 200/no-store, phone/Fire→Google, forced phone Kindle mode→Google, approval on either UA→Google, and forged client identity headers cannot bypass auth. Backend anonymous/unlisted/owner responses remain 401/403/200; pairing DB is mode0600. Physical trial requested; Kindle SSH timed out, so user is opening the stock browser manually. Initial pip run from the SSH private home failed before source/config changes; retry from `/opt/summra` succeeded.

## 2026-10-27: Consistent book actions and reader continuity release

- User authorized fixing the three book actions, then committing, pushing and deploying both this styling update and the reader backward-section fix below.
- Grouped Distill's primary reading, restart and read-status controls into a wrapping row. All share font family, .9rem/600 typography, line-height, padding and at least 44px height; both secondary actions have matching styling. Primary remains filled. Destinations, status handling and live announcements are unchanged. Updated ERD/PRD; no architecture, schema or product-flow changes.
- Browser checks pass in Chromium and WebKit at widths 1280, 390 and 375: identical computed typography/padding, 44px targets and no horizontal overflow. Finished labels/restart link were added to the local page DOM for these visual checks, without modifying saved progress. All 251 Distill/shared-reader backend tests pass. The earlier five navigation regressions and real-book desktop/mobile browser checks pass; two unrelated JavaScript suite failures are recorded below. Build freshness passes.
- Production preflight: both services active at 5e028f3; no tracked production edits. Existing untracked backend and environment files will be preserved. No database copy or migration. Committed and pushed e6cb60f to main; production fast-forwarded to that revision and both services restarted, both active. Owner library/book/reader responses are 200/private; anonymous/stranger responses remain 401/403. Served shared reader/pagination modules on both apps, Plainly bundle and Distill stylesheet exactly match local SHA-256 hashes. Post-restart public checks: Distill redirects to sign-in (302), Plainly returns 200. No database copy or migration. Unrelated iOS icon changes remain outside this release.

## 2026-10-27: Reader backward section skips (deployed)

- Investigated the reported 细胞传 chapter 21 → 14 jump: backward section navigation rendered the previous multi-chapter section at page zero. It now opens that section's last page. Forward navigation and button availability use the last rendered section, preventing repetition of the second section prefetched on open. Rendered section IDs stay aligned after a boundary turn.
- Section loads lock repeated input and discard responses after reader exit, replacement or mode change. No source text, index, marker format, database schema or API changes. Rebuilt Plainly's production bundle because both apps share the fix. Preserved existing unrelated Distill template/test and documentation edits.
- Five new regression tests failed before the implementation and pass afterward. Real cell-song Chromium/WebKit checks pass at 1280×900 and 390×844: backward lands on page 20/20 or 40/40 at unit 83, forward returns to unit 84, and forward after the prefetched window reaches unit 120. These are browser engine checks, not a physical iPhone test.
- JavaScript suite: 63/65 pass; existing failures are the side-by-side selector spy expecting one call instead of two and the mode-switch test lacking a document stub. All 45 focused shared reader backend tests pass (using importlib collection with app packages preloaded and the tests helper path). Build freshness and scoped whitespace checks pass. Local preview on port 5019. Deployed with the book-action styling in e6cb60f; see the release entry above.

## 2026-10-26: Distill lists and tables flow across reader pages (deployed)

- Replaced Distill web-reader list/keypoint containers with numbered or bulleted paragraphs, and tables with stacked cells labeled by their column headers. Long items/cells split through the shared paginator without nested scrolling. Added an opt-in shared flow renderer; Plainly retains its existing rendering, and Kindle keeps semantic tables/lists. Source blocks, unit IDs and content databases are unchanged.
- All expanded paragraphs retain their source anchors. Saved offsets normalize against displayed flow (including repeated table labels), preserving continuation-page restoration. Inline emphasis, numbering, Chinese keypoint labels, empty/header-only tables and uneven table rows are covered.
- Full-suite check: 1,122 passed, two deselected, nine failures outside this change: eight Gutenberg network-dependent tests fail in the restricted-network sandbox, and one concurrently edited source-chapter test expects the wrong segment payload shape. These files were left to their separate work.
- Distill desktop/mobile/Kindle e2e passes. A synthetic long list/table/keypoint fixture spans nine pages with exact text, no clipping, no nested scrolling and correct saved-page restoration. Plainly side-by-side/verse regression passes, including real Tess pages. Build freshness and scoped whitespace checks pass. Local preview: http://localhost:5018; screenshot: /private/tmp/distill-flat-table-preview.jpg. User authorized commit/push/deploy; committed and pushed feb3b4c to main, fast-forwarded production and restarted both apps (shared Python configuration changed). Both services are active. Live owner book/reader responses are 200/private with flat flow enabled; anonymous/stranger responses remain 401/403. Shared JS/CSS served by both apps and the Plainly bundle match tested commit hashes. Public Distill redirects to sign-in (302), Plainly returns 200. No database copy or migration.

## 2026-10-26: Distill iPhone search focus zoom (deployed)

- User reported iPhone Chrome zooming on focus of the home search field, then allowing sideways panning. Search input was .9rem (14.4px), below iOS's auto-focus-zoom threshold. Set search input and language/category selectors to max(16px, 1rem), retaining accessibility scaling and unrestricted pinch zoom. Viewport meta unchanged.
- Verified iPhone-emulated WebKit and Chromium at 375px, 390px and 844px: all three controls compute to 16px, focusing/typing preserves viewport scale 1, typeahead appears, and document width equals viewport width (no horizontal overflow). This is browser-engine emulation, not physical iOS Chrome. CSS-only change; no build required. User explicitly authorized committing/pushing both fixes to main and deploying them. Committed/pushed 9ba7b2d; deployed to production and both app services restarted successfully.

## 2026-10-26: Shared reader exit releases iOS scroll locks (deployed)

- Distill's reader back button deactivated the reader but bypassed Plainly's app-only scroll cleanup before its full-document navigation. Added shared `leaveContinuousReader`: start the progress save while active, deactivate synchronously, cancel pending wheel/save/completion timers, clear pagination and html/body overflow/classes, and close panels before waiting for persistence/navigation. Plainly now uses the same exit on book selection and other route changes.
- Shared pagehide cleanup releases locks before WebKit's history snapshot; persisted pageshow restores only a reader document and repaginates at its saved marker. Segment/font loads finishing after exit or replacement cannot render into the destination page. Reader back navigation completes even if saving rejects. Rebuilt Plainly's production bundle.
- New tests failed first (missing shared exit; delayed load still rendered). All eight shared JS tests now pass. Full suite: 1,067 passed, one skipped, two deselected, using the existing importlib/preloaded-package workaround. Chromium and WebKit/iPhone reader-back suites pass: Plainly browser back, edge swipe and delayed section load; Distill toolbar back, browser Back, forward-to-reader and another Back. Book scroll position reaches 350px, with visible html/body overflow and reader classes removed. WebKit is engine emulation, not a physical iOS Chrome test. Build freshness and diff checks pass.
- Shared reader/pagination modules and Plainly bundle are ready for deployment; no database changes. Regression commands documented in tests/e2e/README.md. User subsequently authorized commit/push to main and deployment of both fixes. Deployed 9ba7b2d; Distill and Plainly are active. Live owner/private responses for Distill library, book and reader are 200; anonymous backend is 401 and stranger 403. SHA-256 hashes of shared reader/pagination modules on both apps, Plainly bundle and Distill CSS match tested files. Live CSS contains the two 16px-minimum controls rules and the viewport still permits user zoom. Public Distill is 302 to sign-in; Plainly is 200. No database copy or migration.

## 2026-10-26: Shared Chinese paragraph pagination (deployed)

- User reported large blank tails on Distill's Chinese reader pages and requested the same paragraph splitting as Plainly. Confirmed both apps already use `shared/static/js/pagination.js`; its whitespace-only text units made Chinese paragraphs effectively indivisible. Added Unicode Han-character boundaries to that shared splitter while retaining English word and verse line boundaries.
- Shared DOM slicing now retains inline ancestor markup when a cut falls entirely inside an emphasis element. Added a shared fragment-size calculation for Chinese marker offsets, so saving/restoring continuation pages uses character fractions rather than the paragraph's whitespace word count. English offsets keep the existing word-based convention. Reader IDs, database content and marker schema unchanged.
- Regression tests failed before the fix (Chinese boundaries absent; continuation offset .99 instead of .2), then passed. Full suite: 1,064 passed, one skipped, two deselected. Used importlib collection with app packages preloaded to avoid this checkout's existing tests/app package name collision. Distill desktop/mobile/Kindle e2e passes, including no clipping, exact text, emphasis, filled pages and continuation marker round trips. Plainly's side-by-side/verse splitting harness passes, including real Tess pages. Rebuilt app.min.js for production. Updated the Distill cover check to permit the now-complete cover-art collection.
- Mobile inspection of cell-song chapter 544 shows paragraph continuation filling the page. Committed/pushed 82d8648 and fast-forwarded production to it; restarted Distill and Plainly, both active. Owner Chinese reader returns 200/private, unauthorized backend access remains 401/403; public Distill redirects to sign-in (302), Plainly returns 200. SHA-256 of both shared JS modules served by both apps and Plainly app.min.js match the tested files. No database copy or content/index migration.

## 2026-10-26: Distill search and drop logo deployment (complete)

- Owner authorized commit, push and deployment. Current branch matches origin/main at 2ea7a86. Production checkout is at f2e82f6 with no tracked edits; existing untracked backend/config files will be preserved.
- Full suite passed: 1,106 tests, two deselected. All 160 Distill tests pass. Browser checks for typeahead and combined filters completed before this deploy.
- Committed and pushed 38c6397 to origin/main; production fast-forwarded to that revision and Distill restarted successfully. Verified rollback snapshot: `/opt/summra/data/distill.db.bak-pre-search-38c6397`. Additive categories column migrated on startup; SQLite quick_check passes. User-progress DB was not copied or modified by the deployment.
- Production checks: anonymous backend 401, stranger 403, owner 200 with private caching; public `/distill/` redirects to Google sign-in (302), and `/plainly/` remains 200. Owner responses contain the fixed drop, typeahead metadata for 54 books, correct `/distill` form/navigation paths and the new CSS. Chinese filter returns six books; Chinese + Science & technology + Chinese query returns one; empty search and book detail verified.
- Exact pre/post SHA-256 fingerprints match for existing book fields (54 books), all chapters (1,564), image BLOBs (886), and reader units (11,374). No chapter content, cover art, reader units, shared code, or Plainly service changes. Signed-in browser checks were completed locally; production verified through trusted loopback owner requests because the browser had no active sign-in session.

## 2026-10-26: Distill drop logo selected; typeahead (local preview)

- Fixed the header to the selected drop mark and removed the logo picker, alternate marks, preview CSS, and localStorage override. Existing device selections can no longer override the chosen logo.
- Added instant title/author suggestions from the private library metadata, capped at six results and scoped to the selected language/category. Search catalog remains available when editing a submitted query. Click or arrow keys + Enter opens a book; Escape/blur dismiss, regular Enter still submits search, and Chinese IME composition is respected. Uses textContent for suggestions and Jinja tojson for catalog escaping.
- Validation: both new regression tests failed before implementation; all 160 Distill tests passed. Browser verified title and author matches, mouse selection, arrow/Enter selection, Chinese suggestions combined with language/category, Escape dismissal, and no-match feedback. Fixed drop visible in library and book detail. `git diff --check` passes.
- Local preview: http://localhost:5013/. Screenshot: /private/tmp/distill-typeahead-preview.jpg. No production deployment.

## 2026-10-25: Distill search, filters and logo options (local preview)

- Added server-rendered title/author search and combinable Chinese/English and category filters to the web library. GET parameters preserve selections and support sharing/bookmarking; category/language changes submit automatically, with a normal submit button for search and no-JavaScript use. Added result counts, clear filters, empty states, language/category captions and responsive controls.
- Added optional `categories` metadata to the book format and import path, with a backward-compatible SQLite column migration. Existing 54-book collection uses explicit editorial category assignments by slug; future books may provide their own categories, otherwise appear under Uncategorized. Reader content checksums and progress IDs do not depend on categories.
- Added three inline SVG logo directions: drop, open book and funnel. The library's Explore logos control previews each and remembers the device's choice in localStorage. Default is the drop. No new asset files or dependencies.
- Validation: new tests failed before implementation and now pass; all 158 Distill tests pass. Full suite: 1,096 passed and eight existing Gutenberg network tests failed under restricted DNS; rerunning those eight with network access passed all eight (1,104 passing across the two runs; two deselected). `git diff --check` passes.
- Browser verified against all 54 local books: Chinese gives six results; Chinese plus Science & technology gives one; Chinese text search combines with both. Logo selection survives reload. Desktop and 390px mobile inspected, with no horizontal overflow. Preview server: http://127.0.0.1:5013/. Production has not been changed. Existing unrelated worktree edits preserved.

## 2026-10-25: Distill missing cover artwork (deployed and verified)

- Exact audit: 27 of 54 books had no cover pointer. Downloaded real edition covers (English editions, including books with Chinese summary titles); decoded and visually checked every cover. Added `images/cover.jpg` and its cover reference to the local import folders under `data/distill_import/run5/`.
- Inserted 27 image BLOBs and updated only `books.cover_image_id` in the local master. Existing image ids, book metadata, chapter text and reader indexes are unchanged; SHA-256 fingerprints of chapters/reader tables match before and after; SQLite integrity check passes. Local rollback DB: `/tmp/distill-missing-covers/distill.db.before-covers`.
- Verified production and local DB table fingerprints matched before this change. Deploy uses the existing Distill content-DB snapshot/upload/checksum/swap workflow. Reading progress is in a separate DB and is untouched.
- Deployment completed on `wordpress-2-vm` using `venv/bin/python -m distill.scripts.deploy_db`. Service active. Production library returns 200 for owner; all 54 cover URLs returned 200, decoded successfully, and retained private caching. Production SQLite integrity and unchanged chapter/reader fingerprints verified. Public library and new cover redirect to sign-in (302); Plainly remains 200. No code deployment or user-progress DB changes.
- Download provenance:
  - `the-goal`: ISBN `0884271951` — https://images-na.ssl-images-amazon.com/images/P/0884271951.01.L.jpg
  - `guns-germs-and-steel`: ISBN `0393317552` — https://images-na.ssl-images-amazon.com/images/P/0393317552.01.L.jpg
  - `quanqiutongshi-zhangjie-zongjie`: ISBN `0139238972` — https://images-na.ssl-images-amazon.com/images/P/0139238972.01.L.jpg
  - `a-thousand-brains`: ISBN `1541675819` — https://images-na.ssl-images-amazon.com/images/P/1541675819.01.L.jpg
  - `abundance`: ISBN `1451614217` — https://images-na.ssl-images-amazon.com/images/P/1451614217.01.L.jpg
  - `antifragile`: ISBN `1400067820` — https://images-na.ssl-images-amazon.com/images/P/1400067820.01.L.jpg
  - `blue-ocean-strategy`: ISBN `1591396190` — https://images-na.ssl-images-amazon.com/images/P/1591396190.01.L.jpg
  - `built-to-last`: ISBN `0060516402` — https://images-na.ssl-images-amazon.com/images/P/0060516402.01.L.jpg
  - `business-adventures`: ISBN `1497644895` — https://images-na.ssl-images-amazon.com/images/P/1497644895.01.L.jpg
  - `cell-song`: ISBN `1982117354` — https://images-na.ssl-images-amazon.com/images/P/1982117354.01.L.jpg
  - `energy-and-civilization`: ISBN `0262035774` — https://images-na.ssl-images-amazon.com/images/P/0262035774.01.L.jpg
  - `first-break-all-the-rules`: ISBN `0684852861` — https://images-na.ssl-images-amazon.com/images/P/0684852861.01.L.jpg
  - `good-to-great`: ISBN `0066620996` — https://images-na.ssl-images-amazon.com/images/P/0066620996.01.L.jpg
  - `growth-smil`: ISBN `0262042835` — https://images-na.ssl-images-amazon.com/images/P/0262042835.01.L.jpg
  - `how-the-world-really-works-smil`: ISBN `0593297067` — https://images-na.ssl-images-amazon.com/images/P/0593297067.01.L.jpg
  - `life-3-0`: ISBN `1101946598` — https://images-na.ssl-images-amazon.com/images/P/1101946598.01.L.jpg
  - `numbers-dont-lie`: ISBN `0143136224` — https://images-na.ssl-images-amazon.com/images/P/0143136224.01.L.jpg
  - `poor-charlies-almanack`: ISBN `1953953239` — https://images-na.ssl-images-amazon.com/images/P/1953953239.01.L.jpg
  - `poor-richards-almanack`: ISBN `0486408914` — https://images-na.ssl-images-amazon.com/images/P/0486408914.01.L.jpg
  - `silent-spring`: ISBN `0618249060` — https://images-na.ssl-images-amazon.com/images/P/0618249060.01.L.jpg
  - `surely-youre-joking-mr-feynman`: ISBN `0393316041` — https://images-na.ssl-images-amazon.com/images/P/0393316041.01.L.jpg
  - `the-glory-and-the-dream`: ISBN `0553012908` — https://covers.openlibrary.org/b/id/9740819-L.jpg
  - `the-intelligent-investor`: ISBN `0060555661` — https://images-na.ssl-images-amazon.com/images/P/0060555661.01.L.jpg
  - `titan-rockefeller`: ISBN `1400077303` — https://images-na.ssl-images-amazon.com/images/P/1400077303.01.L.jpg
  - `wealth-of-nations`: ISBN `0553585975` — https://images-na.ssl-images-amazon.com/images/P/0553585975.01.L.jpg
  - `why-nations-fail`: ISBN `0307719219` — https://images-na.ssl-images-amazon.com/images/P/0307719219.01.L.jpg
  - `winning-jack-welch`: ISBN `0060753943` — https://images-na.ssl-images-amazon.com/images/P/0060753943.01.L.jpg

## 2026-10-26: Distill `--deploy` and standalone DB push (complete)

- New `distill/scripts/deploy_db.py` (`deploy_db(db_path, settings, run=subprocess.run)`, `DeployError`, runnable as `python -m distill.scripts.deploy_db`). It checkpoints the WAL, snapshots the VM copy (skipped on a first push), scps to `~/distill.db.new`, compares md5 before touching the service, then stops, swaps, chowns, chmods and starts the unit. It checks `is-active` and a local 401, then prunes to the newest 2 `*.bak-pre-push-*`.
- `push_book <folder> --deploy` runs it after a successful import and prints the book URL. `--deploy` with `--dry-run` is an argument error.
- Settings: gitignored `deploy/distill/deploy.local.env`; committed `deploy.local.env.example`.
- Tests: `tests/distill/test_deploy_db.py` mocks only the subprocess boundary.
- Live check: pushed the unchanged local DB. The service came back, `/distill/` still 302s to Google, `/plainly/` is 200.

## 2026-10-26: Distill phase 6 — old /pages summaries taken down (complete)

I compared VM `/var/www/html/pages` (55 files) with the vault `03-resources/book-summaries/` by name and md5.
- 50 were identical.
- 2 differed: `guns-germs-and-steel`, `the-sixth-extinction`. Their VM copies were downloaded into the vault as `<name>.vm-copy-2026-10-26.html`, md5-verified, with nothing overwritten.
- 3 are not book summaries: `index.php` (the reading tracker), `index.php.bak` and `superlinear-academy-public-guide.html` (in the vault under `02-areas/learn/ai`). They were left on the VM.

Backup: `/home/pengyao/pages-backup-20261026.tar.gz` (28 MB, holds all 53 HTML files plus `/var/lib/pages-progress`).

Deleted the 52 summary pages. No redirects, per the owner.

## 2026-10-26: Distill phase 4 — deployed to the VM (complete; owner sign-in check pending)

**Plainly.**
- Pulled `main` to `f2e82f6`.
- The VM's `summra.conf` static `<Directory>` gained `Options -Indexes +FollowSymLinks`. A backup is at `summra.conf.bak-pre-distill-*`.
- Apache reloaded and `summra.service` restarted.
- `/plainly/`, `/plainly/api/books` and `/plainly/static/shared/{css,js}/*` all return 200, gzipped.

**Distill.**
- New `deploy/distill/` holds `distill.service` (user unit for `summra`), `distill.conf` (Apache, `OIDCUnAuthAction auth`, everything proxied, no static Alias) and `distill.env.example`.
- On the VM:
  - Pillow installed in the venv.
  - `/opt/summra/distill.env` (mode 600) binds `127.0.0.1:5002`, with its own proc name and pidfile, and allow-lists the owner only.
  - `data/distill.db` copied up (154.6 MB, 54 books, md5 matched) and owned `summra` with mode 664.
  - The unit is enabled, and `distill.conf` installed.
- Checked on the VM: anonymous 401, stranger 403, owner 200. Pages are `private, no-cache`, images `private, max-age=3600`, and every link is `/distill`-prefixed. A Kindle user agent gets the e-ink library.
- Checked publicly: every `/distill` path (page, static, API, image) redirects a signed-out visitor to Google sign-in, and a forged `X-Remote-Email` doesn't get past it.
- Port 5002 added to the vault port registry.
- CLAUDE.md gained "Deploying Distill (same VM)".

## 2026-10-25: Distill phase 3 final-review fixes (complete)

Fixed the whole-branch review findings (I1-I4, M1-M9; M10 skipped, outside the branch). I1: segment fetch URL carries `&v=<manifest content_version>` (IndexedDB already keyed on content_version); `app.min.js` rebuilt. I2: `GUNICORN_PIDFILE` / `GUNICORN_PROC_NAME` (defaults unchanged). I3: CLAUDE.md deploy section gained the `+FollowSymLinks` step and `shared/**` / `distill/**` restart rows. I4/M1/M5/M8/M9: ERD "Adding a third app" rewritten with the auth-first order, `install_web_basics`, private cache hook and one-app-per-process; symlink depths corrected; shared localStorage and same-origin XSS noted; PRD 17.1 says the sign-in prompt is Apache's. M2: Kindle glue (`account_user_id`, `render_page`, `not_found_page`, page sizes) moved to `shared.kindle.pages`. M3: block-type CSS moved to shared `reader.css`; the "Key points" label stays in `distill.css` as app copy. M4: Kindle progress rejects bool ids. M6: Distill book page uses the chapter outline plus `count_chapters`. M7: Distill Kindle reader maps `?chapter=<id>` to its ordinal. Full pytest 1076 passed; node 60; Plainly e2e 14/14; style snapshot clean; `distill.mjs` passed.

## 2026-10-25: Distill phase 3 — shared reader + web app (complete)

- Task 10: docs. `docs/ERD.md` gained "Reader platform" (every `ReaderConfig`/`ReaderMode`/`ReaderMember`/`ReaderFeatures`/`ReaderSettings`/`KindleOptions` field, the `ALL_MODES` registry, the plug-in surface incl. the host-must-provide list, the render vocabulary, serving/bundling with the Apache `+FollowSymLinks` note, "Adding a third app", Plainly-only code left in shared) and "Distill app" (routes, auth env, two DBs, block-JSON units, image route, Kindle, the ordinal-keyed re-import caveat); `docs/PRD.md` gained 16 (Plainly selector hides for single-mode books) and 17 (Distill). Stale doc references fixed: `style.css` line numbers dropped or pointed at `shared/static/css/reader.css`, `pagination.js`/`settings.js` paths, the Figtree fonts path. CLAUDE.md Frontend Test Loop and `tests/e2e/README.md` document the Distill server on 5003, `distill.mjs` and `reader_style_snapshot.mjs`. Docs only: pytest 1066, node 59, build:check unchanged.

**Phase 3 summary.** The reader moved out of Plainly into a config-driven platform in `shared/` (`ReaderConfig`, `install_reader_platform`, shared JS mixins, CSS, templates, block renderer, Kindle helpers and a shared Kindle progress function), and Distill became the second app on it: library with Reading now, book page, single-mode reader, saved place and progress ("Chapter n of m" / "Overview"), and Kindle mode, all private behind an allow-list. Plainly behaviour was held fixed by golden markup tests, the reader style snapshot, a 52-unit block characterization and the Plainly e2e set; the one visible Plainly change (owner-approved) is that the mode selector hides when a book has fewer than two available modes: **3 of the 90 local Plainly books** (108 Douglass, 110 Augustine, 114 Udolpho; original only). Final pytest **1066 passed** (baseline 916 at phase start, 924 after Task 1); node 59; `npm run build:check` fresh. E2E run: the 14 Plainly scripts (`smoke`, `kindle_mode`, `reader_progress`, `reader_themes`, `reader_last_line_visible`, `reader_opens_at_chapter`, `reader_segments_fast_open`, `reader_illustrations`, `reader_font_figtree`, `reader_nav_mouse`, `sxs_row_split`, `text_size_adjust`, `redesign_home`, `redesign_reader`) 14/14 after each of Tasks 1–9, `reader_style_snapshot.mjs` compare clean, `reader_blocks_characterization.mjs` identical, and `distill.mjs` (desktop, mobile 375x667, Kindle 758x950). Not done (phase 4): the VM, Apache and systemd setup for Distill, and Plainly's next deploy must reinstall `deploy/apache/summra.conf` for `+FollowSymLinks` on the static `<Directory>` and check `/plainly/static/shared/*` returns 200.

**Backlog from phase 3** (also in ERD "Reader platform", Known gaps):
- A "Key points:" lead paragraph can be orphaned at the bottom of a page, apart from its list (shared pagination).
- Kindle contents repeat the part heading on a page that starts mid-part.
- The legacy chapter page calls `authModule.trackPageChange` / `onChapterComplete` without a guard (Plainly-only path).
- Shared partials hold fixed English UI copy.
- Distill re-import keys chapter ids by ordinal: a chapter inserted mid-book shifts content under existing ids, and quote recovery works only within the marker's chapter.

- Task 9: Distill Kindle mode. Ruling J: `POST /api/kindle/progress` moved into `shared/kindle/progress.py` as `save_progress(config, user_db, content_db, user_id, position)` (feature/user_db 404, 401, int `book_id`/`ch`/`p` with `p >= 0`, `text in config.kindle.text_modes`, then `record_page`); each app keeps a 4-line route plus a `position(content_db, book_id, ch, p, text) -> (unit_id, quote) | None` hook (Plainly: verse/modern/original via `_reader_split_paragraphs`, unchanged logic; Distill: chapter by ordinal, quote = `block_text` single-spaced, cut to 180). Plainly's Kindle tests pass unchanged. `reader_base.html` documents its context variables and `base.html` gained a `lang` block (default `en`). New `distill/kindle_routes.py` (blueprint `distill_kindle`; library with Reading now then All books at 7 per page, contents with `li.part` headings at 8 per page and Continue / You are here, reader at the web reader's URL so relative `images/..` srcs hit the private image route), `distill/templates/kindle/{library,book,reader}.html`, `distill/static/css/distill_kindle.css` (no JS), `DistillDatabase.get_chapter_outline` / `get_chapter`, and `reading_cards` / `newest_first` shared with the web library in `distill/routes.py`. `tests/distill/test_kindle.py` (13 tests) failed first (404 / missing route); `distill.mjs` gained a Kindle pass at 758x950 (no module script, contents, table+image chapter loads `kindle.js`, no `tr`/`figure` across columns, `naturalWidth > 0`, tap at x=700 turns the page). pytest **1062 passed**, tests/distill 124, node 59, build:check fresh, Distill e2e passes, Plainly e2e 14/14, style snapshot no differences, goldens green.
- Task 8 fix round 1: lists and keypoints scroll inside a `calc(100dvh - 180px)` box (they were clipped up to ~90px at 375x667); `distill.mjs` gained a mobile pass (red first), real-keypoints label check, `withBasePath` API calls; `image_base` escaped in `blocks.py` and `blocks.js` (app.min.js rebuilt); `DistillDatabase.count_chapters` replaces loading blocks in the library. pytest **1049 passed**, tests/distill 111, node 59, Plainly e2e 14/14, goldens and style snapshot unchanged.

- Task 8: Distill pages and reader host. `distill/routes.py` gained `GET /` (library: "Reading now" from `library_cards`, location line from `progress_label`, then "All books" newest import first), `GET /books/<slug>` (cover, progress, Start/Continue reading, TOC grouped by `part_title` with the Overview first, sources via `block_element` with an explicit `<base>/books/<slug>/` image base) and `GET /books/<slug>/read` (reader shell from the shared `_continuous_reader`/`_settings_panel` partials, `lang` from the book). Unknown slug renders `not_found.html` with 404 (page routes only; API and image 404s are unchanged). Templates `base/library/book/reader/not_found/_cover`, `static/css/distill.css`, `static/js/distill_reader.js` (two hooks + boot; no `window.authModule` override, per Ruling K; boot calls the shared module's memoised `initAuth()`). Books with no cover get a title placeholder card. `DISTILL_READER.extra_page_blocks` is now `'table.reader-table, figure.reader-figure'`. Chapter links are absolute (`/books/<slug>/read?chapter=<id>`) since a relative `read?chapter=` would resolve to `/books/read`. `distill.css` defines `.hidden` because the shared reader CSS uses it for the panels but never defines it (Plainly gets it from `style.css`). The `app_env`/`client` fixtures and `pin_platform_globals` moved from `test_app.py` to `tests/distill/conftest.py` (assertions untouched). Tests in `tests/distill/test_pages.py` (12) failed first (404s / ImportError). `tests/e2e/distill.mjs` (default zh slug is `quanqiutongshi-zhangjie-zongjie`): library to book to reader, no mode selector, image + table chapter pages with no overflow and no merged li/td text, `.reader-keypoints::before` in en and zh, reload restores the first anchor, Reading now, IndexedDB has `distill-reader-v1` and not `summra-reader-v2`. Nothing under `shared/` changed. pytest **1046 passed** (full), `tests/distill` 109 passed, node 59 pass, build:check fresh, Distill e2e passes.

- Task 7: Distill app core. `distill/reader_config.py` (`DISTILL_READER`: summary-only, private cache, `inline='strict'`, hint keys as pagination.js), `distill/app_base.py` (`create_app(content_db, user_db, auth_config)`: pchauth from `DISTILL_AUTH_MODE`/`DISTILL_ALLOWED_EMAILS`, mode `off` when unset; `install_reader_platform`; default `Cache-Control: private, no-cache` on every non-static response lacking one), `distill/routes.py` (`book_image`: `/books/<slug>/images/<name>`, login required, `private, max-age=3600`, ETag/304), `distill/app.py` (port 5003), `distill/app_prod.py` (RuntimeError unless `DISTILL_AUTH_MODE=required`), `distill/static/shared` symlink. `get_book`/`list_books` return `cover_image` (name); `config` gained `DISTILL_DB`, `DISTILL_USER_DB`, `PORT`. The `tests/distill` app fixture monkeypatches the `progress_routes`/`whoami` globals so Plainly tests are unaffected. Also moved `tests/fixtures/reader_blocks/` to `tests/shared/fixtures/reader_blocks/` (the old dir is gitignored; only the four path constants changed). New tests failed first (ModuleNotFoundError / KeyError cover_image). pytest **1031 passed** (full), `tests/distill` alone 94 passed, node 59 pass, build:check fresh, Plainly e2e 14/14, Distill dev server serves an image (200, private).

- Task 6: shared block renderer. One render vocabulary owned by `shared/` (`p`, `h`, `verse`, `li`, `quote`, `ul`, `ol`, `keypoints`, `table`, `image`): `shared/static/js/blocks.js` (`escapeText`, `formatInline(text, 'markdown'|'strict')`, `renderBlock`, `blocksMixin.continuousReaderBlock`, applied by `platform.js`) for the web reader and `shared/reader/blocks.py` (`escape_text`, strict `format_inline`, `render_block`, `block_element`, `block_text`) for Kindle pages. Plainly's `continuousReaderBlock`/`formatContinuousReaderText` became `classifyUnit(text) -> block` (same heuristics, same order); the old inline body moved unchanged into `formatInline('markdown')`. `ReaderConfig` gained `inline` (validated) and `image_base`, both in `to_client()` (pin updated on purpose); Plainly sets `inline='markdown'`. `distill/book_format.block_text` is now a re-export (adds `verse`, `li`). Plainly's Kindle keeps `kindle_inline`. Markup identity: a characterization golden of `continuousReaderBlock` over 52 units (22 heuristic-branch cases + 30 real Pride and Prejudice / Paradise Lost units), with and without marked, recorded on unchanged code (`tests/e2e/reader_blocks_characterization.mjs`, `tests/fixtures/reader_blocks/`), compares identical after the change in dev (app.js) and prod (app.min.js) mode. New tests failed first: `tests/js/blocks.test.mjs` (6), `tests/shared/test_blocks.py`, `test_block_parity.py` (JS vs Python over every type), a config validation test. node **59 pass**, pytest **1018 passed**, build:check fresh, goldens green, style snapshot no differences.

- Task 5: Plainly's Kindle reader now runs on `shared/kindle/`. `shared/kindle/__init__.py` (UA detection, was `shared/kindle.py`), `pages.py` (`register_kindle_pages(bp, handlers, config)` dispatch + Vary hook, no-op when `features.kindle` is off; cookie/URL/pagination/font helpers; `account_context`, `render`, `saved_marker`) and `progress.py` (`record_page`, the `apply_mutation` body moved out of `save_progress`). `kindle.js` (ES5; units are the `#flow` descendants with `data-i`) and `kindle.css` are `git mv`'d to `shared/static/`; templates `base/_masthead/_pager/_account/not_found/reader_base` live in `shared/templates/shared/kindle/` (`reader_base` has `flow_class`/`flow_body` blocks and a Text row built from `kindle.text_modes` + `text_urls`). `plainly/routes/kindle.py` keeps `kindle_inline`, the page functions, `LIBRARY_PAGE_SIZE`, `_signed_in_user_id`, and takes the `text` default/validation from `PLAINLY_READER.kindle`; `/api/kindle/progress` is 404 when the Kindle feature is off. The only golden change is the reader script URL (`/static/js/kindle.js` -> `/static/shared/js/kindle.js`, forced by the move). New: `tests/shared/test_kindle_shared.py` (13, ES5 test moved there with only the path changed) and 1 Plainly test; pytest **972 passed**, node 53 pass, build:check fresh, style snapshot no differences, Plainly e2e 14/14.

- Task 4: reader CSS and templates moved into `shared/`. `shared/static/css/base.css` (Figtree `@font-face`, reset, `:root` tokens; fonts `git mv`'d to `shared/static/fonts/`) and `reader.css` (settings panel, font/size/theme, pagination font family, pagination system, continuous reader) are cut verbatim from `style.css`; `index.html` links base.css, style.css, reader.css in that order. Partials `shared/reader/_continuous_reader.html` (takes `reader_hidden`), `_settings_panel.html` (mode selector only when `modes|length > 1`; fonts, size range and themes from `reader_config.settings`) and macro `shared/_library_card.html` render from `reader_config`; `_book_card.html`'s `library_card(book)` wraps it. Plainly's golden markup tests, `MODE=compare` style snapshot (no differences) and the 14 e2e scripts are unchanged; 3 new template tests; pytest 959 passed.

- Task 3: Plainly's web reader JS is now the config-driven shared platform in `shared/static/js/`: `pagination.js` and `settings.js` (git mv, plus `createPaginationState()`), `continuous_reader.js` (the continuous-reader methods cut verbatim from `reader.js`), `reader_utils.js` (`escapeHtml` from `app.js`, `readerConfig`/`readerMode`/`readerLayout`/`readerAvailableModes`), `reader_state.js` (`window.readerState`, the progress/cache half of `auth.js`), `base_path.js` (`withBasePath` from `route_utils.js`) and `platform.js` (`applyReaderPlatform`). Only the brief's parameterisation rows changed (modes, widths, labels, cell classes, gap copy, settings defaults, IndexedDB name, illustrations/page-turn-hint features, extra page blocks). Owner-approved visible change: the mode selector hides when a book has fewer than two available modes (3 of 90 local Plainly books: 108, 110, 114, original only). New tests failed first: `tests/js/mixins_disjoint.test.mjs` (3), `reader_modes.test.mjs` (15), `base_path.test.mjs` (6, moved), `tests/shared/test_shared_js.py` (3, one moved). node **49 pass**, pytest **955 passed**, build:check fresh, goldens green, style snapshot no differences, Plainly e2e 14/14.
- Task 3 fix round 1: `reader_state.js` defaults `window.authModule` to `{...readerState, initAuth}` when no host set one (Plainly's `auth.js` loads after it and still wins) and builds its API base from `READER_CONFIG.api_base` (fallback `/api`); `splitSideBySideRowToFit` takes its cell selectors from the side-by-side members' `cell_class` (fallback `original`/`modern`); the marker word counts use `readerLayout()`. New tests failed first: `tests/js/reader_state.test.mjs` (3), a row-split selector case in `reader_modes.test.mjs`; plus a script load-order test in `test_reader_config_script.py`. node **53 pass**, pytest **956 passed**, build:check fresh, goldens green, style snapshot no differences, Plainly e2e 14/14.

- Task 2: reader platform server side. `shared/reader/modes.py` (`ALL_MODES`, `SINGLE_MODES`, `SIDE_BY_SIDE_MEMBERS`) is now the one registry: `ReaderIndexMixin._READER_MODES` and `user_models.VALID_MODES` derive from it (resolves the phase 1 duplicate-modes finding); SQL CHECK strings stay literal and a test pins them to the registry. New `shared/reader/config.py` (`ReaderConfig` + validation, `to_client()`), `shared/reader/routes.py` (the four reader handlers moved verbatim out of `plainly/routes/books.py`, DB resolved per request, Cache-Control visibility from config), `shared/reader/platform.py` (`install_reader_platform`), `plainly/reader_config.py` (`PLAINLY_READER`), and the `_config_script.html` partial included in Plainly's `index.html` head. `plainly/app_base.py` now calls `install_reader_platform`. New tests: `tests/shared/test_reader_config.py` (7), `test_reader_routes.py` (8). pytest **939 passed**, 2 deselected; Plainly e2e 14/14.

- Task 1: shared static/template plumbing and Plainly baselines. `shared.web.SHARED_TEMPLATES` and `install_shared_ui(app)` (ChoiceLoader, app templates first), called from `plainly/app_base.py`; Plainly's context processor adds `app_name='Plainly'`. `shared/static/` and `shared/templates/shared/` created; `plainly/frontend/static/shared` is a symlink to `shared/static` (Apache static `<Directory>` now `Options -Indexes +FollowSymLinks`; repo copy only, VM untouched). Baselines recorded on unchanged code: golden markup (`tests/plainly/test_reader_shell_markup.py`, 2 tests, `tests/plainly/golden/`) and the computed-style snapshot (`tests/e2e/reader_style_snapshot.mjs`, `MODE=record|compare`; 4 variants, 52 elements; compare after the change: no differences). New tests in `tests/shared/test_shared_ui.py` (5) and `test_apache_conf.py` (1) failed first. pytest **924 passed**, 2 deselected.

## 2026-10-25: Distill phase 2 — format, import, converter (complete)

- Final-review fixes: CI installs `distill/requirements-tools.txt` (bs4 tests no longer skipped), `CJK_RE` public in `book_format`, converter runs `validate_book` and flags/reports `errors`, `list_books` ordered by title (case-insensitive, id tiebreak), heading-only chapters reported empty before part headings are inserted, `distill/requirements.txt` (Pillow).

- Task 5 (data, not committed): converted all 54 vault summary pages (final run `data/distill_import/run5`, after converter fix rounds 1–2: notes tabs → sources, nested worklogs skipped, lost captions recorded in `dropped`, part subtitle headings kept). 54/54 validate. Flagged 4, accepted: cell-song, guns-germs-and-steel, silent-spring, winning-jack-welch each lose 1–2 SVG/unfetchable images (captions recorded in the report). The two *Abundance* pages are different books (Diamandis & Kotler; Klein & Thompson) and both are imported. Hand fixes in the run5 `book.json` before import: 18 authors the converter guessed wrong or left blank (e.g. silent-spring was "Silent Spring", Klein lacked Thompson) and 3 doubled "Introduction — Introduction" chapter titles. Imported all 54 into `data/distill.db` with `ensure_reader_content` for each: 0 failures; the 4 books imported earlier kept ids 1–4. DB size 154.6 MB (check VM disk before phase 4 push). pytest **912 passed** at `74253b6`.

- Task 1: `distill/book_format.py` (`load_book`, `validate_book`, `block_text`, `iter_chapters`, `FORMAT_VERSION`, `BLOCK_TYPES`). Errors carry the block path, e.g. `parts[1].chapters[3].blocks[2]: ...`. Tests in `tests/distill/test_book_format.py` (15) failed first with `ModuleNotFoundError`.
- Task 4: `distill/scripts/convert_html_summaries.py` (`convert_page`, `PageReport`, `main`; `distill/requirements-tools.txt` has beautifulsoup4, local-only). Tabs become Overview/Sources/parts, chapters from `.chapter` or bare `h3`, "Key Points" headings label the next list as keypoints, Wikimedia originals are fetched as 1280px thumbnails first. Real run over the 54 pages: all 54 `book.json` validate, 4 flagged (SVG images only), no duplicates (the two Abundance books have different authors). Tests in `tests/distill/test_convert_html.py` (31, failed first with ImportError).
- Task 3: `distill/scripts/push_book.py` (`main(argv)`, argparse: `<folder> [--dry-run] [--db PATH]`). Prints title, chapters, words, images and image bytes; validation errors are printed and return 1 (dry-run or not); `--dry-run` never touches the DB; otherwise imports and prints `Imported <slug> as book <id>`. Tests in `tests/distill/test_push_book.py` (3) failed first with `ModuleNotFoundError`. Fix round 1: `book_format.word_count` (CJK per character, then the mixin's word pattern) is shared by push_book and `DistillDatabase._reader_word_count`; `book_format.list_images` is shared by push_book and `import_book`. 5 new tests failed first. pytest **871 passed**, 2 deselected.
- Task 2: `distill/config.py` and `distill/models.py` (`DistillDatabase(ReaderIndexMixin)`: `books`/`chapters`/`images`, `import_book`, getters, library hooks, reader hooks; summary-only units, one per block; CJK-aware word count). Re-import upserts chapters by `(book_id, ordinal)`, so chapter ids stay stable as well as the book id (markers carry chapter ids). Tests in `tests/distill/test_models.py` (13) plus `tests/distill/conftest.py` fixtures; failed first with `ModuleNotFoundError`. pytest **863 passed**. No `shared/` change.

## 2026-10-24: Distill phase 1 — repo split (complete, deployed)

Splitting the repo into `shared/`, `plainly/` and `distill/` with Plainly unchanged. Plan and design: see the Distill design and phase 1 plan commit.
- Task 1 baseline (before any change): pytest **816 passed**, 2 deselected. e2e against local Flask on :5002: `smoke.mjs` passes, `kindle_mode.mjs` all checks passed.
- Task 2: moved `backend/pchauth`, `user_models.py`, `whoami.py` into `shared/auth/` (git mv, no shims). `UserDatabase(db_path, valid_hints=frozenset())` now requires a path; Plainly passes `config.USER_DATABASE_PATH` and `config.READER_HINTS`; `progress_routes` checks `user_db.valid_hints`. Moved user_models/user_hints/pchauth_integration tests to `tests/shared/`. Owner-approved: `test_deploy_config.py::test_user_database_class_default_matches_configured_path` body replaced with a `TypeError` assertion (the class default was removed on purpose). pytest **820 passed** (baseline 818 + 2 new).
- Task 3: moved `backend/progress_routes.py` to `shared/progress/routes.py` (git mv, no shim); the `content_db` surface is documented in the module docstring. App, kindle/pages routes and tests import it as `shared.progress.routes`. New bare-app test in `tests/shared/test_progress_package.py`. pytest **821 passed** (820 + 1).
- Task 4: pinned `source_checksum` for a two-chapter fixture book first (`test_reader_storage.py::test_source_checksum_is_stable_for_fixture_book`, own commit, 822 passed). Then moved the reader index out of `backend/models.py` into `shared/reader/index.py`: `create_reader_tables(cursor)` plus `ReaderIndexMixin`, with no Plainly SQL. Plainly's `Database(ReaderIndexMixin)` implements the hooks (`_reader_load_book`, `_reader_load_chapters`, `_reader_chapter_units`, `_reader_source_checksum`, plus `_reader_plain_coverage` and `_reader_structure`, which the brief didn't list: they hold the `modern_english_text` and `book_sections` SQL that would otherwise have stayed in shared). Old vs new code on a copy of the local DB (96 books): manifests, sampled segments, `reader_version` rows (checksums, etags) and `reader_unit` all identical. New `tests/shared/test_reader_index.py` (4, fake host with no Plainly tables) failed first with `ModuleNotFoundError`. pytest **826 passed** (822 + 4).
- Task 5 (part 1): `shared/web.py` (`PrefixMiddleware`, `gzip_response`, `make_asset_v`, `install_web_basics`) and `shared/kindle.py` (moved from `backend/kindle.py`); `backend/app_base.py` calls `install_web_basics(app)` after the cache-header hook so gzip still runs first. New `tests/shared/test_web.py` (2) failed first with `ModuleNotFoundError`. pytest **828 passed** (826 + 2).
- Task 5 (part 2): renamed `backend/` to `plainly/` (git mv) and rewrote every `backend` reference in py/mjs/sh/toml/service/json/ini/bat and deploy docs (patch targets, `pyproject.toml` include `plainly*`, systemd `plainly.app_prod:app`); dropped the try/except relative-import fallbacks in `plainly/*.py`; moved 66 Plainly tests to `tests/plainly/` (path lookups now `parents[2]`). Added repo-wide guard `tests/test_layering_names.py` (also catches `backend.app_prod`/`backend.app`). The four sys.modules-popping tests now purge `plainly.*` (except `app_prod`) plus `shared.progress`/`shared.auth`, so reloads are real. `python plainly/app.py` on :5002 returns 200; `smoke.mjs` and `kindle_mode.mjs` pass. pytest **829 passed** (828 + guard).
- Task 6: moved `frontend/` and `scripts/` under `plainly/`. `config.COVERS_DIR`/`ILLUSTRATIONS_DIR`/`TTS_OUTPUT_DIR`, Flask `static_folder`/`template_folder`, `package.json` esbuild paths, Apache and nginx static aliases, every `scripts.` import (now `plainly.scripts.`) and every `Path(__file__)` repo-root computation in the moved scripts were updated. `tests/_reload.py` keeps `plainly.scripts` out of the purge (as `scripts` always was). Stale-name guard extended to `scripts`/`frontend/static`; new `tests/plainly/test_layout_paths.py`. Script invocation form is now `venv/bin/python -m plainly.scripts.<group>.<name>` in CLAUDE.md, README and deploy docs; ERD gained a layout section. Tests: **833 passed**; `npm run build:check` fresh; smoke (`/`, `/discover`, `/books`, a book and its reader) and `kindle_mode.mjs` pass on :5002; `generate_summaries --dry-run` works as a module.
- Final whole-branch review fixes (`8496d4d`): `tests/js` paths (node **31 pass**), Plain English agent/doc commands now `python -m plainly.scripts...` with a guard, library-card SQL moved out of `shared/progress` behind `Database.library_books`/`chapter_titles`, an order-dependent reload leak, `config.STATIC_DIR`, and no Plainly names left in `shared/web.py`. pytest **835 passed**.
- Deployed `8496d4d` (2026-10-25): pushed main, VM fast-forwarded, `pip install -e .`, systemd `ExecStart` → `plainly.app_prod:app` (unit backed up), Apache static Alias/Directory → `/opt/summra/plainly/frontend/static` (conf backed up), `configtest` OK, reload, restart: active, local HTTP 200, no errors. Public `/`, `/books`, `/api/books`, `static/css/style.css` and covers 200; `kindle_mode.mjs` passes against production. The `/api/books` `cover_image_url` `.png` values never had files (pre-existing; pages use `.jpg`/`.webp`).
- Final review fixes: JS test paths, agent/doc commands moved to `python -m plainly.scripts...` (guard extended to `.claude/agents` and `docs/*.md`), Library SQL moved behind `content_db.library_books`/`chapter_titles`, test-reload leak purged on teardown, `config.STATIC_DIR`, `shared/web.py` env-var name now an explicit argument.
- Task 1: added empty `shared/` and `distill/` packages, `pyproject.toml` include now `backend*, scripts*, shared*, distill*`, and `tests/shared/test_layering.py` (shared must not import plainly/distill/backend/scripts). Guard test failed first (no `shared/`), then passes.

## 2026-10-24: Distill — design (in progress)

User wants a second app, Distill, at `pengyaochen.com/distill`: a private reader for their own book summaries (made locally by the `book-summary` skill), reusing Plainly's reader, synced progress and Kindle mode, sharing sign-in with Plainly. Decisions from the brainstorm: owner-only and fully behind sign-in; no server-side summarization (1 GB VM); import via a local push command; skill writes a structured `book.json` directly; the 54 existing `/pages` HTML summaries get a one-time conversion, then `/pages` summaries come down; chapter = reader unit; day one is library + reader + progress + Kindle only; repo split into shared / Plainly-only / Distill-only first, with two services and two deploy scripts. WordPress is gone from the VM. Design at `docs/superpowers/specs/2026-10-24-distill-design.md`, approved by the user (content and images in `distill.db`, local master pushed to the VM; progress in a separate `distill_user.db` that the server owns; skill stops producing HTML and drops the Kindle EPUB export; hotlinked images downloaded). Phase 1 plan (repo split into `shared/` / `plainly/` / `distill/`, 7 tasks ending in a VM deploy) at `docs/superpowers/plans/2026-10-24-distill-phase1-repo-split.md`, awaiting review. Plans for phases 2–6 to be written after phase 1 lands. User requirement: web reader code must be heavily shared, not forked. Phase 1 leaves front-end code in Plainly. Phase 3 opens by extracting the common reader components into `shared/` and moving Plainly onto them. No code written yet.

## 2026-10-19: Kindle home shows books in progress with progress (complete, deployed)

User asked to see the books they were reading, with progress, on the Kindle home page. Signed in, home now starts with *Reading now*: up to 3 books in progress (the website Library's Continue reading list), each with current chapter, a black progress bar and the furthest-point %, linking into the reader; *See all N* opens `/?show=reading`, paginated. Signed out keeps the single cookie-based Continue reading card.
- Tests: 4 new cases in `tests/test_kindle_mode.py` failed first, then pass (44 total). `test_signed_in_library_continue_reading_comes_from_account` was updated to the new behaviour at the user's request ("Reading now" replaces the signed-in Continue reading card). Full pytest **816 passed**.
- `kindle_mode.mjs` caught a regression: the new `.reading` CSS also matched the reader's `<html class="reading">`, adding an 18 px margin so the reader page could scroll. Scoped to `section.reading`; all checks pass. Screenshot of the home page checked.
- Deployed `6fcdef6`: pushed main, VM fast-forwarded, gunicorn restarted (active, local HTTP 200, no errors in the log). Public `/`, `/books`, `/api/books` return 200; signed-out `/?show=reading` falls back to the Plain English list; the live `kindle.css` has the scoped `section.reading` rules. `kindle_mode.mjs` passes against production (sync checks skipped: the test browser is signed out), so the signed-in Reading now list is verified locally only.

## 2026-10-19: Kindle mode sign-in and synced progress (complete, deployed)

User signed in on a Kindle through `/login` by hand and asked for an entry point in Kindle mode plus progress synced like the web version.
- Entry points: *Sign in* in the library masthead, a "Sign in to keep your place in sync" line on the library and book pages, and a link in the reader menu. All use the web's logout-first `/login` URL. Signed in shows "Signed in as <email>" (or "Signed in." when the account has no email, as in local off-mode, caught by looking at a screenshot).
- Sync: new `POST /api/kindle/progress`; the server turns the Kindle's (chapter, paragraph, text) into a web-reader progress mutation, so the ES5 script stays small. Resume, *Continue reading* and the furthest point now come from the account when signed in, so the Kindle and website share one position. Details in ERD "Kindle E-ink Mode" and PRD §12.
- Tests: 16 new cases in `tests/test_kindle_mode.py` (40 total) failed first, then pass; full pytest **812 passed**. `kindle_mode.mjs` gained 3 sync checks (page turn saved with HTTP 200, `/api/progress/v2/books/<id>` shows the Kindle's paragraph, reopening resumes at that chapter); all checks pass locally. On a signed-out browser (prod test runs) the sync checks are skipped.
- Deployed `e5bb90e`: pushed main, VM fast-forwarded, gunicorn restarted (active, local HTTP 200, no errors in the log). Public `/`, `/books`, `/api/books` return 200; the Kindle library's Sign in link is `/plainly/login?logout=%2Fplainly%2Flogin`; `POST /plainly/api/kindle/progress` signed out returns 401. `kindle_mode.mjs` passes against production with the sync checks skipped (test browser is signed out), so signed-in sync on production is verified only locally.

## 2026-10-19: Kindle e-ink mode (complete, deployed)

User asked for an e-ink Kindle mode like WeChat Reading's ink version (微信读书墨水屏版), triggered only when the device is a Kindle. Research: Kindle's browser has no app install, is slow, and ghosts on scrolling (sspai); the older browser is WebKit 531, so `app.js` can't run there. Design: a separate server-rendered front end at the same URLs (library → book → reader), tap-to-turn CSS-column pages, ES5 script, black-on-white, no animation. Details in PRD §12 and ERD "Kindle E-ink Mode".
- Detection: `backend/kindle.py`. The Paperwhite UA says "like Android", so Fire tablets are excluded by `Android <digit>`, `Silk`, `KF…` or `Kindle Fire` (caught by the first test run). `?kindle=0|1` overrides by cookie.
- Bug found by the e2e test: the resume paragraph was the last one *starting* on the page, so A+ jumped a page ahead. Now it's the first paragraph whose last page is ≥ the current page.
- Tests: `tests/test_kindle_mode.py` (24) failed first, then pass; full pytest **796 passed**. `tests/e2e/kindle_mode.mjs` (21 checks: no scroll, tap right/left, no cut lines, menu, A+ re-paginates and is remembered, last page → next chapter, back → end of previous chapter, Plain↔Original keeps the paragraph, desktop unaffected) passes; `smoke.mjs` passes on `/`, `/discover`, book and reader pages with a desktop UA.
- Not verified on a real Kindle. The Kindle UA on the newest firmware (5.16.4+, updated browser) wasn't confirmed by any source; if it lacks the `Kindle` token, detection misses and the reader can use `?kindle=1`.
- Deployed `9e49d25`: pushed main, VM fast-forwarded from `e708282`, gunicorn restarted (new templates and backend; active, local HTTP 200, no errors in the log). Public `/`, `/books`, `/api/books` return 200. `kindle_mode.mjs` passes all 21 checks against `https://pengyaochen.com/plainly` (links and cookies work under the prefix) and `smoke.mjs` passes on `/` and a book page with a desktop UA.

## 2026-10-18: Home tab title shows Plainly (complete, deployed)

User asked to update the browser-tab text for Plainly. The server already rendered `Plainly — Read the Classics in Plain English`, but `showHomeSection()` in `app.js` replaced it with the pre-rebrand tagline `Free Classic Book Summaries, Chapter Summaries & Full Text | Plainly`, which hid the brand on narrow tabs. The user picked "fix home only": other pages keep `… | Plainly`. Rebuilt `app.min.js` (`build:check` up to date).
- Test: `tests/e2e/home_tab_title.mjs` checks the title on first load and after SPA navigation back to home. Both checks failed before the fix and pass after; `smoke.mjs` passes.
- Deployed `1ca7624`: pushed main, VM fast-forwarded (static-only, no restart; `asset_v` hashes per request so clients get the new bundle). Public `/`, `/books`, `/api/books` return 200 and `home_tab_title.mjs` passes against prod.

## 2026-10-18: Production URL moved to pengyaochen.com/plainly (complete, deployed)

User asked to change the domain to `pengyaochen.com/plainly` after the Plainly rename. The app reads `X-Forwarded-Prefix`, so only Apache changed.
- Repo: `deploy/apache/summra.conf` now has `RedirectMatch 301 ^/summrabook(/.*)?$ ${SUMMRA_PREFIX}$1`, so old links land on the same page and keep their query string. `tests/test_apache_conf.py` renders the fragment the way `install.sh` does; it failed before the line was added and passes after. Full pytest **770 passed**. Deploy docs' example prefix is now `/plainly`.
- VM: pulled `ed07a6b`. Backed up the vhost (`wordpress-https.conf.bak-<ts>-plainly`) and the old fragment (moved to `/etc/apache2/summra.conf.bak-<ts>-plainly`, outside `service-locations/` so `*.conf` doesn't include it). Changed `Define SUMMRA_PREFIX` to `/plainly`, re-rendered the fragment with install.sh's sed, `apache2ctl configtest` OK, reloaded Apache. No gunicorn restart (no app code changed). OIDC needed no change: its callback is `/oidc/callback` and the cookie path is `/`.
- Verified: `/plainly/`, `/api/books`, `manifest.json`, `sitemap.xml`, `robots.txt` and static CSS return 200; `/plainly/login` sends you to Google; `APP_BASE_PATH`, canonical, manifest `start_url` and the robots sitemap line all use `/plainly`. `/summrabook`, `/summrabook/` and `/summrabook/books/moby-dick-or-the-whale?…` 301 to the `/plainly` equivalents. Smoke passes against prod (home, Moby Dick, discover), and `signin_link_navigates.mjs` passes. WordPress root still 200.
- Follow-up for the user: update Google Search Console (new sitemap URL) and any links outside this server.

## 2026-10-18: Brand renamed Summra → Plainly (complete, deployed to production)

User picked "Plainly" from a name shortlist, since the app's focus moved from summaries to Plain English. Changed only user-facing text: page titles and meta/OG tags, logo, footer, iOS install banner, manifest, robots.txt, audio album name, the "isn't authorized for…" sign-in banner, and the blog's default author. Code identifiers, `SUMMRA_*` env vars, the `/summrabook` prefix, DB and deploy names are unchanged (listed in ERD "Brand name"). Rebuilt `app.min.js`.
- Test: `tests/test_brand_name.py` (24 cases) failed before the change and passes after; full pytest **767 passed**. `smoke.mjs` passes on `/` and `/discover`. `/blog` returns 404 locally on unchanged `main` too, so `blog_post_title_not_overwritten.mjs` can't run here (string updated to `Blog Post | Plainly`).
- Not done: 8 existing `blog_posts` rows in the DB still say "Summra" in their content or author.
- Deployed `6a8911e`: pushed main, production fast-forwarded, gunicorn restarted (active, local HTTP 200, no errors in the log). Public `/`, `/books`, `/api/books` and `/manifest.json` return 200. The live title, logo, footer and manifest `short_name` all say Plainly, and neither the home page nor `app.min.js` contains "Summra".

## 2026-10-18: Grimms' Fairy Tales (book 62) Plain English (complete, deployed to production)

User asked to process book 62. All **61 tales now have Plain English, 908 exactly paired paragraphs** (ratios 0.94–1.01). Deployed to production (see below). DB backup: `data/database.pre-62-plain-20261018.db`. Run dir (gitignored): `data/log/agent_plain_english/book62`.
- Cleanup: `reformat_paragraphs.py` split 60 of 61 tales (ingest had one hard-wrapped line each). **Order mistake:** I ran the footnote, caption and divider dry-runs *before* the reformat, when every chapter was one paragraph, so they found nothing. Re-run after reformat they found a `*****` divider (ch61, stripped from the original, and from the JSON entry) and the default caption rules, which would have deleted 16 Juniper-tree song lines in ch40 and real headings in ch15/56/57, so they were not run (`--tags-only` finds nothing). ch50 had a `[*] Simpleton` footnote paragraph and a `[*]` marker; both removed from the original and the JSON by hand. ch61 ends with a Grimm-brothers biography paragraph, kept and translated.
- Writers: 9 Sonnet writers (`effort: low`) at ~60–70K characters each (ch1–8, 9–16, 17–23, 24–30, 31–37, 38–46, 47–53, 54–58, 59–61). First batch spot-checked before launching the rest. No usage limit was hit.
- Gate workaround again: paragraphs introducing a rhyme or spell end in a colon in the source. Writers changed them to "…sang this song." / "said these words." (about 70 paragraphs). Rhymes were rendered without rhyme, with thee/thou modernized.
- Quotes: the first batch used straight `'` and `"`; later writers, told to use curly quotes, did. A smart-quote script over the JSON fixed 61 paragraphs before apply.
- 9 fresh Sonnet verifiers made **17 fixes in 908 paragraphs (1.9%)**: leftover archaic words ("rue" x5, "thee", "desert" meaning wilderness, "slut" meaning untidy woman, "sexton"), a reversed pronoun ("my own amusement"), "grief" turned into "anger", one invented detail ("nine dead men's leg bones"), a dropped "therefore", and a wrong sense in "whom to blame". Six of nine verifier ranges had 0 fixes.
- Tests: `agent_plain_english_side_by_side.mjs` now includes book 62 and passes (908 rows). `smoke.mjs` (book and reader), `sxs_row_split.mjs` and `reader_opens_at_chapter.mjs` pass.
- Deployed: per-book `chapters` update on the VM (not a whole-DB copy). Pre-flight showed the VM's book 62 text matched the pre-change local backup (61 chapters, no Plain English). VM DB snapshot `/opt/summra/data/database.db.bak-pre-62-20261019-022442`; updated 61 rows (`chapter_text` and `modern_english_text`) in one transaction; `ensure_reader_content(62)` rebuilt the reader index (plain coverage 1). VM now has 61/61 chapters with Plain English for book 62 and 2,328 chapters in all, equal to local. Public `/`, `/books`, the book page, Side-by-Side reader and `/api/books` return 200. No service restart (data only). Code commit `6599da5` is local, not pushed, so the VM checkout is unchanged. Check ch53 P6 ("I come" to "I came") if re-reading.

## 2026-10-18: Sign-in links did nothing (fixed and deployed)

User reported the sign in button doesn't work. Root cause: `setupRouting()`'s delegated `a[href^="/"]` click handler in `app.js` also caught `/login?logout=…`, the Apache OIDC entry point. It ran `pushState` and the SPA router instead of loading the page, so the URL changed and Google sign-in never started. Production showed the same thing (header and footer links). The server side was fine: `/summrabook/login` returns a 302 to Google.
- Fix: the router lets any link starting with `withBasePath('/login')` load normally. Rebuilt `app.min.js`.
- Test: `tests/e2e/signin_link_navigates.mjs` clicks the phone header link and the desktop footer link and checks that the browser requests `/login`. It failed before the fix (URL changed, no request) and passes after. `mobile_header.mjs` and `smoke.mjs` pass.
- Deployed `af4f6ef`: production fast-forwarded from `f6b4667`. Only static JS changed, so there was no gunicorn restart. The live page loads the new `app.min.js?v=301915641`, which matches the local bundle's CRC. `signin_link_navigates.mjs` passes against production (both links), and a real click on the footer link reached Google's account chooser.

## 2026-10-18: Pending commits pushed; Origin of Species deployed (complete)

User requested committing/pushing everything and uploading the translation to production.
- The worktree was already clean with four pending commits. Pushed all through `b83f7a3` (new favicon, Origin completion, E2E adjustment, Mississippi completion documentation); production checkout fast-forwarded from `9665e13` to the same commit without modifying its untracked config/backup files.
- Uploaded only book 2's verified `modern_english_text`, using an in-memory SSH transfer and one SQLite transaction. All 14 source hashes and the expected old/new translation hashes were checked before writing. Changed chapters 1, 6, 7, 9, 10, 11–14; all 14 resulting translation hashes match local. No whole-DB replacement or DB backup; other books and user state were left intact.
- Rebuilt book 2's reader index: production reader version 4, all 14 chapters available, 1,264 paired paragraphs, 565 index paragraphs verbatim. The first transfer script stopped on a quoting error before any remote code executed; corrected and syntax-checked before the successful retry.
- Restarted the user service because the favicon template changed; service active, local HTTP 200, normal startup logs. Public HTML references the new SVG favicon.
- Validation: **40 local tests passed** (favicon + rewrite/reformat helpers); public full-book Side by Side E2E **14 checks passed**; all **14 public chapter hashes** equal local; public smoke passed home, books, Origin book and reader routes with no console/request errors.
- Deployment record committed and pushed after verification. Only the Origin translation was synchronized; the separate Mississippi translation remains local as recorded below.

## 2026-10-18: Life on the Mississippi (book 112) Plain English (complete locally)

User picked book 112 from the queue. All **61 chapters now have Plain English, 1,974 exactly paired paragraphs** (ratios 0.94–1.06). Local DB only; not deployed or committed. DB backup: `data/database.pre-112-plain-20261018.db`. Run dir (gitignored): `data/log/agent_plain_english/book112`.
- Cleanup: `reformat_paragraphs.py` split all 61 chapters (ingest had one hard-wrapped line per chapter). `strip_footnotes.py` found nothing: this book's footnotes are inline `{footnote [...]}` paragraphs, left in place and paired like any other paragraph. No captions or dividers. Ch0 is front matter (credit line, title, contents list, epigraph); ch60 holds Appendices A–D. Neither was restructured.
- Writers: 13 Sonnet writers batched at ~70K characters (ch0–3, 4–8, 9–13, 14–17, 18–24, 25–29, 30–34, 35–41, 42–48, 49–53, 54–59, ch60 in two halves). The first writer copied the Huck Finn raft passage in ch3 verbatim because my brief said "keep dialect faithful"; it was redone in plain English. Briefs now say: rewrite dialect, keep the joke.
- Slurs: every writer replaced the period slur with "Black man", "enslaved man" or similar, as earlier books did. Verifiers were told not to reintroduce it.
- Gate workaround: the gate fails paragraphs ending in a colon, comma or dash. Speech lead-ins ("He said--") were changed to end in a period ("He said this."). About 120 paragraphs across the book. The ch60 three were fixed by hand.
- 13 fresh Sonnet verifiers made **26 fixes in 1,974 paragraphs (1.3%)**: lost "not only … but" (3), invented numbers/speakers (4), missing glosses for "undertaker", "chute", "Sandwich Islands" (5), wrong glosses ("quarter less twain", "doughface", "come up to blow", "mile-wide"), a wrong pronoun, a tense slip, and invalid `\'` JSON escapes in ch35. Writer effort `low` showed no quality loss against Wealth of Nations' 5%.
- Tests: `tests/e2e/agent_plain_english_side_by_side.mjs` now includes book 112 (passes for all 4 books), and its footnote check was narrowed from `\[Illustration` to `\[Illustration\b` because Twain's footnote "[Illustrations of it thoughtlessly omitted…" was a false positive. `smoke.mjs` (book and reader), `sxs_row_split.mjs` and `reader_opens_at_chapter.mjs` pass. Screenshot of ch1 Side by Side checked.
- Open: apostrophes left as the source has them (straight `'`), not normalized. Not deployed: needs the DB copy flow in CLAUDE.md or a per-book `chapters` update on the VM.

## 2026-10-18: New flat favicon, open book with gold spark (done locally)

Replaced the detailed illustrated book-and-vines icon with a flat mark: two paper-coloured pages (`#F6F1E7`) on the burgundy accent tile (`#8A2E2E`), with a four-point gold spark (`#D9A441`) above them. The user first picked a plain book (option B), found it too plain, then chose "spark of insight" (option I) from a second round.
- New `frontend/static/images/icon.svg` is the main favicon (`<link rel="icon" type="image/svg+xml">` in `index.html`). Regenerated `icon-16/32/192.png`, `icon.png` (512, header logo) and their `.webp` versions from it with ImageMagick plus cwebp. `icon-180.png` (apple-touch) is full-bleed with no rounded corners because iOS adds its own mask.
- Same filenames, so the manifest and header logo pick up the new mark with no other changes. `asset_v` hashes bust the caches.
- Tests: `tests/test_favicon.py` (3, red then green, including the spark colour); full suite 743 passed; smoke `/` passed; header screenshot checked.
- Deploy: needs a gunicorn restart because `index.html` changed.

## 2026-10-18: Mobile fixes — reader last line, phone header, search bar (worktree `mobile-fixes`)

User reported three iPhone bugs with screenshots.

1. **Reader: last line cut off by the progress footer** (Wealth of Nations, "Of Public Debts", Figtree). Cause: pages were cut before the Figtree web font loaded. When it loaded, the text re-wrapped into more lines and each page's last line slid under the footer. Georgia (system font) was never affected. Fix: `loadContinuousReaderAt()` in `reader.js` awaits `document.fonts.load()` for the content's font before rendering. Test `tests/e2e/reader_last_line_visible.mjs` holds back the font request and checks 50 pages. It failed before the fix (pages overflowed by 1–19px) and passes after.
2. **No Categories or sign-in on phones.** A ≤600px rule hid `#categories-nav-btn` ("also linked from the footer"); that rule is removed. Added a phone-only `Sign in` link to the header (`#header-signin-link`). `updateAuthUI()` handles it together with the footer link. Below 400px the header gap, nav gap and font shrink, so a signed-in Library + Discover + Categories + search + account still fits at 360px.
3. **Search bar covered the breadcrumb.** Below 900px the bar was absolutely positioned over the page. Now it is a full-width row inside the header (`.header-search { display: contents }`, panel `flex: 0 0 100%`, `order: 1`) and pushes the page down. The panel is `position: static`, so the results list anchors to `.header`. If it anchored to `.header-content`, that element's phone `overflow-x: auto` would clip it.
- Test `tests/e2e/mobile_header.mjs` covers 360/402px signed out and signed in: Categories and sign-in visible, no clipping, search bar above the breadcrumb, results unclipped. It failed before the fix and 14/14 pass after.
- Regression: 23 e2e scripts pass. `sticky_overlap.mjs` already fails the same way on main (legacy chapter route timeout); not related.
- Dev note: `backend` is an editable install pointing at the main checkout. To serve a worktree's own code, run Flask with `PYTHONPATH=.`.

## 2026-10-18: Origin of Species remaining Plain English chapters (complete locally)

User resumed chapters 11–14 with Sol writers and fresh Sol verifiers. All **14 chapters now have Plain English**, with **1,264 exactly paired paragraphs**. The 565 alphabetical index paragraphs remain verbatim. No DB backup created; no deployment or commit.

- Completed ch11 (47 paragraphs), ch12 (32), ch13 (66), ch14 (50 prose + 565 index). Used updated shared RULES.md prompts and gates; resumed the saved ch11 draft and copied index chunks rather than discarding them.
- Fresh `gpt-6-sol` reviewers checked every remaining prose pair and mechanically confirmed every index pair. Corrected **18 new-chapter paragraphs**: ch11 P29/P47; ch12 P7/P18/P30; ch13 P17/P23/P24/P39/P48/P50/P51/P59; ch14 P24/P31/P42/P43/P49. No unresolved meaning issues.
- The updated gate flagged 23 pairs in earlier chapters. A separate fresh review (batched with ch12) corrected **7 earlier paragraphs**: ch1 P24/P34, ch6 P27, ch7 P44, ch9 P35/P42, ch10 P37. This restored qualifiers/connectives, plant coverage, and removed filler. The remaining 19 keyword WARNs are faithful equivalents such as “may”, “as well as”, or paired sentences; independently checked and recorded in `continuation_warning_ledger.json` and `continuation_existing_flags_review.md`.
- Normalized apostrophes in 98 paragraphs, then reran the complete apply dry-run and gate. Applied all verified output atomically through the existing helper. Original source hashes stayed unchanged; unaffected chapters 2–5 and 8 retained their existing modern text. All chapters are EXACT, ratios 74–86%.
- Validation: **37 helper tests passed**. Full-book E2E passed (14 checks), including all 1,264 pairs, chapter 11 opening, the final prose paragraph and the index endpoint. Additional API audit confirmed all 565 index entries verbatim; desktop Side by Side and mobile Plain English checks passed for chapters 11 and 14 with no gaps/overflow/console errors. Both book/reader smoke routes, side-by-side pagination and chapter-opening regressions passed. Screenshots inspected.
- Added Origin to the existing full-book E2E; updated scratch `verify_reader.mjs` from partial to complete coverage. Final provenance, review reports and hashes: `data/log/agent_plain_english/book2/result.json` and adjacent files (gitignored). Existing development server was reused and left running.

## 2026-10-18: Agent Plain English: gate, prompt and token improvements (done locally)

Follow-up to the Wealth of Nations run. The user asked for better gates and docs, a separate learnings doc, and lower token use.

- Gate (`scripts/content/passage_rewrite.py`):
  - FAILs "…something. If he…" filler unless the original says "something".
  - WARNs (prints, does not fail) when "therefore", "perhaps" or "not only" has no plain-English equivalent. On the Iliad's finished output: 3 warnings in 1,524 paragraphs, no new failures.
- Export:
  - Writes `$DIR/in/RULES.md` once per book. Chunk files carry only the chapter title, numbered paragraphs and output path. The repeated rules were 39% of prompt text before.
  - The rules gained the mid-run lessons: keep connectives and hedges, short parenthetical glosses, keep `{See …}` braces, no filler, fix scanning errors in names.
- Agent types `.claude/agents/plain-english-writer.md` and `plain-english-verifier.md`: Sonnet, Read/Write/Bash only, brief built in, short reports. `.gitignore` now ignores `.claude/*` except `agents/`.
- Docs:
  - New `docs/agent_plain_english_learnings.md`: cross-book lessons, token analysis, and the per-book notes moved out of the workflow doc.
  - The workflow doc now covers the agent types, ~60–80K characters per agent, sitting planning and the structure check.
  - The CLAUDE.md pointer is updated.
- Tests: `tests/test_passage_rewrite.py`.
  - New: filler fails; "something" in the original is not filler; a dropped connective warns; a kept connective doesn't; the rules state the lessons.
  - The two prompt tests were rewritten for the new spec: the rules live in RULES.md, and a chunk holds only its paragraphs. All failed first.
  - 23/23 pass; full pytest 740 passed.
- Not tried on a real book, at the user's request.
- Later the same day: the writer agent is set to `effort: low` and the verifier to `effort: medium`. The workflow now says to coordinate each sitting in a fresh Sonnet session. Check the effort change against the 5% fix rate on the next book.

## 2026-10-17: Plain English for The Origin of Species (book 2) (partial, stopped at user request)

User requested Sol writers and fresh Sol verifiers in place of Sonnet, following `docs/agent_plain_english_workflow.md`. Later requested wrapping up without starting more chapter rewrites.

- Applied **chapters 1–10 only**: 504 paragraphs, all exactly aligned with their originals. Ratios 76–86%, every chapter passes the mechanical gate and ends at its original narrative endpoint.
- Sol (`gpt-6-sol`) wrote the drafts; separate fresh Sol agents reviewed every pair and corrected 69 paragraphs. Corrections included omitted qualifiers, reversed comparisons, scientific distinctions, first-person voice, and historical claims. No unresolved issues in applied chapters.
- Normalized original paragraph separators in all 14 chapters: 1,264 paragraphs total. No footnotes, illustration tags, or decorative dividers needed removing. Source hashes captured before rewriting and checked unchanged before apply. Apostrophes normalized after review, then all ten apply dry-runs and gates passed.
- User approved scratch files and then requested no DB backup; the already-created task backup was removed. Scratch/provenance/review reports: `data/log/agent_plain_english/book2/` (gitignored).
- **Chapters 11–14 have no applied Plain English.** Ch11 has one unverified scratch chunk (P1–10), ch12–13 are unwritten, and ch14 has only verbatim index-only chunks copied mechanically. The index begins at ch14 P51 and must remain verbatim when resumed.
- Validation: passage/reformat tests **31 passed**; API confirms all 504 completed paragraphs paired and later chapters unavailable; desktop side-by-side and mobile Plain English reader checks, two book/reader smoke routes, side-by-side pagination, and chapter-opening regressions pass. Screenshots inspected. Mobile reader validation uses Plain English (side-by-side requires a 1024px viewport).
- The full-book E2E registration was removed when the scope became partial; scratch `verify_reader.mjs` checks the exact applied range and remaining gaps. Changes are local; no deployment or commit performed.

## 2026-10-17: Plain English for The Wealth of Nations (book 3), plus Book/chapter structure (DB deployed 2026-10-18)

User picked Wealth of Nations first from the hardest-to-read queue. Agent workflow (`docs/agent_plain_english_workflow.md`): Sonnet writers, fresh Sonnet verifiers. No Gemini.

Prep:
- Backup: `data/database.pre-wealth-plain-20261017.db`.
- `reformat_paragraphs.py`: all 32 chapters were one hard-wrapped paragraph each; now 2,271 paragraphs, 2.3M characters.
- `strip_footnotes.py` and `strip_decorative_dividers.py`: nothing to strip.
- Did NOT run `strip_illustration_captions.py`: its 15 hits are real section headings (italic sub-headings in ch.111, `APPENDIX TO BOOK IV`, `PART II. Of the Expense of Justice`) and flattened table rows. Writers keep those verbatim.
- Ingest flattened the tables (ch.111 `PRICES OF WHEAT`, ch.409 salt tables, money totals in ch.502–503) into rows of numbers. They stay verbatim in Plain English.
- Export: 211 chunks. Chapters with more than 6 chunks are split across writers.
- Gate change: `passage_rewrite.py` now accepts a terminator followed by a closing `}`. Smith's paragraphs often end with a citation like `{See Pfeffel.}`. New tests in `tests/test_passage_rewrite.py`: a braced citation passes, and an unterminated one (`{See Pfeffel}`) still fails. The first failed before the change; 17/17 pass after.
- Usage limit: about 17 agents running at once hit the session limit at about 20:50 and stopped 18 agents. They were resumed with `SendMessage` after the 21:20 reset, 8 at a time.
- A second usage limit hit at about 23:00 and stopped 12 agents; they were resumed on 2026-10-18 after the reset.

Writing and verification:
- 48 Sonnet writers (chapters with more than 6 chunks split 2–5 ways) and 49 fresh Sonnet verifier ranges. Shared briefs: `data/log/agent_plain_english/book3/WRITER_BRIEF.md` and `VERIFIER_BRIEF.md`.
- Verifiers fixed 109 paragraphs. The main error types:
  - lost "therefore", "not only… but" and hedges ("perhaps", "seem");
  - reversed meanings (Chinese "own ships"; the East India Company "claim"; the shepherds/hunters direction);
  - invented framing or locations;
  - OCR names left in (Vasco da Gama, Walter Raleigh, Tyrrell);
  - unglossed false friends ("undertaker", "workhouse", "police", "pretty");
  - Spain and Portugal figures stated per country instead of combined.
- A writer habit: a "that"-clause turned into filler ("…noticed something. If he…"). Verifiers fixed some; I fixed the last four by grep.
- Kept verbatim: headings, italic sub-headings, flattened tables (`PRICES OF WHEAT`, salt duties, sums with dotted leaders) and quoted statutes where a verifier judged them quotations. Braced citations `{See …}` are kept with their prose translated.
- Word apostrophes were normalised to ’ (580 paragraphs) to match the source.
- Result: all 32 chapters EXACT, ratio 87–100%, gate PASS.

Structure (user request): the book is now two-level, like the newer books.
- 5 `book_sections` (type BOOK, Smith's Book titles); chapters renumbered 1..34 with `section_id`. Before, the Book was encoded in the chapter number (101..503).
- The Book II introduction had been stuck at the end of "Of the Rent of Land" and the Book IV introduction at the end of ch. 304. Both are now their own "Introduction" chapters (12 and 22), with new short summaries.
- The stray Book III and Book V heading paragraphs at the ends of chs. 205 and 409 were removed. Both text columns moved together, so alignment holds.
- Chapter summaries that said "Chapter 202" now say "Book II, Chapter 2".
- Done with a one-off script (not committed). Backup: `data/database.pre-wealth-sections-20261018.db`.
- The main "Introduction and Plan of the Work" was never ingested and is still missing.

Tests:
- `agent_plain_english_side_by_side.mjs`: new Wealth of Nations entry. It failed before applying and passes after (11/11; the suite is 40/40 across 3 books).
- smoke (book and reader pages), `reader_opens_at_chapter`, `sxs_row_split` pass.
- pytest 734 passed.
- Deployed 2026-10-18 with the DB copy flow. Pre-flight: local had the same or more rows than prod in every table. md5 matched, the service is active, and public `/`, `/books`, `/api/books` and the book page return 200. `agent_plain_english_side_by_side.mjs` against prod passes 14/14. The VM snapshot is `database.db.bak-pre-copy-20261018-171143`.
- Deploy note: DB-only change. Ship with the DB copy flow, or by updating book 3's rows and `book_sections` on the VM.

## 2026-10-17: Figtree replaces Open Sans as the sans reading font (deployed)

User wanted a better sans font. Compared Source Sans 3, Atkinson Hyperlegible Next, Inter, IBM Plex Sans, Nunito Sans and Figtree in a preview page; the user picked Figtree.

Finding: "Open Sans" was never loaded (no `@font-face` or font link), so it showed Helvetica Neue on Apple and Segoe UI/Roboto elsewhere.

Changes:
- Self-hosted Figtree variable font (300–900, SIL OFL) from Google Fonts: `frontend/static/fonts/figtree-latin.woff2` (20 KB) and `figtree-latin-ext.woff2` (10 KB). `@font-face` at the top of `style.css`.
- `data-font="opensans"` → `"figtree"` in `style.css` and `index.html`; label "Figtree".
- `settings.js` `loadReadingPreferences()` rewrites a saved `opensans` to `figtree` (same pattern as the Sepia → Light migration). app.min.js rebuilt.
- New `tests/e2e/reader_font_figtree.mjs` (7/7): picker choices and labels, Figtree applied and actually loaded, saved Open Sans migrated. `sxs_font_regression.mjs` / `sxs_font_other_views.mjs` switch to `figtree` instead of `opensans`.
- Regression: `sxs_font_regression` 8, `reader_themes` 5, `redesign_reader` 16, `text_size_adjust`, smoke pass. `sxs_font_other_views` fails on main before this change too (hardcoded `:5004`, waits for the old `#chapter-detail-section` to be visible); left as is.
- Deploy note: static files only plus `index.html` → needs a gunicorn restart for the template.
- Deployed `52868f6`: VM fast-forwarded, gunicorn restarted (active, no errors). Public `/`, `/books`, `/api/books` and `/static/fonts/figtree-latin.woff2` return 200; `reader_font_figtree.mjs` passes 7/7 against prod.

## 2026-10-17: Home page stuck (no scroll) on iOS Chrome after reader → back (deployed)

User report: the home page couldn't scroll on iOS Chrome, maybe after reader → back.

Cause (reproduced): iOS Chrome's back is an edge swipe from the left.
- The page goes back to home before the finger lifts, and that touch still ends on the reader's now-hidden page area.
- The Kindle-style swipe (deployed today) took it as a completed turn. After the slide it called `navigateToPreviousPage()`.
- Pagination had been cleared by the route change, so the turn went to `navigateContinuousSegment(-1)`.
- Browser back (popstate → `handleRoute`) never marked the reader inactive; only the reader's ← button and `selectBook` did. So the section load re-ran `initializePagination`, which locks html/body (`overflow: hidden`, `pagination-active`) on the home page.

Fix:
- `showOnlySections`: leaving the reader by any route saves (`navigation`) and sets `continuousReader.active = false`. Late reader work (section loads, viewport enforcement) is then a no-op.
- `setupTouchGestures`: a release, or the delayed turn after the slide, does nothing but reset if the page area is no longer on screen (`offsetParent === null`).

Test: new `tests/e2e/reader_back_unlocks_scroll.mjs`. It goes home → reader in-app, then three kinds of browser back: plain, during an edge swipe whose finger lifts after the back, and while a section is still loading. It checks that the home page scrolls. `ENGINE=webkit` runs it in WebKit (iOS's engine); Playwright WebKit was installed for this.
- The edge-swipe case failed before the fix in both Chromium and WebKit (html/body `hidden`, `pagination-active`), and passes after in both.
- Regression: reader e2e suites, `redesign_home` 49/49 and smoke pass; pytest 732 passed. app.min.js rebuilt.

Committed as `b81a69b` and deployed 2026-10-17 as a VM fast-forward only. Front-end only, so no restart: Apache serves static files, and `asset_v` hashes file contents on each render.
- Public `/`, `/books` and `/api/books` return 200. The live `app.min.js` matches local (md5).
- Against production: `reader_back_unlocks_scroll` 3/3 in Chromium and in WebKit, `reader_nav_touch` 25/25.

## 2026-10-17: Sepia theme merged into Light (deployed)

User: Light and Sepia were too similar; merge them. Light is already warm paper (#F6F1E7 with #2B2622 ink); Sepia was #f4ecd8 with #5c4f3d. Kept Light and Dark.
- Removed the Sepia button from the picker in `index.html`; the picker grid now has 2 columns.
- `settings.js`: a saved `reading_theme = 'sepia'` opens as Light and is rewritten to `light`.
- `style.css`: the Light swatch now shows the real paper color instead of white; removed every `[data-theme="sepia"]` rule, the `.theme-preview-sepia` swatch and the `--reading-theme-sepia-*` variables (85 lines). A diff audit confirmed nothing else was removed. My first regex pass also swallowed `.continuous-reader-section` through a comment that mentioned sepia; I restored the file and redid the removal.
- app.min.js rebuilt; PRD theme sections updated.

Test: new `tests/e2e/reader_themes.mjs` (5 checks: only Light and Dark offered, default Light, saved Sepia → Light and rewritten, Dark unchanged). It failed first: 3 checks.

Deployed 2026-10-17 together with the Kindle-style swipe: `kindle-swipe` was merged into main as `4f70ceb` (the WORK_LOG conflict kept both entries; app.min.js was rebuilt from the merged source).
- Combined code: every reader e2e suite passes (`reader_nav_touch` 25/25), and pytest 732 passed.
- On the VM: fast-forward, restart, active, local 200, no journal errors. Public `/`, `/books` and `/api/books` return 200.
- Against production: `reader_nav_touch` 25/25, `reader_nav_mouse` 36/36, `reader_nav_hint` 14/14, `reader_themes` 5/5.

## 2026-10-17: Kindle-style swipe: the neighboring page slides in edge to edge (deployed)

User feedback, with a Kindle screenshot: during a swipe the next page should already be rendered and slide in edge to edge. Before this, only the current page moved, with a blank area behind it, and it was clipped at the text column's edge.

What changed:
- `setupTouchGestures` (`pagination.js`) renders a neighbor page (a copy of the page element holding `pages[current ± 1]`, with anchors and ids stripped, inert) one screen width beside the current page. Both pages translate together.
- A committed turn slides both pages the rest of the way (120–300ms), then navigates, resets and removes the neighbor in the same task, so there is no flash.
- At a section boundary the neighbor is blank until the next section loads (the page stays out of view, with a 3s fallback reset).
- CSS: `.pagination-wrapper.is-swiping { overflow: visible }` and `.pagination-neighbor { position: absolute; pointer-events: none }`.

Test: `tests/e2e/reader_nav_touch.mjs` gains 11 checks, now 25 in all.
- During the drag: the neighbor shows exactly the next (or previous) page, sits one screen width away, is visible at the screen edge (not clipped), and carries no anchors.
- After a turn: only the real page remains, and it shows the same text that slid in.
- The new checks failed before the change. The edge check was confirmed to fail when the wrapper clips. The probe briefly lifts `inert` and `pointer-events` on the neighbor, because `elementFromPoint` skips both.

Worktree gotcha: the shared venv has `backend` installed editable from the main checkout. Flask started in a worktree silently serves the MAIN checkout's code and static files unless started with `PYTHONPATH=<worktree>`.

## 2026-10-17: Reader page-turn controls: mouse first on web, swipe first on mobile (deployed)

User asked for better left/right navigation. On mobile the arrow circles flashed over the text on every touch; on web there was no sideways trackpad swipe and the arrows faded 1s after the mouse entered.

Agreed plan (controls chosen by input device, `(hover: hover) and (pointer: fine)` vs touch, not by width):
1. Web: full-height click strips in the margins beside the text, faint at rest and full on hover, never over text (a minimum margin is kept on narrow windows). Scroll wheel unchanged; add sideways trackpad swipe, Space/Shift+Space, PageUp/PageDown.
2. Mobile: no visible buttons and no flash on touch; the buttons stay for screen readers only.
3. Mobile: the page follows the finger and snaps forward/back.
4. A once-per-account hint (`user_hint_seen` table, keys `reader_swipe_mobile` and `reader_nav_desktop`); signed-out readers use localStorage.

What changed:
- `pagination.js`:
  - The nav buttons have no auto-hide timers or flash-on-touch any more.
  - The wheel handler uses the dominant axis, so a sideways trackpad swipe works like the wheel.
  - New keys: Space/Shift+Space and PageUp/PageDown. Space is ignored when a button has focus.
  - New `pageTurnAvailability()` (shared by the buttons and the swipe).
  - `setupTouchGestures` now moves the page with the finger: it turns past 25% of the width or on a flick, otherwise snaps back, with resistance at the book's ends.
  - New `showPageTurnHintOnce()`.
- `style.css`:
  - Touch: the buttons are hidden at 1px (kept for screen readers).
  - Mouse: full-height 64px margin strips, and the text column always leaves room for them.
  - `overscroll-behavior-x: none` stops a trackpad swipe from going back/forward in the browser.
  - Hint pill and nudge styles, with a dark-theme pill and reduced-motion support.
- `auth.js`: new `hintSeen` / `markHintSeen`. A hint is seen if the account or this browser has seen it.
- Backend:
  - New `user_hint_seen` table and `get_seen_hints` / `mark_hint_seen` in `user_models.py`.
  - New `POST /api/hints/<key>/seen` in `progress_routes.py` (login required, 400 for unknown keys).
  - `/api/auth/check` returns `hints_seen`.
- app.min.js rebuilt. PRD and ERD navigation sections rewritten.

Bug found while testing: the reader rebuilds its page wrapper about 250ms after opening (and on resize). A hint attached to the wrapper vanished about 40% of the time.
- Fix: the hint attaches to the reader section, and the nudge is a class on the section that targets the page with a descendant selector.
- Two test scenarios reproduce it (a rebuild during the sign-in check, and one after the hint shows). Both failed before the fix.

Tests (each failed first for the missing behavior):
- New `tests/e2e/reader_nav_mouse.mjs` (36 checks), `reader_nav_touch.mjs` (14), `reader_nav_hint.mjs` (14; 8 runs in a row clean) and `tests/test_user_hints.py` (6).
- The touch test's button checks were confirmed failing on the pre-change code with `git stash`.
- One test parameter was mine and inconsistent with the agreed 25% rule (a 120px "short" drag is 31% of 390px), so I changed it to 80px.

Regression:
- pytest 732 passed.
- Reader e2e suite, smoke and side-by-side tests pass.
- Pre-existing failures, also failing on the pre-change code: `chapter_view_default.mjs` (legacy chapter page default mode) and `sxs_font_other_views.mjs` (hardcoded port 5004).
- Not tested on a real iPhone: Safari's own edge-swipe and text-selection behavior still need a check on the device.

Note: the PRD's old "page turns must be instant (no animations)" rule now applies to mouse and keyboard only. A touch swipe finishes with a 150ms slide.
- Deploy needs a gunicorn restart (backend and template-adjacent changes). The new table is created by `UserDatabase.init_db` on boot.

Deployed 2026-10-17 (`92e882e`), code only, no content DB copy.
- The VM fast-forwarded and the service restarted: active, local 200, no errors in the journal. `user_hint_seen` exists in `/opt/summra/data/summra.db`.
- Public `/`, `/books` and `/api/books` return 200.
- Against production: `reader_nav_mouse` 36/36, `reader_nav_touch` 14/14, `reader_nav_hint` 14/14. These stub sign-in and the hint POSTs, so nothing was written to prod.

## 2026-10-17: Reader text hidden under the toolbar on iPhone (deployed)

User report (iPhone Safari, Iliad Introduction): the top lines of the page sat under the reader toolbar, with an empty band above the footer. This is the same mechanism as the 2026-05-31 fix for the old chapter page (the `body { min-height: 100svh }` note in style.css), brought back by the continuous reader. The document had scroll slack:
- `.continuous-reader-section` used `min-height: 100vh`, which on iOS is the large viewport (toolbar collapsed), taller than what is visible;
- the site's `.main-content` added `padding-bottom: 40px` below the full-height reader.

The toolbar and footer are fixed, so a swipe (or iOS settling into the slack) slid the page up under the toolbar. In Chromium the slack was exactly 40px at every size.

Fix:
- The reader section uses `100svh`.
- New body class `on-reader-page`, set in `showOnlySections` and in the template for direct chapter and `/read` loads, removes the `.main-content` bottom padding on the reader only. The summary page also has `on-chapter-page`, still scrolls, and keeps its padding.
- app.min.js rebuilt.

Test: new `tests/e2e/reader_no_scroll_slack.mjs` (10 checks).
- iPhone 13 and desktop, plain and side by side: no slack, `scrollTo` leaves `scrollY` at 0, the first line stays below the toolbar.
- The summary page keeps its 40px padding.
- The slack and scroll checks failed before the fix (slack 40, scrollY 40).

Regression run:
- Reader e2e suite passes. `reader_progress` timed out once on a page load, then passed twice in a row (7/7).
- Smoke passes, JS 31/31.
- Not run in WebKit here: Playwright's WebKit build doesn't match the installed one. Needs a check on the iPhone.

## 2026-10-17: Backup cleanup (done)

User asked to clean up the backups. Following CLAUDE.md (keep at most the last 1–2), I kept the newest backup on each side and deleted the rest.
- VM: deleted `database.db.bak-pre-slim-20261016-194322` (1.2GB) and `database.db.bak-pre-iliad-plain-20261017-065722`. Kept `database.db.bak-pre-happyprince-plain-20261017-151640`. Also removed the deploy temp files in `/home/pengyao`. Disk use went from 8.7G to 7.4G.
- Local: deleted `data/database.pre-verse-20261015.db` (734MB) and `data/database.pre-iliad-plain-20261016.db`. Kept `data/database.pre-happyprince-plain-20261017.db`.
- Prod `/` returns 200 afterwards.

## 2026-10-17: The Happy Prince (book 105) Plain English, Sonnet writers + fresh verifiers (deployed)

First book under the new rule: a Sonnet subagent writes each chapter, and a separate, fresh agent verifies it.

**Cleanup.** Local backup: `data/database.pre-happyprince-plain-20261017.db` (SHA-256 `9dfaacfdcc8f0f06…`).
- `reformat_paragraphs` (5/5 chapters).
- `strip_illustration_captions --tags-only`: 12 `[Picture: …]` tags and 1 trailing "Printed by BALLANTYNE…" line.
- `strip_decorative_dividers`: 1 divider.
- `--tags-only` now covers `[Picture` tags, and drops trailing notes including "printed by"; two new tests failed first.
- Result: 397 paragraphs in 8 export chunks.

**Writing and verification.**
- 5 Sonnet writers (one per tale) all passed the gate.
- 5 fresh Sonnet verifiers made 7 fixes: an invented "merchants", the dropped "lips", the "affected" pun, a quote mark in the Linnet's story-within-a-story, and wording. The Iliad's Haiku drafts needed 317.
- The usage limit stopped the verifiers once; they were resumed after the reset.

**Result.**
- Applied: all 5 EXACT, ratios 96–99%.
- `tests/e2e/iliad_side_by_side.mjs` became the data-driven `agent_plain_english_side_by_side.mjs`, with one `BOOKS` entry per book. Book 105 failed it before apply and passes after; 27/27 checks for both books.

Deployed 2026-10-17 with the user's OK, the same way as the Iliad. Only Book 105's 5 `chapters` rows were copied.
- The VM rows first hashed identical to the local pre-change backup (`52e8ad60…`).
- VM backup: `/opt/summra/data/database.db.bak-pre-happyprince-plain-20261017-151640` (SHA-256 `736ba702…8271`).
- The update ran as `summra` and matched local. `ensure_reader_content(105)` published version 4.
- The VM fast-forwarded to `c7ab432`; no runtime code changed, so no restart.
- Public `/`, `/books`, `/api/books` and the book and `/read` pages return 200. Against production, `agent_plain_english_side_by_side.mjs` passes 27/27 for both books.

## 2026-10-17: Reader settings icon: "Aa" instead of the gear (deployed)

User: the gear icon in the reading view looked odd. It was a hand-traced gear whose teeth blurred into a blob at 20px. Replaced it with Lucide's `a-large-small` "Aa" glyph (ISC licence): the usual reading-settings icon in e-readers, drawn in the same 2px stroke as the Contents icon. Template-only change (`frontend/templates/index.html`). Test: `redesign_reader.mjs` checks for the Aa paths and the label; it failed before the change, and all 16 checks pass after. Checked in light and dark screenshots.

## 2026-10-16: Reader: chapters start a new page; Side by Side shows chapter headings (deployed)

User asked to fix the two behaviours I had reported as by design after the Iliad work.

Root causes:
1. **Wrong chapter after opening one, or after a mode switch.** Pagination packed chapters back to back, so the page holding chapter N's heading usually began with the end of chapter N-1. The reading position is the page's first paragraph. So opening Book II put the title bar on "Book I", and switching to Side by Side mapped a Book I (or Introduction) position, landing on the end of the previous Book. Journey to the Centre of the Earth had the same wrong title.
2. **No chapter headings in Side by Side, in any book.** Its pagination selector took only `.side-by-side-row, figure.reader-illustration`, so the `h2.reader-chapter-heading` the renderer emits was dropped.

Fix (`frontend/static/js/pagination.js`, app.min.js rebuilt):
- The page ends before each chapter heading.
- Side by Side paginates the heading.
- The old keep-heading-with-next rule became dead code and was removed.

Including headings exposed a latent measuring bug: the measuring page got the container's computed `line-height: 28px` while live text inherits the unitless 1.75. A 25.6px heading therefore measured 16.8px short, and Iliad Book I's Side by Side page overflowed by 7px. The measuring page now gets the ratio.

Tests: new `tests/e2e/reader_chapter_starts_page.mjs` (10 checks): pages open with the heading, the title bar names the opened chapter (Iliad, Journey), a switch to Side by Side at Book I stays at Book I, Side by Side shows headings (Frankenstein), and paging from Book XIX starts Book XX on a new page. 9 of 10 failed before the fix; the 10th errored before. `iliad_side_by_side.mjs` now expects the heading, and its overflow check caught the line-height bug.

A 30-page sweep of plain, original and side by side in three books found no overflow, no text-less page and no heading below text. Reader e2e: 13 of 15 pass. `chapter_header_hidden` and `sxs_font_other_views` fail identically with the change stashed, because they wait for the retired `#chapter-detail-section`. JS 31/31; pytest 724.

## 2026-10-16: The Iliad (book 66) Plain English by Haiku subagents, Sonnet QC (done, local only)

Goal (user): write the Iliad's Plain English with Haiku subagents instead of Gemini, using the generator's own prompt (`build_single_chapter_prompt` in `generate_modern_english.py`); quality-check with Sonnet subagents; make side-by-side work; then document the process in its own file for other books.

State found: Pope's translation (pg6130), `is_poetry=0`, 25 chapters (0 = Introduction + Pope's Preface, 1–24 = Books). Paragraphs are separated by single `\n` (verse lines were flattened into one line per verse paragraph at ingest). There are 46 `[Illustration: ]` caption lines, inline footnote markers `[n]`, and all 300 endnotes appended to Book XXIV. No Plain English yet. Local DB backup: `data/database.pre-iliad-plain-20261016.db` (SHA-256 `3759746e…79d0`).

Plan: (1) clean the original with the standard steps (reformat paragraphs, strip captions, strip editor footnotes); (2) export per-chunk prompts and have Haiku write one Plain English paragraph per original paragraph; (3) mechanical gate; (4) Sonnet QC per chapter; (5) apply, audit, verify side-by-side; (6) write the process doc.

Direction from the user mid-task: follow the app's prose workflow, not the Paradise Lost verse-passage approach, and give the agents the instructions of the Gemini generator script. So the original stays as flattened paragraphs (`is_poetry` stays 0). The Haiku prompts are built by `ModernEnglishGenerator.build_single_chapter_prompt` (made a `@staticmethod`), with numbered `[P#]` paragraphs and a JSON output section added.

**Cleanup (original side).**
- `reformat_paragraphs.py` changed all 25 chapters to `\n\n` paragraphs.
- New `scripts/audits/strip_footnotes.py` removed 300 `[n]` markers, plus 461 endnote paragraphs appended to Book XXIV.
- New `strip_illustration_captions.py --tags-only` removed 71 `[Illustration: ]` lines. The default caption rules would also have deleted the headings `ARGUMENT`, `A. POPE`, `END OF THE ILIAD` and the Preface title.
- Result: 1,524 paragraphs, 987K characters.

**Writing.**
- `passage_rewrite.py export` cut the chapters into 98 chunks of about 12K characters.
- 26 Haiku agents (one per Book, two for the Introduction and Preface) wrote JSON per chunk and ran the gate.
- The gate gained three relaxations, each test-first:
  - a verbatim heading needs no terminator;
  - `._` (italics) counts as a terminator;
  - a summary phrase passes if the chapter's original uses it (the Preface says "the poet").

**QC.**
- The new `review` command pairs paragraphs for review. 26 Sonnet agents fixed 317 paragraphs, 5–22 per Book.
- Most fixes were swapped speakers or agents, reversed meanings ("I doubt not" had become "I doubt that"; curses and counterfactuals inverted), wrong genealogy, invented details, and text the writer admitted it compressed.
- Apostrophes were normalized to curly `’` (155 paragraphs).
- The account's usage limit stopped the run once. Agents were resumed with SendMessage; nothing was lost.
- Several reviewers shared a scratchpad `fix.py` and overwrote each other's. Their asserts failed before any write; I checked the fixes landed in the right chapters and found no duplicated paragraphs.

**Result.**
- `passage_rewrite.py apply`: all 25 chapters EXACT, ratios 94–107%.
- Reader manifest: side by side has 1,524 units, equal to the original's.
- New `tests/e2e/iliad_side_by_side.mjs` (14 checks) passes. It walks every segment (both sides present, Book I opens with ARGUMENT on both sides, ends with END OF THE ILIAD, no footnotes or tags) and opens `/read?mode=side_by_side&chapter=<Book I>` (paired rows, no gaps, no overflow, no console errors).
- 40 consecutive pages show no clipping.
- Smoke on `/books/the-iliad` and `/read` passes, as do `sxs_row_split`, `reader_opens_at_chapter`, `redesign_reader` and `sxs_page1_has_rows`.
- pytest: 724 passed.

Two reader behaviours I checked and left alone (by design, documented):
- switching modes keeps the first-on-page position, so switching to side by side from the top of a Book shows the end of the previous one;
- side by side renders no chapter headings, in any book.

Process doc for other books: `docs/agent_plain_english_workflow.md`.

Deployed 2026-10-17 together with the reader fix (commit `7543bb4`): pushed to main and fast-forwarded the VM. No restart; backend Python was unchanged.
- Database: only Book 66's 25 `chapters` rows. The VM rows first hashed identical to the local pre-change backup (`6f039487…`).
- VM backup: `/opt/summra/data/database.db.bak-pre-iliad-plain-20261017-065722` (SHA-256 `b209fb22…571e`).
- The rows were updated in one transaction as `summra` and verified equal to local. `ensure_reader_content(66)` published version 4: 1,524 units in original, plain and side by side.
- Public `/`, `/books`, `/api/books`, `/books/the-iliad` and `/read` return 200. The served app.min.js contains the fix.
- Against production, `iliad_side_by_side.mjs` passes 14/14 and `reader_chapter_starts_page.mjs` 10/10.

User feedback after review: Haiku left too many gaps. From now on a Sonnet subagent writes and a separate, fresh agent verifies (process doc and CLAUDE.md updated).

## 2026-10-16: Home page calmer below the hero (option A; deployed)

User feedback: the hero is good, but below it the page changed background too often (dark hero, tan, paper, dark), and "Find a book at the right level" carried too much information (four cards, four explanation blocks, a footnote). I showed three mockups (A quiet paper, B level tabs on the shelf, C level strip) and the user picked A.

Changes: everything below the hero sits on one `--paper` background, separated by a rule above each later section's heading (`.home-section:not(.hidden) ~ .home-section`). Removed `.home-band--deep`, `.home-band--ink`, `.grade-cards-label` and `--paper-band`. The levels section is now one line, four cards with short descriptions, and a "How we grade books →" link (about 400 words down to about 60). The four level notes and the Flesch–Kincaid footnote moved to a collapsible `<details id="how-we-grade">` on Discover. The Discover intro link now points there instead of `/#reading-levels`. `revealHowWeGrade()` in app.js opens and scrolls to the panel on `/discover#how-we-grade` and on hashchange. Rebuilt app.min.js.

Tests: the spec changed, so I rewrote the old home tests. In `tests/test_home_redesign.py`, "levels section explains its sources" became "levels section is short (<80 words), has no ATOS/Flesch/Common Core, and links to how-we-grade", plus "How we grade on Discover explains its sources". In `tests/test_plain_english_levels.py`, the live Plain English count now checks the Discover panel. In `tests/e2e/redesign_home.mjs`, "neighbouring sections differ in background" became "sections below the hero share one light background", and I added "How we grade opens on Discover, scrolled into view". Each failed before the change. 707 pytest pass; redesign_home (40), redesign_discover (27), redesign_chrome (26), footer_check (5) and the smoke checks pass.

Follow-up, same day: fixed the four issues noticed above.
- **"0%" on continue cards:** not a calculation bug. The percentage comes from the furthest marker, which only advances when you page through in order (`reader.js` qualifies it on sequential boundaries), so books opened and jumped around in have none. Tracking is unchanged. Cards with 0% now say "Just started" in place of "Continue reading", with no bar and no number.
- **Loose mode label:** the reading mode joins the location line ("Marley's Ghost · Plain English"; labels Plain English / Original / Side by side / Summary), and `.library-card-mode` is gone.
- **Uneven buttons:** the bar and button sit in `.library-card-foot` (`margin-top: auto`), so buttons line up across a row.
- **Start here left arrow:** disabled carousel arrows are `visibility: hidden` rather than faded (this applies to every carousel), and the shelf's left arrow starts disabled in the HTML.
- **Reading time wrapping:** `.book-card-time` always takes its own line under the tags, because "Original: Grade 10" plus "15½ hrs" was 6px wider than a 168px card.

Both card renderers changed together (`library_card()` in `_book_card.html` and `renderLibraryCards()` in reader.js), and I rebuilt app.min.js.

Tests: new pytest `test_continue_card_without_progress_says_just_started`. New checks in `redesign_home.mjs`: card progress label, Just started, mode on the location line, no loose label, buttons aligned, back arrow hidden at the start and shown after scrolling, and reading time on its own line at 1280 and 375px. All failed first (I fixed the arrow check's threshold after it falsely passed at 30% opacity). 708 pytest pass; redesign_home (49), redesign_cards, redesign_discover, reader_progress, redesign_book_page, redesign_chrome and smoke on / /discover /library pass.

Deployed 2026-10-16: commit `1061abe` pushed to main. On the VM I fast-forwarded and restarted the service (no backend code changed; I restarted only in case gunicorn had cached the templates). The service is active with no log errors. Public `/`, `/books`, `/api/books` and `/discover` return 200 in under 0.3s, and smoke passes against production. The home page has the new layout and Discover has the `#how-we-grade` panel.

## 2026-10-16: Single-copy reader storage (done locally)

Goal: keep book text once, in `chapters`. The user approved all four steps with no backward compatibility (no real users).
Plan: (1) keep no retired reader versions; (2) drop `books.full_text`; (3)+(4) replace the eight `reader_*` tables, which hold a second text copy, normalized quotes, UUID-text keys and history, with `reader_version` (one row per book) and `reader_unit`. `reader_unit` has integer keys, word counts and segment numbers, and no text. Segment text is re-split from `chapters` on request by the same function the compile step uses. Unit IDs are `<chapter_id>.<chapter_ordinal>`; side-by-side pairs by position. Recovery uses the marker's own quote, then its ordinal. The API shape for the frontend is unchanged. VACUUM after the migration.

Result: the eight `reader_*` tables became `reader_version` + `reader_unit` (no text; see ERD). `books.full_text` was dropped, and `regenerate_medium_summary.py` now joins chapter text. Local DB: 746MB → 159MB after VACUUM (`chapters` 132MB, reader index 32MB); compiling all 90 books takes 7.6s. The API shape is unchanged; IDs are now `<chapter_id>.<ordinal>` and segments `<mode>.<n>`. Recovery: quote within the chapter, then position; this also applies when the version matches but the ID doesn't resolve. The migration continues each book's version numbering from the old table so pre-migration markers read as stale (unit test covers it).

Tests: new `tests/test_reader_storage.py` (10; each failed before). Existing route and database reader tests pass unchanged. One fixture change: `tests/e2e/reader_stale_marker_and_long_paragraphs.mjs` marker `content_version` 1 → 0. Its premise ("older than the published version") stopped holding once local versions restarted at 1; with 0 it again passes through server quote recovery with an old-format ID. 705 pytest, 31 JS, the reader e2e suite (11 scripts) and smoke all pass.

Deployed 2026-10-16: commit `fd76c85`. On the VM I stopped the service, backed up to `/opt/summra/data/database.db.bak-pre-slim-20261016-194322` (1.2GB), fast-forwarded, and ran the migration once by hand rather than letting several gunicorn workers race on DROP COLUMN. I then compiled all 90 books (24s, none skipped), ran VACUUM with `SQLITE_TMPDIR` on the data disk, and started the service (active, no log errors). VM DB: 1,223MB → 160MB. Version numbering continued (Paradise Lost 3 → 4). Public `/`, `/books`, `/api/books`, Paradise Lost book and read pages, Tess read page and the manifest return 200 in under 0.5s. Segments take 0.14–0.22s. On production in side-by-side, Paradise Lost (26 pages) and Tess (30 pages) have no overflowing pages.

Backup cleanup 2026-10-16: deleted VM `database.db.bak-pre-verse-20261016-070637` and local `data/database.pre-slim-20261016.db` (already migrated, misnamed). Kept: VM `database.db.bak-pre-slim-20261016-194322` (pre-migration, 1.2GB) and local `data/database.pre-verse-20261015.db`.

Local caveat: the Flask dev server auto-reloaded on the `models.py` edit and ran the migration before I took a backup. So `data/database.pre-slim-20261016.db` (746MB) is already migrated, just not vacuumed; it is not a pre-migration copy and can be deleted. The real pre-change local copy is `data/database.pre-verse-20261015.db`. Local had no old versions left to seed, so local versions restart at 1.


## 2026-10-16: Side-by-side columns fill each page independently (done, local only)

User report: a split Paradise Lost row left the Plain English stopped mid-sentence ("who led the") above blank space. Cause: `splitSideBySideRowToFit()` cut both columns at the same fraction of their text, so the shorter column ended early. Now each column is filled independently to the largest prefix that fits and continues on the next page; a column that runs out leaves later cells empty. Removed `sentenceCut()` (no longer used). Changed the requirement in `tests/e2e/sxs_row_split.mjs`, since the user changed the spec: "columns stay in step" became "plain column fills every page it continues from" and "shorter column finishes first". The fill check failed before the fix (gap of about 560px on every page). Also corrected the test's re-measuring box to match the paginator's (the header band included; real container width 900px instead of a nominal 1100px). Both mismatches had shown the same false gap in both columns. Results: sxs_row_split passes, the reader e2e suite (9 scripts) passes, and on local Paradise Lost both columns end on the same line.

DB size question (investigated, nothing changed): the VM's `database.db` is 1.2GB because `_compile_reader_content` keeps every retired reader version. The VM has 78 retired versions, holding 372K `reader_paragraph` rows (110MB of text plus `normalized_quote`, plus indexes), against 12 locally. `reader_paragraph` alone is 523MB on the VM. Pruning has to keep whatever saved-place recovery still reads.

## 2026-10-16: Side-by-side page splitting fixed; Paradise Lost verse passages and new Plain English (done, local only)

Local DB backup before changes: `data/database.pre-verse-20261015.db` (SHA-256 `9af13ce42d9d4d20aed688162848a75e972774755c701389a876e57569868cf1`).

**Side-by-side text loss (all books).** Three causes in `frontend/static/js/pagination.js`:
1. The row split searched one column while keeping the other whole, so a row taller than the page never found a fit, was force-placed, and was clipped by `overflow: hidden` (Tess preface).
2. Measuring pages were appended to `<body>`, outside `.continuous-reader-section`, so its row padding and border (~30px per row) were missing. The header banner's height was also subtracted from a box that still displays the banner. Live pages ran 20–160px taller than measured on every Tess page.
3. Rows split only at the top of a page, cut both columns at the same word count, and lost `<em>`.
Fix: `textUnits()`/`sliceUnits()` cut at word starts (or line breaks for verse) with a DOM Range. The row split is proportional (the column with more units drives; each cut snaps to a nearby sentence end) and fills partly used pages (needs at least 3 lines). Measuring happens beside the live page, with the banner inside the box. Test `tests/e2e/sxs_row_split.mjs` (each case failed before): huge row with no overflow and every word once, drift 1.2%; a long row starts under a short one; verse splits between lines; first 8 live Tess pages fit.

**Paradise Lost (book 102).** The source (pg26) has no verse-paragraph breaks, and the old Plain English was unusable (Book I a 5% summary; four Books a single paragraph). `scripts/content/segment_verse_passages.py` grouped the 10,566 lines into 518 passages (about 20 lines each, ending at sentence ends). The reader now splits `is_poetry` originals on blank lines and keeps line breaks (`_reader_split_paragraphs(text, verse)`; `.reader-verse` rendering). All old Plain English was discarded (user's call). Twelve Haiku subagents, one per Book, rewrote it one paragraph per passage; no Gemini calls. Gate `scripts/content/passage_rewrite.py check` (exact count, one line each, ends at a terminator, per-passage ratio 0.5–1.3, chapter 0.50–1.10, no summary language) passed on all 12. CLAUDE.md audit: all 12 Books show EXACT, ratios 104–109%. Spot-checked I.1, IX.57, XII.34 against the verse: complete and faithful. Haiku reports speeches crossing passage breaks use open-quote-per-paragraph; some books (II, IX, X, XI) note the quote marks at those boundaries are not fully consistent.

Tests: `test_segment_verse_passages.py` (8), `test_reader_verse_passages.py` (4; I corrected one expected word count I had miscounted, 20 → 19), `test_passage_rewrite.py` (8; written with the script rather than failing first). 695 pytest passed; 31 JS unit tests pass; reader e2e suite (10 scripts) and smoke on `/`, Paradise Lost and Tess read pages pass. Not deployed; the prod DB needs the local DB copied (deploy step 4) for the new Paradise Lost text.

Known cosmetic issue: a split row still shows its bottom rule at the page cut.

Deployed 2026-10-16: commit `412dc68` (this section plus the published-reading-level change above) pushed to GitHub `main`, fast-forwarded on the VM, service restarted (active). Database: the VM's `reader_*` tables hold 61 more content versions than local (163 vs 102), which saved reading places map through. So instead of copying the whole local database, I updated only Paradise Lost's 12 `chapters` rows (`chapter_text`, `modern_english_text`). First I confirmed each VM row's text hashes matched the local pre-change backup. Then `ensure_reader_content(102)` published version 3 (id 164) from the VM's own history. VM backup: `/opt/summra/data/database.db.bak-pre-verse-20261016-070637` (SHA-256 `d4c2a6ef6a5cb52f52f1c4aa5a3abf7872ac323673208e8213270884f744c4de`). Public `/`, `/books`, `/api/books`, the Paradise Lost and Tess read pages, and the reader manifest return 200 in under 0.6s (one transient connection timeout, then 3/3 OK). On production in side-by-side, Paradise Lost (27 pages) and Tess (31 pages) have no overflowing pages, and verse passages pair with their Plain English.

Backup cleanup 2026-10-16: deleted the older database backups. VM: `database.db.bak-pre-continuous-reader-20260907-153504`, `database.pre-audit-20261013.db`, `database.pre-redesign-20261015-055245.db`. Local: `data/database.pre-audit-20261013.db`. The rollback backups named in the 2026-10-13 and earlier entries no longer exist. Kept: VM `database.db.bak-pre-verse-20261016-070637`, local `data/database.pre-verse-20261015.db`.

## 2026-10-15: Published reading levels only; ATOS re-check (local, not committed)

Problem: cards mixed "Original: Grade 8" (published ATOS) with "Original: Moderate" (a fallback from `books.cefr_level`). Those CEFR values are estimates from `scripts/migrations/add_cefr_levels.py`; no authority publishes CEFR levels for unabridged classics (only for graded-reader adaptations).

ATOS re-check: searched Renaissance AR BookFinder (Parent view) for all 25 books without an ATOS level, by title and by author. Result: 0 new levels; the earlier pass (`data/metadata_audit/atos_part*.json`) was correct. Near-misses, all rejected as different texts: Monte Cristo (Abridged) 8.8; "The Happy Prince" single story 6.9; A Room with a View in Spanish only (7.1 SP); The Man in the Iron Mask (Unabridged) 10.2, a different part of the Bragelonne romance; Origin of Species only as adaptations. AR has no Chesterton, Nietzsche, Gaskell, Smollett, Le Fanu, Radcliffe, Gibbon, Milton, Adam Smith or J. S. Mill entries.

Lexile (hub.lexile.com Find a Book): 5 free searches/month without an account. Sampled 2: neither Cranford nor The Man Who Was Thursday is listed. Lexile codes poetry/plays NP (non-prose), so Paradise Lost would get no number either.

Change: a level tag only when a published ATOS grade exists. Removed the CEFR fallback from `difficulty_tag` (`_book_card.html`) and `difficultyTagHtml()` (`app.js`), and the now-unused `.level-tag` CSS (color tokens kept; `.grade-tag` uses them). The API still returns `level`. Tests: `test_no_level_tag_without_a_published_grade` (book page + Discover card); `tests/e2e/level_tag_published_only.mjs` (client card). Updated `test_meta_row_is_server_rendered`, which asserted the removed fallback ("Original: Challenging"). 675 pytest passed; card/Discover/home/book-page e2e and smoke pass. PRD/ERD noted.

California: the CDE Recommended Literature List (cde.ca.gov/ci/cr/rl/) assigns recommended titles to grade spans; spreadsheets (through 2021, 2.2 MB; 2022–2025 updates, ~100 KB each) not yet downloaded — awaiting approval.

## 2026-10-15: Fix shared CI test dependencies

Inspected Actions runs 38846708355, 38846646556, 38749488277, and
38749293749 (commits ce4f27a, daf6ee5, f288f96, 4bb8321). All fail
on the same four tests: three chapter-numbering tests initialize Gemini with
an empty key; the curated hero audit runs against the empty database created
by app imports on a clean checkout. These are test isolation failures.

Chapter-numbering setup now mocks Gemini and Database, following the existing
summary-test pattern. The real-content audit has an explicit `content` marker,
excluded by default and selectable with `pytest -m content`. Fixture-backed
hero rendering and pairing tests remain in the default suite. README documents
the audit command. No application behavior or CI secrets changed.

Verification: focused modules pass (18 passed, 1 deselected); explicit content
audit passes against the local curated database; `npm run build:check` passes.
Full suite with `.env` loading disabled and Gemini/Google API keys unset:
674 passed, 2 deselected (slow + content), on local Python 3.14. Network access
was required for the existing Gutenberg checks; the sandbox-only run passed
666 tests and failed those eight network checks. GitHub uses Python 3.11; a
new Actions run after pushing remains the hosted confirmation.

## 2026-10-15: Repeated poetry chapter headings fixed locally

Confirmed Paradise Lost source has one chapter title per book and no embedded repeated Book I headers. `renderContinuousSegments` incorrectly inserted a chapter heading and illustration at the start of every loaded segment, even when its first unit was mid-chapter. Poetry makes this especially visible because each verse line consumes one reader unit. Now only chapter ordinal zero emits chapter-start content. Added a regression in the existing manifest test file covering ordinals 0, 80, and 160; confirmed failure before the fix and four passing tests afterward. Rebuilt app.min.js; all 31 JavaScript tests pass. This fixes repeated chapter starts, independently of the passage-alignment/content quality work above. Not deployed.

## 2026-10-15: Reader loading skeleton (done, local only)

Before: opening a book showed a bare "Opening book…" line under the reader header (cold manifest ~1.2s locally). After: `showContinuousReader()` in `frontend/static/js/reader.js` renders a pulsing skeleton of the reading column (title bar + three paragraphs of lines) if the open takes over 250ms; cached opens show nothing. The skeleton carries `role="status"` / `aria-label="Opening book…"`. The `#reader-status` line now appears only for errors and the recovery notice; failures that occur mid-load stay visible instead of being hidden when loading ends. Removed the now-unused `recoveryNotice` field. Test: `tests/e2e/reader_loading_state.mjs` (slow open shows skeleton, then text; fast open never flashes it). Reader e2e tests pass.

## 2026-10-15: Smoke failure on the reader — stale-place recovery and paginator cutoff (done, local only)

`smoke.mjs` failed on `/books/paradise-lost/read` with two bugs.
1. Saved-place recovery 404. The `/api/progress/v2` projection stores markers per mode without a `mode` field. `recoverContinuousMarker()` sent them as-is, and `recover_reader_marker()` returns `None` without a mode. A place saved against an older content version (Paradise Lost v1 → v2) was therefore rejected and the reader fell back silently. Fix: the client sends `{ ...marker, mode }`, as `mapContinuousMarker()` already did.
2. Paginator cutoff. `calculatePages()` capped its loop at 3× the initial block count. Split remainders are spliced into `blocks`, so a segment with a few very long paragraphs (Paradise Lost's summary-shaped Plain English) needed more pages than the cap, logged `INFINITE LOOP DETECTED`, and dropped the rest of the segment. Fix: the cap is re-read against the current `blocks.length`. Each split keeps at least one word on the page, so the loop still terminates.

Test: `tests/e2e/reader_stale_marker_and_long_paragraphs.mjs` (stubs auth/progress, so it never writes local reading state). Each half failed before its fix. `smoke.mjs` now passes on `/`, `/books/paradise-lost/read`, and Journey to the Centre of the Earth `/read`. Reader e2e suite passes. 

Follow-up: ported `tests/e2e/sxs_font_regression.mjs` to the continuous reader. It defaulted to port 5004 and waited for `#chapter-detail-section`, which `/chapters/N` no longer shows. It now opens `/books/a-christmas-carol-in-prose/read` on :5001 with auth stubbed anonymous (no progress writes), picks Side-by-Side from Reading settings, and switches font. The row-count regex now matches `side-by-side-row reader-alignment-row`. Two new assertions keep it from passing vacuously: `data-font` changed, and `pagination.pages` was rebuilt. Result: 28 pages before and after, 8/8 assertions pass. `sxs_font_other_views.mjs` has the same stale chapter-page setup and was not changed.

Deployed 2026-10-15: commit `daf6ee5` (this section, the loading skeleton, and the verse-heading fix) pushed to GitHub `main` and fast-forwarded on the VM. Static-only change, no restart. Public `/`, `/books`, `/api/books`, `/books/paradise-lost/read` returned 200 in under 0.5s; the served page references `app.min.js?v=1596262923`, matching the local bundle's hash, and the served bundle contains the skeleton code.

## 2026-10-15: Poetry comparison investigation — Paradise Lost

Investigated local `data/database.db`, book 102, all twelve books of the poem, and the continuous reader compiler/rendering. Current alignment in `backend/models.py` treats every nonempty source line as a paragraph, then zips original and plain paragraphs by ordinal. Thus a verse line is paired with a whole prose paragraph; the remaining verse receives false unavailable gaps. CSS cannot repair the semantic mismatch.

Content audit: Book I has 798 verse lines / 5,945 words against three plain paragraphs / 277 words (5%); it is a condensed summary. Books II–V have only 29–53% of source word counts and require completeness review. Books VII, VIII, and XII each have a single plain paragraph despite roughly 100% word counts. Equal word counts alone do not establish faithful coverage.

Proposed design (investigation complete; implementation pending): use explicitly mapped verse passages, each with source line start/end and matching prose. Preserve verse breaks and indentation, show line ranges, align the top of each passage pair, and let the taller cell determine row height. Bound passages at complete thoughts/stanzas, not arbitrary line or word counts. Page continuation must preserve the passage identity and avoid presenting independently split columns as new semantic matches. On mobile, stack each passage's original and prose with the same line-range label. Existing summaries must be labeled chapter summaries and shown as a companion outside the aligned comparison until a complete passage rewrite exists. Do not infer correspondence from relative text length. Requires a many-lines-to-passage mapping rather than the existing single-paragraph alignment member. No application code or source content changed during this investigation.

## 2026-10-13: Book metadata, chapter, and tag audit fixes (local database)

Local backup before changes: `data/database.pre-audit-20261013.db` (SHA-256 `57694296e44ca7a3697d92a6e1dff26f40d10b6a5487ab41e4cfad84ad685389`). VM backup before changes: `/opt/summra/data/database.pre-audit-20261013.db` (SHA-256 `ba1c55c082ae42d608dd253647b8ec360563eddb57403867a7d97712c2e2ad65`). Restore either backup over its respective `database.db` while the app is stopped; this rolls back the database changes in this section.

Primary text and metadata references: [Moby Dick #2701](https://www.gutenberg.org/ebooks/2701), [The Call of the Wild #215](https://www.gutenberg.org/ebooks/215), [The Vicomte de Bragelonne #2609](https://www.gutenberg.org/ebooks/2609), [Gulliver’s Travels #829](https://www.gutenberg.org/ebooks/829), [Count Fathom #6761](https://www.gutenberg.org/ebooks/6761), [The Wealth of Nations #3300](https://www.gutenberg.org/ebooks/3300), [Round the Moon (combined edition) #83](https://www.gutenberg.org/ebooks/83). [Council of Europe CEFR framework](https://www.coe.int/en/web/common-european-framework-reference-languages/introduction-and-context) defines learner proficiency, not an edition rating.

Reader cache fix: before, changing only `book_sections.section_title` left the published reader structure unchanged because the title was absent from its source checksum; after, the joined section title enters the checksum and a new reader version is published. Verified on local books 84, 88, and 58 (published version 2), and with six passing targeted tests. The local database still contains 44 pre-existing orphan chapter/summary/audio foreign-key violations, outside the changed records.

VM migration: applied the same 620 row/link operations after checking each original row value. Before: 90 books, 4,159 chapter rows, 53 dangling tag links, 17 books without a resolvable tag. After: 90 books, 4,161 chapter rows, zero dangling tag links, zero books without a resolvable tag. The production backup above precedes all writes. Deployed the reader checksum/query update to `/opt/summra/backend/models.py` after backing up its prior version as `models.py.pre-audit-20261013`; restarted the `summra` user service (active). Before: section-only edits could retain a stale published reader structure. After: production reader versions for books 84, 88, and 58 published as version 2. GitHub `main` commit `0d349e7` contains the code fix and first worklog checkpoint. On 2026-10-14, switched the VM checkout from its preserved `feat/consolidated-login` branch to `main` and fast-forwarded to GitHub commit `121f6cc`; the prior reader file diff was saved in a Git stash. After restart, the VM service was active and both `http://127.0.0.1:5001/` and the public Moby Dick page returned HTTP 200.

| Fix | Record | Before | After | Source |
| --- | --- | --- | --- | --- |
| books.title | 35 | 'Moby Dick' | 'Moby Dick; Or, The Whale' | Project Gutenberg #2701 |
| books.gutenberg_id | 3 | None | 3300 | Project Gutenberg #3300 |
| books.gutenberg_id | 92 | None | 83 | Project Gutenberg #83, combined From the Earth to the Moon and Round the Moon |
| chapters.chapter_title | 768 | 'Preface' | 'Front Matter' | Project Gutenberg #2701 opening contains transcriber notes, Etymology, and Extracts |
| chapters.chapter_number | 6499 | 0 | 1 | Project Gutenberg #215: Chapter I Into the Primitive |
| chapters.chapter_title | 6499 | 'Preface' | 'Into the Primitive' | Project Gutenberg #215 |
| chapter split | 84/39 → 84/39+40 | one row; text 19146 chars; summary 4481 chars | two rows; texts 9002 + 10111 chars; summaries 2107 + 2372 chars | Project Gutenberg #2609, chapters XL and L |
| chapter split | 84/49 → 84/49+50 | one row; text 21531 chars; summary 2753 chars | two rows; texts 13408 + 8068 chars; summaries 1315 + 1436 chars | Project Gutenberg #2609, chapters XL and L |
| chapters.chapter_title | 1795 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1796 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1797 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1798 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1799 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1800 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1801 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1802 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1803 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1804 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1805 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1806 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1807 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1808 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1809 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1810 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1811 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1812 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1813 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1814 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1815 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1816 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1817 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1818 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1819 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1820 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1821 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1822 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1823 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1824 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1825 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1826 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1827 | '' | 'Chapter 33' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1828 | '' | 'Chapter 34' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1829 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1830 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1831 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1832 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1833 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1834 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1835 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1836 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1837 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1838 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1839 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1840 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1841 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1842 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1843 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1871 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1872 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1873 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1874 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1875 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1876 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1877 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1878 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1879 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1880 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1881 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1882 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1883 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1884 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1885 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1886 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1887 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1888 | '' | 'Chapter 33' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1889 | '' | 'Chapter 34' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1890 | '' | 'Chapter 35' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1891 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1892 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1893 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1894 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1895 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1896 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1897 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1898 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1899 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1900 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1901 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1902 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1903 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1904 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1905 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1906 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1907 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1908 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1909 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1910 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1911 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1912 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1913 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1914 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1915 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1929 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1930 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1931 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1932 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1933 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1934 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1935 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1936 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1937 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1938 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1939 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1940 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1941 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1942 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1943 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1944 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1945 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1946 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1947 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1948 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1949 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1950 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1951 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1952 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1953 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1954 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1955 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1956 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1957 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1958 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1959 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1960 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1961 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1962 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1963 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1964 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1965 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1966 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1967 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1968 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1969 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1970 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1971 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1972 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1973 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1974 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1975 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1976 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1977 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1978 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1979 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1980 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1981 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1982 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1983 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1984 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1985 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1986 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1987 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1988 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1989 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1990 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1991 | '' | 'Chapter 33' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1992 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1993 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1994 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1995 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1996 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1997 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1998 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1999 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2000 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2001 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2002 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2003 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2004 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2005 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2006 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2007 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2008 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2009 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2010 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2011 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2012 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2013 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2014 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2015 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2016 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2017 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2018 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2019 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2020 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2021 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2022 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2023 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2024 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2025 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2026 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2027 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2028 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2029 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2030 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2031 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2032 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2033 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2034 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2035 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2036 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2037 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2038 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2039 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2040 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2041 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2042 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2043 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2044 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2045 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2046 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2047 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2048 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2049 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2050 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2051 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2052 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2053 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2054 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2055 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2056 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2057 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2058 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2059 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2060 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2061 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2062 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2063 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2064 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2065 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2066 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2067 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2068 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2069 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2070 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2071 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2072 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2073 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| numbered chapter labels | 52 | 239 blank titles | 239 explicit Chapter N titles | Original part/book numbering |
| chapters.chapter_title | 1845 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1846 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1847 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1848 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1849 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1850 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1851 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1852 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1853 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1854 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1855 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1856 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1857 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1858 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1859 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1860 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1861 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1862 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1863 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1864 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1865 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1866 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1867 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1868 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1869 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1870 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1916 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1917 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1918 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1919 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1920 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1921 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1922 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1923 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1924 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1925 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1926 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1927 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 1928 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| numbered chapter labels | 56 | 39 blank titles | 39 explicit Chapter N titles | Original part/book numbering |
| chapters.chapter_title | 2075 | '' | 'Chapter 1' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2076 | '' | 'Chapter 2' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2077 | '' | 'Chapter 3' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2078 | '' | 'Chapter 4' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2079 | '' | 'Chapter 5' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2080 | '' | 'Chapter 6' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2081 | '' | 'Chapter 7' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2082 | '' | 'Chapter 8' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2083 | '' | 'Chapter 9' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2084 | '' | 'Chapter 10' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2085 | '' | 'Chapter 11' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2086 | '' | 'Chapter 12' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2087 | '' | 'Chapter 13' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2088 | '' | 'Chapter 14' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2089 | '' | 'Chapter 15' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2090 | '' | 'Chapter 16' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2091 | '' | 'Chapter 17' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2092 | '' | 'Chapter 18' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2093 | '' | 'Chapter 19' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2094 | '' | 'Chapter 20' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2095 | '' | 'Chapter 21' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2096 | '' | 'Chapter 22' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2097 | '' | 'Chapter 23' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2098 | '' | 'Chapter 24' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2099 | '' | 'Chapter 25' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2100 | '' | 'Chapter 26' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2101 | '' | 'Chapter 27' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2102 | '' | 'Chapter 28' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2103 | '' | 'Chapter 29' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2104 | '' | 'Chapter 30' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2105 | '' | 'Chapter 31' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2106 | '' | 'Chapter 32' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2107 | '' | 'Chapter 33' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2108 | '' | 'Chapter 34' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2109 | '' | 'Chapter 35' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2110 | '' | 'Chapter 36' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2111 | '' | 'Chapter 37' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2112 | '' | 'Chapter 38' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2113 | '' | 'Chapter 39' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2114 | '' | 'Chapter 40' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2115 | '' | 'Chapter 41' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2116 | '' | 'Chapter 42' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2117 | '' | 'Chapter 43' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2118 | '' | 'Chapter 44' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2119 | '' | 'Chapter 45' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2120 | '' | 'Chapter 46' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2121 | '' | 'Chapter 47' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2122 | '' | 'Chapter 48' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2123 | '' | 'Chapter 49' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2124 | '' | 'Chapter 50' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2125 | '' | 'Chapter 51' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2126 | '' | 'Chapter 52' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2127 | '' | 'Chapter 53' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2128 | '' | 'Chapter 54' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2129 | '' | 'Chapter 55' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2130 | '' | 'Chapter 56' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2131 | '' | 'Chapter 57' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2132 | '' | 'Chapter 58' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2133 | '' | 'Chapter 59' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2134 | '' | 'Chapter 60' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2135 | '' | 'Chapter 61' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2136 | '' | 'Chapter 62' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2137 | '' | 'Chapter 63' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2138 | '' | 'Chapter 64' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2139 | '' | 'Chapter 65' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2140 | '' | 'Chapter 66' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2141 | '' | 'Chapter 67' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2142 | '' | 'Chapter 68' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2143 | '' | 'Chapter 69' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2144 | '' | 'Chapter 70' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2145 | '' | 'Chapter 71' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2146 | '' | 'Chapter 72' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2147 | '' | 'Chapter 73' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2148 | '' | 'Chapter 74' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2149 | '' | 'Chapter 75' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2150 | '' | 'Chapter 76' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2151 | '' | 'Chapter 77' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2152 | '' | 'Chapter 78' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2153 | '' | 'Chapter 79' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2154 | '' | 'Chapter 80' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2155 | '' | 'Chapter 81' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2156 | '' | 'Chapter 82' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2157 | '' | 'Chapter 83' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2158 | '' | 'Chapter 84' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2159 | '' | 'Chapter 85' | Source chapter numbering within each part/book |
| chapters.chapter_title | 2160 | '' | 'Chapter 86' | Source chapter numbering within each part/book |
| numbered chapter labels | 57 | 86 blank titles | 86 explicit Chapter N titles | Original part/book numbering |
| chapters.chapter_title | 2443 | '' | 'SOME SAGE OBSERVATIONS THAT NATURALLY INTRODUCE OUR IMPORTANT HISTORY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2444 | '' | 'A SUPERFICIAL VIEW OF OUR HERO’S INFANCY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2445 | '' | 'HE IS INITIATED IN A MILITARY LIFE, AND HAS THE GOOD FORTUNE TO ACQUIRE A GENEROUS PATRON.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2446 | '' | 'HIS MOTHER’S PROWESS AND DEATH; TOGETHER WITH SOME INSTANCES OF HIS OWN SAGACITY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2447 | '' | 'A BRIEF DETAIL OF HIS EDUCATION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2448 | '' | 'HE MEDITATES SCHEMES OF IMPORTANCE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2449 | '' | 'ENGAGES IN PARTNERSHIP WITH A FEMALE ASSOCIATE, IN ORDER TO PUT HIS TALENTS IN ACTION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2450 | '' | 'THEIR FIRST ATTEMPT; WITH A DIGRESSION WHICH SOME READERS MAY THINK IMPERTINENT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2451 | '' | 'THE CONFEDERATES CHANGE THEIR BATTERY, AND ACHIEVE A REMARKABLE ADVENTURE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2452 | '' | 'THEY PROCEED TO LEVY CONTRIBUTIONS WITH GREAT SUCCESS, UNTIL OUR HERO SETS OUT WITH THE YOUNG COUNT FOR VIENNA, WHERE HE ENTERS INTO LEAGUE WITH ANOTHER ADVENTURER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2453 | '' | 'FATHOM MAKES VARIOUS EFFORTS IN THE WORLD OF GALLANTRY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2454 | '' | 'HE EFFECTS A LODGMENT IN THE HOUSE OF A RICH JEWELLER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2455 | '' | 'HE IS EXPOSED TO A MOST PERILOUS INCIDENT IN THE COURSE OF HIS INTRIGUE WITH THE DAUGHTER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2456 | '' | 'HE IS REDUCED TO A DREADFUL DILEMMA, IN CONSEQUENCE OF AN ASSIGNATION WITH THE WIFE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2457 | '' | 'BUT AT LENGTH SUCCEEDS IN HIS ATTEMPT UPON BOTH.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2458 | '' | 'HIS SUCCESS BEGETS A BLIND SECURITY, BY WHICH HE IS ONCE AGAIN WELL-NIGH ENTRAPPED IN HIS DULCINEA’S APARTMENT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2459 | '' | 'THE STEP-DAME’S SUSPICIONS BEING AWAKENED, SHE LAYS A SNARE FOR OUR ADVENTURER, FROM WHICH HE IS DELIVERED BY THE INTERPOSITION OF HIS GOOD GENIUS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2460 | '' | 'OUR HERO DEPARTS FROM VIENNA, AND QUITS THE DOMAIN OF VENUS FOR THE ROUGH FIELD OF MARS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2461 | '' | 'HE PUTS HIMSELF UNDER THE GUIDANCE OF HIS ASSOCIATE, AND STUMBLES UPON THE FRENCH CAMP, WHERE HE FINISHES HIS MILITARY CAREER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2462 | '' | 'HE PREPARES A STRATAGEM BUT FINDS HIMSELF COUNTERMINED—PROCEEDS ON HIS JOURNEY, AND IS OVERTAKEN BY A TERRIBLE TEMPEST.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2463 | '' | 'HE FALLS UPON SCYLLA, SEEKING TO AVOID CHARYBDIS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2464 | '' | 'HE ARRIVES AT PARIS, AND IS PLEASED WITH HIS RECEPTION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2465 | '' | 'ACQUITS HIMSELF WITH ADDRESS IN A NOCTURNAL RIOT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2466 | '' | 'HE OVERLOOKS THE ADVANCES OF HIS FRIENDS, AND SMARTS SEVERELY FOR HIS NEGLECT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2467 | '' | 'HE BEARS HIS FATE LIKE A PHILOSOPHER; AND CONTRACTS ACQUAINTANCE WITH A VERY REMARKABLE PERSONAGE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2468 | '' | 'THE HISTORY OF THE NOBLE CASTILIAN.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2469 | '' | 'A FLAGRANT INSTANCE OF FATHOM’S VIRTUE, IN THE MANNER OF HIS RETREAT TO ENGLAND.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2470 | '' | 'SOME ACCOUNT OF HIS FELLOW-TRAVELLERS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2471 | '' | 'ANOTHER PROVIDENTIAL DELIVERANCE FROM THE EFFECTS OF THE SMUGGLER’S INGENIOUS CONJECTURE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2472 | '' | 'THE SINGULAR MANNER OF FATHOM’S ATTACK AND TRIUMPH OVER THE VIRTUE OF THE FAIR ELENOR.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2473 | '' | 'HE BY ACCIDENT ENCOUNTERS HIS OLD FRIEND, WITH WHOM HE HOLDS A CONFERENCE, AND RENEWS A TREATY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2474 | '' | 'HE APPEARS IN THE GREAT WORLD WITH UNIVERSAL APPLAUSE AND ADMIRATION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2475 | '' | 'HE ATTRACTS THE ENVY AND ILL OFFICES OF THE MINOR KNIGHTS OF HIS OWN ORDER, OVER WHOM HE OBTAINS A COMPLETE VICTORY.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2476 | '' | 'HE PERFORMS ANOTHER EXPLOIT, THAT CONVEYS A TRUE IDEA OF HIS GRATITUDE AND HONOUR.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2477 | '' | 'HE REPAIRS TO BRISTOL SPRING, WHERE HE REIGNS PARAMOUNT DURING THE WHOLE SEASON.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2478 | '' | 'HE IS SMITTEN WITH THE CHARMS OF A FEMALE ADVENTURER, WHOSE ALLUREMENTS SUBJECT HIM TO A NEW VICISSITUDE OF FORTUNE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2479 | '' | 'FRESH CAUSE FOR EXERTING HIS EQUANIMITY AND FORTITUDE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2480 | '' | 'THE BITER IS BIT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2481 | '' | 'OUR ADVENTURER IS MADE ACQUAINTED WITH A NEW SCENE OF LIFE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2482 | '' | 'HE CONTEMPLATES MAJESTY AND ITS SATELLITES IN ECLIPSE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2483 | '' | 'ONE QUARREL IS COMPROMISED, AND ANOTHER DECIDED BY UNUSUAL ARMS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2512 | '' | 'AN UNEXPECTED RENCONTRE, AND A HAPPY REVOLUTION IN THE AFFAIRS OF OUR ADVENTURER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2513 | '' | 'FATHOM JUSTIFIES THE PROVERB, “WHAT’S BRED IN THE BONE WILL NEVER COME OUT OF THE FLESH.”' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2486 | '' | 'ANECDOTES OF POVERTY, AND EXPERIMENTS FOR THE BENEFIT OF THOSE WHOM IT MAY CONCERN.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2487 | '' | 'RENALDO’S DISTRESS DEEPENS, AND FATHOM’S PLOT THICKENS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2488 | '' | 'OUR ADVENTURER BECOMES ABSOLUTE IN HIS POWER OVER THE PASSIONS OF HIS FRIEND, AND EFFECTS ONE HALF OF HIS AIM.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2489 | '' | 'THE ART OF BORROWING FURTHER EXPLAINED, AND AN ACCOUNT OF A STRANGE PHENOMENON.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2490 | '' | 'COUNT FATHOM UNMASKS HIS BATTERY; IS REPULSED; AND VARIES HIS OPERATIONS WITHOUT EFFECT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2491 | '' | 'MONIMIA’S HONOUR IS PROTECTED BY THE INTERPOSITION OF HEAVEN.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2492 | '' | 'FATHOM SHIFTS THE SCENE, AND APPEARS IN A NEW CHARACTER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2493 | '' | 'TRIUMPHS OVER A MEDICAL RIVAL.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2494 | '' | 'REPAIRS TO THE METROPOLIS, AND ENROLS HIMSELF AMONG THE SONS OF PAEAN.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2495 | '' | 'ACQUIRES EMPLOYMENT IN CONSEQUENCE OF A LUCKY MISCARRIAGE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2510 | '' | 'HIS ECLIPSE, AND GRADUAL DECLINATION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2511 | '' | 'AFTER DIVERS UNSUCCESSFUL EFFORTS, HE HAS RECOURSE TO THE MATRIMONIAL NOOSE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2498 | '' | 'IN WHICH HIS FORTUNE IS EFFECTUALLY STRANGLED.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2499 | '' | 'FATHOM BEING SAFELY HOUSED, THE READER IS ENTERTAINED WITH A RETROSPECT.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2500 | '' | 'RENALDO ABRIDGES THE PROCEEDINGS AT LAW, AND APPROVES HIMSELF THE SON OF HIS FATHER.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2501 | '' | 'HE IS THE MESSENGER OF HAPPINESS TO HIS SISTER, WHO REMOVES THE FILM WHICH HAD LONG OBSTRUCTED HIS PENETRATION, WITH REGARD TO COUNT FATHOM.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2502 | '' | 'HE RECOMPENSES THE ATTACHMENT OF HIS FRIEND; AND RECEIVES A LETTER THAT REDUCES HIM TO THE VERGE OF DEATH AND DISTRACTION.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2503 | '' | 'RENALDO MEETS WITH A LIVING MONUMENT OF JUSTICE, AND ENCOUNTERS A PERSONAGE OF SOME NOTE IN THESE MEMOIRS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2504 | '' | 'HIS RETURN TO ENGLAND, AND MIDNIGHT PILGRIMAGE TO MONIMIA’S TOMB.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2505 | '' | 'HE RENEWS THE RITES OF SORROW, AND IS ENTRANCED.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2506 | '' | 'THE MYSTERY UNFOLDED—ANOTHER RECOGNITION, WHICH, IT IS TO BE HOPED, THE READER COULD NOT FORESEE.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2507 | '' | 'A RETROSPECTIVE LINK, NECESSARY FOR THE CONCATENATION OF THESE MEMOIRS.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2508 | '' | 'THE HISTORY DRAWS NEAR A PERIOD.' | Project Gutenberg #6761 chapter heading in stored source text |
| chapters.chapter_title | 2509 | '' | 'THE LONGEST AND THE LAST.' | Project Gutenberg #6761 chapter heading in stored source text |
| descriptive chapter labels | 63 | 67 blank titles | 67 source heading titles | Project Gutenberg #6761 |
| chapters.chapter_title | 2689 | '' | length 223 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2690 | '' | length 314 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2691 | '' | length 205 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2692 | '' | length 238 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2693 | '' | length 284 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2694 | '' | 'Of the inhabitants of Lilliput; their learning, laws, and customs; the manner of educating their children. The author’s way of living in that country. His vindication of a great lady.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2695 | '' | 'The author, being informed of a design to accuse him of high-treason, makes his escape to Blefuscu. His reception there.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2696 | '' | 'The author, by a lucky accident, finds means to leave Blefuscu; and, after some difficulties, returns safe to his native country.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2697 | '' | length 288 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2698 | '' | 'A description of the farmer’s daughter. The author carried to a market-town, and then to the metropolis. The particulars of his journey.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2699 | '' | length 320 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2700 | '' | 'The country described. A proposal for correcting modern maps. The king’s palace; and some account of the metropolis. The author’s way of travelling. The chief temple described.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2701 | '' | 'Several adventures that happened to the author. The execution of a criminal. The author shows his skill in navigation.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2702 | '' | length 204 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2703 | '' | length 259 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2704 | '' | 'The king and queen make a progress to the frontiers. The author attends them. The manner in which he leaves the country very particularly related. He returns to England.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2705 | '' | 'The author sets out on his third voyage. Is taken by pirates. The malice of a Dutchman. His arrival at an island. He is received into Laputa.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2706 | '' | length 218 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2707 | '' | 'A phenomenon solved by modern philosophy and astronomy. The Laputians’ great improvements in the latter. The king’s method of suppressing insurrections.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2708 | '' | length 220 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2709 | '' | 'The author permitted to see the grand academy of Lagado. The academy largely described. The arts wherein the professors employ themselves.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2710 | '' | 'A further account of the academy. The author proposes some improvements, which are honourably received.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2711 | '' | 'The author leaves Lagado: arrives at Maldonada. No ship ready. He takes a short voyage to Glubbdubdrib. His reception by the governor.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2712 | '' | 'A further account of Glubbdubdrib. Ancient and modern history corrected.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2713 | '' | 'The author returns to Maldonada. Sails to the kingdom of Luggnagg. The author confined. He is sent for to court. The manner of his admittance. The king’s great lenity to his subjects.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2714 | '' | 'The Luggnaggians commended. A particular description of the Struldbrugs, with many conversations between the author and some eminent persons upon that subject.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2715 | '' | 'The author leaves Luggnagg, and sails to Japan. From thence he returns in a Dutch ship to Amsterdam, and from Amsterdam to England.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2716 | '' | length 264 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2717 | '' | length 223 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2718 | '' | length 239 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2719 | '' | 'The Houyhnhnms’ notion of truth and falsehood. The author’s discourse disapproved by his master. The author gives a more particular account of himself, and the accidents of his voyage.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2720 | '' | 'The author at his master’s command, informs him of the state of England. The causes of war among the princes of Europe. The author begins to explain the English constitution.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2721 | '' | 'A continuation of the state of England under Queen Anne. The character of a first minister of state in European courts.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2722 | '' | length 235 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2723 | '' | 'The author relates several particulars of the _Yahoos_. The great virtues of the _Houyhnhnms_. The education and exercise of their youth. Their general assembly.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2724 | '' | 'A grand debate at the general assembly of the _Houyhnhnms_, and how it was determined. The learning of the _Houyhnhnms_. Their buildings. Their manner of burials. The defectiveness of their language.' | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2725 | '' | length 364 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2726 | '' | length 252 | Project Gutenberg #829 chapter synopsis |
| chapters.chapter_title | 2727 | '' | length 506 | Project Gutenberg #829 chapter synopsis |
| descriptive chapter labels | 70 | 39 blank titles | 39 source synopsis titles | Project Gutenberg #829 |
| book_sections.section_title | 28 | '' | 'Part 1' | Source part numbering |
| book_sections.section_title | 29 | '' | 'Part 2' | Source part numbering |
| book_sections.section_title | 30 | '' | 'Part 3' | Source part numbering |
| book_sections.section_title | 31 | '' | 'Part 4' | Source part numbering |
| book_sections.section_title | 32 | '' | 'Part 5' | Source part numbering |
| book_sections.section_title | 33 | '' | 'Part 6' | Source part numbering |
| book_sections.section_title | 34 | '' | 'Part 7' | Source part numbering |
| book_sections.section_title | 35 | '' | 'Part 8' | Source part numbering |
| section labels | 52 | 8 blank titles | 8 explicit Part N titles | Original part numbering |
| book_sections.section_title | 36 | '' | 'Part 1' | Source part numbering |
| book_sections.section_title | 37 | '' | 'Part 2' | Source part numbering |
| book_sections.section_title | 38 | '' | 'Part 3' | Source part numbering |
| book_sections.section_title | 39 | '' | 'Part 4' | Source part numbering |
| book_sections.section_title | 40 | '' | 'Part 5' | Source part numbering |
| book_sections.section_title | 41 | '' | 'Part 6' | Source part numbering |
| section labels | 56 | 6 blank titles | 6 explicit Part N titles | Original part numbering |
| book_sections.section_title | 50 | '' | 'Part 1' | Source part numbering |
| book_sections.section_title | 51 | '' | 'Part 2' | Source part numbering |
| book_sections.section_title | 52 | '' | 'Part 3' | Source part numbering |
| section labels | 58 | 3 blank titles | 3 explicit Part N titles | Original part numbering |
| book_sections.section_title | 57 | '' | 'Part 1' | Source part numbering |
| book_sections.section_title | 58 | '' | 'Part 2' | Source part numbering |
| section labels | 63 | 2 blank titles | 2 explicit Part N titles | Original part numbering |
| broken tag link | 239 | book 38 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 249 | book 41 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 254 | book 29 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 261 | book 3 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 262 | book 3 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 268 | book 52 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 269 | book 61 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 272 | book 61 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 273 | book 61 → category 81 | deleted dangling link | Database referential integrity |
| broken tag link | 277 | book 49 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 283 | book 56 → category 81 | deleted dangling link | Database referential integrity |
| broken tag link | 293 | book 30 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 297 | book 44 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 305 | book 39 → category 80 | deleted dangling link | Database referential integrity |
| broken tag link | 309 | book 36 → category 84 | deleted dangling link | Database referential integrity |
| broken tag link | 310 | book 36 → category 80 | deleted dangling link | Database referential integrity |
| broken tag link | 314 | book 57 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 315 | book 57 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 320 | book 35 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 324 | book 60 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 335 | book 5 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 337 | book 7 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 339 | book 7 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 344 | book 10 → category 33 | deleted dangling link | Database referential integrity |
| broken tag link | 349 | book 48 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 354 | book 63 → category 33 | deleted dangling link | Database referential integrity |
| broken tag link | 366 | book 50 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 370 | book 51 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 376 | book 42 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 379 | book 8 → category 67 | deleted dangling link | Database referential integrity |
| broken tag link | 396 | book 64 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 405 | book 28 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 410 | book 9 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 425 | book 58 → category 33 | deleted dangling link | Database referential integrity |
| broken tag link | 433 | book 4 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 437 | book 45 → category 72 | deleted dangling link | Database referential integrity |
| broken tag link | 438 | book 45 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 453 | book 55 → category 33 | deleted dangling link | Database referential integrity |
| broken tag link | 458 | book 68 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 462 | book 69 → category 59 | deleted dangling link | Database referential integrity |
| broken tag link | 468 | book 71 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 473 | book 72 → category 103 | deleted dangling link | Database referential integrity |
| broken tag link | 479 | book 73 → category 80 | deleted dangling link | Database referential integrity |
| broken tag link | 483 | book 74 → category 84 | deleted dangling link | Database referential integrity |
| broken tag link | 489 | book 75 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 493 | book 77 → category 96 | deleted dangling link | Database referential integrity |
| broken tag link | 494 | book 77 → category 76 | deleted dangling link | Database referential integrity |
| broken tag link | 498 | book 78 → category 95 | deleted dangling link | Database referential integrity |
| broken tag link | 587 | book 101 → category 44 | deleted dangling link | Database referential integrity |
| broken tag link | 588 | book 101 → category 36 | deleted dangling link | Database referential integrity |
| broken tag link | 589 | book 101 → category 40 | deleted dangling link | Database referential integrity |
| broken tag link | 590 | book 101 → category 94 | deleted dangling link | Database referential integrity |
| broken tag link | 591 | book 101 → category 49 | deleted dangling link | Database referential integrity |
| book tags | 76 | [] | [34, 36, 40, 51] | Existing category taxonomy; book genre/subject |
| book tags | 80 | [] | [34, 37, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 83 | [] | [34, 37, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 84 | [] | [34, 37, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 85 | [] | [34, 37, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 86 | [] | [37, 40, 42, 46] | Existing category taxonomy; book genre/subject |
| book tags | 87 | [] | [34, 37, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 88 | [] | [34, 35, 40, 102] | Existing category taxonomy; book genre/subject |
| book tags | 89 | [] | [35, 40, 42, 113] | Existing category taxonomy; book genre/subject |
| book tags | 99 | [] | [38, 40, 42] | Existing category taxonomy; book genre/subject |
| book tags | 107 | [] | [36, 40, 42, 48] | Existing category taxonomy; book genre/subject |
| book tags | 108 | [] | [35, 40, 41, 63] | Existing category taxonomy; book genre/subject |
| book tags | 109 | [] | [36, 40, 42, 48] | Existing category taxonomy; book genre/subject |
| book tags | 110 | [] | [40, 41, 94] | Existing category taxonomy; book genre/subject |
| book tags | 111 | [] | [36, 40, 42, 46] | Existing category taxonomy; book genre/subject |
| book tags | 112 | [] | [35, 40, 101] | Existing category taxonomy; book genre/subject |
| book tags | 114 | [] | [36, 40, 42, 113] | Existing category taxonomy; book genre/subject |
| book tags | 70 | [112] | [36, 40, 42, 112, 113] | Existing category taxonomy; book genre/subject |

CEFR: unchanged pending an official, edition-specific source. The existing values were estimates; Council of Europe CEFR rates learner proficiency, and Project Gutenberg does not assign these originals CEFR levels.

Ulysses episode titles remain blank because the source does not give official episode names; reader fallback numbering remains. The 59 blank book descriptions and present-day relevance fields require editorial writing and were not invented in a formatting/data-integrity pass.

---


[Previous content preserved...]

---

## 2026-10-13: Reading guide paths and Alice paragraph data (local)

- Reading guide images used database URLs such as `/static/guides/39_themes.webp` without the `/summrabook` deployment prefix. `app.js` now applies `withBasePath()` to the displayed images and lightbox URLs; rebuilt `app.min.js`. The guide files are present locally.
- Alice's Adventures in Wonderland, chapter 1 had `Alice was starti\n\nng to get` in `modern_english_text`. Corrected the local `data/database.db` row to `Alice was starting to get`; the database is ignored by Git and production needs the same data correction. Recompiled local reader content to version 2 and confirmed its first Plain English paragraph starts with the full word.
- Verification: JavaScript route tests (18 passed), URL prefix tests (7 passed), and `npm run build:check` passed. No production deployment or live database change was made.

---

## 2026-10-15: Reading levels: original vs Plain English — DONE, deployed 2026-10-15

User: the level filters describe the original text, but the selling point is the simplified text; check past notes for the Plain English target and rethink Discover's filters and the home levels section. Chose "keep grade, relabel it" and "show books without Plain English, marked Original only".

- **Target found:** the 2026-05-31 prompt rewrite in `generate_modern_english.py` targets a U.S. 8th-grade reader (Flesch–Kincaid 7–9, Lexile 925L–1185L, 15–20 words per sentence). 62 of 90 books have Plain English; 28 have none.
- **Measured (local, no API cost):** FK on all 62 books, original vs Plain English: median 6.5 → 5.7, words per sentence 16.4 → 15.3; only 11 books land in FK 7–9. FK can't see archaic vocabulary/syntax, which is what the rewrite changes, so it can't grade Plain English either. We state the target, not a measured grade. Script: scratchpad `fk_compare.py` (not committed).
- **Changes:** listings carry `has_plain_english` (`Database.plain_english_book_ids`, cached 300 s); grade tags read "Original: Grade N"; Discover filter "Original’s level", new "Plain English" toggle (`?plain=yes`), sort "Easiest original first", intro no longer claims every book is rewritten; "Original only" tag on cards and book page; book page badge "Plain English · grade 8"; home levels section rewritten around the grade 8 target with a live "62 of 90" count, notes in a 2×2 grid, Flesch–Kincaid footnote updated with our measurement.
- **Tests:** new `tests/test_plain_english_levels.py` (9, red first); label assertions updated in test_book_page_redesign, test_discover_page, test_home_redesign and e2e redesign_cards; e2e redesign_discover gains Plain English toggle + client-card checks. `test_get_all_books::test_uses_one_connection` caught a second connection, fixed by reusing the listing's. 674 pytest passed; e2e suite all green.
- **Deployed 2026-10-15** as `4bb8321` (with the rank-badge removal): VM fast-forwarded, service restarted, no errors in the log. Public `/` 0.16–0.23 s, `/discover` 0.20–0.28 s, `/api/books` 0.16–0.24 s; 28 cards tagged Original only, home shows "62 of 90", no rank badges. The Plain English query takes 7 ms on the VM. One 4.4 s first request after the first restart did not repeat (0.10 s after a second restart).

---

## 2026-10-14: Home "Start here" — drop the No. 1–10 badges — DONE, deployed 2026-10-15

Removed the "No. N" rank badge from the Start here covers (book_card/book_cover macros, createBookCard/bookCoverHtml in app.js, `.book-card-rank` CSS, the unused `rank` field in `pages._top10_books`). Shelf order is unchanged. Tests flipped first to assert no badge (test_home_top10_ssr, test_home_redesign, e2e redesign_home), then green: 665 pytest; e2e redesign_home, top10_ssr, redesign_cards, hero_home_navigation, catalog_fetch_once, smoke, redesign_discover pass.

---

## 2026-10-14: Feedback round 2 — checklist — DONE, deployed 2026-10-14

1. [x] Book page: hide "About the author" when it has no content.
2. [x] Book page: remove "About this book" for all books (duplicates the Summary).
3. [x] Nav: drop "Books" (overlaps Discover) from header and footer; `/books` redirects to `/discover`.
4. [x] Fonts: nav, footer and stray links ("Learn more →" rendered as a purple visited link) match the design system.
5. [x] Hero copy: replace "Stuck on a sentence? …" with the side-by-side message.
6. [x] Hero on mobile: redesign (desktop is good).
7. [x] Home sections: stronger separation/contrast between Continue reading, Start here, etc.
8. [x] Continue reading: no late pop-in (server-render it for signed-in readers / reserve its place), faster.
9. [x] Replace "How it works" with a reading-level section explaining the research behind grade levels.
10. [x] Reader perf: an arbitrary chapter (e.g. /books/paradise-lost/chapters/7) took ~10 s; load progressively instead of the whole book.
11. [x] Metadata audit (Sonnet subagents): genres from BISAC, origin from Library of Congress Class, audience, school lists; fix wrong tags; no one-off categories.
12. [x] Reading-grade tags (Flesch–Kincaid or equivalent) for original and plain English; filter on Discover.
13. [x] Report further tagging ideas for young readers and parents.

### Notes (round 2)
- **Perf (10):** the reader already loads progressively (manifest + ~12 KB segments). The slowness was server-side: books rows store `full_text` before gutenberg_id/slug/cefr_level, so listing queries walked every book's text; on the 1 GB prod VM `/` took 6–10 s (measured on the VM: top-10 3.6 s cold) and the per-worker home counts stalled other pages. Fixed with a covering index (`idx_books_listing_v2`).
- **Metadata (11):** three Sonnet agents audited all 90 books (Gutenberg LoC subjects + a second source). Categories are BISAC subject headings, siblings grouped so each has ≥3 books (17 categories). Two corrections (Gatsby, Uncle Tom's Cabin aren't historical fiction). Common Core Appendix B exemplars verified by searching the archived PDF's full text (14 books; the agents had missed six). Old categories redirect (301) via a reviewed map (`category_redirects` table) — ids differ per database.
- **Grade levels (12):** Flesch–Kincaid was computed for every book and rejected: it rates dialogue-heavy classics far too low (Romeo and Juliet 3.0, Crime and Punishment 5.6, Ulysses 5.4) and barely separates plain English from the original. Used published ATOS book levels + AR Interest Levels from Renaissance's AR BookFinder instead (65/90 books; unabridged editions only — the rest are treatises/obscure works AR doesn't carry). One agent hit a rate limit; its 30 books were looked up directly with the same script.
- **UI (9, 12):** Discover filters are Reading level (grade bands), Ages (interest level), Length and a Common Core toggle; cards and the book page show "Grade N" (falls back to the old level label), the book page adds ages and a Common Core badge. Home "Choose by level" + "How it works" became "Find a book at the right level" (grade cards + where the levels come from).
- **Apply on prod:** `PYTHONPATH=. venv/bin/python scripts/content/apply_book_metadata.py --dry-run` then without `--dry-run` (idempotent; rehearsed on a copy of the main DB: 637 rows, second run 0).
- **More tagging ideas (13):** content advisories (violence, mature themes) from Common Sense Media-style sources; award/curriculum lists beyond Common Core (AP Literature open-question titles, state reading lists); series/companion links (e.g. Alice → Looking-Glass); historical period and setting (useful for history classes); "read-aloud friendly" for younger kids; audio availability; translation/original language.
- **Deployed 2026-10-14:** rebased onto main (`de8e017`, the parallel metadata/chapter audit), main → `4c7eb5b`; 665 pytest passed, e2e all green. VM fast-forwarded to `4c7eb5b`. Prod DB backed up first to `/opt/summra/data/database.pre-redesign-20261015-055245.db` (SHA-256 `d12e5e32…910d`; restore over `database.db` with the service stopped to roll back). Restart ran the migrations (new columns, `idx_books_listing_v2`, `category_redirects`). `apply_book_metadata.py` on prod: dry run 637, applied 637, re-run 0. Same applied to the local main DB. Public timings after: `/` 0.29 s (was ~7 s), `/discover` 0.20 s, `/api/books` 0.25 s, `/books/paradise-lost/chapters/7` 0.24 s; `/books` → 301 `/discover`; no errors in the service log. The redesign worktree and branch were removed afterwards; the audit inputs moved to the main checkout's `data/metadata_audit/` (gitignored).

---

## 2026-10-12: Site redesign ("Quiet library + study cues") — DONE, deployed 2026-10-13

Branch `redesign` (worktree `.claude/worktrees/redesign`). Direction chosen by user: mix of A (warm paper, serif, oxblood accent, home leads with an original → plain-English sentence pair) and C (difficulty level, reading time, progress cues on Discover and book pages). Audience: general. Spec: `docs/superpowers/specs/2026-10-12-site-redesign-design.md`. PRD Design Principles §6 and ERD Frontend Module Map updated.

### Baseline captured (before any UI change)

- New `tests/e2e/capture_pages.mjs`: full-page JPEG screenshots at 1280×900 and 375×812 of home, discover, books, categories, library, book (Frankenstein), author, reader (plain) and reader (side by side, desktop only). `BASE_URL` and `OUT_DIR` env vars. Waits for network idle + all images complete.
- Baseline at `docs/redesign/before/local/` (local `main` @ 051244c) and `docs/redesign/before/prod/` (live site). Note: prod's reader still shows the older top-bar mode toggle; local `main` has the continuous reader with modes in the settings panel — the script handles both.
- Gotcha: the shared venv installs `backend` as an editable package pointing at the main checkout, so `python backend/app.py` in a worktree silently serves main's code. Run with `PYTHONPATH=$PWD` from the worktree root.

### Phase 0 — spec + docs (DONE, e377cb4)

### Phase 1 — tokens + global chrome (DONE)

- `style.css` `:root`: new design-system tokens (`--paper`, `--paper-deep`, `--surface`, `--ink`, `--ink-muted`, `--rule`, `--rule-strong`, `--accent`, `--accent-hover`, `--on-accent`, `--font-serif`, `--font-sans`, `--level-*`). Legacy tokens (`--primary-color`, `--secondary-color`, `--background-color`, `--card-background`, `--text-*`, `--border-*`, `--hero-accent`, …) now alias onto them, so un-migrated pages pick up the palette.
- Header: paper background, ink nav, hairline rule (was black). Body: paper, system sans (dropped 'Amazon Ember'). Buttons: `.btn-primary`, `.book-read-btn`, `.hero-cta-primary` are oxblood; `.btn-secondary` is an ink outline.
- Footer: tagline + Discover/Books/Categories links + © line (kept "Plain English rewrites of classic literature", which `tests/test_footer_copy.py` protects).
- Page sections that painted white/surface bands on paper (`.summary-section`, `.hero-learn`, `.library-section` gradient, summary "Read more" fades) now sit on paper. Reader sections keep `--surface` by design.
- Deferred to the home phase: header search icon; Categories stays in the nav until Discover absorbs it.
- Tests: new `tests/e2e/redesign_chrome.mjs` (20 checks: paper bg, header, ink nav, serif wordmark, footer links, oxblood CTA, no off-paper bands, no console errors) — written first, failed, now green. pytest 549 passed. e2e: all green except 6 scenarios that also fail on unmodified main (stale tests for the old chapter-detail view + a blog test needing posts) — flagged as a separate task.
- After screenshots: `docs/redesign/after/phase1/`.
- Worktree gotcha: `tests/e2e/node_modules` as a symlink isn't covered by the `tests/e2e/node_modules/` ignore pattern — stage files explicitly, never `git add -A`.

### Phase 2 — study cues (DONE)

- New `backend/study_cues.py`: `level_label(cefr)` (upper bound of a CEFR range: ≤B1 Easy, B2 Moderate, C1+ Challenging, else None), `reading_minutes(words)` (ceil at 230 wpm), `summary_excerpt(text)` (first sentence of the first paragraph, markdown stripped, abbreviation/initial-aware, ≤160 chars on a word boundary), plus `add_book_cues` / `add_chapter_cues`.
- Wired in `backend/models.py` where rows become dicts, so every consumer agrees: `get_all_books`, `get_books_by_category`, `get_book`/`get_book_by_slug` add `level` + `reading_minutes`; the three chapter-metadata queries add `reading_minutes` + `summary_excerpt` via a shared `CHAPTER_CUE_COLUMNS` SQL fragment (private `_text_words` / `_summary_head` columns, popped before returning).
- **Data gotcha:** `chapters.word_count` is the *summary's* word count (`add_chapter` computes it from `summary`), e.g. Frankenstein chapters sum to 16,802 vs 75,042 for the book. Chapter reading time therefore uses `chapter_text`, word-counted in SQL (whitespace separators + 1; ~2.6% mean / 8.7% max error vs `split()`) so the chapter list never loads full text. The column itself is left as is — other code may rely on it.
- Real data: 13 Easy, 25 Moderate, 23 Challenging, 29 no level. `/api/books/30/chapters` 18 ms.
- Deferred: SSR `__INITIAL_DATA__.book` doesn't carry the cues yet (`tests/test_book_page_ssr.py` pins its exact shape); phase 5 renders the meta row in the template instead. Discover's existing "Easy to Read" carousel still matches any level containing A2/B1 (so B1-B2 lands there) — replaced in phase 4. `get_books_by_gutenberg_ids` (home top-10) and the author getters don't select `cefr_level`/`word_count` yet — phases 3/6.
- Tests: `tests/test_study_cues.py` (34; red against a stub first). pytest 583 passed. e2e smoke, redesign_chrome, book_page_fast_path, listing_pages_catalog, catalog_fetch_once, top10_ssr, reader_opens_at_chapter all green.

### Phase 3 — shared book card (DONE)

- `app.js`: `createBookCard(book)` is now the only book card — an `<a href="/books/<slug>">` (plain click → `selectBook`, modifier/middle click opens a tab) with a 2:3 cover box, serif title, author, level tag and reading time. Category/discover carousels (`createCarousel`) and "You may also like" now call it; their bespoke `.carousel-book-card` / `.related-book-card` markup and CSS are gone. New `bookCoverHtml(book)` (cover box whose serif title shows until the image loads or if it fails) and `coverSources(url)` (WebP/JPG URL logic pulled out of `getImageHtml`). Removed `formatNumber` (its only caller was the old card).
- Library (`reader.js`) keeps its progress card but uses `bookCoverHtml`; restyled on tokens (oxblood Continue button and progress fill, serif headings). Category shelf titles are serif.
- Server: `study_cues.format_reading_time()` ("8 min", "1 hr", "5½ hrs") → `reading_time` on books and chapters, so JS and later Jinja share one formatter. Author and related-book queries (`get_books_by_author_id/_name`, `get_books_in_same_categories`, `get_books_by_author_country`) now select `cefr_level` and add cues.
- CSS: 58 legacy card rules (+11 emptied media queries) removed; new `.book-card*`, `.level-tag--{easy,moderate,challenging}` rules; titles reserve two lines so rows align.
- `app.min.js` rebuilt (`check-build-fresh` OK) and the card test also passes against the prod-mode bundle (app_prod on :5003).
- Tests: pytest `test_study_cues.py` +11 (format, author/related cues). New `tests/e2e/redesign_cards.mjs` (19 checks: links, 2:3 covers, Frankenstein = Challenging / 5½ hrs, uniform row heights, serif placeholder with covers blocked, shared card on categories/discover/author/related, in-app click incl. the accented `louise-de-la-vallière` slug). pytest 594 passed; e2e suite green (same 6 pre-existing failures excluded). One unexplained `redesign_cards` timeout inside a full-suite run; not reproducible in 7 further runs, including the same ordering.
- After screenshots: `docs/redesign/after/phase3/`.

### Phase 4 — Discover grid (DONE)

- `/discover` (`backend/routes/pages.py`) server-renders every book as a card (`frontend/templates/_book_card.html` macro, mirrors `createBookCard`), with Level (All/Easy/Moderate/Challenging) and Length (All/Short/Medium/Long) chips and a Sort select (A–Z / Shortest first / Easiest first). `?level=&length=&sort=` are read server-side; unknown values fall back to defaults.
- Filtering is pure CSS on the grid's `data-filter-level` / `data-filter-length` vs each card's `data-level` / `data-length`, so it works before JS and server/client share one mechanism. `showDiscoverPage` fills the grid from the catalog on in-app navigation, wires chips once, updates count, empty state ("Clear filters") and the URL via `replaceState`. `applySortToDiscoverGrid` matches `DISCOVER_SORTS` in Python.
- `study_cues.length_label`: Short < 50k words, Medium < 120k, else Long (21 / 33 / 36 books).
- Removed: `backend/routes/discover.py` (`/api/discover/carousels`), its blueprint registration and its characterization test (endpoint only served the old carousels; now 404, pinned by a test); `renderDiscoverPage`, `createDiscoverSection`, `renderTop10AsStandardCarousel` and the dead `isDiscoverPage`/`popular` branch.
- The "404 on Discover" from the first review was my own visit to a nonexistent `/explore` URL — no bug.
- /discover HTML: 16 KB gzipped (was 9 KB) and TTFB 66 ms, but cards now paint without waiting for /api/books + carousels.
- Tests: `tests/test_discover_page.py` (19) and `tests/e2e/redesign_discover.mjs` (19), both red first. pytest 612 passed; e2e suite green (6 pre-existing failures excluded); discover + cards tests also pass against the prod bundle.
- After screenshots: `docs/redesign/after/phase4/`.

### Phase 5 — book page (DONE)

- Header (server-rendered, `book_meta` in `pages.book_detail`): serif title, author, meta row (level tag · N chapters · reading time · "Plain English" badge), primary "Start reading" button and a "Read side by side" link (`/books/<slug>/read?mode=side_by_side`, hidden without plain English and below 1024px). `renderBookMeta()` in `app.js` rebuilds the same row from `/api/books/<id>/chapters` (whose `book` now carries `level` + `reading_time`). New `Database.count_chapters()`.
- Order: About this book → summaries → chapters → reading guides → About the author → You may also like. "About the author" is its own `#about-author-section`; `updateAboutSection` toggles both with `.hidden` (and `loadBookMetadata`'s loading state no longer sets inline display on the bio's parent).
- Chapter list: `createChapterRow()` builds `<a class="chapter-box">` rows (number, title, `summary_excerpt`, `reading_time`, read check). A plain click calls `openChapterInReader(n)` → continuous reader at that chapter, same as a direct `/books/<slug>/chapters/<n>` load. **Behaviour change:** on main, clicking a chapter on the book page opened the old chapter-detail view (with header mode toggle) while the same URL loaded directly opened the continuous reader.
- Progress: `applyBookProgress()` reads the v2 reader state (`authModule.getReaderState`): button becomes "Continue · <chapter>" (current marker, last-used mode) or "Read again" (finished); chapters before the furthest marker get the check. Removed the dead `showResumeReadingButton` + `.resume-reading-btn` CSS and the `getReadingProgress` / `getCompletedChaptersForBook` stubs (they always returned null / [] on main, so the old resume button and checks never appeared). `showChapterDetailPage` kept — e2e tests drive the legacy view through it.
- Styling: TOC rows are ruled lines (no grey bars/blue border), serif section headings, sentence-case headings ("About this book", "About the author", "You may also like").
- Tests: `tests/test_book_page_redesign.py` (8) and `tests/e2e/redesign_book_page.mjs` (17, mocks `/auth/check` and `/progress/v2/books/30` for the signed-in case), both red first; the e2e also passes on the prod bundle. pytest 619 passed; e2e suite green (6 pre-existing failures excluded). The e2e caught one real bug (author section hidden by a stale inline style) and one test bug of mine (hidden sections measured at y=0).
- After screenshots: `docs/redesign/after/phase5/`.

### Phase 6 — home page + header search (DONE)

- Hero (paper, no cover wall): serif "Read the classics in plain English.", search, "Find your next classic", and a real original → plain-English sentence pair from `HERO_EXAMPLES` in `backend/routes/pages.py` (Pride and Prejudice, Jane Eyre, Frankenstein, Great Expectations ch. 1 — first sentences that line up 1:1; books without a rewrite are skipped). "Another example →" cycles them (`wireHeroExamples`). New `study_cues.first_sentence()`; `summary_excerpt()` now builds on it.
- Sections: Continue reading (signed in, first 3 of `/library` continue_reading via the shared `renderLibraryCards`, extracted from `showLibrary` and now container-scoped), Start here (top-10 shelf now uses the `book_card` macro / `createBookCard` with `className: 'top-10-book-card'` + small "No. N" badge; keeps `.top-10-rank-number`), Choose by level (three cards → `/discover?level=…`, counts from new `Database.count_books_by_cefr()`), How it works (three steps + a side-by-side snippet).
- Home content (`hero_examples`, `level_counts`) comes from an `app_context_processor` with a 5-minute per-DB cache, because `#hero-section` is rendered (hidden) on every page for in-app navigation. Hero is now also hidden on server-rendered `/discover` (type was missing from the list).
- Header search: magnifier in the header opens a search box on every page; `HeroSearch` takes element ids and runs twice (hero + header). Fixed in passing: result covers used a nonexistent `book.cover_image` field (every cover was broken/hidden), and the typed query was inserted unescaped (no-results message and highlight) — now escaped, regex-safe.
- **Routing fixes found by the new tests:**
  - The delegated `a[href^="/"]` handler ignored modifier/middle clicks and `defaultPrevented`, so Cmd-click on any card navigated the current tab, and cards that also had their own click handler loaded twice. It now skips those; cards, chapter rows and the side-by-side link have no click handlers of their own anymore — one routing path for every real link. `[data-route]` handler removed (only my new links used it, and it double-routed).
  - `resolveBookBySlug` compared the percent-encoded path segment to the decoded slug, so `/books/louise-de-la-vallière` never hydrated (no summary/chapters) — also broken on main. Now decodes.
  - Top-10 arrows could stay disabled after returning home (scroll event while hidden); `updateTop10Buttons()` re-runs each time home is shown. `top10_ssr.mjs` was intermittently failing on this; 6/6 after.
  - `#hero-section` kept a `width: 100vw` full-bleed rule → 20px horizontal scroll on desktop and content flush left. Removed.
  - Discover's client fill re-checks after its `await` so two quick navigations can't double-fill (was 180 cards / 90 unique).
- CSS: a rule-aware pruner removed 105 old home rules (hero banners, cover wall, learn-* clipart grid, big rank numerals, gradient band); new `.home-*`, `.hero-sentence*`, `.level-card*`, `.how-*`, `.header-search*` rules; search box restyled on tokens. Phone header hides the wordmark and Categories (footer has it) so Library/Discover/Books fit.
- Test edited (flagged): `tests/test_response_compression.py::test_html_is_gzipped` used the old heading text "Where Most Readers" as its marker; switched to the structural `id="hero-section"` — the gzip behaviour it checks is unchanged.
- Left in place: `frontend/static/images/{infographic,chapter_view,summary,library_view}.{jpg,webp}` (~940 KB) are now unreferenced; `renderTop10CarouselInContainer` in app.js was already unused before the redesign.
- Tests: `tests/test_home_redesign.py` (10) and `tests/e2e/redesign_home.mjs` (20), red first; `redesign_cards.mjs` +1 (accented direct load). pytest 629 passed; e2e suite green (same 6 pre-existing failures excluded); redesign tests + top10_ssr also pass on the prod bundle.
- After screenshots: `docs/redesign/after/phase6/`.

### Phase 7 — reader restyle (DONE)

- Structure unchanged: back · chapter / book title · contents · reading settings; reading mode (Summary / Original / Plain English / Side-by-Side) stays in the settings panel — no header toggle (user decision).
- Light theme: paper toolbar with ink text and hairline (was a black bar), outline buttons, serif chapter title in the toolbar and serif chapter headings. Dark and sepia themes now style the toolbar themselves (dark keeps #1a1a1a with dark borders; sepia gets the sepia background).
- Progress: thin oxblood bar (`#reader-progress-fill`, updated next to the existing percentage in `reader.js`).
- Panels: contents and settings on `--surface` with serif headings; active mode in oxblood; settings labels sentence-case ("Reading settings", "Font", "Text size"). Replaced the remaining hard-coded old-blue tints (`rgba(52,152,219,…)`) in font/size/theme controls and the "coming soon" pill.
- Side by side: hairline between aligned rows in the continuous reader.
- Tests: new `tests/e2e/redesign_reader.mjs` (15 checks incl. dark theme and mobile), red first; also passes on the prod bundle. pytest 629 passed; e2e suite green (6 pre-existing failures excluded).
- After screenshots: `docs/redesign/after/phase7/`.

### Follow-ups from review (2026-10-13)

- **Chapter illustrations restored.** On main they were drawn only by the old chapter view; once phase 5 sent book-page chapter clicks to the continuous reader they were unreachable (Alice, Peter Pan, Oz, A Christmas Carol — 58 chapters). The continuous reader now renders each illustrated chapter's picture as a frontispiece just before its heading (`continuousIllustrationHtml`, URLs from `illustrationSources`, shared with the old view), in all modes incl. side by side; fixed-height `figure.reader-illustration` registered as a pagination block in `pagination.js`. Click opens the existing lightbox. Test: `tests/e2e/reader_illustrations.mjs`.
- **Chapter-list excerpts removed** (user: cut-off snippets that mostly restated "Chapter N, '<title>'"). Rows are number · title · time · check. Dropped `summary_excerpt` from the API, `study_cues.summary_excerpt` and the `_summary_head` SQL column; `first_sentence` stays (home hero).
- **Book header redesigned** (user): framed 220px cover with shadow, balanced serif title, both actions 48px and on one row ("Side by side" is a surface button with a two-column icon), button label is just "Start reading" / "Continue reading" / "Read again", and a progress line under it ("Chapter 6 of 13 · The Five Orange Pips" + thin bar) for signed-in readers. Phones: cover beside title/author/meta, actions and progress full width below. `redesign_book_page.mjs` updated (24 checks).
- pytest 622 passed; e2e suite green (6 pre-existing failures excluded); book page + illustrations pass on the prod bundle.
- **Illustration below the chapter title** (user). Pagination now keeps a chapter heading with the block after it — a page never ends on a heading — so title + picture open the chapter together.
- **Reader progress stuck at 0%** (user; also on main). The footer % came from the furthest marker, which only advanced when a page turn's first paragraph was exactly the next paragraph ordinal — almost never true (several paragraphs per page; long ones span pages). So Library % and book-page checks barely moved either. Now: a forward page turn (`navigateToNextPage`, or moving into the next segment) sets `reader.forwardTurn`, which is what counts as sequential; the footer/bar show the current position. Removed the now-unused `lastDisplayedOrdinal`. Test: `tests/e2e/reader_progress.mjs` (progress API mocked; 8 turns → 0% → 4%, every save carries an advancing furthest marker, a backward turn doesn't). Existing users' saved furthest positions only advance from their next read.
- **Header search, account, summary + Listen redesigned** (user, 2026-10-13). Header search is an always-visible 240px field on screens ≥900px (results right-aligned under it, no heavy focus ring or native clear button); below 900px the magnifier opens a full-width bar under the header. The account button is a 36px circle with the reader's initial (no emoji); the account modal is a surface card with a serif title, email row, two stat tiles and an "Open your library" link. The summary block: "Summary" heading, a Short/Full segmented switch with reading times ("Short · 2 min"), serif text, "Read more"/"Show less" with a chevron (collapse no longer throws — it scrolled to a removed element), and "Read the full summary →" on Full. Listen is one stateful button (Listen → Preparing… → Pause → Resume) that follows the audio element; a second click pauses instead of regenerating. The bottom player is a flat surface bar with SVG controls. One control radius (`--radius-control: 8px`) for primary/secondary/read/listen buttons; `.btn-primary` uses `--on-accent`/`--accent-hover`. 63 legacy rules removed (old tabs, expand links, user modal, gradient player).
  - Bugs fixed on the way (also on main): pausing before audio started rejected `play()` with AbortError, which showed an alert and stopped playback; lock-screen artwork requested `/static/covers/<id>.png` (404 — covers are .jpg/.webp), now uses `coverSources`.
  - Test: `tests/e2e/redesign_header_summary.mjs` (TTS endpoint mocked to an existing audio file). `redesign_home.mjs` no longer clicks the desktop search toggle (it no longer exists on desktop). pytest 622 passed; e2e suite green; new tests pass on the prod bundle.
- **Continue-reading / Library card covers cropped** (user). The cover frame stretched to the card's full height while the cover stayed 108px (82px on phones) wide, so the 2:3 box became ~1:2 and `object-fit: cover` cut off the sides of the art. The frame now top-aligns the cover at its natural 2:3. Test: `redesign_home.mjs` checks the cover ratio and that the image fills it, at 1280px and 375px.
- **Home hero: option B "open book" + more contrast** (user picked B from three mockups — A title page, B open book, C shelf backdrop — and asked for more contrast). The hero is now a full-bleed ink band (`--ink` bg, paper title, serif-italic tagline, one paper-filled CTA). The sentence example is an open book spread: original on the left page, plain English on the right (stacked on phones), shaded toward the spine, with a page-edge stack and source line as the running foot. All examples share one grid cell (hidden ones `visibility: hidden`), so the book is as tall as the longest example and "Turn the page" never moves the content below. The hero search box was removed — the header search is the one search on every page. Tests: `redesign_home.mjs` (contrast ≥7:1, full-width band, serif tagline, one search field, pages face each other, constant height through every example, phones stack). Updated because the old design changed: `catalog_fetch_once.mjs` and `hero_home_navigation.mjs` now use the header search; `redesign_chrome.mjs`'s "no off-paper bands" rule exempts `.hero-main`.
- **Home hero: text thread, teen tone** (user: the book spread looked like "a book sideways" on phones; the app should suit teenagers assigned a classic, not feel old or serious). Of three options (flip card, text thread, highlighter notes) the user chose the text thread. The author's original line arrives as a left-hand message ("Jane Austen · Pride and Prejudice"), the plain-English version replies from the right in a brighter red bubble (`--accent-bright`), with a short pop-in (off under reduced motion). Same layout on every screen. Messages are bottom-anchored inside the fixed-height cell, so spare space sits above the thread. Copy: "Classics, minus the confusion." / "Find your book" / "Show me another". The generated library backdrop and the engraving options were dropped as too old for the audience (not committed). Tests: `redesign_home.mjs` thread checks at 1280px and 375px, friendly-copy check; `test_home_redesign.py` caption check is now order-independent (sender first is intentional). Open: whether to carry the teen voice and type (sans headlines, highlighter accent) site-wide.
- **Hero examples: harder sentences, complete rewrites, calmer first load** (user). Examples are now famous openings students get stuck on: Pride and Prejudice, Jekyll and Hyde, Great Expectations, Huckleberry Finn, The Time Machine, The Scarlet Letter — the last two later swapped, see below (Jane Eyre and Frankenstein dropped as too easy). The plain side used to be only the first sentence of the rewrite, which lost content when the rewrite split one long sentence in two (Scarlet Letter dropped "…studded with iron spikes"). `pages._hero_pair` now keeps every plain sentence that belongs to the original's first sentence (whole plain paragraph for a one-sentence original; otherwise add sentences while they share more content words with original sentence 1 than 2). All six pairs reviewed by hand. `study_cues.first_sentence` replaced by `split_sentences` (its only caller). The reply bubble animates only after "Show me another" (app.js marks the shown example `.is-new`), not on page load. Phones: smaller bubble type so the fixed-height thread wastes less space (examples 201–384px tall at 375px). Tests: `test_home_redesign.py` (pair matching incl. the split-sentence case, real-DB check that every example resolves, is ≥15 words, and Scarlet's plain text has "spikes"), `redesign_home.mjs` (no animation on load, animation after click).
- **Hero examples swapped for similar lengths** (user chose option 3). Jekyll and Hyde and The Scarlet Letter made the fixed-height thread ~180px taller than the shortest example on phones; replaced with The Hound of the Baskervilles ("save upon those not infrequent occasions") and The Great Gatsby. Phone heights now 201–270px. Test: `redesign_home.mjs` "≤100px of spare space" at 375px. The Scarlet-specific real-DB assertion was removed with the example; split-sentence matching stays covered by the `_hero_pair` unit test.

### Phase 8 — build, compare, deploy (DONE)

- `app.min.js` rebuilt and fresh (`check-build-fresh`); every redesign e2e test also passes against the prod-mode bundle (app_prod on :5003).
- Comparison page: `docs/redesign/compare.html` (before = local main @ 051244c, after = phase 7; desktop/mobile toggle; 17 screen pairs).
- Local perf (perf.mjs, 3 runs, FCP / total bytes): home 284·84·68 → 272·72·72 ms, 1676 → 1461 KB; book page 56·52·52 → 60·56·56 ms, 1635 → 1655 KB; /discover 48·52·48 → 72·100·80 ms (server-renders 90 cards; main's earlier paint is an empty shell that then waits for two API calls), 4144 → 3562 KB.
- **Deployed 2026-10-13** (user approved): `main` fast-forwarded to `redesign` (051244c → d367683, 21 commits) and pushed; VM pulled (24 commits behind, clean FF), `summra.service` restarted (active, local 200, no errors in journal). No DB copy needed. Public `/`, `/books`, `/api/books`, `/discover`, a book page all 200 in <0.4 s; `redesign_home` (34), `redesign_book_page` (24) and `redesign_discover` (19) checks pass against production.

---

## 2026-10-12: Deployed b4359b9; corrected CLAUDE.md deploy section — DONE

Deployed the site-wide speed-up + reader chapter fix (`b4359b9`) to the VM; public pages verified 200, gzip on, SSR carousel/header live, `chapter_ids` in the reader manifest.

The deploy exposed stale facts in CLAUDE.md's deploy section, now corrected (real values stay in the gitignored `.prod-metadata.local.md`, which gained `<GCP_ACCOUNT>`, `<SERVICE_UID>`, `<GUNICORN_PORT>`, `<APACHE_PROXY_CONF>`):
- gunicorn is a systemd **user** service of the service user (needs `sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=/run/user/<SERVICE_UID> systemctl --user ...`), not a system unit.
- It binds `:5001` via `GUNICORN_BIND` in `service.env`, not `:5000`.
- Apache (with OIDC) fronts it, not nginx; Apache gzips static files only.
- The VM checkout's branch tracks a deleted upstream, so the pull step now uses `git pull --ff-only origin main` behind a `merge-base --is-ancestor` guard.
- Only one gcloud account/project can reach the VM; local gcloud config now defaults to them.

---

## 2026-10-12: Chapter destinations open the reader on the right page — DONE (not deployed)

### Bug

Legacy `/books/<slug>/chapters/<n>` links, `/read?chapter=<id>` and table-of-contents jumps loaded the segment containing the chapter but showed that segment's first page — e.g. chapter 20 of *A Journey to the Centre of the Earth* opened on "The Wrong Road!", two chapters early. Same on prod (pre-existing). Also, a signed-in reader's saved place silently overrode an explicit chapter destination.

### Fix (`frontend/static/js/reader.js`)

- `renderContinuousSegments(segments, restoreMarker, chapterId)`: with no restore marker, opens on `findContinuousPageForChapter(chapterId)` — the first page containing that chapter's content (its heading). `loadContinuousReaderAt()` passes the chapter through, which covers all three entry points.
- `showContinuousReader()`: an explicit chapter destination drops the saved marker unless the marker is already inside that chapter.

Note: chapters flow continuously across pages, so the opened page can begin with the last lines of the previous chapter; the chapter heading is on that page.

### Tests

`tests/e2e/reader_opens_at_chapter.mjs` — legacy link and `?chapter=` at 1280px and 390px, TOC jump, saved place resumed by plain `/read`, explicit chapter overriding the saved place. Failed before the fix, passes after. pytest 549 passed; all 13 e2e scenarios pass.

---

## 2026-10-12: Site-wide load-time pass (6 follow-ups to the carousel/book-page fix) — DONE (not deployed)

### Why

Audit after the home/book SSR change found the same "wait on something unnecessary" pattern across the site. User asked for all six fixes.

### What changed

1. **Gzip HTML/JSON in Flask** (`app_base.gzip_response`). Prod's Apache gzips static files but passed gunicorn responses through raw: home HTML 45 KB → ~10 KB, `/api/books` 56 KB → ~8 KB, `/api/discover/carousels` 101 KB → ~9 KB. ETags computed over gzipped bytes (`mtime=0` keeps them stable); 304s still work.
2. **`get_all_books()` single query** — was 1 query + 1 new SQLite connection per book (91 per call). Local: 40 → 16 ms median, 264 → 20 ms max. Output verified identical on the real DB. Also speeds up the sitemap, `/books` SSR and `/api/discover/carousels`.
3. **Summary / reader / legacy chapter routes** render from `__INITIAL_DATA__.book` via new `resolveBookBySlug()`; all four `/books/<slug>/…` routes now embed the same book shape (`_initial_book()` in `pages.py`).
4. **Reader**: manifest segment descriptors gain `chapter_ids`, so opening at a chapter fetches its segment directly instead of scanning segments one by one; current + next segments fetched in parallel. Old cached manifests fall back to the scan.
5. **One catalog fetch**: `loadBooks()` shares one in-flight promise; HeroSearch loads the catalog on first focus/keystroke instead of every page load. Home and book pages now make 0 `/api/books` requests.
6. **Author / category pages** no longer wait for the catalog; `/categories` fetches catalog + category list in parallel. `/api/categories/<id>/books` now includes `slug` + `cefr_level` so its cards open the right book page.

### Found, not fixed

- ~~Legacy `/books/<slug>/chapters/<n>` opens the reader at the start of the segment containing chapter N~~ — fixed, see next entry.
- Prod serves HTTP/1.1 and runs 1 gunicorn worker × 4 threads — server config, not changed.

### Tests

New: `tests/test_get_all_books.py`, `tests/test_response_compression.py`, `tests/test_reader_manifest_chapter_ids.py`, category-books fields test in `test_api_routes_characterization.py`, `_initial_book` cases in `test_book_page_ssr.py`; e2e `catalog_fetch_once.mjs`, `book_routes_without_catalog.mjs`, `listing_pages_catalog.mjs`, `reader_segments_fast_open.mjs` (each failed before its fix). pytest 549 passed; all 12 e2e scenarios pass.

---

## 2026-10-12: Faster home "Where Most Readers Start" carousel + book page first paint — DONE (not deployed)

### Why

User report: the home carousel always loads slowly; book pages sometimes take a few seconds for content to appear. Both waited on a serial waterfall: HTML → `app.min.js` → `/api/books` (full ~57 KB catalog, uncompressed, fetched twice — by `SummraApp` and `HeroSearch`) → per-book APIs → covers.

### What changed

- Home: top-10 cards server-rendered from `TOP_10_GUTENBERG_IDS` (`backend/routes/pages.py`) via new `Database.get_books_by_gutenberg_ids()`. Cards are now real `<a>` links. `renderTop10Carousel()` keeps SSR cards, builds client-side only after SPA navigation, and wires listeners once (fixes stacked duplicate nav-arrow handlers on repeat home visits). Home no longer awaits `/api/books` on full loads.
- Book page: header (title, author, cover) server-rendered; `__INITIAL_DATA__.book` gains `cover_image_url`; router renders the book from it on first load instead of awaiting the catalog.
- Details in `docs/ERD.md` → "First-Paint Server Rendering".

### Measurements (Chromium, 390×844, 150 ms RTT / 1.6 Mbps; prod static assets + local HTML/JS/API through a gzip proxy, old vs new code)

| | Old | New |
|---|---|---|
| Home: first 3 covers visible | 4.4–4.6 s | 2.9–3.0 s |
| Home: DOMContentLoaded | 2.0–2.3 s | 2.9–3.0 s |
| Book: cover visible | ~2.3 s | ~1.5 s |
| Book: summary + chapters + cover | 2.32 s | 2.02 s |
| Book: content with `/api/books` stalled 8 s | waits 8 s+ | 80–110 ms |

Trade-off: home DCL is ~0.8 s later on slow links because covers now share bandwidth with scripts (prod serves HTTP/1.1, so no stream prioritization). Tried eager/`fetchpriority=high` covers: covers 3.35 s but DCL 3.3–3.5 s — worse; all-lazy was best.

### Not done / follow-ups

- Prod serves HTTP/1.1 and `/api/books` isn't gzipped (static assets are) — server config changes (HTTP/2, gzip for JSON) would help every page.
- `HeroSearch.fetchBooks()` still downloads the full catalog on every page load (now off the critical path).
- Top-10 ID list is duplicated in `app.js` (3 places) and `pages.py`.

### Tests

`tests/test_home_top10_ssr.py`, `tests/test_book_page_ssr.py` (pytest: 534 passed), `tests/e2e/top10_ssr.mjs`, `tests/e2e/book_page_fast_path.mjs` (both fail against old code, pass on new), plus smoke, hero_home_navigation, breadcrumb_navigate, breadcrumb_no_flash passing.

---

## 2026-10-18 — Beyond Good and Evil Plain English (in progress)

User requested Plain English for existing book 61. Confirmed all ten chapters (preface 0 and chapters 1–9) lack rewrites. Dry-run: eight Gemini batches. Preserved chapter rows in `/private/tmp/plainly-book61-before.json`; removed stray transcriber/contents material before the preface and the Gutenberg end marker. Normalize source paragraph boundaries before generating; stage output for alignment/completeness review before applying.

Generation stopped before producing output: Gemini API returned `402 RESOURCE_EXHAUSTED` (prepayment credits depleted). Asked user whether to use Codex subagents for the alternative writer/verifier workflow. Prepared numbered prompts and added book 61 to the existing side-by-side regression harness. Source audit: 352 paragraphs, all aphorisms 1–296 plus 65A, 73A, 237A retained. Baseline reader manifest: original 352 units; Plain English and side-by-side unavailable (0 units). No translated content applied.

User authorized Codex subagents and specified GPT 6.1 Sol: low effort writing, medium effort independent verification. Updated local workflow and CLAUDE.md routing accordingly; continuing book 61 via numbered paragraph JSON.

Codex writing underway in disjoint chapter groups using `gpt-6.1-sol` low effort. Persisted original chapter backup at `data/log/agent_plain_english/book61/chapters-before.json`. Initial completed drafts: preface/chapter 1 pass (2/26 paragraphs, ratios 0.90/0.83). Existing gate and availability tests: 33 passed. Fresh medium effort verification remains required before apply.

Seven sections drafted and gated (0–5 and 8). Fresh `gpt-6.1-sol` medium effort verifier started on preface/chapter 1 while writers finish 6–7 and 9. Preserve source edition limitations: aphorism 190 literally contains `[Greek words inserted here.]` in both the ingested text and `data/books/pg4363.txt`; no quotation fabricated.

Independent medium effort QC complete for chapters 0–3: 68 pairs reviewed, 18 paragraphs corrected (7 in 0–1, 11 in 2–3), all four chapter gates pass with no connective warnings. Corrections include lost modal/conditional scope, uncertainty vs doubt, a dropped number, and technical glosses. Writers have completed 350/352 draft paragraphs; QC continues for remaining chapters.

All 352 paragraphs drafted in 41 JSON chunks; independent verification complete for 279 paragraphs across sections 0–8. QC has corrected 57 paragraphs so far (7 + 11 + 17 + 13 + 9 across reviewer groups). Final chapter/poem review in progress. No rewrite applied to DB before all independent reviews finish.

### Beyond Good and Evil — complete (local library)

All 10 sections (preface + 9 chapters), 352 paragraphs, written by six fresh-context GPT 6.1 Sol low effort writers and independently reviewed by six fresh GPT 6.1 Sol medium effort verifiers. Review corrected 66 paragraphs (7/11/17/13/9/9 by group); all aphorism/stanza numbers retained. Applied via `passage_rewrite.py apply` after all reviews and dry-run. Every chapter has exact paragraph alignment, ratios 0.82–0.93, no gate warnings.

Validation: 33 gate/Plain English unit tests passed; side-by-side harness passed all 14 checks, walking all 352 paired units and verifying first/last anchors, no gaps, overflow or console errors. Book page and reader smoke checks passed; reader screenshot inspected. Reader manifest exposes original/plain/side_by_side at 352 units each. Local only; no production deployment. Run outputs, original backup and completion audit are in `data/log/agent_plain_english/book61/` (gitignored). Source limitation: aphorism 190 retains the supplied edition's missing-Greek placeholder.

Local instructions now route Codex to `gpt-6.1-sol` low writing/medium fresh verification via AGENTS.md, CLAUDE.md and both workflow documents; Claude's Sonnet setup remains intact.

### GitHub and production deployment — in progress

User authorized commit/push and VM update. Production: `wordpress-2-vm`, `us-west1-a`, project `<GCP_PROJECT>`, app `/opt/summra`, public prefix `/plainly`. Confirmed no tracked VM edits; existing untracked service config/backups preserved. VM book 61 has the expected original source and no Plain English. Deploy only book 61 chapter source/Plain English with source-hash guards and a full content-DB backup; keep unrelated content and user DB intact. Local gate rechecked: 10/10 pass, no warnings.

### Beyond Good and Evil — deployed to production

Committed and pushed `d59645a` to `origin/main`; VM checkout fast-forwarded to that commit. Updated only the ten book 61 chapter source/Plain English fields, guarded by hashes of the prior production source and verified against the local payload. Full content DB backup: `/opt/summra/data/database.pre-book61-plain-20261019T051032Z.db`. Backup and updated database both pass SQLite quick_check. Unrelated books, user DB and existing untracked VM configuration preserved. No new static assets or dependency changes required.

Restarted the `summra` user service; `systemctl --user is-active summra` returned `active`. Live verification at `https://pengyaochen.com/plainly`: all 14 `agent_plain_english_side_by_side.mjs` checks pass, including every one of 352 paired units, correct first/last anchors, chapter opening, no gaps/overflow and no console errors. Public reader: `https://pengyaochen.com/plainly/books/beyond-good-and-evil/read?mode=side_by_side`.


## 2026-10-18 — Bleak House Plain English (in progress)

User requested the same Codex Plain English workflow for book 93. Source has 68 sections and 1,927,392 characters; no existing rewrites. Using GPT 6.1 Sol low effort writers and separate fresh medium effort verifiers, three concurrent children maximum, with durable checkpoints. Backed up full content DB to `data/database.pre-bleak-house-plain-20261018.db` and chapter rows to `data/log/agent_plain_english/book93/chapters-before.json`. Removed redundant title/byline in preface and moved its stranded PREFACE label to the start; retain Dickens’s author notes and all narrative. Will verify locally and deploy through the established GitHub/VM process.

Bleak House checkpoint: sections 0–7 drafted and pass their chapter gates, with no unresolved writer doubts. Fresh medium effort QC started on chapters 4–5. Run plan has 29 disjoint groups, 194 chunks and 7,172 paragraphs; progress and role briefs are persisted in the book93 run directory.

### 2026-10-19 continuation

Prior sitting stopped at the Codex usage limit with groups 1–3 written, groups 1–2 verified (454 pairs, 15 corrections), groups 4–5 partially written, group 3 verification interrupted. User requested continuation; confirmed usage reset and resumed the three existing agents with saved outputs. No chapter rewrites applied to DB yet.

Checkpoint: sections 0–11 now written AND independently verified (1,089 paragraphs, 40 corrected). All chapter gates pass with no remaining warnings or doubts. Writing continues on 12–17. Progress JSON preserves per-group state and review tallies; no rewrites applied before whole-book verification.

Checkpoint: sections 0–17 independently verified (1,831 paragraphs; 73 corrected), all gates clean. Writing 18–23 underway. Reusing a completed low effort writer context for a new disjoint assignment to reduce startup overhead; prior verified outputs are explicitly out of scope. Verification continues to use fresh medium effort agents for every new range.

Checkpoint: sections 0–19 independently verified (2,058 paragraph pairs; 80 corrected). All clean gates, no unresolved doubts. Drafts 20–21 complete and in fresh review; writing 22–25. Checkpoint manifest and original backups intact; library/production still unchanged for Plain English until whole-book QC.

Checkpoint: sections 0–25 independently verified: 2,866 of 7,172 paragraph pairs, 101 paragraphs corrected. All gates clean, no unresolved doubts. Active writers on 26–28 and 29–30 have saved partial outputs. Usage approaching window limit; optional free-reset authorization asked, no answer yet. No rewrite text applied or deployed.

### 2026-10-19 evening continuation

User requested continuation after another usage stop. Confirmed natural reset (0% primary; three free reset credits still unused). Resumed writer groups 13/14 from saved files; started group 15 (31–32) in an existing low effort writer context. Verified checkpoint remains 0–25, 2,866 pairs, 101 corrections. No text applied or deployed.

Checkpoint: all sections 0–30 independently verified, 3,409 paragraph pairs; 129 corrected. Every gate clean with no unresolved doubts. Writing continues 31–36. Source backup and per-chunk artifacts retained; no Plain English applied/published before all 68 sections pass QC.

Checkpoint: all sections 0–36 independently verified, 4,158 of 7,172 pairs; 161 corrected. All gates clean, no unresolved doubts. Writers on 37–44. Original and staged translation files remain separate; no premature apply or deployment.

Checkpoint: all sections 0–44 independently verified, 4,948 of 7,172 paragraph pairs; 190 corrected. All gates pass, no unresolved doubts. Writers on 45–52, final 15 chapters still pending after those assignments. No text applied or deployed before full verification.

Checkpoint: sections 0–47 independently verified (5,278 of 7,172 pairs; 203 corrected), clean gates and no unresolved doubts. Review 48–49 active; writing 50–52 active. Usage near limit, prioritizing existing review work. Optimized pending plan: tiny final chapters66–67 join group25 chapters55–56 (70,527 chars), group29 merged; unique coverage of all68 sections retained. No text applied/deployed.


## 2026-10-26 — Distill contents cleanup (local)

Reviewed all 54 books / 1,564 TOC entries. Applied 254 title-only repairs across
41 books: 207 concise section-overview labels (Chinese books use 本节概览), seven
doubled chapter numbers in The Vital Question, twelve inherited parent numbers
in Invention and Innovation, five double appendix colons, duplicated Foreword
wording, distinct Introduction overview / Introduction labels, consistent
unnumbered Feynman stories, and the stray “Chapter:” prefix on Wealth of Nations’
introduction. Preserved numbering resets within parts/volumes, decimal sections,
years, mathematical titles, and all chapter order and content. No empty or
malformed titles or duplicate titles within a part remain in the local corpus.

Shared normalization in distill/book_format.py now runs for folder imports and
HTML conversion. Badge handling preserves decimal and Roman numbering, retains
years embedded in named labels, and avoids duplicating existing number/Foreword
prefixes. DistillDatabase.repair_toc() previews changes by default; explicitly
pass dry_run=False to apply in-place title updates. Existing run5 import folders
produce the repaired titles for all 54 books, so reimport does not undo cleanup.

Before application, backed up content DB to
/private/tmp/distill-pre-toc-20261026T160759Z.db (temporary local recovery copy).
Verified all 1,564 chapter IDs, ordinals, part titles and blocks unchanged; all
book metadata and images unchanged; user/progress database logical fingerprint
unchanged. Refreshed 54 existing reader indices and verified every one of 11,374
reader-unit rows identical, including paragraph IDs, offsets and counts.
SQLite integrity_check passes; repeating the repair proposes zero changes.

Validation: all 174 Distill tests pass. An initial reader-shell configuration
expectation mismatch was resolved by concurrent reader work; the final full-suite
run is green. New regressions cover badge normalization, hierarchy/math/year preservation,
part-scoped repairs, idempotence, dry-run behavior, reimport stability, and reader
coordinate preservation. Test invocation uses PYTHONPATH=.:tests, preimports
app packages, and pytest --import-mode=importlib to avoid test-package shadowing.
Installed the existing Beautiful Soup tools dependency in venv to run converter
tests. No production deployment or changes to original vault HTML sources.


### 2026-10-26 — Source as the final Distill chapter (local)

Moved source presentation into a final ungrouped chapter titled Source for all
54 books. Removed the separate sources section below the book-page TOC and its
unused styles. Both web and Kindle readers expose the final chapter through
their existing navigation and block rendering. Empty source metadata creates
no chapter. iter_chapters() includes sources for future imports; books.sources
remains the canonical input metadata for compatibility with existing folders.
DistillDatabase.append_source_chapters() previews by default and appends in
place with dry_run=False; reruns do not duplicate Source, and changes to source
metadata update an existing final Source chapter in place.

Backed up the content DB to
/private/tmp/distill-pre-source-chapters-20261026T161227Z.db before applying.
Verified all 1,564 prior chapter rows and 11,374 prior reader-unit rows remain
identical after refreshing all 54 reader indices. Source adds 54 new chapters
(1,618 total) without changing old IDs, ordinals, blocks, or reader coordinates.
The user/progress database logical fingerprint and book metadata are unchanged.
All 54 canonical run5 folders produce exactly the migrated chapters on reimport;
SQLite integrity_check and migration idempotence pass. Existing saved positions
remain valid; total chapter/unit counts now include Source.

Validation: all 177 Distill tests pass, including migration preservation,
reimport stability, no-source behavior, Source in the web reader API and Kindle
reader, final-chapter completion, and absence of a separate source section.
Updated the design spec to reflect the new presentation. Local only; no deploy.


## 2026-10-26 — Distill latency pass

Profiled the book-to-home path against all 54 real books, using a scratch user DB
with 54 in-progress states (the actual local user DB has none). Found that home,
/api/library, and even a single book page constructed full reader manifests for
the entire reading list. Each manifest reparsed and hashed every chapter before
building metadata that the library needed only for its word count. Auth also
updated last_login on every page/API/private-image request, contending with the
SQLite progress writer.

Replaced Distill library manifest fan-out with a batched word-total hook over the
existing reader index; batched chapter counts and user mode-state retrieval;
scoped book-page progress lookup to that book. Finished cards skip totals.
Added persistent per-book revision tracking with SQLite chapter triggers so
unchanged reader requests can use an already verified index across worker
restarts without reparsing text. Imports and external SQL edits invalidate it;
a concurrent edit cannot be falsely marked indexed. The first lookup after a
legacy migration or content change still validates/rebuilds normally.

Known-user authentication reads instead of updating last_login on every request;
timestamps refresh at most every five minutes. Verified authentication succeeds
while a progress write lock is held, with zero busy timeout. Authorization and
allow-list checks still run on every request. Content-hashed static URLs now
cache privately for one year; bare module URLs and obsolete hashes revalidate,
so deployments remain fresh and assets never become publicly cacheable.

Representative local warm Flask test-client medians (same 54-state fixture):
home 105.20 -> 8.24 ms; book page 96.88 -> 2.78 ms; /api/library 95.43 -> 4.13 ms;
reader manifest 2.34 -> 1.76 ms. The first home lookup after adding revision
tracking was 164 ms, including initial validation and template compilation;
subsequent fresh app processes reuse the persisted index verification.

Headless Chromium desktop (1280x900) and mobile (375x667), actual back-to-library
links, three runs each: home TTFB 9–12 ms, DOM-ready 20–61 ms. Source chapter
reading, reader-back to book, and back-to-home pass without JavaScript errors.
Benchmarks use loopback/dev hardware, not production timings. Scratch user DB:
/private/tmp/distill-latency-benchmark-user.db. Real reading progress untouched.


Validation complete: 328 Distill/shared tests pass, plus 20 Plainly home tests
(1 content audit deselected by the repository default). Ran the Plainly tests in
a separate invocation because the combined run exposed the existing _reload /
tests/plainly package-shadowing problem; the isolated run is green. New coverage
prevents manifest fan-out on home/book pages, verifies batched percentages and
single-book projections, checks index reuse across process restarts and external
or concurrent edits, checks authentication under a held write lock, and checks
private cache headers and authentication enforcement. git diff --check passes.
No source text, chapter IDs, saved positions, or actual user progress modified;
no production deployment. Temporary browser-test server stopped after validation.


## 2026-10-26 — Pre-generated AVIF cover thumbnails (local)

Added 320×480-bounded cover thumbnails in AVIF (quality 60/speed 6), WebP
(quality 80), and optimized JPEG (quality 82). Imports generate all three before
the content transaction; requests only serve stored bytes. The derived
cover_thumbnails table references original image IDs and cascades on reimport.
URLs use a hash of the encoded outputs and return authenticated, private,
one-year immutable caching with ETags. Different cover bytes generate new URLs.
Existing books without derivatives fall back to their original images.

Web cover markup now uses picture with AVIF, WebP and JPEG fallback; list covers
remain lazy and the book-detail cover loads eagerly. CSS preserves existing
cover geometry. Kindle gets the JPEG thumbnail directly. Original book-folder
format, full-size covers, and reader illustrations remain unchanged. Raised
Distill's Pillow minimum to 11.3 (built-in AVIF encoder in supported wheels).
Documented derived-cover delivery in the existing design spec.

Backed up the content DB to
/private/tmp/distill-pre-cover-thumbnails-20261026T200556Z.db, then ran
DistillDatabase.generate_cover_thumbnails() for all 54 books. It generated 162
variants: AVIF 794,971 bytes; WebP 1,113,666; JPEG 1,669,435. Originals total
3,840,055 bytes, so AVIF reduces aggregate cover transfer by 79.3%. A second
backfill generates zero covers. Verified every original image digest, book
metadata row, chapter row, reader-unit row, and real user/progress fingerprint
unchanged; SQLite integrity_check passes.

Validation: 333 Distill/shared tests pass; Kindle tests rechecked (20 pass) after
adding a JPEG-fetch assertion. Coverage checks decode all formats, verify MIME,
ETags/304, authentication, private caching, stale/missing URL handling, no runtime
encoding, idempotent backfill, and reimport invalidation. Chromium desktop and
mobile at 2x pixel density select AVIF and successfully fall back to WebP then
JPEG when the corresponding picture sources are removed. No JavaScript/image
errors; book covers keep 160×240 desktop and 100×150 mobile dimensions. Visually
reviewed original/AVIF/WebP comparisons for representative covers and the mobile
book page. QA artifacts: /private/tmp/distill-cover-quality-comparison.jpg,
/private/tmp/distill-cover-1280.png, /private/tmp/distill-cover-375.png.
Temporary test server stopped. No production deployment.


## 2026-10-26 — Drop favicon and installable Distill PWA (local)

Created SVG and 16/32px ICO favicons from the existing drop logo, plus 32px PNG,
180px Apple touch icon, and 192/512px install icons. Preserved the exact drop
paths and brand colors (#8A2E2E / #FBF8F1); app icons have opaque backgrounds and
padding that keeps the mark inside the maskable safe circle. Chromium rendered
the source SVG into PNGs; visually verified the 512px icon.

Added authenticated /manifest.webmanifest, /sw.js and /favicon.ico routes.
Manifest uses the live prefix for id/start_url/scope and versioned PNG icon URLs;
the HTML link sends credentials for the private deployment. Base HTML includes
favicon/touch-icon links, standalone/iPhone metadata, theme color, and a small
PWA client. It registers the scoped service worker and exposes Install app only
when beforeinstallprompt is available. iPhone installation uses Share -> Add to
Home Screen. The worker stays network-only, with a generic offline navigation
fallback and scoped retry link; it never writes private pages/books/progress to
Cache Storage. Existing authentication and app content remain unchanged.

Validation: all 338 Distill/shared tests pass, including authenticated asset
access, manifest metadata/prefixes, icon decoding/dimensions, maskable safe area,
and worker scope/cache headers. Chromium reports zero manifest or native PWA
installability errors at both / and /distill/. Verified worker control, empty
Cache Storage, offline fallback without book content, successful reconnection,
and install-button prompt handling. Prefix browser test uses a WSGI proxy
simulation that supplies the prefix to every request, including Chrome’s
internal worker/manifest/icon fetches; page-only extra headers were insufficient
for that test harness. Scoped offline retry stays under /distill/.

New assets are distill/static/images/{favicon.svg,favicon.ico,icon-32.png,
icon-180.png,icon-192.png,icon-512.png} and distill/static/js/{pwa.js,sw.js}.
No production deployment or installation on the user’s device. Installability
requires HTTPS in production; localhost is supported for development.


## 2026-10-26 — Complete Plainly PWA installation support (local)

Audited existing support: manifest and iPhone guidance existed, but the manifest
referenced a missing 512px icon, no worker registered, and beforeinstallprompt
was swallowed without exposing an installation action. Added the missing 512px
and padded maskable icons from Plainly's existing book-and-spark SVG, preserving
its separate identity from Distill. Existing 180/192px icons remain unchanged;
the 192px icon now correctly declares purpose any, with a separate safe-area
maskable variant.

Manifest now has a stable prefix-aware app ID, updated brand colors, landscape
support, and credentialed linking. Added an uncached /sw.js endpoint with a
prefix-scoped network-only worker and generic offline navigation fallback.
It never caches HTML, scripts/styles, books, or personal progress in Cache
Storage, preserving the reason the old offline caching worker was removed.
Install app now invokes the native Chromium prompt and hides after installation.
Retained iPhone Share/Add-to-Home-Screen guidance, added iPad detection and
standalone suppression, and made dismissal storage tolerant of blocked storage.
Updated README and removed outdated comments claiming a cache-first worker.

Validation: 69 targeted Plainly URL-prefix, branding, asset-versioning, and home
page tests pass (one content audit deselected). Added manifest/icon dimension,
maskable safe-circle, worker MIME/cache/scope, and installation-markup coverage.
Rebuilt app.min.js; npm run build:check passes. Chromium native manifest and
installability checks report zero errors at / and /plainly/, with correct app
ID/scope, worker control, and empty Cache Storage. Native-prompt wiring, scoped
offline fallback, reconnection, and iPhone install guidance/dismissal pass with
no JavaScript errors. Browser verification uses scratch content/user databases
and an accurate prefix proxy simulation. Visually inspected the maskable icon.
No production deployment or installation on the user's device.


## 2026-10-26 — Release preparation

User authorized committing, pushing and deploying the TOC/Source, latency,
cover-thumbnail, and Distill/Plainly favicon/PWA work. Final checks: 338
Distill/shared tests, 69 targeted Plainly tests, and production bundle freshness
pass. The test suites must run separately and sequentially: their shared fixture
cleanup can delete the other suite's databases if run concurrently; the initial
parallel attempt exposed that harness limitation and the sequential rerun passed.
Production checkout has no tracked edits and is at feb3b4c; host-owned untracked
backend/config files remain untouched. Production Pillow 13.0 already supports
AVIF/WebP. Apply Distill content migrations to the live content DB in place,
with a backup and before/after identity/content checks, instead of overwriting
it with a local DB. Preserve both apps' user/progress databases.

## 2026-10-26 — Production deployment completed

Committed and pushed release e1fbc39 to main, then fast-forwarded the production
checkout on wordpress-2-vm. Restarted distill.service and summra.service; both
are active. Host-owned configuration and untracked files were preserved.

Backed up all four production databases under /opt/summra/data using suffix
.pre-release-20261026T221553Z (an earlier backup set also exists with suffix
.pre-release-20261026T221204Z). Migrated Distill in place: 254 title repairs,
54 terminal Source chapters, and 54 covers with AVIF/WebP/JPEG variants; total
chapters 1,618. All old chapter IDs, ordinals, parts and blocks, original images,
book metadata, and existing reader-unit coordinates remain identical. Both
user/progress databases and Plainly content passed before/after fingerprints;
all four databases pass SQLite integrity checks. TOC/Source migration reruns
report no further changes. AVIF covers total 794,971 bytes across 54 books.

The first verifier accumulated full database dumps in memory and caused swapping
on the small VM. Stopped it before content migration, restored service availability,
then reran with incremental hashing and bounded memory; all preservation checks
passed. This extended maintenance downtime by several minutes. Future releases
should use streaming verification from the outset and precompute cover variants
before stopping services where possible.

Post-deploy authenticated loopback checks pass for Distill home/book/reader,
favicon, all three cover formats, manifests, icons and scoped workers for both
apps. Anonymous Distill remains denied internally and redirects to authentication
on public HTTPS. Warm median loopback home latency: Distill 9.4ms, Plainly 4.5ms
(excludes network/browser latency). Public HTTPS Chromium reports zero Plainly
PWA installability errors, correct /plainly/ worker control and empty Cache
Storage. Distill's authenticated public PWA was not rechecked in a logged-in
browser; its authenticated internal manifest/assets/scopes pass, alongside prior
root/prefix browser verification. No device installation was performed.

## 2026-10-26 — Plainly/Distill sharing review

Reviewed both app shells, PWA routes/scripts/workers, cover rendering, library
cards, reader-index hooks, cache policies and Kindle adapters. No application
code or production data changed during this review.

Highest-value opportunities: move Distill's persistent reader freshness and
batched word totals into shared.reader for both apps; consolidate the duplicated
PWA registration/install lifecycle and network-only worker with app metadata;
share static cache policy with explicit public/private visibility and immutable
caching only for verified content hashes; introduce a common cover-source
contract and picture renderers across Jinja/JS, keeping storage adapters separate;
finish library-card sharing by centralizing the client renderer/view-model and
its server/client parity tests. Existing reader engine, settings, auth, progress,
base styles and Kindle paging/progress are already shared.

Important constraints: Plainly freshness invalidation must include book verse
metadata and section-title edits as well as chapter edits. Preserve stable unit
coordinates and independent user databases. PWA consolidation should retain
app-specific logos, scopes, access rules, colors and optional iOS guidance.
Cover URLs must declare available formats explicitly: Plainly currently renders
WebP/JPEG pairs while Distill has AVIF/WebP/JPEG thumbnails; do not infer AVIF
availability or replace Plainly's storage with Distill's schema. Library-card
sharing must preserve Plainly's Finished/Read again/Mark unfinished controls.

Before expanding the shared server setup, replace module-global progress/whoami
DB handles with app-scoped dependencies; registering a second app in the same
Python process currently overwrites the first app's bindings. Current separate
production processes avoid that condition. Keep discovery/grade filters,
Plain English/audio features, import formats and app-specific TOC semantics in
the owning apps. Further Kindle route unification is lower value because those
content and anonymous-resume semantics differ substantially.

This was a source review; no new runtime benchmark or tests were run. Proposed
implementation order: shared reader fast paths, PWA support, static cache policy,
cover renderers, then remaining library-card rendering. Use cross-app contract
tests for revision invalidation, scopes/auth, SSR/JS parity and progress identity.

## 2026-10-26 — Share reader freshness and batched word totals

Implemented review item 1. shared.reader.index now owns revision-table/trigger
installation, persistent reader freshness checks, and batched library word
totals. Both content databases opt into the shared implementation; Distill's
duplicate methods are removed. Plainly now skips full-book source loading and
checksum work on clean reader requests, and its library projection uses the
existing batch hook instead of building a full manifest per in-progress book.
Hosts without revision tracking retain checksum-based validation.

Plainly invalidation covers chapter insert/update/delete/reassignment, poetry
metadata, and section insert/update/delete (including dangling legacy links).
Non-content book edits do not invalidate the index. Clean requests stay read-only;
dirty validation/compilation and freshness publication use one write transaction,
with a second freshness check after taking the lock. Competing workers therefore
cannot publish an older index over a newer one; failed compilation rolls back
both the unit index and freshness state.

Distill upgrades its existing freshness metadata to reader_revision in place,
preserving revision values, indexed revisions, reader versions and units, then
removes the retired Distill-only metadata/trigger set. Plainly seeds revisions
for existing books, validating each existing checksum lazily once; unchanged
content retains its published version and unit coordinates. Neither app's user
or progress database is migrated or rewritten. No production deployment yet.

Validation: 350 Distill/shared tests pass; 131 targeted Plainly reader, poetry,
Kindle, home, API characterization and listing tests pass (one content audit
deselected). Added cross-app tests for restart persistence without text reads,
external edits, chapter reassignment/deletion, batched totals and dirty-book
selection, concurrent compilers, rollback, and upgrades preserving versions,
units and resolved markers. Added section deletion/restoration and unrelated
metadata regression tests. The first Plainly collection needed Kindle tests
listed before tests that import its fixtures relatively; the reordered run
passes. No production database was used by these test runs.

Benchmark on scratch SQLite backups of local content, warm medians: Plainly's
largest-book freshness check 45.74ms -> 0.32ms; totals for ten largest books
309.75ms -> 10.46ms. Totals match the previous per-book manifest results in all
modes. These measure server-side work, excluding browser/network latency. Distill
continues using its existing fast path, now shared (0.15ms freshness, 0.55ms totals
for ten large books in the same local check). Original content/user databases
were not modified by the benchmark.

## 2026-10-26 — Shared reader changes deployed

Committed and pushed ac80229, then fast-forwarded wordpress-2-vm and restarted
both app services. Created SQLite backups of all four databases under
/opt/summra/data with suffix .pre-shared-reader-20261026T233327Z. Used streaming
table fingerprints to keep verification memory bounded. All existing content
tables, reader versions/units, and both progress databases remained identical
through migration; Distill's revision metadata copied exactly into the shared
table. All four databases passed integrity checks and acquired no new foreign
key violations. All 54 Distill indexes stayed clean without loading chapters.

Post-restart validation warmed all 90 existing Plainly indexes and 54 Distill
indexes; no content versions changed. Both apps' batched totals and clean
freshness checks then passed with chapter/manifest loading disabled. Warm batch
totals across the full indexed catalog: Plainly 84.2ms (90 books), Distill 2.5ms
(54 books). Warm loopback home medians: Plainly 5.0ms, Distill 11.9ms. These
server-side measurements exclude browser and network time.

Both systemd services are active. Authenticated Distill home/book/reader,
cover variants, icons, and both apps' manifests/workers pass live checks.
Public HTTPS returns Plainly 200 and Distill's expected sign-in redirect 302;
anonymous loopback Distill remains denied. Local Python's certificate-store
configuration prevented its HTTPS probe; the system curl certificate store
verified both HTTPS endpoints successfully. Host-owned config/untracked files
were preserved. No user-device installation or browser UI changes were needed.

## 2026-10-26 — Distill product and reliability review

Reviewed current library/book/reader/PWA routes, templates, styles and shared
reader behavior, then exercised an isolated local copy of Distill's 54-book
content DB with a scratch user DB. Production content/progress were not touched.
Desktop 1440px and mobile 390px layouts had no horizontal overflow, and normal
navigation produced no JavaScript page errors. Inspected desktop reader/TOC and
mobile library screenshots. No application code changed during this review.

Verified findings, prioritized for follow-up:
- Reader exit still awaits progress persistence before navigating. Holding the
  mutation response for 3s kept the reader open for ~3091ms after Back; fast
  backend pages alone cannot remove this delay. Bound the exit wait/use suitable
  keepalive persistence, retaining conflict handling and clear save feedback.
- A failed first manifest fetch renders 'Unable to open this book. Retry.' with
  no retry control. Back is also unwired at that point because chrome handlers
  are installed only after manifest/state success. Wire escape navigation early
  and provide functional retry/re-auth/error recovery actions.
- Reader Contents flattens the manifest to chapters only. Winning has five part
  headings on its book page, but zero in the reader panel, so repeated 'Section
  overview' entries lose context. Preserve part headings, mark the current
  chapter, and scroll its row into view on opening.
- Finished state is stored correctly but not represented in Distill's library.
  A scratch completion yielded status finished; the book page nevertheless
  displayed 'Chapter 27 of 27 · 100%' and 'Continue reading', while the shelf
  had no Finished section or badge. Add completion-aware actions/history and
  label Source by its title rather than treating its storage ordinal as a
  numbered content chapter.
- Returning via the book page's Library link discards language/category/search
  context. Reproduced filtered library -> book -> Library returning to bare /.
  Preserve a validated return URL and the prior shelf position.
- TOC overlay does not close on Escape or transfer focus into its panel;
  reproduced focus remaining on reader-toc-button with the panel still open.
  Define panel keyboard/focus behavior, restore focus on close, and prevent
  background page-turn shortcuts while interacting with a panel.

Secondary product opportunities: capped/expandable Reading now, Finished/Unread
filters and shelf sorting, reading-time estimates on book cards/pages, and iOS
Add to Home Screen guidance (Distill currently has no equivalent of Plainly's
banner). Several reliability/accessibility fixes belong to the shared reader
and would benefit Plainly too. This review used browser smoke/fault injection,
not a full regression-suite rerun or a production latency benchmark.

## 2026-10-26 — Distill review fixes and installation branding

Implemented all reviewed items. Shared reader Back now waits at most 250ms for
progress persistence; mutation requests use fetch keepalive and preserve the
existing server-side validation/conflict rules. Added visible save status and
conflict/failure feedback. Back is wired before book/auth loading, load failures
have actionable retry/sign-in recovery, and failed segment requests can be
retried instead of retaining a failed promise. Authentication and manifest
loading begin in parallel. No reading-progress format or content IDs changed.

Reader Contents retains part headings, marks/reveals the current chapter,
transfers/restores focus, closes on Escape, traps Tab within an open panel and
suspends underlying page-turn controls. Settings gets the same focus behavior.
Finished books now have a history shelf and badges, Read again starts at the
beginning without erasing saved progress, and Mark unfinished uses the existing
mutation API. Source is labeled by title. Library links retain validated,
prefix-aware search/filter/sort return URLs and restore prior shelf scroll.
Added Unread/Reading/Finished filters, newest/title/author/shortest sorting,
batched reading-time estimates (220 English words or 400 Chinese characters per
minute), and six-card Reading now with expandable remainder. Added dismissible,
standalone-aware iPhone/iPad installation guidance.

Investigated the portrait PWA icon: live anonymous requests for the manifest
and icon returned Google authentication redirects instead of branding. Changed
the manifest and icon links to dedicated public app-icons URLs, retaining the
stable app ID/scope and original drop artwork. Added a narrow Apache exception
and exact Flask endpoint exemptions for the manifest/favicon/named icons only;
books, reader code, images, progress and the worker remain protected. No user
identity is resolved/upserted for these public requests. Existing installed
shortcuts may retain an OS-cached icon until refreshed/reinstalled; no app-ID
change or progress reset is needed.

Validation so far: 361 shared/Distill tests and 147 targeted Plainly tests pass;
Plainly production bundle rebuilt and freshness checked. Updated the intentional
shared-shell accessibility snapshot. Added tests for public branding/private
content boundaries, validated return paths, status filtering, finished actions,
Source labels, navigation deadline/keepalive and failed-segment retry. Desktop
and mobile fault-injection checks verified initial-load retry, filtered returns,
TOC parts/current/focus/Escape, dismissed iOS guidance and no horizontal overflow
or JavaScript errors. A delayed 3s save now exits in ~336ms. The first full
browser scenario passed its visual/content assertions but found missing valid
hint keys in the scratch server configuration; rerunning with production-equivalent
hint configuration. Production deployment is pending these final checks.

Final pre-deploy checks: the corrected full Distill browser scenario passes,
including desktop/mobile pagination, list/table/figure integrity, Chinese
continuations and restored offsets, structured/current/focus-aware TOC, and
Kindle navigation. A separate browser check confirmed Read again opens Overview. The manual-unfinish
check exposed a missing mode field in the marker copied from the projection;
corrected the request to include that mode before final deployment validation. All 361
shared/Distill and 147 targeted Plainly tests pass; bundle freshness passes.
The deployed Apache fragment matches the repository version before modification,
so the narrow branding exception can be applied without replacing host edits.

## 2026-10-26 — Distill fixes deployed and verified

Released e15e240 plus bfa1434 (manual-unfinish marker correction) to the VM.
Backed up all four production DBs online with suffix
.pre-distill-ui-20261027T020747Z. Backed up the live Apache fragment to
/etc/apache2/service-locations/distill.conf.pre-drop-icons-20261027, installed
the narrow public-branding exception, passed apache2ctl configtest, and reloaded
Apache. Both app services restarted successfully; no content/progress schema
migration or reading-position reset was performed.

Public HTTPS now returns 200 for the Distill manifest, 180/512px app icons and
favicon, with exact SHA-256 matches to the repository's drop PNGs. Manifest
identity/scope remain /distill/. Signed-out home, worker, app JS and library API
still redirect to authentication (302). Authenticated book/reader/assets and
both apps' manifests/workers pass live checks. Reader indexes retained all 90
Plainly and 54 Distill content versions; no stale indexes needed recompilation.
Warm loopback home medians: Distill 13.7ms, Plainly 7.5ms.

Final targeted API regression passes for the mode-bearing unfinish marker;
the corrected browser request returned 200, and a fresh page confirms in-progress
state with finished controls removed. Local Chromium reports zero installability
errors using the new branding metadata. The full Distill browser suite passes;
362 distinct shared/Distill tests and 147 targeted Plainly tests pass across the
final suite runs (509 total). Production bundle freshness passes. A diagnostic
browser wait on an outgoing response body stalled after a successful navigation;
server results and a fresh-browser state check independently confirmed the action.
Existing OS-cached shortcut icons may still need removal/reinstallation; server
progress survives that operation. No user-device shortcut was removed remotely.

## 2026-10-26 — Explicit Read status and saved-progress visibility

Investigated the reported missing progress for 细胞传 against production using
read-only queries. Its state was present: current place in 第四章, furthest place
in the afterword, 685 active seconds, 53 forward boundaries and 123 accepted
mutations. It was automatically marked Finished by an earlier completion event.
That hid it from Reading now; the Finished shelf was below the 54-book grid and
its default Read again link forced restart=1 despite the newer saved location.
No existing reading markers were lost.

User explicitly requires marking a book Read before it enters Finished.
Distill now sets automatic_completion=False in the shared reader configuration;
web and Kindle APIs ignore automatic last-page completion for this host, while
Plainly retains its existing setting. Added authenticated, JSON-only book-status
actions using the existing mutation model (manual_finish/manual_unfinish), with
Mark as read / Mark unfinished controls on web and Kindle book pages. Explicit
status changes retain current/furthest positions; books without prior progress
can also be marked Read. Stale clients cannot auto-finish via the server API.

On adopting this policy, clear_automatic_completions reclassifies only Finished
records without an accepted manual_finish as in_progress. It clears the automatic
finished timestamp and advances the book revision; all mode markers, furthest
positions, reading time and mutation history remain untouched. The operation is
idempotent and never clears explicitly marked Read books on subsequent startups.
Deploy with a progress DB backup and before/after coordinate/history checks.

Finished books now default to resuming their saved place; Read from beginning
is a separate action. Their saved chapter is visible, and the Finished shelf
moves above All books with an expandable remainder. Library bfcache returns
refresh the server projection while retaining scroll position. No automatic
reading-position reset is performed.

Validation: 366 shared/Distill tests pass, covering last-page non-completion,
explicit Read/unfinished actions, first-time manual Read, preserved positions,
legacy-status conversion and idempotence, and default resume. A fresh browser
verified that automatic completion leaves the book in progress, explicit marking
changes its status, and Continue reading resumes the saved terminal chapter.

## 2026-10-26 — Explicit Read policy deployed

Deployed 6d1317e. Backed up Distill user state to
/opt/summra/data/distill_user.db.pre-explicit-read-20261027T022828Z.
Reclassified two automatic Finished flags (books 17 and 56) as in progress.
Verified all users, mode_reading_state rows (including current/furthest markers,
reading time and revisions), progress_mutation history and hint records remained
identical through migration. Only completion status/timestamp and book revision
metadata changed. The migration rerun returned zero changes; SQLite integrity
passed and both app services are active. A first deployment precheck used the
wrong hint-table name, aborted before migration and restored the previous code;
the corrected precheck/migration passed.

Validation: 366 shared/Distill plus 131 targeted Plainly tests pass (497 total),
with browser verification of explicit Read, unfinished and saved-place resume.
The bundle freshness check passes. Plainly keeps its existing automatic
completion setting; the new explicit policy is enabled only for Distill.

## 2026-10-26 — Canonical ERD and PRD aligned with deployed reader

Updated [ERD](docs/ERD.md) and [PRD](docs/PRD.md) to cover the deployed
Distill/shared-reader changes: TOC normalization and terminal Source chapters,
precomputed AVIF/WebP/JPEG covers, revision-triggered index freshness and batched
library totals, bounded navigation saves, library filters/shelves and recovery
controls. Added the reader_revision and cover_thumbnails relationships and fields
to the ERD, plus explicit status endpoint and migration semantics.

Documented the Distill-only explicit Read policy, saved-place resume for Finished
books and preservation of current/furthest markers, reading time and mutation
history. Plainly retains automatic completion. Corrected the obsolete claim that
PWA installation has no worker: both apps now use scoped network-only workers;
per-app reader content caches remain distinct from server-only progress.
Recorded the narrow public Distill branding exception that allows OS icon fetches
without exposing books, covers, APIs or the worker.

Validation: checked documented configuration, routes, SQL fields, image encoder
settings and migration behavior against their implementations; reviewed the diff,
Markdown fences and local document links; git diff --check passes. Documentation
only; no application code, database migration or service restart in this update.
Historical superseded continuous-reader designs remain unchanged.

## 2026-10-26 — Distill PWA sign-in entry

Added a public, content-free /launch screen and made it the manifest start URL,
retaining the stable /distill/ identity and scope. The screen uses inline styling
and script plus public drop branding; it never depends on protected reader assets.
A credentialed no-store session check with manual redirect handling opens the
library for an authenticated owner, or leaves a clear Sign in link when signed
out. Visibility/bfcache returns recheck the session. The protected /login route
uses the existing Apache Google/OIDC challenge and redirects to the library after
authentication. Extended only the exact public launch exception in Flask/Apache;
books, progress, other assets and the worker remain protected. No progress reset.

The existing worker already passed a desktop cross-origin redirect test; this
change provides a deliberate installed-app entry rather than assuming its cookie
jar shares a Safari/Chrome sign-in. Existing installations can retain the previous
root start URL until their manifest refreshes; root authentication remains valid.

Validation: 369 shared/Distill tests pass, including root/nested deployment
prefixes, anonymous launch and protected login. Full Distill web/mobile/Kindle
browser regression passes with signed-out launch and authenticated relaunch checks.
A separate two-origin gateway simulation verified the actual launch HTML with an
active Distill worker, sign-in navigation, callback cookie, return to the private
library and authenticated relaunch. Real Google authentication on an installed
user device was not exercised. ERD and PRD updated; git diff --check passes.
These changes remain local; production needs the matching Apache fragment as well
as the app code before the public launch URL can work.

## 2026-10-26 — Required documentation before commits

Updated AGENTS.md to require ERD, PRD and worklog updates after every coding
update and before committing. The pre-commit check must confirm all three reflect
the final implementation and are included in the commit. Changes without an
architectural or product impact must explicitly record that assessment rather
than skip a document. This instruction update changes no application behavior
or data model.

## 2026-10-26 — PWA sign-in release preparation

Reviewed the PWA login changes and all three canonical documents before commit,
including the new AGENTS.md documentation requirement. Re-ran shared/Distill
regressions: 369 passed. The VM is at 4443d50 with no tracked changes; its Apache
fragment matches the repository and both app services are active. Deployment will
back up the Distill progress database and Apache fragment, fast-forward the
checkout, install the matching fragment, validate Apache configuration, restart
only Distill and reload Apache. Verify public launch/manifest, OIDC login redirect
and protected content boundaries; record the actual result after verification.

## 2026-10-26 — PWA sign-in and documentation deployed

Committed/pushed adfee9e (PWA sign-in, canonical ERD/PRD/worklog alignment and
AGENTS.md documentation requirement) and fast-forwarded /opt/summra to that commit.
Backed up Distill progress online to
/opt/summra/data/distill_user.db.pre-pwa-login-20261027T024300Z and Apache to
/etc/apache2/service-locations/distill.conf.pre-pwa-login-20261027T024300Z.
Installed the matching Apache fragment, passed apache2ctl configtest, restarted
only Distill and reloaded Apache. Both Distill and Plainly services are active.

Live public HTTPS: launch/manifest/drop icon return 200; login, library, worker,
reader script and auth API redirect signed-out visitors to OIDC. Verified stable
manifest identity/scope /distill/ and start URL /distill/launch, plus the visible
Sign in link without private asset dependencies. Authenticated loopback library,
auth check, 细胞传 book page and worker return 200; /login redirects to /distill/.
SQLite integrity passes. All previous progress/mutation/hint rows remain present;
existing mutation history is unchanged. Concurrent real reading added navigation,
page-turn and explicit manual_finish mutations (219 to 228 rows at verification),
so live book/mode state legitimately advanced after the backup rather than being
byte-identical. No reading markers were reset.

369 shared/Distill regressions passed before release; the preceding full browser
suite and two-origin login simulation passed. Direct SSH and HTTPS briefly timed
out during follow-up checks; IAP verified the VM and VM-origin public HTTPS 200.
An initial external Chromium navigation also timed out, so do not treat that
attempt as proof of actual device Google sign-in. No Google credentials were
entered and no user-device installation was modified.
A fresh external Chromium retry succeeded: the live launch screen's Sign in
action navigates to accounts.google.com. Authentication completion with the
owner's credentials remains a device-level check; no credentials were entered.

## 2026-10-26 — Whole-card saved-place navigation

Distill Reading now and Finished cards now wrap the complete card in one native
reader link, including cover, title, progress and whitespace. The Continue/Resume
visual is a span inside that link, avoiding nested interactive elements. Added a
visible keyboard focus outline and retained saved-place and library-return URLs.
Plainly's JS-controlled cards without read_href keep their existing markup. No
schema or progress-storage changes; ERD and PRD updated before any commit.

Validation: 369 Distill/shared tests pass in the established Distill-then-shared
order. Browser checks on the rendered shared template verify cover, title, author,
location, progress, Continue action, empty space and Tab/Enter all navigate to the
same saved-place reader URL. An initial reverse-order suite exposed the already
documented shared app-global isolation limitation; the established order passes.
git diff --check passes. Changes remain local and uncommitted; no deployment.

## 2026-10-26 — Whole-card navigation deployed

Committed/pushed 6293e57 with the card changes and ERD/PRD/worklog updates, then
fast-forwarded /opt/summra and restarted Distill. Both Distill and Plainly services
are active. Authenticated production library HTML verifies all three live shelf
cards are complete native anchors to reader URLs, retain the library-return query
and do not force restart. Continue/Resume visuals are spans, with no separate
button-only click target; the deployed CSS contains the visible focus outline.
No Apache configuration, database migration or progress reset was required.

The preceding 369-test suite and browser checks cover every card region and
Tab/Enter; all 19 reader-config/template regressions passed again before commit.
Updated ERD and PRD with the live verification result. Documentation-only follow-up
requires a VM fast-forward, with no further service restart.

## 2026-10-26 — Higher-resolution iOS Home Screen icon

Investigated Distill's icon assets: the existing 512×512 drop PNG is sharp and
fully opaque, but apple-touch-icon explicitly selected the separate 180×180 PNG.
iOS prefers the Apple touch link over manifest icons, so the manifest's 512px
entry alone did not change this selection. Pointed the shared Distill web base
(including public launch) to the existing public 512px drop with accurate sizes
and its content hash, changing the requested URL from icon-180 to icon-512.
No raster upscaling or new asset is involved. No data-model, app identity,
authentication or progress changes. ERD and PRD updated. This improves the supplied
source resolution; actual device appearance and OS icon-cache refresh still need
iOS verification. Existing installs may need re-adding after deployment.

Validation: all 28 Distill app tests pass, including public icon decoding and
Apple-touch selection on library/launch at root, /distill and nested prefixes.
git diff --check passes. Local changes only; not yet committed or deployed.

## 2026-10-27 — CI repaired after pairing tests landed

CI on main had failed for 8 pushes, starting with the Kindle pairing commit.
pytest stopped at collection: `tests/distill/test_pairing.py` imported
`tests.distill.conftest`, and `tests/` is not a package under CI's plain `pytest`.
It now uses a relative import, as `test_app.py` does. This exposed two more
problems. First, the Kindle reader golden had not been updated for the
font-size data attributes added in 497f761, so it was regenerated. Second,
CI never installed `distill/requirements.txt`, so `qrcode` was missing and the
QR route returned HTML. That install is now in `ci.yml`. Run 40623715697 passed
(1205 tests). The local venv's editable install was stale (it mapped the
pre-split `backend`/`scripts`) and was reinstalled with `pip install -e .`.

## 2026-10-29 — How Big Things Get Done: Distill content import

Processing the owner's supplied English EPUB (Crown/Currency, 2023; ISBN
9780593239520) with the book-summary skill's source-extraction, parallel-writing,
independent-review, assembly and direct Distill import workflow. Staging files:
/private/tmp/distill-how-big-things-20261029/. Three writers covered disjoint
chapter groups; a separate fresh-context reviewer is checking the assembled book.
The companion includes the introduction, all nine chapters, coda, both appendices,
an overview and provenance, the complete 25-row cost-risk reference table, all
three embedded figures and the EPUB's cover. No web images were requested.

Pre-import read-only production check: live and local catalogs match exactly
(54 book IDs/slugs/titles/checksums). Local recovery snapshot:
/private/tmp/distill-how-big-things-20261029/pre-import-distill.db. Mechanical
checks pass: 13/13 mapped entries, D1/D2/D3 all 5, all key points present; D6's
numerical 1 reflects intentionally unillustrated chapters (online sourcing off).
Dry-run validates 15 reader chapters including Overview/Source and 12,436 words.
Scratch import passes web/Kindle library, book and reader rendering, all four
JPEG routes, reader manifest, database integrity and foreign-key checks. Scratch
user state is separate from real reading progress. No application code, schema,
or product requirements changed; ERD/PRD changes are unnecessary for this content
addition. Independent review found and corrected two compression errors (ongoing versus completed book-writing duration; the number of stations versus the number of shared designs). The fresh reviewer verified both fixes in rebuilt book.json and approved the final result: D4/D5/D7 all 5. Rebuilt gate/D1/D2/D3 still pass; final text is 12,448 words. Added the generalizable source-compression safeguards to the skill as its feedback step requires. Master import succeeded as book 59, bringing the catalog to 55 books; all previous 54 IDs/titles/checksums are unchanged, integrity is OK, and foreign-key checks pass. Deployment succeeded with the existing push_book --deploy script (verified media upload and live backup, content DB swap, service restart and expected unauthenticated 401). Live checks confirm 55 books, new book 59, 15 reader chapters, authenticated book/reader/cover/manifest HTTP 200 and every reader segment HTTP 200. Live integrity and foreign-key checks pass. Published URL: https://pengyaochen.com/distill/books/how-big-things-get-done. Account/progress databases were not replaced. No code changes or commit.

## 2026-11-02 — The Innovator’s Dilemma: Distill content import

Prepared an original English summary from the owner-supplied Clayton M.
Christensen EPUB (SHA256
40cfb78b6cfd019d789df284ade43d381ed0dfe995280026076cc9fc2a062834).
Authoring folder: data/distill_import/the-innovators-dilemma/ (ignored data);
source extraction and consistent pre-import DB backup are under
/private/tmp/distill-innovators-dilemma/. The owner explicitly approved creating
the folder and publishing. The summary includes an overview, introduction, all
eleven chapters, book-group discussion/application, provenance and EPUB cover:
15 reader chapters, 5,395 words. Historical examples and the hypothetical
electric-vehicle application are identified as the book’s period and argument.

Pre-import read-only checks found identical local/live catalogs (55 book
IDs/slugs/titles/checksums). Format validation passes; a scratch import passes
web/Kindle library, book and reader rendering, cover and manifest routes, both
reader segments, anonymous auth rejection, integrity and foreign-key checks.
Scratch account/pairing DBs are isolated from real user state. Source spot-checks
confirmed resource/process/value distinctions, market-relative disruption,
organizational independence, and the EV chapter’s speculative status. No app
code, schema or product requirements changed; ERD/PRD need no content-only
update. Publication is pending; no commit.

Publication completed through the existing push_book --deploy workflow: book 60,
56 total books. All prior 55 local IDs/slugs/titles/content checksums remain
unchanged. Live catalog digest matches the complete local catalog
(3bb2c904a567a07472e111306be4baf83888882a8edf07a670e4e04002f78d7a).
Verified live book checksum, 15 chapters, integrity OK and no foreign-key errors.
Authenticated loopback library, book, reader, EPUB cover, manifest and both reader
segments return HTTP 200. Public launch returns 200 and the private book URL
redirects signed-out visitors (302). The deploy script completed verified media
installation, live database backup, content swap/restart and expected anonymous
loopback 401. It did not replace account/progress or pairing databases.
Published: https://pengyaochen.com/distill/books/the-innovators-dilemma.
Content-only addition; no code changes or commit.

## 2026-11-02 — The Innovator’s Dilemma: rubric audit and rebuild

At the owner’s request, audited the published book against the now-discovered
book-summary skill and RUBRIC.md. The initial mechanical check scores D1 1/5
(all 13 sections below 600 words), D2 5/5, D3 3/5 (Introduction lacks keypoints),
and D6 1/5 (no embedded figures). Existing source notes omit extraction details
and explicit part-grouping provenance. The supplied EPUB contains substantive
figures for the Introduction and chapters 1–10, so the prior omission does not
qualify for the skill’s default online-image exemption. Chapters 11 and the Book
Group Guide have no substantive embedded figure; external sourcing remains off.

Verified that local and production catalogs match: 56 books, identical IDs,
titles, slugs and content checksums (catalog digest
6a258cb408cb38c927902f861337ae1d8182e941c77f4c53cd29bf2f6cc772d2).
Book 60 is the existing entry and will retain its slug/ID. Created a consistent
pre-revision content snapshot in the existing scratch authoring directory,
/private/tmp/distill-innovators-dilemma/. Three source-reading writer subagents
are rebuilding disjoint chapter ranges; a fresh independent review will follow.
Recorded the actual TOC/source lengths and restored eleven EPUB illustrations,
with original source credits. Rebuilding content/provenance only; no app code,
architecture, schema or product-requirement changes, so ERD/PRD are unaffected.
Publication pending completion of the rubric gate and independent review.

## 2026-11-02 — How Big Things Get Done: published rubric audit

Read-only audit requested by the owner against the book-summary skill and its
RUBRIC.md. Confirmed production book 59 matches the local content checksum
cb670b0823adf1986bccaf40c6113a87ca634605aea963a27c0b665c44995d54.
Recovered the actual Crown/Currency 2023 EPUB from the Calibre library; its NCX
confirms all 13 mapped entries and their order. Recomputed source lengths from
the chapter XHTML and current summary lengths with the skill scorer in memory:
all summaries are 713–1,222 words, in the allowed band including its soft cap.
Gate passes; D1/D2/D3 score 5. All three substantive embedded figures are present
in the correct chapters (1 and 9), plus the edition cover. D6 numerically scores
1 for 2/13 chapter coverage, but online sourcing remains off under the skill's
explicit default exemption; no embedded figures are missing.

A fresh independent reviewer read Overview, all 13 mapped entries, and Source,
and checked consequential claims against the actual EPUB throughout the book.
D4 specificity and D5 provenance score 5; D7 readability scores 4. No confirmed
factual errors, chapter gaps, or contradictions require rewriting. Optional
presentation polish: move Chapter 1's performance figure beside its dataset
explanation; move Chapter 9's two figures beside their respective discussions;
format Chapter 4's four iteration advantages as bullets. These are minor
presentation findings rather than failed chapters. The prior Caro duration and
Madrid station/design corrections remain accurate. Appendix A's 25 rows and
three numeric columns match the source. No full independent external fact-check
or live visual inspection was claimed. Content, deployment, application code,
architecture, schema, and product requirements are unchanged; no commit.

Rebuild complete: 13 mapped source entries / 15 reader chapters, 13,782 reader
words, eleven embedded chapter illustrations plus the original EPUB cover.
Mechanical gate passes 13/13; D1/D2/D3 all 5/5, every chapter 600–1,300 words
(including the rubric’s soft cap allowance). Raw D6 is 3/5 (11/13); only the
source-unillustrated chapter 11 and guide are exempt under embedded-only scope.
The fresh independent reviewer read all drafts and final JSON and checked
source-sensitive claims. D4/D5 score 5/5. Two D7 findings in chapter 9 and the
guide were fixed by restoring explicit strategy/principle/response lists;
reviewer confirmed both assembled blocks and upgraded D7 to 5/5, with no
outstanding findings. These reinforce the skill’s existing enumeration rule;
no new generalizable error class required an additional skill rule.

The final scratch import passes web/Kindle library/book/reader HTTP rendering,
all twelve original images (exact bytes), three cover variants, all five reader
segments, privacy rejection and SQLite integrity/foreign-key checks. Real user
and pairing state were isolated throughout scratch validation. Source provenance
now records both the OPF and copyright-page ISBNs without conflating them.
Final publication authorized by the original redo/redeploy request; proceeding
through the existing verified-media deployment workflow. No app-code changes or
commit; only this existing work log is tracked.

Re-deployed successfully as the existing book 60 at
https://pengyaochen.com/distill/books/the-innovators-dilemma.
All 55 other book records/checksums are unchanged; all 15 existing chapter IDs
are retained. Final live catalog matches local (56 books; digest
703bb1ed680812d66b086f955e7d03b94da65f5963a9bdf32d2d3733b7a98a4e).
Revised book checksum:
1a17455494a7edbb94253f4c937979509b7175a56e7c2ee9c9280b6d45c56219.
Production verification passes authenticated web/Kindle library/book/reader,
all twelve image endpoints, reader manifest and all five segments (HTTP 200),
expected anonymous book rejection (401), integrity OK and zero foreign-key
errors. Live manifest reports 13,782 words. Deployment refreshed the existing
backup and verified media before metadata activation, then restarted Distill;
account/progress/pairing databases were not replaced. Content-only revision;
no code/schema migration or commit. Scratch findings and verification output
remain in /private/tmp/distill-innovators-dilemma/.

## 2026-11-02 — A Philosophy of Software Design: Distill reading companion

User requested the book-summary skill for the supplied English EPUB and publication
to Distill. Source is John Ousterhout, second edition v2.0 (July 2021), Yaknyam
Press; copyright ISBN 978-1-7321022-1-7. Extracted the complete XHTML spine and
185 print-page anchors. User explicitly selected 22 detailed chapter summaries
with subsection topics retained within each chapter. Three independent writing
chunks cover chapters 1–7, 8–14, and 15–22; fresh rubric/coherence review follows
assembly. Scratch authoring and recovery snapshot are under
/private/tmp/distill-software-design/. Original EPUB cover and nine substantive
embedded illustrations across eight chapters selected; repeated warning icons
and separators excluded. Online image sourcing is off by default. No invented
Parts; closing reference lists are explicitly identified when used in chapter 22.
Validation, independent review, and deployment are pending. Content-only addition;
no application code/schema changes or commit. Existing work-log changes preserved.

Assembly passes the Distill validator and chapter gate (22/22). D1/D2/D3 are
5/5; every chapter is in the rubric depth band with canonical key points.
Raw D6 is 1/5 (8/22 illustrated, nine figures); remaining fourteen chapters have
no substantive embedded illustrations and are exempt under the default online
sourcing scope. Original cover is the tenth image file. Current reader text is
18,432 words across 24 entries (22 numbered chapters, Overview, and canonical
Source). Scratch import passes web/Kindle library/book/reader rendering, all ten
image endpoints with exact byte comparisons, cover endpoints, all six reader
segments, SQLite integrity, and foreign-key checks. Local/live preflight catalogs
match exactly (56 books; digest
703bb1ed680812d66b086f955e7d03b94da65f5963a9bdf32d2d3733b7a98a4e).
Fresh independent review is in progress; master content DB remains unchanged.

Fresh reviewer completed full draft/overview/source reading and targeted source
checks. Three caption precision findings (chapters 2, 3, 7) were confirmed
against original figures and fixed: avoid introducing CSS, preserve the strategic
progress figure’s qualitative/nonempirical status, and distinguish pass-through
configuration variables from the context-object remedy. Reviewer confirmed all
three corrections in rebuilt book.json. Final scores: gate pass; D1/D2/D3/D4/D5/D7
all 5/5; D6 raw 1/5 with source-unillustrated chapters exempt. Added a targeted
caption-grounding self-check to the invoked book-summary skill as its required
feedback step directs. Final validator and scratch reader checks pass again:
18,456 reader words, 24 entries, ten images, six segments. Category: Science &
technology. Publishing is authorized by the original user request; proceeding
through the existing verified-media deployment workflow. No code/schema changes.

Published successfully as book 62:
https://pengyaochen.com/distill/books/a-philosophy-of-software-design.
Live verification confirms 57 books and catalog digest matching local:
4f7c043fa8468edd5287f21867b1490fa841d01e9d7312902f5bc87819d2a3ef.
New-book checksum:
7294d8b5f2323b49da85d37ab62a6f970a2d304cac9155f16bc4d6cbf94532f4.
All previous 56 local IDs/slugs/titles/checksums unchanged. Production web/Kindle
library/book/reader return HTTP 200, all ten image endpoints and six reader
segments pass, anonymous book access returns expected 401, integrity is OK, and
foreign-key checks are clean. Live reader reports 18,456 words and 24 entries
(22 chapter summaries + Overview + Source). Deployment verified media before
activation, refreshed backup, and restarted the service; account/progress DBs
were not replaced. Three writer agents and one fresh independent reviewer used.
No application code/schema change or commit; content and deployment evidence
remain in scratch, with only the existing work log updated in the repository.

## 2026-11-02 — NVIDIA full equity research publication and table support

User requested both supplied October 31 NVIDIA Markdown documents as one Distill
entry, with no summarization, tagged equity research and readable web/Kindle
tables. Built `nvidia-equity-research-2026-10-31` in scratch: 2 parts, 21 sections,
14,626 words, all 21 source tables. Sequential preservation check covers 587
research and 744 valuation source units; both source SHA256 values are recorded
in /private/tmp/distill-nvidia-20261031/conversion-verification.json. Formatting
adaptations: omit YAML delimiters, expose each Markdown link as label plus full
URL (strict-inline does not allow hyperlinks), and use Unicode literal footnote
asterisks. Source files untouched. No summarization or fact revision.

Implemented opt-in grid presentation: actual table grids on web, bounded by the
measured pagination height, with local wheel/touch scrolling. Existing tables
keep their prior flow. Kindle expands opted-in tables into readable paragraphs
with row/column context and original block progress indices. No schema/auth
changes. ERD and PRD updated. Local/live preflight catalogs match at 57 books,
digest 4f7c043fa8468edd5287f21867b1490fa841d01e9d7312902f5bc87819d2a3ef.
Initial focused tests: 48 passed. Broader tests found the expected configuration
snapshot assertion, now updated. Desktop/phone/landscape browser table checks
pass; Kindle's test expected-count typo corrected (194 cells in comps chapter).
Final regression run and deployment pending. Existing WORK_LOG changes preserved.

Final local regression: 257 tests pass (Distill suite, shared block parity, shared
Kindle). Frontend bundle rebuilt; build freshness and diff whitespace checks
pass. Chromium desktop 1280×900, phone 390×844 and landscape 844×390 checks
confirm the 10-column / 17-row comparison grid is retained, bounded, and scrolls
both axes without turning pages. Kindle UA at 1072×1268 renders all 194 cells
of the two comps tables as labeled, paginatable paragraphs; screenshot inspected.
This is browser emulation, not a physical Kindle check. Production checkout HEAD
matches local and has no tracked modifications. Deployment will copy only the
reviewed changed runtime files with a rollback archive; no commit or push, and
pre-existing local work-log changes remain intact.

Published successfully as book 63 at
https://pengyaochen.com/distill/books/nvidia-equity-research-2026-10-31.
Production verifies 58 books, category Equity research, all 21 sections and 21
tables, 844 Kindle cell paragraphs, all 5 reader segments and 14,626 reader words.
Live runtime file SHA256 values match the verified local files. Web/Kindle
library/book/reader return 200; anonymous book access returns 401. SQLite
integrity and foreign keys pass. Catalog digest:
10c0f791b1aa5c93838a1c42c2e553f7caced2a579a2231c690d844b616ad11e.
New book checksum:
95d639d75f35591e11fb3019b1591c1ee00920d02c8b6d7799a92cf70682166a.
All 57 previous local book IDs/slugs/titles/checksums were verified unchanged
before deployment; the exact live catalog matches local after deployment.
The existing deploy workflow refreshed its consistent content/account/pairing
backup, verified media, then activated metadata and restarted Distill. Account,
progress and pairing DBs were not replaced. Code rollback archive:
/opt/summra/data/backups/nvidia-reader-before-20261102.tar.gz. Reader code was
deployed directly; local and production tracked changes remain uncommitted.
No Git commit/push was requested or made. Final Kindle focused run: 22 passed
after adding paragraph separation; prior broad run: 257 passed. Browser screenshots
and conversion/live evidence are in /private/tmp/distill-nvidia-20261031/.

## 2026-11-02 — Kindle startup flash and partially rendered illustrations

User reports visible chapter-start render/flash/re-render and images with blank
upper halves. Code inspection confirms initial pagination/show followed by a
second native PW3 pagination/show after 200 ms, with neither waiting for image
requests; figure/image layout also relied on HTML5/default inline formatting.
The previously configured device at <KINDLE_IP>:2222 timed out, so no physical
reproduction or verification is claimed.

Implemented head-time visibility gating with a 15-second failure fallback,
load/error-aware image readiness capped at 10 seconds, and a single final reveal
after the preserved PW3 shell settlement. Images are explicitly proportionally
sized before columns to fit the viewport with caption/margins. Distill figures
and images use explicit block layout. Identical resize events no longer trigger
repagination. Broken/stalled images cannot reflow visible text later. No schema,
content, account, auth, launcher or device changes. Existing NVIDIA/table work
and prior work-log modifications are preserved. ERD/PRD updated.

Added delayed-image portrait/landscape browser coverage in the existing Kindle
e2e script, including single reveal, image/figure geometry and end-anchor reload.
Initial Chromium and WebKit image/readiness/geometry checks passed; the initial
end-anchor test used same-document fragment navigation, corrected to reload for
a true chapter-start check. ES5 source gate initially matched the word “let” in
a comment; wording corrected without changing syntax. Full regression and final
browser checks are running; deployment pending.

Local validation complete: 301 relevant Python tests pass (Distill, shared Kindle,
Plainly Kindle and markup characterization), plus the ES5 source gate. Extended
Chromium/WebKit tests pass for delayed portrait/landscape images, one startup
reveal, unchanged-geometry resize suppression, font resizing, native fullscreen
entry/exit, end-anchor restoration, failed/stalled image late-arrival stability,
and no-JavaScript reading. Existing full Plainly Kindle browser suite passes,
including sync/resume, Original/Plain English switching, page boundaries and
native PW3 shell/fullscreen geometry. Real Atomic Habits and Software Design
illustrations fit and appear complete in WebKit screenshots, visually inspected.
Physical Kindle remains unreachable; browser emulation cannot establish device
paint correctness or native drag containment. Preparing a five-file deployment
with preimage hash checks and rollback; content DB will not be deployed.

Deployed the five reviewed runtime files with exact preimage/SHA256 checks;
rollback: /opt/summra/data/backups/kindle-render-before-20261102.tar.gz.
Restarted Distill and Plainly because both cache the shared reader template;
both services are active. Production verifies all five file hashes, startup
visibility guard in the head before the body, updated JS/CSS, authenticated
Distill and Plainly Kindle chapters (200), original illustration asset (200),
and anonymous Distill rejection (401). All 58 book records/checksums match the
pre-deploy catalog digest
10c0f791b1aa5c93838a1c42c2e553f7caced2a579a2231c690d844b616ad11e;
integrity and foreign keys pass. No content/account/progress/pairing database
was copied or replaced. No launcher/device modifications. No commit or push;
earlier local and production changes remain preserved. Final diff whitespace
check passes. Live/deploy evidence: /private/tmp/distill-nvidia-20261031/
kindle-live-verification.json and kindle-deployment.json. On-device confirmation
of the reported painting symptoms remains pending; no claim of physical proof.

## 2026-11-03 — Commit and synchronize all pending changes

Owner explicitly requested logging, committing, and pushing all changes to
GitHub and the VM. Scope includes the pending historical content-publication
work-log entries, full NVIDIA publication, opt-in research grids and Kindle
cell flow, startup single-reveal/image sizing repairs, built web bundle, and
regression tests. ERD/PRD describe the final implemented behavior and explicitly
record no additional product/schema impact from this synchronization step.
The previous “no commit/push” notes describe the earlier deployment stage and
are superseded by this request.

Re-fetched origin before committing. Targeted regressions pass: 303 tests;
frontend build freshness passes. Earlier Chromium/WebKit image regressions,
full Plainly Kindle navigation/sync/fullscreen checks, web table viewport checks,
and live production/privacy/catalog checks passed as recorded above. A final
full Python suite is running. GitHub push and VM Git synchronization are pending;
VM directly deployed runtime edits will be preserved and matched by hash before
fast-forwarding the checkout. Databases/media are already live and will not be
replaced. Physical Kindle verification remains pending (device unreachable).

Final validation: the full suite passed 1,219 tests; eight Gutenberg-dependent
checks failed only because sandbox DNS/network access was blocked. Re-ran those
eight with network access: 8/8 passed. Combined result: all 1,227 selected tests
pass, with two existing deselections and one dependency deprecation warning.
Build freshness and diff whitespace checks pass. Origin/main matches local base
(e5849fa), and the VM is on that base with exactly the twelve expected tracked
runtime edits. Proceeding with the owner-authorized commit and push; runtime
hash comparison and a recoverable stash will protect VM edits during Git sync.

Code release committed and pushed to origin/main as
575447d1c3c8559ee2896ce6beea362578941feb (Fix Distill research tables and Kindle
rendering). GitHub CI run 41667479715 passed, including the full Python suite
and bundle freshness check:
https://github.com/pengyaoc/summra/actions/runs/41667479715.

VM fast-forwarded to the same revision. All 19 changed file SHA256 values match
local committed files; its tracked worktree is clean. The twelve matching direct
runtime edits were preserved in recovery stash
70717e5c40806c2f3e5da42efbb4a25727b620f4 before synchronization. Both services
restarted and are active. Live Distill web/Kindle library/book/reader, actual
illustrations and Plainly Kindle reading return 200; anonymous Distill returns
401. Startup guard and updated renderer assets are present. All 58 content
records/checksums remain unchanged (digest
10c0f791b1aa5c93838a1c42c2e553f7caced2a579a2231c690d844b616ad11e),
SQLite integrity is OK and foreign keys are clean. No content/media/account or
pairing data were replaced. Existing VM-only untracked configuration was left
untouched. Physical Kindle painting verification remains pending.

This final documentation-only commit records verified outcomes and will also
be pushed and fast-forwarded on the VM. It changes no runtime behavior, schema,
product requirements or data. ERD/PRD include that assessment and the successful
release/CI status. No repeat runtime deployment or test run is required for the
documentation-only sync.

## 2026-11-03 — Physical Kindle verification and image painting follow-up

Connected to the owner's PW3 at <KINDLE_IP>:2222 using its existing key-only
SSH. Owner opened Distill Fullscreen after the initial KOReader screen prevented
normal browser focus. Used XTest pointer input through existing LuaJIT/X11 and
vendor framebuffer screenshots; no browser/root-filesystem/launcher/SSH settings
were changed. Eight-second chapter-start capture shows intermediate blank
startup frames followed by one settled content state; no text-first/text-second
layout is visible. Raw framebuffer sampling omits compositor overlay regions;
vendor screenshots confirm the running header/footer are intact. The initial
missing-header suspicion was a capture-plane artifact, not a reader defect.

Software Design chapter 2 initially paints its complete illustration at the
owner's size 8 / Hei font. Increasing to size 9 reproduces the exact reported
failure: full reserved footprint with a blank upper image region and only its
lower portion painted. This is device-specific multicolumn replaced-image
painting, not absent image bytes or a missing caption. Before/after evidence is
in /private/tmp/distill-nvidia-20261031/vendor-image.png and
vendor-image-size9.png. Physical verification is not complete.

Implementing a native-PW3-only unfragmented image layer: original image footprints
remain in flow/progress, cached display copies paint outside columns at the
same viewport-relative rectangles. Page turns and font relayout reposition the
copies; other profiles/no-JS remain unchanged. Added browser projection regression
checks. ERD/PRD updated; regression, deployment and physical retest pending.

The first follow-up deployment attempt stopped before touching runtime because
the existing backup directory is root-owned. Repeated with root for backup
creation, retaining the exact prior-file hash gate; successfully installed the
single static JS change. Rollback:
/opt/summra/data/backups/kindle-js-before-physical-image-fix-20261103.js.
No service restart was needed: this is a standalone static asset and its
content-hashed URL changes on the next chapter request.

Physical retest passes: the same size-9 layout now paints the complete
1023×483 illustration rather than just its lower portion. Returning to it after
paging also preserves the whole image. Evidence: physical-overlay-size9.png
and physical-overlay-size9-revisited.png in the existing scratch folder.
The owner's size 8 / Hei setting was restored and verified from the menu
(physical-font-restore-check.png). Opened chapter 3 from the actual contents;
its 343×214 illustration and full caption also paint completely. Chapter 2 and
chapter 3 startup captures each show one settled content layout after blank
initialization. Chapter 3 includes a partial rasterization frame immediately
before the complete frame, with the same text geometry; no second/repositioned
content layout is observed. Framebuffer sampling is not a measurement of the
panel's hardware flash waveform. Vendor screenshots are authoritative for
composited header/footer; raw web-content-plane captures can omit them.

The ordinary idle timeout fired during testing because synthetic XTest clicks
do not count as physical power activity. Woke the device normally and used the
existing bounded fullscreen script with a ten-minute test ceiling; no sleep
prevention or persistent power/SSH/launcher/browser configuration changes.
Native actions need settled-screen waits after font changes; an early automated
navigation sequence landed on Overview rather than the intended next chapter.
That capture is not counted as a chapter-transition pass. The explicit chapter-3
contents selection and subsequent screenshot/capture provide the valid check.
Reading navigation uses the existing signed-in progress synchronization; no
account/progress DB was copied, replaced or manually edited.

Validation: 83 focused Kindle tests pass, then 303 Distill/shared/Plainly reader
regressions pass. Extended Chromium and WebKit delayed-image suites pass,
including native unfragmented-image footprint matching, font changes, startup,
fullscreen, failed/stalled images, end anchors and no-JS. Bundle freshness and
diff whitespace checks pass. No generated media/content changes. ERD/PRD reflect
the physical findings and final correction. Committing and pushing this follow-up
under the owner's standing instruction to log/sync all changes; final Git/VM
revision and CI outcome are reported in the completion message.

After physical testing, requested replacement of the ten-minute test session
with the standard existing fullscreen session for the current browser. This
removes the test-specific ceiling while retaining normal sleep restoration;
no installed script/settings changes. The reader is left at Software Design's
illustration with size 8 / Hei restored.

## 2026-11-03 — Shared Distill article/research publishing skill

Created `skills/distill-publish/SKILL.md` with a focused format/deployment reference, using ordinary tools available to both Claude Code and Codex. Defaults to full-content publication; covers multi-document entries, source attribution/coverage, opt-in web grids and Kindle labeled-cell flow, source images, live/local full-catalog preflight, backups, scoped authorization and accurate physical-device claims. One canonical repo folder will be linked into both agents’ personal discovery directories. No application/runtime/schema changes and no private content or deployment credentials added. ERD/PRD record the no-impact assessment.

Validation: the reference JSON passes the real publisher dry-run and imports into an isolated scratch content DB; no master/live content touched. Skill validation and discovery-link checks are recorded below once complete.

Skill validator passes. The ~/.agents, ~/.claude and ~/.codex discovery links resolve to the same repo skill and matching contents. Publisher example dry-run and scratch import pass. Diff whitespace passes. No runtime tests needed for this documentation-only change. GitHub/VM synchronization follows this commit; no service restart or content deployment required.

## 2026-11-03 — Tesla and SpaceX full equity research publication

User requested Tesla/SpaceX published in the same manner as NVIDIA. Selected each company's November 3 research-document and valuation-analysis Markdown pair, preserving all content in one entry per company with two document parts and category Equity research. Supporting workbooks, chart bundles and session logs are outside this matched scope; neither Markdown source embeds figures. Source hashes and exact sequential source-unit coverage checks are retained in /private/tmp/distill-tesla-spacex-20261103/conversion-verification.json. Tesla: 20 sections, 15 tables, 13,819 reader words; SpaceX: 23 sections, 13 tables, 10,940 reader words. Adaptations match NVIDIA: semantic grid table blocks; Markdown links exposed as label plus full URL; literal unbalanced footnote asterisks represented by ∗; Markdown separator lines omitted. No summarization, source revision, or added financial claims.

Validation: both publisher dry-runs and isolated scratch imports pass. Desktop 1280×900, phone 390×844 and landscape 844×390 browser previews pass table sizing and horizontal/vertical scrolling without page turning or JS errors. Inspected web/Kindle screenshots; Kindle emulation renders largest comps chapters as 135 Tesla and 150 SpaceX labeled cell paragraphs. No physical-device verification claimed for these new entries. Local/live preflight inventories match across books, chapters, images and cover thumbnails at 58 entries; integrity/foreign keys pass. Consistent local backup: /private/tmp/distill-tesla-spacex-20261103/before.db. Master import/deployment and final live verification follow. No app code/schema/product behavior changes. Existing uncommitted Kindle launcher/test/docs work is unrelated and preserved.

Published successfully: Tesla book 64 at https://pengyaochen.com/distill/books/tesla-equity-research-2026-11-03 and SpaceX book 65 at https://pengyaochen.com/distill/books/spacex-equity-research-2026-11-03. Existing publisher performed verified media installation, a consistent live metadata/account/pairing backup, the content DB swap/restart, and normal anonymous 401 check. Final live/local inventories match exactly across all four content tables at 60 entries; all 58 pre-existing book/chapter/image/cover records were verified unchanged. No account/progress/pairing DB replacement. All 43 live Kindle chapters pass exact cell-text/context comparison (535 Tesla, 585 SpaceX cell paragraphs); 4 Tesla and 3 SpaceX reader segments return 200. Both authenticated web/Kindle book/read pages return 200 and anonymous pages return 401; integrity and foreign keys pass. All four vault source hashes remain unchanged. Detailed audit/browser/live results are in the task scratch folder. Only this publication log is being committed; unrelated pre-existing Kindle changes remain in the working tree.

### 2026-11-03: Expand corner reveal hit target after physical retest

- User corrected initial acceptance: bottom-left toolbar reveal was inconsistent.
  Physical logs include presses at x106–107, just outside the 101px reveal target;
  toolbar dismissal still worked there because the page-wide dismissal zone was
  active. Enlarged the reserved corner to 11% of display height (159px on PW3),
  preserving outside-tap dismissal and keeping browser control native.
- Added controller regressions for the observed tap coordinates, the enlarged
  target's on/off behavior and pass-through outside it. Embedded on-device
  controller tests and all 20 focused pytest tests pass. Reinstalled on PW3;
  native XTest verifies reveal and hide at (107,1367), plus swipe reveal and
  outside dismissal. User physically retested and reported “much better now”;
  improved reliability is confirmed, without claiming every tap succeeds.

## 2026-11-03 — Dated NVIDIA, Tesla and SpaceX research covers

User requested one dated cover for each published research entry. Generated a coordinated 2:3 ivory/charcoal engraved illustration series using the built-in image generation tool: NVIDIA GPU/data-center artwork dated October 31, 2026; Tesla electric-car/energy artwork and SpaceX rocket/satellite artwork dated November 3, 2026. Visually checked company names, subtitles and dates. Final original PNGs and exact generation prompts are saved under data/log/distill-research-covers-20261103/ (gitignored content assets); originals remain in the generator output directory. No outside source imagery or added investment claims. Staged each cover against the matching published book JSON and confirmed complete chapter/block parity before import. All three format dry-runs and scratch imports pass, including AVIF/WebP/JPEG cover derivative generation. Production preflight, backups, cover import, deployment and final verification follow. No runtime/schema/product behavior changes; unrelated pending Kindle launcher work is preserved.

Dated covers deployed successfully through the existing media-first/backed-up metadata activation workflow. Pre-import local/live inventories matched across all four content tables at 60 entries. Backup: /private/tmp/distill-research-covers-20261103/before.db. Cover import changed only the three cover pointers/import timestamps plus their new image/derivative records; all chapter IDs/blocks and report checksums are exact matches, and all unrelated content/media records remain unchanged. Final local/live inventories match; integrity and foreign-key checks pass. All nine live AVIF/WebP/JPEG derivatives return exact expected bytes at 320×480, private immutable caching and anonymous HTTP 401. Authenticated web/Kindle book and reader pages return 200. Desktop/phone library screenshots inspected; all three covers load and Kindle contents pages use readable JPEG covers. This is browser/HTTP verification, not a fresh physical Kindle test. Existing account/progress/pairing stores were not replaced. Exact built-in prompts and final workspace paths are recorded in data/log/distill-research-covers-20261103/generation-prompts.json. Only this cover publication log is being committed/synced; pending unrelated Kindle changes are preserved.

## 2026-11-03 — Default dated covers in distill-publish

Updated the shared Claude/Codex publishing skill at the user's request: generate and apply a dated cover per new entry by default, retain approved covers on routine updates, use the actual source/report date (or explicitly labeled publication date), coordinate batch styling, and check text/date accuracy and grayscale readability. Added workspace/prompt persistence, importer-derived AVIF/WebP/JPEG delivery, cover-only text/chapter/checksum preservation, and web/Kindle/private-access verification. Removed the conflicting prohibition on creating covers while retaining the restriction on decorative body images. Updated the format reference to distinguish optional schema support from the workflow default. No application architecture, schema, or product runtime changes. Existing unrelated Kindle launcher work remains untouched.

Skill validation and diff whitespace checks pass; all three personal discovery links resolve to the updated canonical skill. No runtime tests or service/content deployment needed for this instruction-only update.

## 2026-11-03 — Hide absent Distill authors

User requested hiding the None author shown on the three research entries. Added nonblank-author conditions to Distill library/book and Kindle library/contents markup, shared Continue reading cards, and client-side search suggestion author elements. Null, empty and whitespace-only authors omit the element; known names remain visible. No data migration or content changes. ERD/PRD updated. Existing unrelated Kindle launcher/shared-runtime work remains untouched. Existing page/Kindle tests: 53 pass; shared reader configuration tests: 19 pass. Isolated browser verification covers null/empty/whitespace author values, named-author preservation and Kindle/desktop/search views; deployment status follows below.

Live deployment verified at 1bb299d: all five template hashes match, both services active, web/Kindle views omit missing authors and retain James Clear on the named-author control, anonymous access remains 401, and Plainly returns 200. The first Plainly probe preceded listener readiness; the settled recheck passed without another restart. All 60 entries and four content-table inventories are unchanged. Only this deployment-status note is committed; unrelated working-tree changes remain intact.

## 2026-11-03 — Chinese summary of 《真本事：从会工作到会赚钱》

User supplied Sun Yuzheng's Chinese EPUB and requested a Chinese summary published to Distill. Read the actual 2026-04-01 People's Posts and Telecommunications Press edition, ISBN 9787115690500, directly from OPF/NCX/spine XHTML. Extracted all 21 numbered chapters (90,908 CJK characters), with front matter integrated into a Chinese overview. Preserved original 上篇 认知觉醒 / 下篇 知行合一; unnumbered subsections are integrated into their chapters. Three separate writer agents drafted seven chapters each; a fourth fresh-context reviewer read all drafts, checked selected source passages and all captions, and found no substantive factual/coherence/provenance defect. Applied its two list-format improvements in chapters 14 and 21. Every chapter has canonical Chinese key points. Cover extracted from the supplied edition; 10 chapters carry substantive embedded illustrations, and 11 remain unillustrated under the default no-online-sourcing policy. Decorative/repeated assets omitted. Scenario chart captions explicitly qualify hypothetical returns. No independent verification of the author's business/income claims; provenance discloses this. EPUB has no verified printed-page mapping.

Validation: format dry-run and scratch import pass; Gate 21/21 PASS; D1/D2/D3 5/5, reviewer D4/D5 5/5, D7 5/5 after specified formatting fixes; D6 mechanically 1/5 at 10/21 and partially N/A under source-only images. Desktop 1280px, phone 390px and Kindle-UA preview checked, Chinese content renders with no horizontal overflow or JS errors. All 21 scratch Kindle chapters, referenced images, manifest and four segments return 200. Physical Kindle not tested. Categories: Personal growth; Business & leadership. Preflight local/live catalogs match at 60 entries; consistent SQLite backup /private/tmp/distill-zhenbenshi-20261103/before.db. Publication staging and review audit are in that scratch folder. Production import/deploy and final verification follow. No application code, schema, architecture or product behavior changes; ERD/PRD need no runtime changes for this content-only publication.

Published successfully as book 69: https://pengyaochen.com/distill/books/zhen-ben-shi. Existing deployment completed verified media installation, consistent live backups, content activation and service/auth checks. Final VM-local authenticated web/Kindle checks return 200; all 21 numbered chapter routes, 10 chapter images, four manifest segments and all three cover derivatives pass. Anonymous access remains 401. Final local/live inventories match exactly at 61 entries, SQLite integrity/foreign keys pass, and all 60 pre-existing book/chapter/media/cover rows are unchanged. Original EPUB SHA256 remains unchanged; account/progress/pairing DBs were not replaced. Reproducible staged book, extracted text, source hash, review, fixes and browser/live audits saved under gitignored data/log/distill-zhenbenshi-20261103/. No code commit or VM code synchronization needed for this content-only task.

## 2026-11-03 — 国家视角 chapter companion publication

User supplied the 436-page Chinese PDF of James C. Scott's Seeing Like a State and requested a summary published to Distill. Prepared direct PDF-page chapter mapping, ten Chinese chapter summaries across three independent writer chunks, an overview, original four-part structure, and edition/source notes. Used Social Sciences Academic Press June 2019 first edition/printing (王晓毅译、胡搏校; ISBN 978-7-5201-4593-0), retaining the distinction between this edition and its included 2011-edition translator afterword. Extracted the actual edition cover and seven substantive embedded illustrations; chapters 3/9/10 remain unillustrated, with online sourcing skipped by default. Staging and source SHA256 audit: /private/tmp/distill-seeing-like-state/. No application code, schema, or runtime behavior changes. Local/live four-table inventories match at 60 entries, integrity/foreign keys pass, and a SQLite-API local backup is saved as before.db. Independent content review, format/depth validation, preview and deployment verification follow before publication is reported complete.

## 2026-11-04 — Uber equity research publication (post-Q3 update)

User requested the Uber initiation, updated for the Q3 2026 results released that morning, be published to Distill, with Uber only and no changes to other companies' notes. Published in the same manner as NVIDIA/Tesla/SpaceX: the vault's Uber research-document and valuation-analysis Markdown pair (updated in place for Q3: results, Q4 guidance, Hazelbaker departure, re-run model and valuation; BUY, $100 target) as one entry with two parts, category Equity research. Slug uber-equity-research-2026-11-04, 23 chapters, 17,438 words, no author. Exact sequential source-unit coverage check passes for both documents (retained in /private/tmp/distill-uber-20261104/conversion-verification.json). Adaptations: semantic grid tables; Markdown links as label plus URL; separator lines omitted. Cover: a typeset (not AI-generated) 2:3 ivory/charcoal cover in the NVIDIA/Tesla/SpaceX layout dated November 4, 2026, because the image-generation tool was unavailable in this session; final PNG in /private/tmp/distill-uber-20261104/uber-cover.png.

Validation: publisher dry-run and scratch import pass; scratch web preview shows the book page with the cover and a reader chapter. Preflight: local and live catalogs identical across books, chapters, images and cover thumbnails (61 entries) with integrity/foreign-key checks ok; backup /private/tmp/distill-uber-20261104/before.db. Master import (book 70) and existing deploy_db workflow completed; post-deploy local and live inventories match exactly (62 entries) and all 61 prior entries are unchanged. Anonymous request to the book page redirects to sign-in. Authenticated desktop/phone/Kindle reader and physical-device checks were not performed. No application code, schema or product behavior changes.

2026-11-04 continuation: all three writer chunks completed and a separate fresh reviewer checked every draft, overview, source notes and assembled JSON against the rubric, with targeted raw-source fact checks. Corrected the chapter 7 comparative case to explicitly identify Malawi/Nyasaland and distinguish faster dry-season soil drying from meteorological drought; named Manhattan in the chapter 4 example. Improved chapter 2–4 framework lists and split chapter 5's dense concluding paragraph. Reviewer verified fixes: gate PASS; D1/D2/D3/D4/D5/D7 all 5/5, D6 2/5 (7/10 illustrated, expected default no-online-sourcing exception). Ten original numbered chapters, one source-based third-part introduction, overview and source notes yield 13 reader chapters and 19,920 reader word-equivalents. Format dry-run and isolated import pass. Desktop 1280×900, phone 390×844 and touch-enabled Kindle 1072×1448 previews inspected; cover/illustrations load, and ordinary browser checks have no JS errors. Kindle browser emulation is not a physical-device test; touch emulation avoids activating the separate non-touch native PW3 calibration. Updated the book-summary skill with the generalizable geography/causal-level compression safeguard. Current local/live catalogs match at 62 entries (two unrelated additions since the original preflight); fresh SQLite backup retained. Production content deployment is underway; final live verification follows.

Published and verified 2026-11-04: https://pengyaochen.com/distill/books/seeing-like-a-state-zh (book 71). Existing publisher completed the deployment; all 62 pre-existing entries and their chapter/media/cover records remain unchanged, with 63 entries now live. Full live/local inventories match across all four content tables; SQLite integrity and foreign keys pass. VM-loopback authenticated checks return 200 for web/Kindle book/read pages, all 13 Kindle chapter views, all three reader segments, seven chapter-image responses, and AVIF/WebP/JPEG cover derivatives. Anonymous book access remains 401 in both web and Kindle modes. No session cookies or spoofed identity headers were sent to public endpoints; trusted identity verification was VM-local. Account/progress/pairing stores were not replaced. Final content, score/review, screenshots and live verification are retained under data/log/distill-seeing-like-state-20261104/ (gitignored private publication artifacts). Local preview server stopped. No application code changes or physical Kindle verification; no commit requested or made.

## 2026-11-04 — Distill home browser title

Changed the web library template document title from `Library · Distill` to exactly `Distill`, per user request. Updated ERD (no architecture/data impact) and PRD. Validation: rendered the Jinja title block with the existing venv and confirmed exact text `Distill`; diff whitespace check passes. The separate .venv lacks Jinja, so validation used venv. Deployment: local source change only; not deployed.

Deployment completed at user request: applied the reviewed one-line template change directly to `/opt/summra/distill/templates/library.html` after checking the production working tree and exact old title. Restarted only the Distill user service; service is active. Authenticated VM-loopback request to the live home page returns HTTP 200 and exactly `<title>Distill</title>`. No database deployment or migration. Production change is currently an uncommitted template update; no commit/push was performed.

2026-11-04 — Uber Distill cover replaced with an AI-generated cover. Codex CLI updated 0.155.1 → 0.166.0 (older version rejected all models for the ChatGPT login); cover generated with `codex exec` imagegen using the Tesla cover as style reference (UBER / EQUITY RESEARCH & VALUATION / NOVEMBER 4, 2026; engraved street, route pins, delivery scooter; no logos or ratings), saved at /private/tmp/distill-uber-20261104/gen/uber-cover-gen.png. Cover-only update of slug uber-equity-research-2026-11-04 (book 70): fresh preflight local==live at 63 entries, backup before2.db; after import only the Uber books row (cover_image_id, imported_at), its single image row and its three cover thumbnails changed; chapters (1,795), content checksum and every other book unchanged. Existing deploy_db completed; post-deploy local/live inventories identical (63). Anonymous book request still redirects to sign-in. Authenticated library/Kindle cover and physical-device checks not performed. No application code changes.

## 2026-11-04 — Approved Reading desk redesign and home typography

User selected Reading desk, requested Kai for Chinese title/subtitle, then approved daylight mode, the same fonts on home, and commit/push. Implemented a responsive jacket/sidebar plus overview excerpt/contents column, native expandable parts with the saved part open, and direct Overview/Source links. Preserved current reading/finished/restart/status/return behavior. The overview excerpt comes from existing content, remains escaped, and reads only ordinal 0. Chinese title/subtitle, home tiles, progress-card titles, placeholders and suggestions use Kai; English titles use editorial serif, body/UI/contents use sans. Added language annotations and self-hosted LXGW WenKai v1.311 WOFF2 plus OFL license, with explicit permission to add these files. Browse pages force warm daylight while reader/Kindle theme controls remain intact. ERD/PRD updated; no schema or data deployment. Existing unrelated publication log edits remain outside this commit's scope.

Validation complete: 414 Distill/shared backend tests and 24 Plainly home/book regressions pass (1 unrelated deselection). Distill browser suite passes desktop/mobile/Kindle scenarios, including OS-dark daylight rendering, actual self-hosted Kai loading, expandable chapter links and 320/390px Chinese/English layouts. Saved-part/escaped-excerpt and home-language regressions pass. Inspected daylight book/home screenshots; diff whitespace check passes. Initial new-test fixture/locator issues were corrected and rerun. Prepared for the user-authorized commit and push; deployment has not been requested for this redesign and has not been performed.

## 2026-11-04 — Reading desk VM deployment

At the user's request, deployed the pushed redesign commit `42763f9` to `/opt/summra` via fast-forward. The only tracked VM edit was this chat's earlier home-title hotfix; verified its exact content against HEAD before replacing it with the now-committed change. Preserved untracked VM configuration and all content/media/progress stores. Restarted Distill and Plainly because the shared card template changed; both user services are active. No database copy or migration.

Live authenticated VM-loopback verification: home HTTP 200 with exact title `Distill` and daylight browsing; Chinese global-history and English Atomic Habits details HTTP 200 with Reading desk, overview excerpt, expandable parts and `/distill/` return links. Live CSS contains the fixed light scheme and Kai face; authenticated self-hosted WOFF2 returns 200 and its SHA256 matches the local tested 7,231,496-byte asset. Anonymous private-book access remains 401. Plainly home returns 200 on its configured port 5001; an initial check landed before its listener was ready and the follow-up passed. Runtime HEAD is `42763f9`. Desktop/mobile/Kindle browser regressions passed locally before this deployment; live verification here is HTTP/source/hash, not a new physical-device trial.

## 2026-11-07 — Authorize an invited reader across personal-site apps

User explicitly authorized <INVITED_EMAIL> for Distill, Plainly and other apps on pengyaochen.com. Read-only production inventory found the invited reader already present in Plainly's SUMMRA_ALLOWED_EMAILS, OpenReader's READER_ALLOWED_EMAILS and Apache's protected /pages/, /mathpad/ and /inkchinese/ policies. Public personal-site and Explainer routes require no invitation. Distill's DISTILL_ALLOWED_EMAILS contains only the owner and is the identified missing entry; its service is active. Checking InkChinese's secondary application gate before final verification. Planned scoped change: preserve all existing Distill environment settings and allowlist members, make a private rollback backup, add the invited reader, restart only Distill, then verify allowed/denied/anonymous responses through trusted VM-loopback requests and inspect the unchanged site policies. ERD/PRD now describe invited-reader access and separate account progress; no application code or schema change. Existing uncommitted documentation changes are preserved.

Completed live: added <INVITED_EMAIL> to /opt/summra/distill.env's existing DISTILL_ALLOWED_EMAILS, with every other line and existing allowlist member preserved. Private rollback backup: /opt/summra/distill.env.before-invite-20261107T234123Z. Restarted only distill.service; readiness and active status pass. VM-loopback trusted-identity checks: the invited reader/owner 200 and unlisted 403 for Distill, Plainly, OpenReader /api/me and InkChinese /api/me; anonymous remains 401 for private Distill/InkChinese and 200 for intentionally public Plainly/OpenReader browsing. Distill book, reader and manifest each pass the invited reader=200/unlisted=403/anonymous=401. OpenReader recognizes the invited reader's existing account (its display username differs from her email); InkChinese's active INKCHINESE_ALLOWED_EMAILS already includes her. MathPad backend healthy; existing MathPad/InkChinese/protected-pages Apache email-claim policies include the invited reader, and apache2ctl configtest passes. No Apache changes/reload, other service restart, content deployment, admin grant, Google/email changes, or user-progress migration. These are VM-local authorization checks and policy inspection, not a real Google sign-in as the invited reader; trusted identity headers were never sent to the public site. Initial probes were adjusted to OpenReader's protected account endpoint and existing display-name semantics. ERD/PRD/worklog updated; no commit requested or made.

## 2026-11-07 — Good Strategy/Bad Strategy reading companion

User requested the book-summary skill and publication to Distill from the supplied English EPUB. Source: Richard P. Rumelt, Profile Books 2011, print ISBN 9781846684807 / eISBN 9781847657466. Staging and source-hash audit: /tmp/rumelt-distill/. Extracted Introduction plus all 18 numbered chapters (95,004 source words), preserved the author's three parts, and mapped 17 substantive embedded figures across nine chapters plus the manifest-designated edition cover. Decorative assets omitted; online illustration sourcing off by default. Five independent writer chunks and a separate fresh rubric/coherence review are used. Reflowable EPUB has no reliable page count. Initial complete local/live content inventories match across books, chapters, images and cover derivatives (63 entries); local integrity and foreign keys pass. No application code/schema/product behavior change; existing documentation edits preserved. Content review, isolated preview, final catalog preflight/backup and deployment verification remain pending.

Content review complete: five writer agents and one separate fresh reviewer; chapter gate PASS 19/19, D1/D2/D3/D4/D5/D7 all 5/5, D6 mechanically 1/5 (9/19 illustrated, expected partial N/A because online sourcing is off). Fixed chapter 3's Arthur Andersen/Enron diagram caption and chapter 14's conflation of adjusted operating gains with accounting profit; reviewer verified both in final JSON. Added the generalizable metric-attribution safeguard to the book-summary skill. Final dry-run: 21 reader entries, 17,624 reader words, 17 body images plus cover. Isolated scratch import/HTTP checks pass for all 21 Kindle entries, six reader segments, all 18 image responses and three cover derivatives. Inspected desktop/phone book and illustrated reader views plus touch-enabled Kindle emulation; no JS errors. Physical Kindle not tested. Final complete catalog preflight remains equal at 63 entries; SQLite backup /tmp/rumelt-distill/before.db. Existing content publisher deployment is running; account/progress stores are not replaced.

Published and verified: https://pengyaochen.com/distill/books/good-strategy-bad-strategy (book 73), category Business & leadership. Live/local complete content inventories match exactly at 64 books. All 63 prior books, 1,795 chapters, 935 images and 189 cover derivatives retain their original records. VM-loopback authenticated web/Kindle details and reader return 200; all six reader segments, 21 Kindle chapter entries, 18 images (including cover) and three cover derivatives return 200. Live SQLite integrity/foreign keys pass; anonymous web and Kindle access remain 401. Trusted identity checks were VM-local only, with no identity headers sent publicly. No physical Kindle test, application code change, schema migration or commit. Final book, drafts, source audit, review, score, screenshots and catalog inventories archived under data/log/distill-good-strategy-bad-strategy-20261107/ (gitignored). Account/progress databases preserved by publisher.

## 2026-11-07 — 基因传 reading companion

User requested book-summary skill and publication to Distill from supplied Chinese MOBI. Edition: 悉达多·穆克吉, 马向涛译, 中信出版社2018年1月, ISBN 9787508682426. Staging/source hash: /private/tmp/distill-gene-20261107/. Converted once with Calibre to EPUB, mapped 34 numbered chapters across the six original parts plus preface, epilogue and four back-matter sections (40 source entries). Extracted 13 embedded body figures including two timeline pages and the manifest-designated cover; no online image search. Source has ~341k machine-extracted CJK characters plus image-only timeline; no reliable reflowable page count. Independent writer chunks and a separate fresh review are in progress. Initial complete local/live inventory matches at 64 books across books/chapters/images/cover_thumbnails; SQLite integrity and foreign keys pass. No application code, architecture, schema or product behavior changes. Existing unrelated working-tree changes preserved. Preview, final review, catalog recheck/backup, deployment and live verification pending.

Content assembled: five independent writer agents plus main-agent back-matter curation, with a separate fresh reviewer. Mechanical gate PASS40/40; D1=5 (37/40 within band, three deliberately proportionate short appendices disclosed), D2=5 (no stubs), D3=5; D6=1 mechanically (7/40 sections contain13embedded figures;33unillustrated sections expected partial N/A because online sourcing off). Dry-run validates42reader entries (40source sections plus Overview/Source),14image files including cover. Isolated scratch DB preview: all42Kindle chapter entries,9reader segments,14images and3cover derivatives return200; integrity/foreign keys pass. Desktop/390px phone/Kindle screenshots inspected, no JS errors. Illustrated Kindle chapter font change fs6→fs7 and page away/back passed; physical device not tested. Local SQLite backup before.db retained in staging. Independent semantic review and final deployment remain pending.

Independent review completed and all four findings applied: distinguished winter1989PGD intervention from subsequent twin births; explicitly disclosed source-internal SRY and genetic-code chronology differences between prose and timeline; converted four groups of historical lessons into a real numbered list. Reviewer verified final JSON, no open actionable findings; final D4/D5/D7=5/5. Added the reusable body-versus-timeline chronology safeguard to the book-summary skill. Reassembly/dry-run and final isolated HTTP checks pass; countable rubric scores unchanged. Content ready for final catalog preflight and user-authorized deployment.

Published and verified: https://pengyaochen.com/distill/books/the-gene-zh (book74), categories Science & technology and History & biography. Final reviewed Chinese reading companion covers all40source sections (34numbered chapters, preface, epilogue, four appendices), plus Overview/Source for42reader entries. All five writer chunks and separately curated back matter were independently reviewed; gate PASS, D1–D5/D7 all5/5, D6=1 partial N/A (book-only imagery). All final live/local content inventories match at65books; all64prior books,1816chapters,953images and192cover derivatives retain their exact previous records. VM-loopback authenticated web/Kindle book and reader return200; all9reader segments,42Kindle entries,14image responses including original cover and3cover derivatives return200. SQLite integrity and foreign keys pass; anonymous private-book access remains401 in web and Kindle. Trusted identity headers used only VM-locally, never publicly. No account/progress replacement, application code/schema change, commit, or physical Kindle test. Final book, drafts, source hashes/text extraction, reviews, score, screenshots and catalog/live verification archived under data/log/distill-the-gene-zh-20261107/ (gitignored); source EPUB and local backup remain in staging. Temporary local preview stopped after completion.

## 2026-11-08 — Distill audio: 48 kHz voice, Opus 24 kbps only

User asked to shrink deployed audio, then found AAC 32 kbps already dull. Listening samples (same passage): AAC 32k at 22 kHz 15.6 MB/h; Opus 16k from that AAC 8.3 MB/h (8 kHz bandwidth, worse); 48 kHz raw 347 MB/h; 48 kHz → Opus 32k 15.3 MB/h; 48 kHz → Opus 24k 11.7 MB/h. Measured: `say` defaults to 22 kHz (11 kHz ceiling) but produces real 11–16 kHz content at 48 kHz. User ruling: Opus 24 kbps; new chapters go raw 48 kHz WAV → Opus 24 directly and keep no AAC; existing chapters convert AAC → Opus 24 without re-rendering; no Opus 16.

Done on `feat/distill-opus`: `SAY_SAMPLE_RATE=48000`; `render_chapter` encodes the joined WAV straight to Opus 24 (`-application audio`, MP4); `chapter_audio.deploy_key` (migration) — new chapters have one file (`storage_key = deploy_key`), older ones keep AAC in `storage_key` with Opus in `deploy_key`; `make_audio --opus-only` converts AAC-only chapters; route serves the Opus; `deploy_db` rewrites the shipped snapshot so the VM references only Opus. A re-render clears the old Opus. Tests: 12 new; full suite 1,291 passed. Real render check: 48 kHz Opus ~23 kbps, file duration 7.308 s equals the timings exactly. WebKit Listen e2e 29/29 and distill.mjs pass against Opus audio. An interrupted early Opus 16 trial left ~50 unreferenced Opus 16 files in the local media store (harmless, never deployed).

## 2026-11-08 — Listen: automatic page turn, hand-turn rules, shared player

User: while watching the text during Listen, the page should turn on its own. Agreed rules after comparing Readwise Reader (return/jump), Audeus (Sync), Voice Dream, Sumatra PDF and Apple Books read-aloud: hands off the page follows the audio; a page turn of your own (playing or paused) stops following and never moves the audio; away from the playing page the bar shows Back to audio and Play from here; pause/play continue the audio and never move the page; following never resumes by itself.

Found two bugs: (1) the page turned only when a new paragraph started, so a paragraph running onto the next page left the highlight off-screen; (2) on phones the bar's own re-layout re-cut the pages, the displayed page no longer held the spoken paragraph, and the old "spoken paragraph not on screen" rule switched following off before anything was touched. Fix: follow on every tick via (unit, offset) → page; detect hand turns by wrapping `navigateToNextPage`/`navigateToPreviousPage` plus contents clicks (wrapping `loadContinuousReaderAt` was tried and rejected: resize/settings call it). Moved the player into the shared platform (`shared/static/js/listen.js`, `shared/templates/shared/reader/_listen_bar.html`, `shared/static/css/listen.css`), parameterised by `{audioApi, storageKey, mode}`; Distill passes its values. Plainly has no timed audio, so it does not use it yet. Branch `feat/shared-listen`. New WebKit e2e `tests/e2e/listen_follow.mjs` (375×667): 14/14 (RED first on the auto-turn, re-layout and Play from here checks). distill_listen 29/29, distill.mjs 71 ok, pytest 1,292 passed.

## 2026-11-08 — 被讨厌的勇气 reading companion

User requested book-summary skill and publication to Distill from supplied Chinese EPUB. Edition verified against copyright page: 岸见一郎、古贺史健著，渠海霞译，机械工业出版社2015年4月第1版第1次印刷，ISBN978-7-111-49548-2. Staging/source hash and extracted chapter map: /tmp/distill-courage-disliked/. Mapped56main-text subsections across original five nights plus seven foreword/introduction/closing sections (63source entries), about85,808CJK characters excluding part-opening narratives; reflowable EPUB has no reliable fixed page count. Three independent writer agents read assigned full texts; fresh independent semantic review pending. Extracted manifest-designated cover plus eight original body illustrations; no online sourcing. Initial complete local/live inventory identical at65books across books/chapters/images/cover_thumbnails; local integrity and foreign keys pass. No application code, schema, architecture or product behavior changes. Final validation, backup, deployment and live checks pending.

Content/review complete: three full-source writer batches, separate fresh independent reviewer. All63source sections preserved, plus Overview/Source =65reader entries. Cover and8embedded body illustrations (9files) retained;56sections unillustrated by default no-online-sourcing policy. Independent review found and closed two keypoint scope errors (blanket rejection of praise was narrowed; paid-work income extended ambiguously to housework), three repetitive conclusions and a writer-process aside. Confirmed fixes against source; added reusable subject/quantifier-scope safeguard to book-summary skill. Final Gate PASS; D1/D2/D3/D4/D5/D7=5, D6=1 partially N/A;60/63within depth band, two927/920-character sections trimmed for fidelity and667-character biography disclosed as exceptions. Format/dry-run/scratch import pass. Desktop1280x900, phone390x844, touch Kindle1072x1448 previews inspected without JS errors; Kindle font6→7 and page away/back with both introduction images loaded pass. Final scratch HTTP verifies11reader segments,65Kindle entries,9images and3cover derivatives; integrity and foreign keys pass. Physical Kindle not tested.

Final content catalog still equal across65books; audio-aware preflight found separate local audio work ahead (575local/563live rows, with24existing Opus-reference differences). To avoid deploying that unrelated work, imported only the reviewed book into local master (book75), then used SQLite backup to make /tmp/distill-courage-disliked/publication.db and restored all563verified live audio records there. Local audio work untouched. Existing deploy_db handles this snapshot with the master media directory via a temporary symlink. Pre-import SQLite backup before.db retained. Deployment in progress; no app code/schema changes or commit.

Published and verified: https://pengyaochen.com/distill/books/the-courage-to-be-disliked-zh (book75), categories Personal growth and Psychology & philosophy. Existing deploy_db snapshot deployment completed. Live/local content inventories match at66books; all65previous books,1858chapters,967images and195cover derivatives retain exact previous records. Deployment snapshot/live match including all563audio records; independently checked every pre-existing live audio row unchanged byte-for-byte at metadata level. Local ahead audio jobs/references untouched. Authenticated VM-loopback web/Kindle book and reader return200;11reader segments,65Kindle entries,9images including cover,3cover derivatives all return200. SQLite integrity/foreign keys pass; anonymous web and Kindle requests remain401. Trusted identity checks only VM-local, no public identity headers. No account/progress replacement, application code/schema change, commit or physical Kindle test. Reviewed deliverable, drafts, source audit/extracted text, independent review, scores, screenshots and live inventories archived under data/log/distill-courage-disliked-20261108/ (gitignored); source EPUB and SQLite backups remain in staging.

## 2026-11-08 — Publishing now includes Listen audio

User chose option 1: publishing a Distill entry did not record audio, so new books had no Listen button and republished text left stale chapters hidden. Added a "Listen audio" section to `skills/distill-publish/SKILL.md` (step 6 of Validate/publish/verify) and a pointer plus report line in the `book-summary` skill's Phase 7. Once the text is live and verified: `make_audio --book <slug> --dry-run`, then `make_audio --book <slug> --jobs 4 --deploy` in the background. One `make_audio` run at a time (`pgrep -f distill.scripts.make_audio`). User set 4 chapters at once for all languages after a benchmark on the M1 Pro (English `say`, 48 kHz, ~50 s clips, with another recording running): 1 job 4.9× real time, 2 7.0×, 3 10.7×, 4 14×, 6 17.5×, 8 19×, 10 18.7×; no hangs in 24 rounds. Siri (Chinese) in parallel not benchmarked. Never self-approve a voice-check failure. Verify on the VM via the audio API and one Opus chapter URL (owner 200, anonymous 401). Skills only; no app code change.

## 2026-11-08 — 政治秩序的起源 reading companion

User requested book-summary skill and Distill publication from supplied Chinese EPUB. Verified edition: 弗朗西斯·福山著、毛俊杰译，广西师范大学出版社，2014年9月第2版/2015年12月第5次印刷，ISBN 9787549555116. Staging/source SHA256 and chapter map: /tmp/distill-political-origins/. Extracted all30numbered chapters with continuation spine files and notes (~278,850CJK characters), preserved original five parts; reflowable EPUB has no reliable page count. Three writer agents read separate ranges, producing six chunks; fresh independent review pending. Extracted edition cover and one embedded figure for each of16illustrated chapters;14chapters unillustrated under default no-online-sourcing policy. Initial complete content inventories equal at66books; integrity and foreign keys pass. Audio-aware inventories differ due to independent local audio work; another make_audio job is active, so publication must preserve verified live audio in an isolated deployment snapshot and new-book recording must wait. No application code/schema/architecture/product behavior change; existing unrelated working-tree edits preserved. Content verification, isolated preview, final catalog recheck, publication and live checks pending.

Draft assembled: all30source chapters across six chunks by three writers;32reader entries including Overview/Source,16body figures plus original cover. Mechanical Gate PASS30/30; D1/D2/D3=5,100%chapters within depth band; D6=2 mechanically (16/30illustrated, partial N/A because online sourcing off). Fresh independent semantic reviewer is reading all chapters. Isolated scratch import and HTTP checks pass for all32Kindle entries,7reader segments,17images and3cover derivatives; SQLite integrity and foreign keys pass. Desktop1280x900,phone390x844,touch Kindle1072x1448 previews inspected with no JS errors. Kindle font6→7 and page away/back passed with chapter30illustration loaded. Physical Kindle not tested. Local pre-import backup before.db retained; final audio-aware preflight and publication snapshot will preserve other local/live audio work.

Independent review complete, all findings closed and final JSON verified: softened chapter13opening from exclusive abstract-state loyalty to a group detached from local kinship; clarified chapter10four-varna taxonomy; converted enumerations in5/11/21/29into actual lists. Sourcechecked disputed dates: chapter9explicit detailed source supports589unification, so no outside correction introduced. Reviewer final Gate PASS; D1–D5/D7=5, D6=2partial N/A; no required changes remain. Added generalizable label-qualification and category-membership safeguards to canonical book-summary skill. Final assembly/dry-run and isolated HTTP checks pass for32reader entries,7segments,17images and3cover derivatives. Publishing only reviewed content with verified-live audio restored in separate snapshot; no application code/schema/product change and no commit requested.

Published and verified: https://pengyaochen.com/distill/books/origins-of-political-order (book76), categories History & biography and Society & economics. Final live/local content inventories equal at67books; all66prior books,1923chapters,976images and198cover derivatives retain exact prior records. Publication snapshot/live inventories also equal including all563prior live audio rows, which are preserved exactly; local ahead recording work untouched. Authenticated VM-loopback web/Kindle details and reader return200;7reader segments,32Kindle entries,17images including cover,3cover derivatives all return200. SQLite integrity/foreign keys pass; anonymous web/Kindle remain401. Trusted identity checks only VM-local, no identity header sent publicly. Final deliverable/drafts/extracted sources/source hash/review/scores/screenshots/catalog checks archived under data/log/distill-political-origins-20261108/ (gitignored); original EPUB unchanged, backups remain staging. No application code/schema/product change, commit, account/progress replacement or physical Kindle test.

Listen: dry-run estimates32entries/~2.9hours spoken audio. Existing how-the-world-really-works-smil recording still active, so launched detached queue worker15827 (/tmp/distill-political-origins/record_when_idle.py, status audio-status.json, log audio.log). It waits for active make_audio/publish jobs, records this isolated publication snapshot with4workers, preserves approved voice references, rechecks live content before deploying, merges only this book's new audio into local master, and retains fresh live audio for all other books. Live-content divergence or voice failure stops deployment and records failure; never self-approves voice. Queued at handoff, no completion ETA until preceding job finishes.

## 2026-11-08 — 政治秩序与政治衰败 reading companion

User requested book-summary skill and Distill publication from supplied Chinese EPUB. Verified edition: Francis Fukuyama/弗朗西斯·福山著，毛俊杰译，广西师范大学出版社2015年9月第1版，2016年3月第2次印刷，ISBN9787549570942. Staging /tmp/distill-political-decay/ retains source SHA256, complete NCX map, per-chapter CJK lengths and extracted spine text. All36numbered chapters plus edition guide and introduction mapped independently, original four parts preserved; six chunks assigned to three writers, independent fresh review pending. Reflowable EPUB has no reliable page count. Extracted original manifest cover and39body figures/tables covering18of38source sections;20unillustrated, online sourcing off by default. Initial local/live inventories match across books/chapters/images/cover_thumbnails at67books; audio differs by one local-ahead chapter from an independently active make_audio run. Publication must use isolated snapshot preserving verified live audio; new Listen recording must queue. No application code, schema, architecture or product behavior changes; no commit requested. Review, preview, backup, final preflight, deploy and live checks pending.

All six drafts assembled:38source sections (36numbered+guide+introduction),40reader entries with Overview/Source;39body figures/tables plus manifest cover. Gate PASS38/38; D1/D2/D3=5,100%in depth band,minimum692word-equivalent; D6=1mechanically (18/38illustrated),partialN/A because all embedded images retained and online sourcing off. Fresh independent full-summary reviewer active. Isolated preview import succeeds; HTTP checks pass for9reader segments,40Kindle sections,40image assets,3cover derivatives; SQLite integrity/foreign keys pass. Desktop1280x900,phone390x844 and Kindle1072x1448 screenshots inspected; no JS errors. Kindle font6→7, page away/back passes with all three chapter34figures loaded and fitting viewport. Physical Kindle not tested. Publication/review closure pending; no app-code/schema/product changes.

Independent review closed all findings: corrected chapter32table7caption from spending/1960 to tax revenue/1965, added table8year2011and original local-revenue scope qualifier; structured chapter1two decay mechanisms and chapter35three capacity foundations as lists; merged chapter5duplicate secret-ballot explanation. Confirmed source chronology caveats in16/25, left original historical claims source-bounded. Added reusable full-resolution table-header metric/year check to canonical book-summary skill. Fresh reviewer verified fixes in final JSON: Gate PASS; D1–D5/D7=5; D6=1partialN/A. Final assembly/dry-run, scratch reimport and full HTTP checks pass. Final preflight content inventories identical across all67existingbooks; local audio ahead by14entries due active unrelated recording. SQLite backup before-import.db made using backup API. Imported new book77into local master, prepared isolated publication snapshot retaining all1606verified live audio rows, leaving local recording untouched. Deployment in progress.

Published https://pengyaochen.com/distill/books/political-order-and-political-decay (book77), categories History & biography and Society & economics. Verified owner VM-loopback web/Kindle details and reader200; all9segments,40Kindle entries,40images including cover and3cover derivatives200; anonymous web/Kindle401. SQLite integrity/foreign keys pass. Local/live content inventories equal at68books; isolated publication snapshot/live inventories also equal including audio. Exact preservation checks retain all67prior books,1955chapters,993images,201cover derivatives and1606prior live audio rows. Original EPUB SHA256 unchanged. No app code/schema/product changes, commit, account/progress replacement or physical Kindle test.

Listen dry-run:40entries/~3.6hours spoken audio. Detached worker42375 (/tmp/distill-political-decay/record_when_idle.py) transitioned queued→recording after prior job cleared; uses4workers, copied existing approved voice references unchanged, isolated snapshot, live-content recheck, only this book's audio merge into local master, verified-live other audio retained during later deploy. Voice failure/content divergence stops safely, never self-approves. Status /tmp/distill-political-decay/audio-status.json and log audio.log. Text is available immediately; Listen appears after recording and verified audio deploy finish.

## 2026-11-08 — Distill home redesign (option A, keep scrolling)

Owner rejected the Reading/Library tabs and chose, after two rounds of mockups, one page: current book with equal Continue and Listen, Also reading, then the whole library; desktop pins the book left. Fixed app background, no swipe-up. Book page uses the same two buttons. Listen now plays on home and book pages (`listen_page.js`, shared Listener with a stand-in reader), saving the place to the server; navigating away stops audio. Old tab tests replaced because the tabs were removed on request; one race fixed in `distill_listen.mjs` setup. Not committed or deployed yet; not checked on a real iPhone.

Header follow-up: on desktop the logo moved into the full-height book panel, removing the bar across the split page and the jump past it when choosing Unread or Finished. Status and search share a line; the three selects sit in a compact row that cannot overflow. Not committed or deployed yet.

## 2026-11-08 — Listen: lock-screen Play after a pause

Owner: lock-screen Pause worked but Play did nothing (with Plainly force-quit), or started Plainly. Code path was correct; matches iOS freezing a paused web app (WebKit bug 243258). `Listener.pause()` now loops silence on the same audio element for up to 30 minutes, keeping the place in `held`; resume reloads the chapter there. Lock-screen Pause while held resumes, because iOS may show Pause during silence. Not yet verified on a real iPhone, which is the only way to confirm it. Tests read `listener.playing` instead of `audio.paused`.

## 2026-11-09 — Chinese audio deployed; VM check in deploy_db

All 12 Chinese books re-recorded with Siri text pieces (no failures) and deployed with `deploy_db`. Owner asked for the VM to be validated: every `deploy_db` run now ends with `db_patch check` (`quick_check`, `foreign_key_check`), a second row-hash comparison that must find no differences, and all referenced media present on the VM; it prints what it verified. TDD in `tests/distill/test_deploy_db.py` and `test_db_patch.py`; full suite 1,352 passed.

## 2026-11-09 — Shared audio player, Distill in-place loading (branch feat/distill-player)

Owner: closing the player moved the reader's text; audio should carry on while browsing, like 微信读书; player logic, highlight, page following, saved place and Listen from here instead must be shared so Plainly works as soon as it has recordings. Spec and plan: `docs/superpowers/{specs,plans}/2026-11-09-shared-audio-player*`.

Built: `AudioPlayer`, sources, `ReaderAudioLink`, `PlayerUI`; mini and full player; Distill in-place loading (`page_swap.js`, persistent reader shell); `shared/audio/` store and API with key `(chapter_id, mode)`; Plainly moved to the shared player; `deploy_code` restarts Plainly when a change affects it.

Timings, tap to content, before and after (ms): home 221 to 226, book 227 to 217, reader open 1481 to 887, page turn 2 to 6 (final run; home and page turn are within the 15 ms noise allowance).

Rulings: Tasks 3 to 5 built as one change, not through a temporary compatibility layer. Timing delay comes from a local proxy because `page.route` turns off the HTTP cache; 15 ms noise allowance. Source tracks load before `setSource` (iPhone tap rule). `mode` is a trailing keyword on the audio store calls, default `summary`. `make_audio` stays in `distill/scripts`, with a small wrapper needed for Plainly. Back to audio and Play from here were removed by the design; paging back or starting a track resumes following. Generated speech uses book id `speech-<id>`. "Resume listening" label removed.

Not verified: iPhone behaviour (audio across a swap, lock screen). The owner waived the gate while away; check on a device.

Local style check against main: all reader variants identical. Home card differences come from this worktree's smaller reading history (1 continue card against 3), not code.

Found in final checks: pressing Listen on a page that opens partway through a paragraph turned back a page, because the player reported 0:00 before its seek landed and the paragraph began on the page before. Now the position reports the seek target, and following never turns back for a paragraph already on screen (`reader_audio_stable.mjs`).

Deploy: `deploy_db` failed its own read-back (3,990 rows) because the local DB still had the old audio key. It now migrates its snapshot before comparing (`test_deploy_db.py`).

## 2026-11-09 — Shared recording; Gemini speech removed from Plainly (branch feat/shared-make-audio)

Owner: `make_audio` should be shared and replace Plainly's Gemini speech. Moved it to `shared/audio/make_audio.py` with `--app` and `<app>/audio_app.py` adapters, plus `--mode`. Added `plainly/scripts/audio/record_summaries.py`. `/api/tts/generate` moved to `app_base.py` and only finds recordings, in dev too. Deleted `gemini_tts_handler.py`, five Gemini audio scripts and `test_tts_streaming.py` (tested the removed streaming generator). Existing Gemini summary files still play until a recording replaces them. Chapters with nothing to say are skipped. Real macOS run on a scratch database produced Opus with timings for a chapter and a summary.

Left: no script ships Plainly's recordings to the VM; no re-recording run done; the browser's chunk-waiting path in `generated_speech_source.js` is now unused by the server.

## 2026-11-09 — Stop listening in the full player

Owner could not turn audio off from the reading page: the only stop was the mini player's close, which is hidden there. Added Stop listening to the shared full player (`player-stop`, the same `player.close()`). Tests in `player_reader.mjs`.


## 2026-11-09 — 最好的告别 reading companion

User requested book-summary workflow and Distill publication from supplied Chinese EPUB. Verified original cover and copyright: Atul Gawande/阿图·葛文德著，彭小华译，王一方主编，浙江人民出版社2015年8月纸版，湛庐授权大陆简体电子版；English copyright2014. Staging /private/tmp/distill-being-mortal retains source hash, extracted spine, original NCX map and per-section CJK lengths. Three parallel writers cover all eight chapters and41named source sections including front/back matter; independent fresh review pending. Reflowable EPUB has no reliable page count. Extracted original cover and three substantive decline diagrams; no online sourcing. Short-source summaries will preserve content without padding to a disproportionate floor. Initial local/live content catalogs match across68books; audio matches after normalizing the new mode=summary schema default and deploy-key representation. No application code/schema/product changes; content-only publication, no commit requested. Final review, preview, preflight/backup, deployment and audio pending.

All three drafts assembled into41source sections plus8chapter introductions, Overview and Source (51reader entries). Gate PASS41/41; D1/D2/D3=5;38/41depth bands, three transparent short-source exceptions;minimum291word-equivalent, no stubs. D6=1mechanically for leaves, N/A: all three actual embedded figures belong to chapter02introduction, while all leaf sections are unillustrated; original cover retained. Independent full-summary review active. Isolated preview HTTP checks pass for7reader segments,51Kindle sections,4assets and3cover derivatives; SQLite integrity/foreign keys pass. Desktop1280x900,phone390x844,Kindle1072x1448 screenshots checked; no JS errors. Kindle font6→7and page away/back retain3loaded diagrams fitting viewport. No physical Kindle test or application changes. Publication pending reviewer closure and final catalog preflight/SQLite backup.

Independent reviewer completed full41-section review: D4/D5/D7=5, no blocking factual errors. Sole finding resolved against source27:51: explicitly restricted70%depleted-savings statistic to NewBridge residents, then rebuilt/revalidated; reviewer confirmed finalJSON fix. Extended existing skill quantitative-claim guidance to preserve facility/sample scope (skill frontmatter unchanged; automated validator unavailable in repo venv because PyYAML is absent). Score unchanged: Gate PASS,D1–D5/D7=5,D6=1with online-off/intro-figure caveat. Final publication preflight and backup starting; no application changes.

Published https://pengyaochen.com/distill/books/being-mortal-zh (book78), categories Science & technology and Psychology & philosophy. Live owner VM-loopback web/Kindle detail and reader200; all7segments,51Kindle entries,4images including cover and3cover derivatives200; anonymous web/Kindle401. SQLite integrity/foreign keys pass. Local/live normalized inventories identical at69books; exact preservation verifies all68prior books,1995chapters,1033images,204cover derivatives and1995audio rows unchanged. Source EPUB SHA256 unchanged. Original2015Chinese edition fully read across three writers (~133863CJK extracted; no fixed pages) and fresh independent reviewer. No app code/schema/product behavior changes, commit or physical Kindle test.

Listen dry-run estimates51entries/~3.2hours spoken audio. Recording began with approved existing Chinese voice and4workers via shared.audio.make_audio --app distill --book being-mortal-zh --jobs4 --deploy; voice check passed. Background verification watcher checks all51live audio entries and private access after recorder/deployer exits; status and verification artifacts under /private/tmp/distill-being-mortal. Text available immediately; audio pending completion.


## 2026-11-09 — 信任 reading companion

User requested book-summary skill and Distill publication of supplied Chinese EPUB. Verified copyright/cover: Francis Fukuyama著，郭华译，广西师范大学出版社2016年3月第1版，ISBN978-7-5495-7853-5，original1995. Staging /private/tmp/distill-trust-fukuyama includes original source SHA256, extracted EPUB spine, real31-chapter map with CJK source lengths, five original part divisions. Chinese drafts dispatched to source-reading writers, separate fresh review required before publication. Original cover plus all five substantive embedded tables retained (chapters3/14/22/27); online images off. Overview distinguishes郭于华导读2016from正文1995. No fixed EPUB pages. Initial69-book local/live content matches; local audio is ahead due an unrelated recording, so preserve live audio during publication and queue this book behind active recording. No app code/schema/product changes or commit requested. Validation/deployment pending.

Listen completion for 最好的告别: all51reader entries recorded/deployed; VM-loopback audio API lists51, sample track200audio/mp4, anonymous API/track401. Automated post-recording verification stored in /private/tmp/distill-being-mortal/audio-verification.json.

All five source chunks fully read by three writers (219514CJK across31chapters, plus front matter handled in Overview). Assembled31chapter summaries+Overview+Source=33reader entries, original5parts. GatePASS31/31; D1/D2/D3=5, all depth bands,minimum722word-equivalent; D6=1mechanically/partialN/A because only4chapters illustrated in source, all5tables kept. Scratch import HTTP checks pass for7segments,33Kindle entries,6assets includingcover,3cover derivatives; SQLite integrity/foreign keys pass. Desktop1280x900,phone390x844,Kindle1072x1448 screenshots inspected with noJSerrors; Kindle chapter14font6→7and page away/back retains both tables within viewport. No physical Kindle test. Fresh independent full-book content review underway. Preflight after prior recording confirms local/live inventories fully equal including audio at69books. No app-code changes.

Independent fresh reviewer read all31summaries+Overview+Sources+finalJSON, checked raw source statistics/captions/coherence and closed two confirmed issues: ch3now names the author’s1995China/Japan prediction rather than vague “strongclaim”, explicitly noting ch29uncertainty; ch25now preserves author’s broad group comparisons and distinguishes counterexamples/editorial caution rather than falsely narrowing his claim. Final GatePASS31/31; D1–D5/D7=5,D6=1partialN/A. Added narrow source-claim/editorial-caution and explicit-prediction check to existing book-summary skill; quick_validate passes. Reassembled/finaldryrun and scratchHTTP checks pass. Final69-book preflight fully equal including audio, no active recorder/publisher; SQLite before-import.db created. Text deployment underway.

Published https://pengyaochen.com/distill/books/trust-fukuyama (book79), categories Society & economics and Psychology & philosophy. Live owner VM-loopback web/Kindle detail+reader200, all7segments,33Kindle entries,6images incl.cover,3cover derivatives200; anonymous web/Kindle401. SQLite integrity/foreign keys pass. Local/live inventories fully equal at70books; exact preservation checks retain all69prior books,2046chapters,1037images,207cover derivatives and2046audio rows. Original EPUB hash unchanged. Final audit /private/tmp/distill-trust-fukuyama/review.md; no required reviewer issues remain. No app code/schema/product changes, commit or physical Kindle test.

Listen dry-run:33entries/~2.9hours spoken audio. Detached worker95998 (/private/tmp/distill-trust-fukuyama/record_when_idle.py) launched with4workers, approved existing voice only, one recorder at a time, automatic audio deploy and authenticated/anonymous VM verification; status audio-status.json, log audio.log. Text immediately available; audio recording pending completion. Worker stops on voice mismatch/failure without self-approving.

Listen completion for 信任: all33reader entries recorded/deployed; VM-loopback audio API lists33, sample track200audio/mp4, anonymous API/track401. Evidence /private/tmp/distill-trust-fukuyama/audio-verification.json.


## 2026-11-11: Prune unused Distill media on deploy

- Why: `install_archive` never deletes, so every re-recording left the old narration behind. The VM held 575 unreferenced media objects (654 MB, almost all old chapter audio).
- `media_transfer.prune_media` / `prune` command: keeps every key referenced by the live DB or by the content DB in the one `distill-latest.tar.gz` backup (so restoring it still works) and anything modified in the last 24 h; an unreadable backup raises before deleting anything.
- `deploy_db` calls it last, after the read-back and auth checks. A failure only warns, since content is already live; until the VM runs this code the step reports "skipped".
- One-off run on the VM 2026-11-11 with the same function: 575 files / 654.1 MB removed; `verify_media` then confirmed all 3,325 referenced objects present. Disk 11G → 9.4G (journal also vacuumed to 100M).
- Tests: `test_file_media.py` (+3), `test_deploy_db.py` (+2); both files 58 passed.


## 2026-11-11 — Dark theme: bold text and page arrows were invisible

Found while recording the Distill demo for pengyaochen.com: in the dark reading theme, bold text (`<strong>`) disappeared. `shared/static/css/reader.css` set `.pagination-page-container strong` to `var(--primary-color)` (dark ink, #2B2622), and no dark rule overrode it. A scan of every visible text element in the dark reader also found the page-turn arrows (`.pagination-nav-button`, `color: var(--text-color)`) dark on dark.
- Bold now uses `color: inherit`. In light mode that resolves to the same ink as before.
- Dark rules added for the page-turn arrows (`--reading-theme-dark-text`) and the blockquote rule (`--reading-theme-dark-border`).
- Shared CSS, so Plainly's reader gets the same fix.
- Validation: local Distill on a library copy, *The Wealth of Nations* ch. 1. In dark, bold and arrows compute to #e0e0e0; in light, bold, arrows and body text are all #2B2622. Full suite 1388 passed. ERD and PRD theme notes updated. Deployed 2026-11-11 (48373b0) with deploy_code; live shared reader.css on the VM has the fix, so Plainly gets it too.

## 2026-11-11 — NVIDIA equity research update (CEO investigation, price)

User asked to update `nvidia-equity-research-2026-10-31` in place with the latest
price and CEO news. Vault sources updated in place (originals archived in
`02-areas/finance/equity-research/nvidia/data/archive-2026-10-31-original/`):
research doc gains Section 0 (November update) plus targeted edits; valuation doc
rewritten on recalculated model (price $173.73 Nov 11 close, beta 1.45→1.55,
WACC 12.0%, P/E 19x, EV/EBITDA 16x, scenario weights 20/50/30). PT $290→$260,
BUY kept. Converter rebuilt (originals reproduce live chapters exactly before
use). Same slug/cover bytes; chapters 21→23, so later ordinals shift by one or
two. Preflight local/live drift 0 (after deploy-audio key rewrite); scratch
import changed only book 63; deployed; post-deploy drift 0, live integrity ok,
FK 0, 70 books, anonymous API 401. Chrome check of book page and update chapter
table. Staging/evidence: /private/tmp/distill-nvidia-update-20261111/. Audio:
all 23 chapters re-recorded with make_audio --deploy.
