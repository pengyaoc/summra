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
python backend/app.py
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
