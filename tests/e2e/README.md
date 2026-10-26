# Frontend smoke harness

Headless Chromium loop for verifying the Flask-rendered frontend.

## One-time install

```sh
cd tests/e2e
npm install
npx playwright install chromium
```

## Run

Start the Flask dev server in another shell:

```sh
source venv/bin/activate
python plainly/app.py
```

Then from `tests/e2e/`:

```sh
npm run smoke                         # hits /
PATHS=/,/book/104 npm run smoke       # multiple paths
HEADED=1 npm run smoke                # watch the browser
BASE_URL=http://localhost:5000 npm run smoke
```

Exit code is non-zero if any page returned a non-OK status, logged a console
error, or had a failed network request. Screenshots land in `screenshots/`.

## Distill and the shared reader

Distill is the second app on the shared reader platform. Start its dev server
(auth is `off` locally, bound to loopback) with a scratch user DB:

```sh
DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app
```

Then from `tests/e2e/`:

```sh
node distill.mjs                      # defaults to http://localhost:5003
BASE_URL=http://localhost:5003 HEADED=1 node distill.mjs
```

`distill.mjs` runs three passes: desktop, mobile (375x667) and Kindle (758x950).
It exits 1 on any FAIL or console error; screenshots are `screenshots/distill_*.png`.

`reader_style_snapshot.mjs` records and compares computed styles of Plainly's
reader chrome. It defaults to `http://localhost:5001`, so pass `BASE_URL` for any
other server:

```sh
MODE=record  BASE_URL=http://localhost:5002 node reader_style_snapshot.mjs
MODE=compare BASE_URL=http://localhost:5002 node reader_style_snapshot.mjs
```

### Plainly e2e set

Run these (each `node <name>.mjs` with `BASE_URL` set to your Plainly server)
after any change under `shared/` or `plainly/`: `smoke`, `kindle_mode`,
`reader_progress`, `reader_themes`, `reader_last_line_visible`,
`reader_opens_at_chapter`, `reader_segments_fast_open`, `reader_illustrations`,
`reader_font_figtree`, `reader_nav_mouse`, `sxs_row_split`, `text_size_adjust`,
`redesign_home`, `redesign_reader`.

### Reader exit and iOS scroll lock

With Plainly on :5016 and Distill on :5015 (use a scratch Distill user DB):

```sh
BASE_URL=http://localhost:5016 DISTILL_BASE_URL=http://localhost:5015 node reader_back_unlocks_scroll.mjs
ENGINE=webkit BASE_URL=http://localhost:5016 DISTILL_BASE_URL=http://localhost:5015 node reader_back_unlocks_scroll.mjs
```

Checks Plainly browser back, edge swipe and late segment loads, then Distill's
reader back button, browser Back and Back/Forward restoration. The book page
must have no reader scroll locks and must scroll after every exit. WebKit uses
an iPhone context; this is engine-level coverage, not a physical iOS Chrome run.
