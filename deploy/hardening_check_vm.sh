#!/usr/bin/env bash
# Hardening check — VM side. Read-only.
#
# Run via:
#   gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> --command="bash -s" < deploy/hardening_check_vm.sh
#
# Sections: A) SSH posture, B) listening ports, D) unattended-upgrades, E) service surface.
# Section C (GCP firewall) is in hardening_check_gcp.sh — runs locally with gcloud.
#
# Exits 0 if no FAIL; non-zero if any FAIL.

set -u  # not -e — we want to keep running through individual check failures

# ----------------------------------------------------------------------------
# When run via `bash -s < script.sh`, the lib file isn't available on the VM.
# Inline the helpers here so the script is fully self-contained.
# ----------------------------------------------------------------------------
HC_PASS=0; HC_WARN=0; HC_FAIL=0
if [ -t 1 ]; then
    HC_GREEN=$'\033[0;32m'; HC_YELLOW=$'\033[0;33m'; HC_RED=$'\033[0;31m'
    HC_BOLD=$'\033[1m'; HC_NC=$'\033[0m'
else
    HC_GREEN=""; HC_YELLOW=""; HC_RED=""; HC_BOLD=""; HC_NC=""
fi
section() { printf '\n%s=== %s ===%s\n' "$HC_BOLD" "$1" "$HC_NC"; }
pass()    { HC_PASS=$((HC_PASS+1)); printf '  %s[PASS]%s %-40s %s\n' "$HC_GREEN" "$HC_NC" "$1" "${2:-}"; }
warn()    { HC_WARN=$((HC_WARN+1)); printf '  %s[WARN]%s %-40s %s\n' "$HC_YELLOW" "$HC_NC" "$1" "${2:-}"; }
fail()    { HC_FAIL=$((HC_FAIL+1)); printf '  %s[FAIL]%s %-40s %s\n' "$HC_RED" "$HC_NC" "$1" "${2:-}"; }
info()    { printf '  [INFO] %-40s %s\n' "$1" "${2:-}"; }
summary() {
    printf '\n%sSummary:%s %s%d pass%s, %s%d warn%s, %s%d fail%s\n' \
        "$HC_BOLD" "$HC_NC" "$HC_GREEN" "$HC_PASS" "$HC_NC" \
        "$HC_YELLOW" "$HC_WARN" "$HC_NC" "$HC_RED" "$HC_FAIL" "$HC_NC"
    [ "$HC_FAIL" -gt 0 ] && return 1 || return 0
}

# ----------------------------------------------------------------------------
# A. SSH posture
# ----------------------------------------------------------------------------
section "A. SSH posture"

# `sudo sshd -T` gives the effective config (resolves Include directives).
SSHD_CONFIG="$(sudo sshd -T 2>/dev/null)"
if [ -z "$SSHD_CONFIG" ]; then
    warn "sshd -T unavailable" "falling back to /etc/ssh/sshd_config* (may miss per-host blocks)"
    SSHD_CONFIG="$(cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | tr 'A-Z' 'a-z')"
else
    SSHD_CONFIG="$(echo "$SSHD_CONFIG" | tr 'A-Z' 'a-z')"
fi

check_sshd() {
    local key="$1"
    local expected_re="$2"
    local label="$3"
    local actual
    actual="$(echo "$SSHD_CONFIG" | awk -v k="$key" '$1==k {print $2; exit}')"
    if [ -z "$actual" ]; then
        warn "$label" "key '$key' not found in sshd config"
    elif echo "$actual" | grep -qE "$expected_re"; then
        pass "$label" "$key=$actual"
    else
        fail "$label" "$key=$actual (expected match: $expected_re)"
    fi
}

check_sshd passwordauthentication           '^no$'                       "PasswordAuthentication=no"
check_sshd permitrootlogin                  '^(no|prohibit-password)$'   "PermitRootLogin no/prohibit-password"
check_sshd pubkeyauthentication             '^yes$'                      "PubkeyAuthentication=yes"
check_sshd permitemptypasswords             '^no$'                       "PermitEmptyPasswords=no"
check_sshd challengeresponseauthentication  '^no$'                       "ChallengeResponseAuth=no"
check_sshd kbdinteractiveauthentication     '^no$'                       "KbdInteractiveAuth=no"

# Authorized-keys hygiene. Walk every user with a home dir + authorized_keys.
while IFS=: read -r user _ uid _ _ home _; do
    [ "$uid" -lt 1000 ] && [ "$user" != "root" ] && continue
    ak="$home/.ssh/authorized_keys"
    [ -r "$ak" ] || continue
    count="$(grep -cvE '^\s*(#|$)' "$ak" 2>/dev/null || echo 0)"
    if [ "$count" -gt 0 ]; then
        info "authorized_keys for $user" "$count key(s) in $ak"
    fi
    # Flag deprecated ssh-rsa (the key type, NOT ssh-rsa-sha2-* signatures)
    if grep -qE '^\s*ssh-rsa\s' "$ak" 2>/dev/null; then
        warn "deprecated key type for $user" "ssh-rsa key present; prefer ssh-ed25519"
    fi
    # Flag keys with no comment (third field empty / missing)
    if awk 'NF==2 && $1 ~ /^(ssh-|ecdsa-)/' "$ak" 2>/dev/null | grep -q .; then
        warn "uncommented key for $user" "harder to audit later; add a comment"
    fi
done < /etc/passwd

# ----------------------------------------------------------------------------
# B. Listening ports
# ----------------------------------------------------------------------------
section "B. Listening TCP ports"

# Capture once; reuse below
PORTS="$(sudo ss -tlnpH 2>/dev/null || ss -tlnH)"

# Expected: 22, 80, 443 on any iface; 5000 only on 127.0.0.1
echo "$PORTS" | awk '{print $4}' | while read -r endpoint; do
    port="${endpoint##*:}"
    iface="${endpoint%:*}"
    case "$port" in
        22|80|443)
            pass "port $port open" "$endpoint"
            ;;
        5000)
            if echo "$iface" | grep -qE '^(127\.0\.0\.1|\[::1\])$'; then
                pass "port 5000 loopback-only" "$endpoint (gunicorn)"
            else
                fail "port 5000 publicly bound" "$endpoint — gunicorn should bind 127.0.0.1 only"
            fi
            ;;
        *)
            proc="$(echo "$PORTS" | awk -v ep="$endpoint" '$4==ep {for(i=6;i<=NF;i++) printf "%s ", $i; print ""}')"
            warn "unexpected port $port" "$endpoint ${proc:-?}"
            ;;
    esac
done

# ----------------------------------------------------------------------------
# D. Unattended upgrades
# ----------------------------------------------------------------------------
section "D. Unattended-upgrades"

if dpkg -s unattended-upgrades 2>/dev/null | grep -q '^Status: install ok installed'; then
    pass "package installed" "unattended-upgrades"
else
    fail "package not installed" "run: sudo apt install unattended-upgrades"
fi

AUTO_FILE="/etc/apt/apt.conf.d/20auto-upgrades"
if [ -r "$AUTO_FILE" ] && grep -q 'APT::Periodic::Unattended-Upgrade *"1"' "$AUTO_FILE"; then
    pass "auto-upgrade enabled" "$AUTO_FILE"
else
    fail "auto-upgrade NOT enabled" "set APT::Periodic::Unattended-Upgrade \"1\" in $AUTO_FILE"
fi

if systemctl is-enabled unattended-upgrades >/dev/null 2>&1; then
    pass "service enabled" "unattended-upgrades.service"
else
    warn "service not enabled" "sudo systemctl enable --now unattended-upgrades"
fi

if systemctl is-active unattended-upgrades >/dev/null 2>&1; then
    pass "service active" "unattended-upgrades.service"
else
    warn "service not active" "sudo systemctl start unattended-upgrades"
fi

LOG="/var/log/unattended-upgrades/unattended-upgrades.log"
if [ -r "$LOG" ]; then
    last="$(sudo grep -E 'Starting unattended upgrades script' "$LOG" 2>/dev/null | tail -1 | awk '{print $1, $2}')"
    if [ -n "$last" ]; then
        last_epoch="$(date -d "$last" +%s 2>/dev/null || echo 0)"
        now_epoch="$(date +%s)"
        days=$(( (now_epoch - last_epoch) / 86400 ))
        if [ "$days" -le 7 ]; then
            pass "last run within 7 days" "$last (${days}d ago)"
        else
            warn "last run >7 days ago" "$last (${days}d ago)"
        fi
    else
        warn "no run history found" "$LOG exists but has no run entries"
    fi
else
    warn "log not readable" "$LOG missing — service may not have run yet"
fi

# Pending security updates
sudo apt-get update -qq >/dev/null 2>&1
PENDING="$(apt-get -s upgrade 2>/dev/null | grep -iE '^Inst .*(security|-security)' | wc -l)"
if [ "$PENDING" -eq 0 ]; then
    pass "no pending security updates" ""
else
    warn "$PENDING pending security update(s)" "run: sudo unattended-upgrade --dry-run -v"
fi

# ----------------------------------------------------------------------------
# E. Service / app surface (informational)
# ----------------------------------------------------------------------------
section "E. Service surface (informational)"

# Try to find the service: any *.service mentioning gunicorn or summra
SVC="$(systemctl list-units --type=service --no-legend --plain --all 2>/dev/null \
    | awk '/(summra|gunicorn)/ {print $1; exit}')"
if [ -n "$SVC" ]; then
    state="$(systemctl is-active "$SVC" 2>/dev/null)"
    info "app service" "$SVC ($state)"
else
    info "app service" "no summra/gunicorn unit found — set manually if name differs"
fi

if command -v nginx >/dev/null 2>&1; then
    info "nginx version" "$(nginx -v 2>&1 | sed 's|.*/||')"
else
    warn "nginx not found" "TLS termination expected via nginx"
fi

# Check gunicorn binds loopback only (read the config file in repo)
GUN_CFG="$(find / -name 'gunicorn_config*.py' -path '*/deploy/*' 2>/dev/null | head -1)"
if [ -n "$GUN_CFG" ]; then
    bind="$(grep -E '^bind\s*=' "$GUN_CFG" 2>/dev/null | head -1)"
    if echo "$bind" | grep -qE '127\.0\.0\.1|localhost'; then
        pass "gunicorn binds loopback" "$bind"
    elif echo "$bind" | grep -qE '0\.0\.0\.0|\b\*\b'; then
        fail "gunicorn binds publicly" "$bind in $GUN_CFG"
    else
        info "gunicorn bind" "${bind:-unknown} ($GUN_CFG)"
    fi
fi

# TLS cert expiry
if command -v certbot >/dev/null 2>&1; then
    while read -r line; do
        case "$line" in
            *VALID:*)
                days_field="$(echo "$line" | grep -oE 'VALID: [0-9]+' | awk '{print $2}')"
                if [ -n "$days_field" ]; then
                    if [ "$days_field" -lt 14 ]; then
                        fail "TLS cert expires soon" "$line"
                    elif [ "$days_field" -lt 30 ]; then
                        warn "TLS cert expiring" "$line"
                    else
                        pass "TLS cert valid" "${days_field}d remaining"
                    fi
                fi
                ;;
        esac
    done < <(sudo certbot certificates 2>/dev/null | grep -E 'VALID:')
else
    info "certbot not installed" "skipping TLS expiry check"
fi

# ----------------------------------------------------------------------------
summary
