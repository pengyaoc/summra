# Shared platform — Product Requirements

> Split out of `docs/PRD.md` on 2026-11-11. The reader, Kindle e-ink mode, sign-in and progress, audio player, media policy and repository layout that both apps use. Newest dated entries are at the top; the reference sections follow.

## 2026-11-07: Kindle back/forward viewport stability

Returning to the next page after paging backward must retain the same full-size
reading rectangle immediately, without an extra page turn, right/bottom blank
space or a scrollbar. The native fullscreen launcher now maintains the reader's
browser scale after navigation. Repeated physical PW3 touchscreen tests and the
owner's finger test confirm full-size reading. Browser toolbar gestures remain
native, with no browser controls added to the web app. Native zoom controls return
for library/ordinary browsing and when leaving the browser. Reading preferences,
font sizes, pagination and saved-position behavior are unchanged. This fix
requires installing the updated device launcher; a website refresh alone does
not install it.

## 2026-11-03: Larger Kindle reader UI

Kindle reader chrome uses 2.5× the former text size: book title, chapter time
remaining and percentage are 35px; Contents/Library/Close, chapter navigation
and ordinary font buttons are 45px; A+ is 55px; row labels and position text are
40px; font-size status is 50px. Saved reading text/font preferences and normal
web/mobile readers are unchanged. The reader reserves 90px above/below prose,
and long titles ellipsize. Settings panels flow and wrap instead of overlapping;
on short displays only the inner menu scrolls, with Close/font controls reachable.
This change is scoped to reader chrome, including the Library/Contents navigation
inside that reader; library/contents pages retain their existing layout. Deployed
to both live apps; refresh/reopen existing Kindle pages to load the new assets.
Implementation release `7b78211` is pushed and synchronized to the live VM; this
release synchronization adds no further product behavior.

## 2026-11-03 — Physical Kindle illustration verification

Physical PW3 testing confirmed the chapter-start content appears once after
settling, but exposed incomplete image painting after enlarging the font.
A device-specific image painting correction keeps the full illustration visible
in its reserved location without changing its caption, reading position or
proportions. Standard browser/no-JavaScript views remain unchanged. Deployed
and physically reverified: complete illustrations at size 9 after the earlier
failure, paging away/back, and a second chapter at the restored size 8 / Hei
setting. Startup shows one settled content layout. This supersedes the earlier
pending physical confirmation; details are recorded in WORK_LOG.md.

## 2026-11-02 — Kindle chapters reveal once, with complete illustrations

A Kindle chapter waits for illustration dimensions and final page layout before
showing the reading page. Intermediate text-only/native-shell layouts are hidden
to reduce e-ink flashing. This removes application-generated startup redraws;
hardware/browser-controlled e-ink refreshes remain outside the page's control.
Portrait and landscape illustrations retain their proportions and fit with their
captions on the reading page. Failed or stalled illustrations retain captions
and do not shift the chapter later. A script failure has a bounded visibility
fallback, and reading without JavaScript stays available. The native fullscreen,
font settings and saved-place behavior are retained. No changes to the catalog,
research content, tagging or account data. Deployed November 2, 2026; browser
and production checks pass. Physical Kindle paint confirmation remains pending.
Validation details are in WORK_LOG.md.

## Generated media repository policy (2026-10-27)

Verified on production: generated media stayed in place with all 634 hashes
unchanged; Plainly audio/images and authenticated Distill library/book/cover
requests pass. Both services remain active. Published main and remaining local
branch/stash/checkpoint references are cleaned; non-media saved work is preserved.
CI passed for the rewrite. This is a storage/deployment policy change only.

Book covers, chapter illustrations, guide images and pre-generated audio are
managed as deployment data instead of Git source/history. Readers keep the same
media URLs and functionality; production copies stay on the VM. Logos, UI icons
and Kindle shortcut covers remain in source control. Generated test screenshots
are also excluded, while their test/comparison source remains versioned.

This changes repository/deployment management only, with no reading, pairing,
progress or authentication behavior change. A developer's fresh clone needs a
separate media/data transfer for the complete library. No media regeneration or
user reauthentication is required on the existing VM.

## Plainly Kindle phone sign-in and maintainable shortcuts (2026-10-27)

Deployment verified: `eb89c5f` is live for both apps. Apache syntax, service health,
Kindle QR/bootstrap, normal Google login, phone-only route challenges and
public/private library boundaries pass live HTTPS checks. Complete approval and
revocation flows pass integration tests; on-device phone approval remains a user check.

Plainly now offers the same Kindle-only phone-assisted Google login as Distill:
choose Sign in, scan the QR code, compare the displayed code and approve your
Kindle on your phone. The Kindle checks every ten seconds without modern
JavaScript. Sessions last up to 30 days and can be revoked from the phone's
paired-device page. Plainly public reading remains available without login;
signing in enables the existing account/progress sync. Distill stays private.
The apps pair independently and label their approval screens by app name.
Desktop/phone/Fire browser login remains the ordinary Google flow.

The working Distill Fullscreen, Plainly Fullscreen and shared Restore Distill
Toolbar shortcuts, matching book covers and installation/recovery instructions
now live in `deploy/kindle/`. They launch the existing stock browser and preserve
normal sleep. Runtime behavior is unchanged by importing their sources into Git.
The old Mac folder is a local copy rather than the authoritative source. Private
SSH material and retired Chromium trial assets are excluded.

VM storage investigation is documented with measured sizes and recommendations
in `deploy/README.md`. Retained rollback DB snapshots account for about 2 GiB;
no user data, media, backups or Git history is removed as part of this work.

## Native Kindle browser controls (2026-11-03)

The fullscreen launcher should let the reader put the Kindle down, sleep normally,
and wake at the same page in fullscreen without exiting/reopening the app.
Swipe down from the top edge to show the native browser toolbar. Reserve the
bottom-left corner to toggle the toolbar both on and off. A tap on the page while
the toolbar is visible dismisses it without also activating the page. Native
Home/menu/address controls remain browser controls; the website has no browser
control UI or bridge. Single power press retains normal Kindle sleep behavior.

Leaving for Home, manual Restore Toolbar, helper failure or browser replacement
ends fullscreen. Sessions no longer expire automatically after four hours;
a bounded diagnostic timeout remains optional. The existing PW3 reader may
reload at its saved paragraph when bars reappear. Physical swipe operation was
confirmed after the stacking fix. Subsequent corner-reveal misses led to enlarging the reserved corner to about 159px on PW3;
the user physically retested and reported substantially improved corner behavior.
Menu/keyboard and physical button/cover acceptance remain distinct from synthetic input and power-service tests; see
WORK_LOG.md for current verification and installation status.

## Verified Distill Fullscreen shortcut (2026-10-27)

On the tested jailbroken PW3, open **Distill Fullscreen** from the Kindle library for an app-style view of the existing signed-in Distill site. Both URL and status bars are hidden and the reader uses the reclaimed216px. Existing font, library and reading progress remain available. The actual Home shortcut, library-to-book navigation, font-menu interaction and all four drag directions have been physically checked. Final setting remains size8/10+黑体.

Power/sleep, leaving the browser, **Restore Distill Toolbar**, or the four-hour ceiling end fullscreen. Reopen the fullscreen shortcut for another session. Returning the bars reloads the reader at the same paragraph to clear this old browser's retained pan. Normal sleep remains enabled. Manual/timeout recovery and subsequent normal-mode drag containment were physically verified; the power listener is configured but was not exercised through a physical power press in this run. This is a native launcher for the existing browser, with no additional Google sign-in, alternate browser or iOS-style PWA installation requirement.

## 2026-10-27: Clear native pan on fullscreen exit

Fullscreen/full-height menu drags and installed timeout restoration physically pass. Returning native chrome retains a pan offset outside DOM scroll coordinates even after remeasurement. On the matched PW3's fullscreen→normal outer-height transition, replace the current fragment with the current paragraph and reload the reader to reset native pan. Fullscreen entry still repaginates locally. The current URL/history entry, font, login and paragraph are retained; exiting fullscreen now requires a page reload. No schema/auth changes. Physical exit verification pending.

## 2026-10-27: Detect measured fullscreen outer height

Physical geometry proves that fullscreen changes outerHeight1232→1448 while innerHeight/clientHeight stay1268. Use the matched PW3's outerHeight equal to screen.height to add216px to the native body/shell. A once-per-second native-only check repaginates only when outerHeight changes, covering builds that omit DOM resize. Regression emulates the real fixed-inner-height behavior. Restore shortcut now validates the exact standard browser title as well as titles with extra fields; manual restoration returns1232px and removes session state. Normal Home scriptlet launch successfully opens the authenticated fullscreen library. Direct browser LIPC `go` caused a Mesquite crash and is excluded; recovery dismissed its dialog and reopened via normal launch. Temporary geometry diagnostic will be removed during clean deployment. No native browser/root-filesystem edits or auth/data changes.

## 2026-10-27: Use native fullscreen browser space

A reversible X11 window-title request (`PC:N` versus normal `PC:TS`) hides the PW3's native status/URL bars without replacing the authenticated browser or editing its files. Physical screenshot confirms1072×1448 at y0 instead of1072×1232 at y216. The native reader now adds any reported viewport-height increase above1268px to its measured1260px body/1279px scroll shell; reversing fullscreen restores normal height. Only the existing matched legacy PW3 profile uses this correction. Added enter/exit height regression coverage. No data/auth/progress schema changes. Launcher and full-height physical verification pending.

## Verified physical Kindle reading behavior (2026-10-27)

The tested PW3 portrait stock browser now keeps the reading page inside the visible area after load/reload, opening settings, increasing/decreasing font size, changing Chinese font and closing settings. Physical up/down/left/right drags produce no blank-space pan or reading-region movement in these cases. Size8/10 and黑体 were restored with the menu closed after verification. Keep this measured native behavior limited to the matching legacy device/engine; other devices retain the general reader. Its slight native fit scaling preserves saved size/font choices. The phone-assisted login, library, content and progress formats are unchanged. Earlier pending/unsuccessful trial entries below are historical and superseded by this verification.

## 2026-10-27: Match measured native surface initialization

Use the physically successful trial sequence directly: finish normal pagination, wrap only the matched PW3 reader nodes, explicitly set native shell/body styles, then repaginate after 200ms. The profile is selected once, so font relayout cannot remove it. Other browsers retain their original unwrapped layout. Earlier class-based/extra-reflow attempts did not pass fresh-load drags and are superseded. No content/auth/storage changes. Final physical verification pending.

## 2026-10-27: Reconcile native scroll range after load

Startup geometry confirms the PW3 profile is selected, but its native scroll range settles later than synchronous DOM layout. Remeasure only this profile one second after window load. Preserve explicit end-of-chapter startup across wrapping/remeasurement. Temporary startup metrics excluded from release. Physical reload verification pending.

## 2026-10-27: Initialize native scroll surface after pagination

Font adjustment/closed-menu drags passed, but a fresh native load retained its initial root pan range. Defer wrapping existing reader nodes until after the first pagination/reflow, then remeasure at the current paragraph, matching the successful physical trial initialization order. No content/auth/storage changes. Fresh-load verification pending.

## 2026-10-27: Preserve native profile after font relayout

The physical PW3 passed settled-load/menu drags but changing size exposed an unstable exact document-width check: native auto-fit can change CSS document width. Keep the legacy no-touch 1072×1448 device match, using portrait document proportions instead of exact width during relayout. This retains the workaround across font changes. No data or authentication changes. Final on-device adjustment/close verification pending.

## Physical PW3 reading fit (2026-10-27)

The older PW3 stock browser requires its own nested reading surface to prevent dragging into blank space; CSS overflow and touch handlers alone are insufficient. The profile retains saved font and size choices, with slight native fit scaling, and keeps header/footer and font banners inside the visible screen. Apply it only to the verified portrait device/engine combination. Other Kindles and normal browsers keep the general reader layout. Real-device tests must cover fresh load, font-menu open, adjustments, and closing/reopening; initial-load/open-menu drags are physically verified, with remaining phases still pending at this checkpoint.

## Prevent dragging into blank space in Kindle reading (2026-10-27)

A reading page that visually fits must also resist dragging into blank document space. Verify immediately after load, with the font menu open, after changing size/font, and after closing/reopening the banners. Tap-to-turn, font controls, links and close/backdrop actions remain usable. Ordinary scrolling on library/contents pages and the no-JavaScript fallback is unchanged.

## Kindle pages fit the browser window (2026-10-27)

The paginated Kindle reader must fit its usable browser window without horizontal or vertical page scrolling. Text size and selected font remain intact. Header/footer stay inside the window; page turns remain available via taps, including after font changes and viewport/orientation resizing. This applies to Kindle reading mode; library and contents pages retain ordinary vertical navigation. The no-JavaScript chapter fallback continues to scroll.

## Kindle-only phone-assisted sign-in (2026-10-27)

An unauthenticated Kindle e-reader visiting Distill automatically sees a QR code and matching eight-character code. Its stock browser requires no JavaScript: HTML refresh checks every ten seconds, with a manual Check approval link. The owner scans the QR code on a phone (or opens `/distill/pair/approve` and enters the code), completes ordinary Google sign-in there, compares the displayed code and explicitly presses Approve my Kindle. The Kindle then opens the existing Kindle library and shares the owner's existing reading progress. Requests expire in ten minutes; approved access lasts up to 30 days and can be revoked at `/distill/pair/devices` using real Google authentication. Phones/desktops retain their current Google sign-in; Kindle display-mode overrides and Fire/Silk/Android clients do not trigger pairing. Google pages and tokens stay on the phone. Never approve a code that is not on the reader you are pairing. The user confirmed successful phone pairing and reading in the physical Kindle stock browser on2026-10-27.

## Reader page continuity (2026-10-27)

In both Plainly and Distill, turning backward across a loaded section boundary must show the immediately preceding page, even when that section spans multiple chapters. Turning forward must continue after all currently rendered sections without repeating prefetched content. Navigation controls reflect the entire rendered window, and repeated taps during section loading must not trigger duplicate transitions. This corrects the reported 细胞传 backward jump from chapter 21 to 14; book text and saved-progress formats are unchanged.

Deployment verification: both the reader continuity and Distill book-action styling shipped in e6cb60f. Both apps are active; live served assets match the tested files. No database migration.
