# Static JS

`app.js` is the source of truth. `app.min.js` is the minified artifact served to users.

## Build

```sh
npm install   # once, from the repo root
npm run build       # regenerate app.min.js from app.js
npm run build:check # fail (non-zero exit) if app.min.js is stale — used in CI
```

`asset_v()` (`backend/routes/system.py` via `backend/app_base.py`) appends a cache-busting query
string automatically — there is no manual `?v=` to bump.

## Why `build:check` exists

There is still no bundler step wired into the dev server (the browser loads the un-minified
`app.js` directly in dev — see `is_development` in `index.html`), so nothing *forces* `app.min.js`
to be regenerated after an edit. `npm run build:check` (wired into CI) is the safety net: it
rebuilds fresh into a temp file and diffs against the committed `app.min.js`, so a stale
production bundle fails CI instead of shipping silently.
