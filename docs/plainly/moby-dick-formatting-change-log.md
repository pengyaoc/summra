# Moby-Dick reader formatting change log

Date: 2026-10-13

## Changes made

- Updated the continuous reader in `frontend/static/js/reader.js` to parse inline Markdown after escaping stored text. This renders emphasis markers such as `_italic_`, `*italic*`, and `**bold**` as formatting while keeping source HTML escaped.
- Added a reader block formatter for short all-caps section labels and “Original Transcriber’s Notes,” which now render as section headings.
- Identified numbered and Markdown bullet lines as list entries. Bullet markers render as bullets, and list entries use compact spacing and hanging indents.
- Added corresponding heading and list styles in `frontend/static/css/style.css`.
- Rebuilt `frontend/static/js/app.min.js` from the current sources. The build also contains the pre-existing guide URL prefix fix from `frontend/static/js/app.js`.
- No Moby-Dick database rows were changed. Its source text and stored emphasis markers remain intact. The separate local Alice chapter correction from the prior request is unchanged.

## Reverting these changes

If `frontend/static/js/reader.js` and `frontend/static/css/style.css` have no later edits, restore them to the repository version and rebuild the bundle:

```sh
git restore --source=HEAD -- frontend/static/js/reader.js frontend/static/css/style.css
npm run build
```

Rebuilding is necessary because `app.min.js` is generated. It preserves the current `app.js` guide URL prefix fix. Remove this log file if the change is fully reverted. No database rollback is needed.
