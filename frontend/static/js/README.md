# Static JS

`app.js` is the source of truth. `app.min.js` is the minified artifact served to users.

To regenerate after editing `app.js`:

    cd frontend/static/js && npx --yes esbuild app.js --minify --legal-comments=inline --outfile=app.min.js

Then bump the `?v=` query string on the `app.min.js` script tag in `frontend/templates/index.html`.
