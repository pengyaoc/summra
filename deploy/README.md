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
sudo deploy/install.sh --prefix /summrabook --bind 127.0.0.1:5001
```
This also drops `deploy/apache/summra.conf` into `/etc/apache2/service-locations/`. The host's
shared vhost (TLS, `ServerName`, `ProxyPreserveHost`, `Define SUMMRA_PREFIX`,
`IncludeOptional /etc/apache2/service-locations/*.conf`) is **not** installed by this script —
it's host-level config owned outside any single service's repo. See
`wordpress-vm-pages-setup.md` for the live example.

Either way, then copy in data:
```bash
gcloud compute scp data/database.db <vm>:/tmp/database.db --zone=<zone>
gcloud compute scp --recurse frontend/static/audio frontend/static/covers <vm>:/tmp/ --zone=<zone>
# on the VM, as the summra user, move these into /opt/summra/data and
# /opt/summra/frontend/static/ respectively
```

## Runtime shape

```
Internet
    |
Apache or nginx (443, shared with other cohosted services)
    ├── <prefix>/static/ → served directly from /opt/summra/frontend/static/
    └── <prefix>/        → proxied to gunicorn on 127.0.0.1:<port>
                                |
                        gunicorn (gthread, 1 worker, 4 threads)
                                |
                        Flask (backend/app_prod.py)
                                |
                        ├── data/database.db   (content, read-only in prod)
                        └── data/summra.db     (user/session state, read-write)
```

**Why `gthread`, not `gevent`:** the app is synchronous WSGI with zero `async def` anywhere in
`backend/` — its per-request work is SQLite reads and Jinja rendering, neither of which
benefits from gevent's cooperative sockets. gevent's only real payoff was not blocking on large
audio-file transfers, which the Apache/nginx static fragment now handles instead. Dropping it
also removes a real deploy risk: the pinned `gevent==24.2.1` has no wheel for newer Python and
fails to build from source, which is what previously forced an unpinned, undocumented install.

**Why no `GEMINI_API_KEY` on the server:** production never generates TTS or calls Gemini for
anything — `app_prod.py` serves only pre-generated audio from `frontend/static/audio/`, 404ing
if it's missing. All Gemini calls happen locally during content generation; only the resulting
audio files and DB rows get deployed. Keep the real key in your local, gitignored `.env` only.

## Sandbox notes

`ProtectSystem=strict` + `ProtectHome=read-only` make everything except
`ReadWritePaths=/opt/summra/data` read-only to the process. This is why all mutable state —
`data/database.db` and `data/summra.db` — must live under `data/`; `backend/config.py`'s
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
