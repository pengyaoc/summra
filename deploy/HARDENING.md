# Hardening checks

Read-only audit scripts for the production VM. Run regularly (monthly or after any infra change). Both scripts make no changes — they only report.

## What gets checked

### `deploy/hardening_check_vm.sh` — runs on the VM

- **A. SSH posture.** `PasswordAuthentication=no`, `PermitRootLogin no/prohibit-password`, `PubkeyAuthentication=yes`, no empty passwords, no challenge-response. Flags deprecated `ssh-rsa` keys and uncommented keys in `authorized_keys`.
- **B. Listening ports.** Walks `ss -tlnp`. Expects 22, 80, 443 anywhere; 5000 on loopback only. Anything else is a WARN.
- **D. Unattended-upgrades.** Package installed, `20auto-upgrades` enables it, service enabled + active, ran within last 7 days, no pending security updates.
- **E. Service surface (informational).** Notes the gunicorn service state, nginx version, gunicorn bind address, and TLS cert expiry.

### `deploy/hardening_check_gcp.sh` — runs locally

- **C. GCP firewall.** Pulls `firewall-rules list` for the project. Any ingress rule covering `0.0.0.0/0` is classified: PASS for tcp:80/443/icmp, WARN for tcp:22 (per user policy, lenient — ssh from variable networks), WARN for anything unexpected.

## How to run

```sh
# Section C — local
bash deploy/hardening_check_gcp.sh

# Sections A, B, D, E — on the VM
gcloud compute ssh <GCP_INSTANCE> --zone=<GCP_ZONE> \
    --command="bash -s" < deploy/hardening_check_vm.sh
```

Replace `<GCP_INSTANCE>` / `<GCP_ZONE>` with the values from `.prod-metadata.local.md`. The GCP script reads `<GCP_PROJECT_ID>` from `.prod-metadata.local.md` automatically (or from `$GCP_PROJECT_ID` env var).

Exit code: **0** if no FAIL fired, **1** if any FAIL.

## How to interpret results

| Level | Meaning | Action |
|---|---|---|
| `[PASS]` | Check passed | Nothing to do |
| `[WARN]` | Suboptimal but acceptable, OR a deliberate trade-off (e.g. ssh from anywhere) | Read the detail. Fix if context has changed |
| `[FAIL]` | Real security gap | Fix before next deploy |
| `[INFO]` | Context line, no judgement | Read for situational awareness |

## Common WARN/FAIL fixes

**SSH `PasswordAuthentication=yes` (FAIL):**
```sh
sudo sed -i 's|^#*PasswordAuthentication.*|PasswordAuthentication no|' /etc/ssh/sshd_config
sudo systemctl reload sshd
```
Verify you can still ssh in a *new* session before closing the current one.

**Unattended-upgrades not installed (FAIL):**
```sh
sudo apt update && sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades  # answer "Yes" to the prompt
```

**Unattended-upgrades installed but not enabled (FAIL):**
```sh
sudo systemctl enable --now unattended-upgrades
echo 'APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";' | sudo tee /etc/apt/apt.conf.d/20auto-upgrades
```

**Pending security updates (WARN):**
```sh
sudo unattended-upgrade --dry-run -v   # preview
sudo unattended-upgrade -v             # apply
```

**Port 5000 publicly bound (FAIL):**
Edit `deploy/gunicorn_config.py` to set `bind = "127.0.0.1:5000"`, redeploy.

**Unexpected listening port (WARN):**
Investigate what process is bound. Either lock it to loopback or close it via `ufw` / GCP firewall.

**TLS cert expires < 14 days (FAIL):**
`sudo certbot renew --force-renewal && sudo systemctl reload nginx`

## When to re-run

- After any change to the GCP firewall, ssh config, or nginx config.
- After a major Debian/Ubuntu upgrade.
- Monthly cadence for routine drift detection.

## Requirements

- VM script: bash, `ss`, `dpkg`, `systemctl`, `apt-get`, `awk`. All standard on Debian/Ubuntu.
- GCP script: `gcloud` CLI authenticated to the project, `jq` for JSON parsing.

## What this does NOT check

Out of scope for these scripts (handle separately if needed):

- Application-layer bugs in the Flask app (run `bandit -r backend/` for a quick scan).
- DDoS protection (use Cloudflare in front if needed).
- Secrets in `.env` rotation cadence.
- Backup verification — checks the cert *exists*, not that backups actually restore.
- Log integrity / SIEM forwarding — none of this is configured on a single-VM personal deploy.
