#!/usr/bin/env node
// Fails (non-zero exit) if the committed app.min.js is not what `npm run
// build` would produce from the current app.js. Run in CI so a stale
// production bundle is caught before merge, instead of silently shipping —
// app.min.js has no build step enforcing it, so it can (and has) drifted
// from app.js for many commits at a time. See frontend/static/js/README.md.
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const appJs = join(here, 'app.js');
const committedMinPath = join(here, 'app.min.js');
const freshMinPath = join(tmpdir(), `app.min.fresh.${process.pid}.js`);

execSync(
  `npx esbuild "${appJs}" --minify --legal-comments=inline --outfile="${freshMinPath}"`,
  { stdio: 'inherit' }
);

const committed = readFileSync(committedMinPath, 'utf8');
const fresh = readFileSync(freshMinPath, 'utf8');

if (committed !== fresh) {
  console.error(
    '\napp.min.js is STALE — it does not match a fresh build of app.js.\n' +
    'Run `npm run build` and commit the result.\n'
  );
  process.exit(1);
}

console.log('app.min.js is up to date with app.js.');
