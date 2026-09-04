#!/usr/bin/env bash
# Idempotent Summra installer — standalone or cohosted.
#
# Replaces the old setup-e2micro.sh / setup-e2small.sh (deleted). Those
# assumed a `www-data`-owned /var/www/summra install; this assumes the
# isolated-service convention documented in the vault note
# 01-projects/personal-brand/vm-service-convention.md:
#   - dedicated Linux user, /opt/<service> install root
#   - systemd --user unit + linger, ProtectSystem=strict sandbox
#   - one EnvironmentFile carries every per-host value
#
# Run as root (creates the user, /opt dir, and Apache drop-in) after a
# `git clone` of this repo to a scratch location — it copies itself into
# place under /opt/summra, it does not run in-place.
#
# Usage:
#   sudo deploy/install.sh [--user summra] [--prefix ""] [--bind 127.0.0.1:5000]
#
# --prefix ""            standalone (mounted at /, default)
# --prefix /summrabook    cohosted behind Apache at this path — also
#                         installs deploy/apache/summra.conf and requires
#                         Apache with mod_proxy/mod_headers/mod_expires

set -euo pipefail

SERVICE_USER="summra"
INSTALL_ROOT="/opt/summra"
BIND="127.0.0.1:5000"
PREFIX=""
REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [ $# -gt 0 ]; do
    case "$1" in
        --user) SERVICE_USER="$2"; shift 2 ;;
        --prefix) PREFIX="$2"; shift 2 ;;
        --bind) BIND="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo deploy/install.sh ...)" >&2
    exit 1
fi

echo "== 1. Service user =="
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
    echo "created $SERVICE_USER"
else
    echo "$SERVICE_USER already exists"
fi
loginctl enable-linger "$SERVICE_USER"

echo "== 2. Install root =="
mkdir -p "$INSTALL_ROOT"
# Fresh clone, not a copy of a possibly-dirty working tree — matches the
# OpenReader precedent documented in the vault note.
if [ ! -d "$INSTALL_ROOT/.git" ]; then
    sudo -u "$SERVICE_USER" git clone "$(git -C "$REPO_SRC" remote get-url origin)" "$INSTALL_ROOT"
else
    echo "$INSTALL_ROOT already a git checkout, leaving as-is (pull separately)"
fi

echo "== 3. Data dir + venv =="
sudo -u "$SERVICE_USER" mkdir -p "$INSTALL_ROOT/data"
if [ -f "$INSTALL_ROOT/summra.db" ] && [ ! -f "$INSTALL_ROOT/data/summra.db" ]; then
    echo "migrating legacy summra.db into data/ (USER_DATABASE_PATH convention)"
    sudo -u "$SERVICE_USER" mv "$INSTALL_ROOT/summra.db" "$INSTALL_ROOT/data/summra.db"
fi
if [ ! -d "$INSTALL_ROOT/venv" ]; then
    sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_ROOT/venv"
fi
sudo -u "$SERVICE_USER" "$INSTALL_ROOT/venv/bin/pip" install -q -r "$INSTALL_ROOT/requirements-prod.txt"

echo "== 4. service.env (per-host EnvironmentFile) =="
if [ ! -f "$INSTALL_ROOT/service.env" ]; then
    cp "$INSTALL_ROOT/deploy/service.env.example" "$INSTALL_ROOT/service.env"
    if [ -n "$PREFIX" ]; then
        echo "GUNICORN_BIND=$BIND" >> "$INSTALL_ROOT/service.env"
    fi
    echo "wrote $INSTALL_ROOT/service.env — review it, it MUST stay out of git"
fi
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_ROOT/service.env"
chmod 600 "$INSTALL_ROOT/service.env"

echo "== 5. systemd --user unit =="
USER_HOME=$(getent passwd "$SERVICE_USER" | cut -d: -f6)
sudo -u "$SERVICE_USER" mkdir -p "$USER_HOME/.config/systemd/user/summra.service.d"
cp "$INSTALL_ROOT/deploy/systemd/summra.service" "$USER_HOME/.config/systemd/user/summra.service"
if [ ! -f "$USER_HOME/.config/systemd/user/summra.service.d/override.conf" ]; then
    cp "$INSTALL_ROOT/deploy/systemd/override.example.conf" \
       "$USER_HOME/.config/systemd/user/summra.service.d/override.conf"
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$USER_HOME/.config/systemd"

echo "== 6. Front-end proxy fragment =="
if [ -n "$PREFIX" ] && [ -d /etc/apache2 ]; then
    mkdir -p /etc/apache2/service-locations
    sed "s#\${SUMMRA_PREFIX}#$PREFIX#g" "$INSTALL_ROOT/deploy/apache/summra.conf" \
        > /etc/apache2/service-locations/summra.conf
    echo "installed /etc/apache2/service-locations/summra.conf"
    echo "REMINDER: the host vhost must define SUMMRA_PREFIX and IncludeOptional"
    echo "  this directory — see wordpress-vm-pages-setup.md in the vault."
elif [ -z "$PREFIX" ]; then
    echo "standalone (--prefix not set) — see deploy/nginx-summra-standalone.conf"
    echo "  and deploy/nginx-summra-common.conf for the nginx equivalent."
fi

echo "== 7. Enable + start =="
sudo -u "$SERVICE_USER" env "XDG_RUNTIME_DIR=/run/user/$(id -u "$SERVICE_USER")" \
    systemctl --user daemon-reload
sudo -u "$SERVICE_USER" env "XDG_RUNTIME_DIR=/run/user/$(id -u "$SERVICE_USER")" \
    systemctl --user enable --now summra

echo "Done. Check: sudo -u $SERVICE_USER env XDG_RUNTIME_DIR=/run/user/\$(id -u $SERVICE_USER) systemctl --user status summra"
