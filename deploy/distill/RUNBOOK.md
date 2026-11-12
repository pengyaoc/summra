# Deploying Distill (same VM)

> Moved from `CLAUDE.md` on 2026-11-11 so agent instructions stay short. `CLAUDE.md` links here; this file is the source of truth.

Distill is the owner-only summary reader at `/distill` on the same host. It shares Plainly's checkout, venv and `<SERVICE_USER>`, but runs its own gunicorn.

**Shape:**
- **Service.** Unit `<DISTILL_UNIT>`, a systemd *user* unit for `<SERVICE_USER>`, installed from `deploy/distill/distill.service`. It runs `gunicorn -c deploy/gunicorn_config.py distill.app_prod:app`.
- **Settings.** `EnvironmentFile=<REMOTE_REPO_PATH>/distill.env` is VM-only, mode 600, and made from `deploy/distill/distill.env.example`. It sets:
  - `GUNICORN_BIND=127.0.0.1:<DISTILL_PORT>`, plus its own `GUNICORN_PROC_NAME` and `GUNICORN_PIDFILE`
  - absolute `DISTILL_DB` / `DISTILL_USER_DB` under `<REMOTE_REPO_PATH>/data/`
  - `DISTILL_AUTH_MODE=required`, `DISTILL_ALLOWED_EMAILS=<owner email>`
- **Apache.** The fragment `/etc/apache2/service-locations/distill.conf` is installed from `deploy/distill/distill.conf`.
  - It sets `OIDCUnAuthAction auth`, so signed-out visitors go to Google sign-in.
  - Everything is proxied to gunicorn, static files included. There is no Apache `Alias`: Distill's static files must not skip sign-in or be cached `public`.
- **App guard.** `distill.app_prod` refuses to start unless the auth mode is `required`, and the app returns 403 to any non-allow-listed email.
- **Database.** `distill.db` holds the content and images. Deploys are incremental: one command compares rows with the VM and sends only the changed books, chapters, images, covers and audio plus media the VM lacks, applied in one transaction with the service running. It backs up the live DB first, refuses a book whose id or slug means something different on each side, leaves books that exist only on the VM alone, checks that the app still returns 401, and lets the VM rebuild its reader index on demand. The VM needs the current `distill/scripts/db_patch.py`, so pull code before the first deploy that uses a change to it:
  - `venv/bin/python -m distill.scripts.deploy_db [--db PATH] [--config PATH]` sends the content changes alone. Every run ends by checking the VM (integrity, every row identical, all media present), so a run with nothing to send is a full check.
  - `venv/bin/python -m distill.scripts.push_book <folder> --deploy` imports the book locally, then runs the same push, and prints the book's URL. `--deploy` with `--dry-run` is an error.
  - Settings come from the gitignored `deploy/distill/deploy.local.env` (override with `--config`). Make it from `deploy/distill/deploy.local.env.example`. Keys: `DISTILL_VM_INSTANCE`, `_ZONE`, `_PROJECT`, `_ACCOUNT`, `_SERVICE_USER`, `_REMOTE_DB`, `_UNIT`, `_PORT`, and `DISTILL_SITE_URL`.
  - A SHA256 mismatch or a conflict stops before anything changes on the VM. Never push `distill_user.db`: it holds reading progress.

**Chapter audio (Listen).** Audio is rendered on the Mac only (macOS voices), never on the VM.
- English uses `say` with the system voice (Siri Voice 2). Chinese uses Mandarin Siri Voice 4 at rate 1.0, through InkChinese's `pipeline/siri_tts.py`; set `DISTILL_SIRI_TTS_PATH` / `DISTILL_SIRI_PYTHON` in `deploy.local.env`.
- Commands:
  - `venv/bin/python -m shared.audio.make_audio --app distill --book <slug> --dry-run` estimates the hours.
  - `... --book <slug> --deploy` renders only stale or missing chapters, then pushes the DB plus only the new media keys.
  - `--all` covers the library.
  - English records at 48 kHz and each chapter is stored only as Opus 24 kbps (ffmpeg; iPhones need iOS 17+). Chapters made before 2026-11-08 are AAC; `... --all --opus-only` converts them to Opus without re-rendering (their AAC stays local, only Opus deploys). `say` at 48 kHz needs its voice reference re-approved once (`--approve-voice`).
  - Use `--jobs 4` for every language (about 3× faster than one at a time on the M1 Pro; speed stops improving past 6–8). Run only one `make_audio` recording at a time. Each voice call times out and retries 3 times if one hangs.
- A run stops if a voice no longer matches its approved reference clip (`data/distill-voice-refs/`). After listening to a sample, re-approve with `--approve-voice`.

**First install** (as done 2026-10-26). Run as root via `gcloud compute ssh`:
1. `pip install -r distill/requirements.txt` in the venv (Pillow).
2. Copy the env file from the example and fill in the allow-list.
3. Copy the unit to `/home/<SERVICE_USER>/.config/systemd/user/`, then `daemon-reload` and `enable --now <DISTILL_UNIT>`.
4. Copy `distill.conf` into `service-locations/`, run `apachectl configtest`, then `systemctl reload apache2`.

**Code deploy:** after pushing `main`, run `venv/bin/python -m distill.scripts.deploy_code`. It refuses unpushed commits or a diverged VM checkout, fast-forwards the VM, restarts Distill, and checks the app returns 401. When a change affects Plainly and `DISTILL_VM_PLAINLY_UNIT` / `DISTILL_VM_PLAINLY_PORT` are set in `deploy.local.env`, it also restarts Plainly and checks for a 200. A pip install stays manual; it says when one is needed. Run it before `deploy_db`, so the VM's schema is migrated first.

**Restart:** the same service-control commands as Plainly, with `<DISTILL_UNIT>`.

**Verify after deploy:**

```sh
# On the VM: anonymous 401, stranger 403, owner 200
curl -sS -o /dev/null -w 'anon %{http_code}\n' http://127.0.0.1:<DISTILL_PORT>/
curl -sS -o /dev/null -H 'X-Remote-Email: stranger@example.com' -w 'stranger %{http_code}\n' http://127.0.0.1:<DISTILL_PORT>/
curl -sS -o /dev/null -H 'X-Remote-Email: <owner email>' -w 'owner %{http_code}\n' http://127.0.0.1:<DISTILL_PORT>/
# Public: a signed-out request is redirected to accounts.google.com
curl -sS -o /dev/null -w '%{http_code} -> %{redirect_url}\n' https://<SITE_HOST>/distill/
```
