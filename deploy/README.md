# Deployment Files for Summra

This directory contains everything needed to deploy Summra — standalone on its own VM, or
cohosted alongside other services (the actual production case: `wordpress-2-vm` runs
WordPress, OpenReader, and Summra together). Both paths use the same committed files; only
`deploy/service.env` (per-host, never committed) differs.

See `01-projects/personal-brand/vm-service-convention.md` in the vault for the isolation and
portability principles this follows, and `wordpress-vm-pages-setup.md` for the live production
setup and its host-owned Apache vhost.

## Files

| File | Purpose |
|---|---|
| `install.sh` | Idempotent installer — creates the `summra` user, `/opt/summra`, venv, `service.env`, systemd unit, and (if `--prefix` given) the Apache fragment |
| `gunicorn_config.py` | The one gunicorn config for every deployment — reads `GUNICORN_BIND`/`GUNICORN_WORKERS`/`GUNICORN_THREADS` from the environment |
| `service.env.example` | Template for the per-host `EnvironmentFile` — the installer copies this to `/opt/summra/service.env` (mode `600`, never committed) |
| `systemd/summra.service` | `systemd --user` unit — sandboxed (`ProtectSystem=strict`), literal `/opt/summra` paths |
| `systemd/override.example.conf` | Template for the per-host `MemoryMax` drop-in |
| `apache/summra.conf` | Cohosted reverse-proxy + static-file fragment, installed to `/etc/apache2/service-locations/` when `--prefix` is used |
| `nginx-summra-standalone.conf` + `nginx-summra-common.conf` | Standalone nginx alternative to the Apache fragment |
| `requirements-prod.txt` | Python dependencies (no TTS — `app_prod.py` only serves pre-generated audio) |
| `DEPLOY.md` | Full walkthrough for a dedicated GCP VM (e2-micro/e2-small), predates cohosting — see the note at its top |
| `hardening_check_vm.sh` / `hardening_check_gcp.sh` / `HARDENING.md` | Security posture checks (SSH, ports, GCP firewall) |

## Quick start

**Standalone** (Summra is the only thing on the box):
```bash
git clone <repo> /tmp/summra-src && cd /tmp/summra-src
sudo deploy/install.sh
```
Serves on `127.0.0.1:5000`. Put nginx (`nginx-summra-standalone.conf` +
`nginx-summra-common.conf`) or Apache in front of it and point DNS at the box.

**Cohosted** (adding Summra to a VM that already runs other services behind Apache):
```bash
sudo deploy/install.sh --prefix /plainly --bind 127.0.0.1:5001
```
This also drops `deploy/apache/summra.conf` into `/etc/apache2/service-locations/`. The host's
shared vhost (TLS, `ServerName`, `ProxyPreserveHost`, `Define SUMMRA_PREFIX`,
`IncludeOptional /etc/apache2/service-locations/*.conf`) is **not** installed by this script —
it's host-level config owned outside any single service's repo. See
`wordpress-vm-pages-setup.md` for the live example.

Either way, then copy in data:
```bash
gcloud compute scp data/database.db <vm>:/tmp/database.db --zone=<zone>
gcloud compute scp --recurse plainly/frontend/static/audio plainly/frontend/static/covers <vm>:/tmp/ --zone=<zone>
# on the VM, as the summra user, move these into /opt/summra/data and
# /opt/summra/plainly/frontend/static/ respectively
```

## Runtime shape

```
Internet
    |
Apache or nginx (443, shared with other cohosted services)
    ├── <prefix>/static/ → served directly from /opt/summra/plainly/frontend/static/
    └── <prefix>/        → proxied to gunicorn on 127.0.0.1:<port>
                                |
                        gunicorn (gthread, 1 worker, 4 threads)
                                |
                        Flask (plainly/app_prod.py)
                                |
                        ├── data/database.db   (content, read-only in prod)
                        └── data/summra.db     (user/session state, read-write)
```

**Why `gthread`, not `gevent`:** the app is synchronous WSGI with zero `async def` anywhere in
`plainly/` — its per-request work is SQLite reads and Jinja rendering, neither of which
benefits from gevent's cooperative sockets. gevent's only real payoff was not blocking on large
audio-file transfers, which the Apache/nginx static fragment now handles instead. Dropping it
also removes a real deploy risk: the pinned `gevent==24.2.1` has no wheel for newer Python and
fails to build from source, which is what previously forced an unpinned, undocumented install.

**Why no `GEMINI_API_KEY` on the server:** production never generates TTS or calls Gemini for
anything — `app_prod.py` serves only pre-generated audio from `plainly/frontend/static/audio/`, 404ing
if it's missing. All Gemini calls happen locally during content generation; only the resulting
audio files and DB rows get deployed. Keep the real key in your local, gitignored `.env` only.

## Sandbox notes

`ProtectSystem=strict` + `ProtectHome=read-only` make everything except
`ReadWritePaths=/opt/summra/data` read-only to the process. This is why all mutable state —
`data/database.db` and `data/summra.db` — must live under `data/`; `plainly/config.py`'s
`DATABASE_PATH` and `USER_DATABASE_PATH` both resolve there. `static/audio/` is deliberately
**not** writable in production, since nothing writes to it at runtime.

If you see `Read-only file system` in `journalctl --user -u summra`, something is trying to
write outside `data/` — check what changed before adding more paths to `ReadWritePaths`, don't
just widen the sandbox to make the error go away.

## Monitoring

```bash
# as the summra user (or root via sudo -u summra ...):
export XDG_RUNTIME_DIR=/run/user/$(id -u summra)
systemctl --user status summra
journalctl --user -u summra -f
```

## Updating

```bash
cd /opt/summra
sudo -u summra git pull
sudo -u summra venv/bin/pip install -r requirements-prod.txt
sudo -u summra env XDG_RUNTIME_DIR=/run/user/$(id -u summra) systemctl --user restart summra
```

## Troubleshooting

**Won't start / crash loop:** `journalctl --user -u summra -n 100 --no-pager`. A
`Read-only file system` error means the sandbox notes above — something outside `data/` got a
write attempt.

**502 / connection refused from the front end:** confirm `service.env`'s `GUNICORN_BIND`
matches what the Apache/nginx fragment proxies to, and that the unit is actually active.

**Out of memory:** check `journalctl --user -u summra` for OOM kills, then raise
`~/.config/systemd/user/summra.service.d/override.conf`'s `MemoryMax` — see
`systemd/override.example.conf` for the standalone-vs-cohosted guidance.


## Kindle launchers and phone-assisted login

See [kindle/README.md](kindle/README.md) for the version-controlled Home shortcut
scripts, monochrome covers, installation, recovery and sign-in instructions.
These files deploy to the Kindle, not to the web server's runtime.

Both Flask apps install `shared.auth.device_pairing.install_pairing` before
reader dispatch. Kindle-only opaque device sessions supplement Apache's Google
identity. Plainly retains optional authentication/public reading; Distill stays
private. Phone approval and device management must always be protected by OIDC
in both Apache fragments. Plainly's `/login` now reaches its Flask route via the
flat proxy rather than being remapped to `/` by a Location ProxyPass.

Pairing storage defaults beside each user database: `distill_pairing.db` and
`plainly_pairing.db`. Overrides: `DISTILL_PAIRING_DB` / `SUMMRA_PAIRING_DB` and
`DISTILL_PAIRING_ORIGIN` / `SUMMRA_PAIRING_ORIGIN` (default
`https://pengyaochen.com`, origin only; proxy supplies the app prefix). Secure,
HttpOnly, SameSite=Lax cookies have app-specific names and paths. Existing
Distill cookies, database and session records remain compatible. There is no
schema migration or sharing of login tokens between apps. QR PNG generation
requires `qrcode` and Pillow in the common production virtualenv.

## Disk audit: wordpress-2-vm, 2026-10-27

Read-only `df`, `du`, file-size and SQLite `dbstat` inspection found:

| Storage | Observed usage | Explanation |
|---|---:|---|
| Entire root filesystem | 11 GB of 30 GB, 37%; 18 GB available | No immediate capacity pressure |
| `/opt/summra` | 3.6 GB | Shared checkout, data and runtime for both apps |
| `data/` | 2.4 GB | Mostly repeated deployment backups |
| 26 top-level backup files | 2,146,037,760 bytes (2.00 GiB) | `.pre-*`, `.bak-*`, plus sidecars; additional small backups under `data/backups/` |
| Live Plainly content DB | 174,051,328 bytes | 138 MB chapter text, 20 MB reader units, 13 MB reader index |
| Live Distill content DB | 159,563,776 bytes | 146 MB image blobs, 9 MB chapters, 4 MB thumbnails |
| `.git/` | 676 MB | 633 MiB packed history plus 41 MiB loose objects |
| Plainly static assets | 408 MB | 332 MB audio, 47 MB illustrations, 25 MB covers |
| `docs/` | 84 MB | 82 MB redesign assets |
| `venv/` | 96 MB | Small relative to data/history |
| Service user's pip cache | 40 MB | Download cache outside the checkout |

The live content DBs have only 4 and 1 free SQLite pages respectively: VACUUM
would reclaim essentially nothing. Disk use is retained data, media and Git
history, not an abnormally large Python runtime or active browser process.
Do not delete live DBs or audio: they serve the apps. No cleanup was performed.

Recommended follow-up: inventory and verify rollback snapshots, copy historical
backups to a compressed off-VM archive, then agree a bounded retention policy
(e.g. last known-good plus recent daily backups). Most immediate reclaimable
space is the 2 GiB of accumulated deployment snapshots. A shallow production
checkout could reduce Git history, after verifying deployment/rollback needs;
normal Git maintenance preserves history and cannot promise equivalent savings.
Avoid taking another full pair of content-DB backups for code-only deployments
that do not migrate those databases. Auth pairing changes need only a small
consistent backup of the pairing DB if one is desired.


## Generated media and history rewrite

On 2026-10-27, generated content media was removed from Git's current tree and
all published history at the owner's request. Ignored directories:

- `plainly/frontend/static/audio/`, `covers/`, `illustrations/`, `guides/`
- the same four directories under the historical `frontend/static/` root
- generated `docs/redesign/before/`, `docs/redesign/after/` and e2e screenshots

Branding/UI assets in `static/images/` and Kindle launcher covers in
`deploy/kindle/` stay versioned. Distill content images are stored in its
untracked content database; those are unaffected. Existing media serving paths,
Apache aliases and database URLs have not changed. Production media remains
under `/opt/summra/plainly/frontend/static/` and must be backed up/transferred
independently of the Git repository.

For a new deployment, restore content databases and all four media directories
from a trusted copy (e.g. the current VM) after cloning. Copy media explicitly
with `rsync -a` or `gcloud compute scp --recurse`; a clone or Git pull alone no
longer supplies a populated library. Keep generated content out of future
commits; `git check-ignore` should report these paths.

When updating an existing checkout across the rewrite, first verify a separate
media copy and a clean tracked working tree. Fetch the rewritten `main` with an
explicit forced remote-ref update. Use `git reset --mixed origin/main` to update
HEAD/index while leaving working media intact, then restore only the reviewed
non-media source/doc changes from the new index. Do not use a hard reset for
this first transition: it can delete media that used to be tracked. Verify
media hashes and HTTP responses before deleting the temporary safety copy.
Normal future code deploys must preserve ignored files: avoid `git clean -fdx`
and rsync `--delete` over media directories.

Commit IDs before the rewrite are obsolete. Other clones must migrate or be
recloned rather than merge/push the old ancestry. The sole published branch is
main; no published tags/open PRs existed during this rewrite. The push uses a
lease on the inventoried old main SHA to avoid overwriting a concurrent update.
After local refs/worktree HEADs are migrated, expire old reflogs and garbage
collect so removed objects no longer occupy those clones. GitHub can retain
unreachable cached objects until its own cleanup and may show stale size stats.

Backup retention cleanup completed before this rewrite: one verified archive
per app at `data/backups/distill-latest.tar.gz` (147,581,980 bytes) and
`plainly-latest.tar.gz` (54,065,818 bytes), covering content, accounts/progress
and pairing databases. Removed 28 older database backup files; net reclaimed
1,946,896,714 bytes. Both services and public launch pages remained healthy.
These database archives do not contain the separate static media library.


### Completed transition verification

Rewritten main `9cca549` passed GitHub CI. The existing VM checkout was migrated
with media intact: all 634 files/509,981,225 bytes match the pre-transition hashes.
Public Plainly audio, covers, illustrations and guide images pass HTTP range
requests with matching bytes; an authenticated Distill library/book/cover check
passes too. Both user services remain active, without needing an app restart.
VM-only old branch/stash and Mac saved stash/tree checkpoints were filtered as
well, preserving their non-media content and stash structure. After expiring old
reflogs and garbage collection, packed Git storage is 11.24MiB on the VM and
11.29MiB on the Mac (small differences reflect local saved work). The temporary
VM media safety copy and isolated rewrite mirror were removed after final hash
verification; the live media remains in its original serving directories.

The Distill database backup is larger than Plainly's compressed archive because
Distill embeds about 146MB of image blobs, which compress little. Plainly's
content database is mostly compressible text; its static audio/images are
outside the database archives. A backup-size comparison therefore does not
compare the apps' complete media libraries.
