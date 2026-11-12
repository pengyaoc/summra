# Distill

Distill is a private reader for chapter-by-chapter summaries of books the owner reads. It is the second app on the Summra platform ([root README](../README.md)). It uses the same reader, saved place, progress sync, Kindle e-ink mode and chapter audio as Plainly, all from [`shared/`](../shared/README.md).

- **Owner only.** Every page sits behind Google sign-in plus an email allow-list, and that includes images and static files. Production refuses to start unless `DISTILL_AUTH_MODE=required`.
- **No LLM on the server.** Summaries are written on the owner's computer, by the `book-summary` Claude Code skill or `skills/distill-publish`, as a Distill book folder. The app only imports and serves them.
- **Pages:** a library with the books in progress at the top, a book page with the table of contents, the reader, and a Kindle version of each.

## Layout

```
distill/
├── app_base.py        App factory: shared reader platform, allow-listed sign-in, private caching
├── app.py / app_prod.py   Dev (:5003) and prod (gunicorn distill.app_prod:app) entry points
├── config.py          DISTILL_DB, DISTILL_USER_DB, auth mode, port
├── models.py          Content DB (data/distill.db): books, chapters, images, audio
├── book_format.py     Book folder format v1: load, validate, read block text
├── reader_config.py   Distill's ReaderConfig
├── audio_app.py       Distill's description for shared/audio's recorder
├── routes.py          Library, book, reader, private image and cover routes
├── kindle_routes.py   Server-rendered Kindle pages
├── templates/, static/   static/shared → ../../shared/static (symlink)
└── scripts/
    ├── push_book.py   Validate a book folder and import it (--deploy also pushes it to the VM)
    ├── deploy_code.py Fast-forward the VM checkout and restart Distill
    ├── deploy_db.py   Send only the changed rows and media to the VM, then verify
    └── …              db_patch, media_transfer, migrate_media, convert_html_summaries (one-time)
```

## Run

```bash
DISTILL_USER_DB=$TMPDIR/distill_user_e2e.db PORT=5003 venv/bin/python -m distill.app
```

Locally, auth is `off` and the server binds to loopback only.

## Add a book

```bash
venv/bin/python -m distill.scripts.push_book <book-folder>             # import locally
```

```bash
venv/bin/python -m distill.scripts.push_book <book-folder> --deploy    # import, then push to the VM
```

Book folders, `data/distill.db` and `data/distill_user.db` must never be committed: this repository is public. Never push `distill_user.db` to the VM either, since it holds reading progress.

## Audio

Chapter audio is recorded on the owner's Mac (macOS `say` for English, Siri for Chinese):

```bash
venv/bin/python -m shared.audio.make_audio --app distill --book <slug> --dry-run
```

## Tests

```bash
venv/bin/python -m pytest tests/distill tests/shared -v
```

```bash
cd tests/e2e && node distill.mjs      # desktop, mobile and Kindle passes against :5003
```

## Deploy

Run code before content, so the VM's schema is migrated first:

```bash
venv/bin/python -m distill.scripts.deploy_code
```

```bash
venv/bin/python -m distill.scripts.deploy_db
```

Settings come from `deploy/distill/deploy.local.env` (gitignored). The service, Apache and env templates are in [`deploy/distill/`](../deploy/distill/). The full runbook is [`deploy/distill/RUNBOOK.md`](../deploy/distill/RUNBOOK.md).

Docs: [`docs/distill/PRD.md`](../docs/distill/PRD.md) (product), [`docs/distill/ERD.md`](../docs/distill/ERD.md) (engineering), and the original design in [`docs/superpowers/specs/2026-10-24-distill-design.md`](../docs/superpowers/specs/2026-10-24-distill-design.md).
