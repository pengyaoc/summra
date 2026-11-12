# Deploying to Production (GCP VM)

> Moved from `CLAUDE.md` on 2026-11-11 so agent instructions stay short. `CLAUDE.md` links here; this file is the source of truth.

Production runs on a GCP VM serving the public production domain (`<PROD_DOMAIN>`). Concrete identifiers — project, instance name, zone, external IP, Linux user, absolute paths — are stored locally in **`.prod-metadata.local.md`** (gitignored). Read that file to fill in any `<PLACEHOLDER>` token below before running a command. If `.prod-metadata.local.md` is missing, stop and recreate it from a password-manager note; never commit the real values.

**VM facts (generic shape):**
- GCP project `<GCP_PROJECT_ID>`, instance `<GCP_INSTANCE>`, zone `<GCP_ZONE>`, external IP `<VM_EXTERNAL_IP>`
- Repo at `<REMOTE_REPO_PATH>` (owned `<VM_USER>:<SERVICE_USER>`, group-writable)
- venv at `<REMOTE_REPO_PATH>/venv/` (Python 3.11)
- gunicorn runs as a **systemd *user* service** `<SYSTEMD_UNIT>` owned by `<SERVICE_USER>` (uid `<SERVICE_UID>`, lingering enabled) — NOT a system unit, so plain `sudo systemctl ... <SYSTEMD_UNIT>` reports "Unit not found". Unit file: `/home/<SERVICE_USER>/.config/systemd/user/<SYSTEMD_UNIT>`; it runs `gunicorn -c deploy/gunicorn_config.py plainly.app_prod:app` from `<REMOTE_REPO_PATH>` with `EnvironmentFile=<REMOTE_REPO_PATH>/service.env`
- gunicorn binds `127.0.0.1:<GUNICORN_PORT>` (set by `GUNICORN_BIND` in `service.env`; the `deploy/gunicorn_config.py` default of `:5000` is NOT what prod uses)
- **Apache** (not nginx — `deploy/archive/nginx-*.conf` is unused on this VM) terminates TLS for `<PROD_DOMAIN>`, runs OIDC (mod_auth_openidc; forwards the signed-in email as `X-Remote-Email`), serves `/plainly/static/` straight from `<REMOTE_REPO_PATH>/plainly/frontend/static/` (gzipped by Apache), and proxies everything else to gunicorn with `X-Forwarded-Prefix: /plainly` (old `/summrabook/...` URLs get a 301 to the same page under `/plainly`). Config: `<APACHE_PROXY_CONF>`. Apache does NOT compress proxied responses — Flask gzips HTML/JSON itself (`gzip_response` in `shared/web.py`). Prod speaks HTTP/1.1.
- DB at `<REMOTE_DB_PATH>` (`<VM_USER>:<SERVICE_USER>`, mode `664`)
- **Layout change (repo split):** the code now lives under `plainly/` and `shared/`. The systemd `ExecStart` must be `gunicorn -c deploy/gunicorn_config.py plainly.app_prod:app`, and the Apache static `Alias`/`<Directory>` must be `<REMOTE_REPO_PATH>/plainly/frontend/static/`. Update both on the VM (and `daemon-reload`) when first deploying this layout.
- `<REMOTE_REPO_PATH>/service.env*` are untracked, VM-only config files — never delete or commit them
- Pull/git work runs as `<VM_USER>`; service work runs as `<SERVICE_USER>` via `sudo -u`

**gcloud account/project:** the VM is only reachable with account `<GCP_ACCOUNT>` and project `<GCP_PROJECT_ID>`. Check with `gcloud config list`; if either differs, set them (`gcloud config set account <GCP_ACCOUNT>`, `gcloud config set project <GCP_PROJECT_ID>`) or pass `--account=<GCP_ACCOUNT> --project=<GCP_PROJECT_ID>` on each command. Symptoms of the wrong one: "resource ... was not found" (wrong project) or "Required 'compute.instances.get' permission" (wrong account).

All commands below assume you're driving the VM remotely via `gcloud compute ssh ... --command="..."`. The base SSH invocation:

```sh
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="<remote command>"
```

Service control (used in steps 2 and 4) — user-level systemctl/journalctl need the service user's runtime dir:

```sh
sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=/run/user/<SERVICE_UID> systemctl --user <restart|stop|start|is-active|status> <SYSTEMD_UNIT>
sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=/run/user/<SERVICE_UID> journalctl --user -u <SYSTEMD_UNIT> --since '1 minute ago' --no-pager
```

## 1. Pull latest `main` on the VM

Always check status first; if behind, fast-forward only (never merge unknown VM-local changes). Pull `origin main` explicitly: the VM checkout sits on a local branch (`feat/consolidated-login`, kept level with `main`) whose upstream no longer exists, so a bare `git pull` fails with "no such ref was fetched". The `merge-base` guard refuses to proceed if the checkout has diverged from `origin/main`:

```sh
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="sudo -u <VM_USER> bash -c 'cd <REMOTE_REPO_PATH> && git fetch origin --quiet && BEHIND=\$(git rev-list --count HEAD..origin/main) && echo BEHIND=\$BEHIND && if [ \$BEHIND -gt 0 ]; then git merge-base --is-ancestor HEAD origin/main && git log --oneline HEAD..origin/main && git pull --ff-only origin main; else echo Already up-to-date; fi'"
```

Untracked `service.env*` files in `git status` are expected (see VM facts).

**If the pull fails with "your local changes would be overwritten":** the VM has uncommitted state. Do NOT `git stash` or `--hard reset` blindly. Run `git diff HEAD -- plainly/` to see if any divergence is prod-only (env-specific config, hot-patches). If it's truly safe to discard, snapshot first to a backup branch:

```sh
sudo -u <VM_USER> bash -c 'cd <REMOTE_REPO_PATH> && git checkout -b vm-state-backup-$(date +%Y%m%d-%H%M%S) && git add -A && git commit -m "snapshot VM working state before reset" && git checkout main && git reset --hard origin/main'
```

The backup branch survives so you can cherry-pick anything that turns out to matter.

**Shared assets symlink (Ruling A) — required when first deploying the `shared/` layout.** Shared CSS, JS and fonts reach Apache through the symlink `plainly/frontend/static/shared -> ../../../shared/static`. Apache follows it only if the static `<Directory>` has `Options -Indexes +FollowSymLinks`; without it every `/plainly/static/shared/...` URL returns 404 and the reader is unstyled. The repo's `deploy/plainly/summra.conf` has the option; the VM's copy may not. Add it to the VM's `<APACHE_PROXY_CONF>` static `<Directory>` (keep the existing `Alias`), then:

```sh
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="sudo apachectl configtest && sudo systemctl reload apache2"
curl -sI https://<PROD_DOMAIN>/plainly/static/shared/css/base.css | head -1   # must be HTTP/... 200
```

## 2. Check whether a restart is needed

| Changed file | Restart? |
|---|---|
| `plainly/**` (any `.py` under plainly/) | **Yes** — gunicorn workers cache imported modules |
| `plainly/requirements.txt` | **Yes** + `pip install -r plainly/requirements.txt` inside the venv first |
| `plainly/models.py` schema changes | **Yes** — `Database.__init__` runs idempotent ALTER-TABLE migrations on boot |
| `deploy/gunicorn_config.py` | **Yes** |
| `/home/<SERVICE_USER>/.config/systemd/user/<SYSTEMD_UNIT>` or `service.env` | **Yes** + `systemctl --user daemon-reload` (as `<SERVICE_USER>`, see service control above) first for unit-file changes |
| `shared/**/*.py`, `shared/templates/**` | **Yes** — restart every app that runs on the VM (Plainly, and Distill once deployed); both import `shared` |
| `shared/static/**` (CSS, JS, fonts) | No — Apache serves it through the `static/shared` symlink (see the symlink step in step 1). Plainly's bundled `app.min.js` embeds shared JS, so rebuild it and treat a changed bundle as a `plainly/frontend/static` change |
| `distill/**` (any `.py` or template) | **Yes** — restart Distill only (`<DISTILL_UNIT>`; see [`deploy/distill/RUNBOOK.md`](../distill/RUNBOOK.md)) |
| `plainly/frontend/templates/**` | **Yes** — gunicorn's Jinja caches compiled templates (debug is off); without a restart the old page keeps being served (seen 2026-10-17) |
| `plainly/frontend/static/**` (CSS, JS, images) | No — Apache serves directly. Bump cache-busting query string in `index.html` if you need clients to pull a new asset |
| `data/books/**` raw text | No — only used during ingestion, not at request time |
| `docs/**`, `WORK_LOG.md`, `README.md`, `tests/**` | No |

```sh
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="export XDG_RUNTIME_DIR=/run/user/<SERVICE_UID>; sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR systemctl --user restart <SYSTEMD_UNIT> && sleep 4 && sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR systemctl --user is-active <SYSTEMD_UNIT> && curl -sS -o /dev/null -w 'local HTTP %{http_code}\n' http://127.0.0.1:<GUNICORN_PORT>/ && sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR journalctl --user -u <SYSTEMD_UNIT> --since '1 minute ago' --no-pager | grep -iE 'error|exception|traceback' | grep -v 'sent SIGTERM' | tail -5 || echo no errors"
```

## 3. Verify public site after deploy

```sh
curl -sSL -o /dev/null -w 'GET /         HTTP %{http_code}  time=%{time_total}s\n' https://<PROD_DOMAIN>/
curl -sSL -o /dev/null -w 'GET /books    HTTP %{http_code}  time=%{time_total}s\n' https://<PROD_DOMAIN>/books
curl -sSL -o /dev/null -w 'GET /api/books HTTP %{http_code}  time=%{time_total}s\n' https://<PROD_DOMAIN>/api/books
```

All should return 200 in under ~1s. If any return 500, check `sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=/run/user/<SERVICE_UID> journalctl --user -u <SYSTEMD_UNIT> --no-pager | tail -50` on the VM.

## 4. Copy local `database.db` to VM and activate it

The VM's DB is the live source of truth for prod. Replacing it is destructive — overwrites whatever has been ingested directly on the VM. Today the VM does NOT take writes (no auth, no user content), so the only thing at risk is recent ingestion done on the VM itself; in practice all ingestion happens locally and is pushed via this flow.

**Pre-flight (always):**
```sh
# row counts side-by-side
sqlite3 <LOCAL_DB_PATH> "SELECT 'books='||COUNT(*) FROM books UNION ALL SELECT 'chapters='||COUNT(*) FROM chapters UNION ALL SELECT 'authors='||COUNT(*) FROM authors;"
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="sudo -u <SERVICE_USER> <REMOTE_REPO_PATH>/venv/bin/python3 -c \"
import sqlite3
c = sqlite3.connect('<REMOTE_DB_PATH>').cursor()
for tbl in ('books','chapters','authors'): print(f'{tbl}=' + str(c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]))
\""
```

If VM counts are higher than local for anything other than `blog_posts`, STOP — the VM has data that's not in local. Investigate first. The reader index (`reader_version`, `reader_unit`) is derived from `chapters` and rebuilt on demand, so differences there don't matter. To ship one book's text you can also update just that book's `chapters` rows on the VM (check they match your local pre-change backup first), then run `ensure_reader_content(<book_id>)`.

**Copy and activate:**
```sh
# 1. Snapshot VM's current DB
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="sudo cp <REMOTE_DB_PATH> <REMOTE_DB_PATH>.bak-pre-copy-\$(date +%Y%m%d-%H%M%S) && ls -lh <REMOTE_DB_PATH>*"

# 2. SCP local DB to /tmp on VM (can't scp directly into <REMOTE_REPO_PATH> — perms)
gcloud compute scp <LOCAL_DB_PATH> <GCP_INSTANCE>:/tmp/database.db.new --zone=<GCP_ZONE>

# 3. Verify checksums match (paranoid but cheap)
md5 -q <LOCAL_DB_PATH>
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="md5sum /tmp/database.db.new"

# 4. Stop service, move into place with correct ownership, restart
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="export XDG_RUNTIME_DIR=/run/user/<SERVICE_UID>; sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR systemctl --user stop <SYSTEMD_UNIT> && sudo mv /tmp/database.db.new <REMOTE_DB_PATH> && sudo chown <VM_USER>:<SERVICE_USER> <REMOTE_DB_PATH> && sudo chmod 664 <REMOTE_DB_PATH> && sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR systemctl --user start <SYSTEMD_UNIT> && sleep 4 && sudo -u <SERVICE_USER> XDG_RUNTIME_DIR=\$XDG_RUNTIME_DIR systemctl --user is-active <SYSTEMD_UNIT>"
```

**Why stop/start instead of just restart:** gunicorn workers hold open SQLite file handles. A live `mv` over the DB leaves workers reading the old (now unlinked) inode until they're recycled — better to take the request path down for ~5s and bring it back on a clean file.

**Why chmod 664 + group `<SERVICE_USER>`:** Flask runs as `<SERVICE_USER>`. The DB needs to be group-readable; the group-write bit lets future writes (if FEATURE_AUTH ever flips on) work without a re-chown.

**Verify the new DB is live:**
```sh
# Confirm a row only present in the new DB resolves publicly. Replace <new-slug>
# with a book that exists locally but did NOT exist on the VM pre-copy.
curl -sSL -o /dev/null -w 'GET /books/<new-slug> HTTP %{http_code}\n' https://<PROD_DOMAIN>/books/<new-slug>
curl -sSL https://<PROD_DOMAIN>/api/books | python3 -c "import sys, json; d=json.load(sys.stdin); books=d.get('books', d); print(f'total: {len(books)}')"
```

**Backups accumulate.** `<REMOTE_DB_PATH>.bak-pre-copy-*` on the VM is root-owned and ~170M each. Periodically: `sudo rm <REMOTE_DB_PATH>.bak-pre-copy-*` after you're sure the deploy is healthy (keep at most the last 1–2).
