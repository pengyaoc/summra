# Static JS

`app.js` is the source of truth. `app.min.js` is the bundled, minified artifact served to users
in production.

## Module structure

`app.js` defines the `SummraApp` class and `import`s subsystems that used to live inline in it
as one 6,000+-line file. Each subsystem module exports a plain object of methods (not a class —
no inheritance needed) that gets merged onto `SummraApp.prototype` via `Object.assign` after the
class body:

```js
import { paginationMixin } from './pagination.js';
class SummraApp { /* ... */ }
Object.assign(SummraApp.prototype, paginationMixin);
```

This is a structural split only — every method still reads/writes `this.*` exactly as it did
inline, and cross-calls between methods (e.g. `this.navigateToNextPage()` calling
`this.recalculatePagination()`) work unchanged regardless of which file a method's source lives
in, since `Object.assign` puts them all on the one `SummraApp.prototype`.

Modules so far:
- `pagination.js` — the page-based chapter reading engine (splitting text into fixed-height
  pages, illustration pages, touch/wheel/keyboard navigation, position persistence). The single
  largest subsystem (~1,100 lines) before this split.
- `route_utils.js` — pure route-parsing helpers (`withBasePath`, `parseAppRoute`, etc.), loaded
  before `app.js` (see below) rather than `import`ed, since `components/BlogIndex.js` and
  `components/BlogPost.js` need `withBasePath()` too and load earlier still.

More subsystems (reader, audio player, breadcrumbs, offline save, reading settings) are natural
candidates for the same treatment but haven't been split out yet.

## Build

```sh
npm install   # once, from the repo root
npm run build       # bundle + minify app.js (and its imports) into app.min.js
npm run build:check # fail (non-zero exit) if app.min.js is stale — used in CI
```

`asset_v()` (`backend/routes/system.py` via `backend/app_base.py`) appends a cache-busting query
string automatically — there is no manual `?v=` to bump.

## Dev vs. prod loading

- **Dev** (`is_development` in `index.html`): `app.js` loads as `<script type="module">`.
  Browsers execute ES modules (and their `import`s) natively — no bundler needed to develop;
  edit `pagination.js` or `app.js` and reload.
- **Prod**: `app.min.js` is `esbuild --bundle --minify`'s single self-contained file, with no
  `import`/`export` left in it, so it loads as a plain (non-module) `<script>`.

## Why `build:check` exists

Nothing *forces* `app.min.js` to be regenerated after an edit to `app.js` or one of its imports.
`npm run build:check` (wired into CI) is the safety net: it rebuilds fresh into a temp file and
diffs against the committed `app.min.js`, so a stale production bundle fails CI instead of
shipping silently.
