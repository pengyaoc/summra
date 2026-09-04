# Summra Production Deployment Guide

Complete guide for deploying Summra to Google Cloud Platform. Covers both e2-micro (FREE) and e2-small (~$13/month) instance types.

> **This guide predates the isolated-service convention now used for the actual production
> deployment** (`wordpress-2-vm`, cohosted with WordPress and OpenReader — see the vault note
> `01-projects/personal-brand/vm-service-convention.md` and `wordpress-vm-pages-setup.md`).
> That deployment uses `deploy/install.sh`, a dedicated `summra` Linux user under `/opt/summra`,
> a `systemd --user` unit with `ProtectSystem=strict` sandboxing, and `gunicorn`'s `gthread`
> worker (not `gevent` — see `deploy/gunicorn_config.py`). The steps below still describe a
> valid **standalone**, single-dedicated-VM path (`www-data`, `/var/www/summra`, system-scope
> systemd unit), but if you're deploying to a box that already runs other services, use
> `deploy/install.sh --prefix /your-path` instead and read `deploy/README.md` first.

---

## Table of Contents

1. [Instance Types](#instance-types)
2. [Prerequisites](#prerequisites)
3. [Create GCP Instance](#create-gcp-instance)
4. [Static IP & DNS](#static-ip--dns)
5. [Deploy Application](#deploy-application)
6. [Upload Data Files](#upload-data-files)
7. [Nginx Configuration](#nginx-configuration)
8. [SSL Certificate Setup](#ssl-certificate-setup)
9. [SSL Auto-Renewal](#ssl-auto-renewal)
10. [Service Management](#service-management)
11. [Monitoring & Maintenance](#monitoring--maintenance)
12. [Troubleshooting](#troubleshooting)
13. [Security](#security)
14. [Backup Strategy](#backup-strategy)
15. [Cost & Upgrade Path](#cost--upgrade-path)

---

## Instance Types

| Instance | Monthly Cost | RAM | vCPU | TTS | Best For |
|----------|-------------|-----|------|-----|----------|
| **e2-micro** | FREE* | 1 GB | 0.25-2 | No | Free tier, testing |
| **e2-small** | ~$13 | 2 GB | 2 | Yes | Production |
| **e2-medium** | ~$25 | 4 GB | 2 | Yes | Heavy traffic |

*e2-micro is free in us-central1, us-west1, or us-east1 (1 instance per billing account)

### Architecture

```
Internet
    |
Nginx (Port 80/443)
    ├── Static files → <REMOTE_REPO_PATH>/frontend/static/
    ├── API requests → Gunicorn (Port 5000)
    └── TTS requests → Gunicorn (Port 5000, 5min timeout)
           |
    Gunicorn (1-2 workers)
           |
    Flask Application
           |
    ├── SQLite Database
    ├── Gemini API (summaries)
    └── TTS Model (audio generation, e2-small only)
```

---

## Prerequisites

**Local machine:**
- `gcloud` CLI installed and authenticated
- Git installed

**GCP:**
- GCP account with billing enabled
- Compute Engine API enabled

**Domain:**
- Domain name registered with DNS access

---

## Create GCP Instance

### e2-micro (FREE)

```bash
gcloud compute instances create summra \
    --machine-type=e2-micro \
    --zone=us-west1-b \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=10GB \
    --tags=http-server,https-server
```

### e2-small (Recommended)

```bash
gcloud compute instances create summra \
    --machine-type=e2-small \
    --zone=us-west1-b \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=50GB \
    --tags=http-server,https-server
```

### Configure Firewall

```bash
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTP traffic"

gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTPS traffic"
```

---

## Static IP & DNS

### Reserve Static IP

Without a static IP, the VM's IP changes on every restart, breaking DNS.

```bash
# Reserve current IP as static
gcloud compute addresses create summra-static-ip \
    --addresses=$(gcloud compute instances describe summra --zone=us-west1-b --format='get(networkInterfaces[0].accessConfigs[0].natIP)') \
    --region=us-west1

# Verify
gcloud compute addresses list
```

**Cost:** FREE while VM is running, ~$3/month while VM is stopped.

### Configure DNS

Create an A record pointing your domain to the VM's external IP:

```
Type: A
Name: @ (or subdomain)
Value: YOUR_VM_EXTERNAL_IP
TTL: 300
```

**Verify propagation (wait 5-30 minutes):**
```bash
dig +short summrabook.com
```

---

## Deploy Application

### SSH into Instance

```bash
gcloud compute ssh summra --zone=us-west1-b --project=YOUR_PROJECT_ID
```

**If SSH fails with "SSH authentication has failed":**
```bash
gcloud compute ssh summra --zone=us-west1-b --project=YOUR_PROJECT_ID --force-key-file-overwrite
```

### Upload and Run Setup

**From local machine:**
```bash
cd /path/to/summra
gcloud compute scp --recurse . summra:/tmp/summra --zone=us-west1-b
```

**On the VM:**
```bash
sudo mkdir -p <REMOTE_REPO_PATH>
sudo chown $USER:$USER <REMOTE_REPO_PATH>
cp -r /tmp/summra/* <REMOTE_REPO_PATH>/
cd <REMOTE_REPO_PATH>

# Both instance types use the same installer now — see deploy/install.sh
sudo deploy/install.sh
```

`deploy/install.sh` creates the dedicated `summra` user, `/opt/summra`, the Python venv, a
`service.env` from `deploy/service.env.example`, and a `systemd --user` unit — see
`deploy/README.md` for the full flow, including the `--prefix`/`--bind` flags for cohosting.

### Fix Permissions

```bash
sudo chown -R www-data:www-data <REMOTE_REPO_PATH>
sudo chmod -R 775 <REMOTE_REPO_PATH>/data
sudo chmod -R 775 <REMOTE_REPO_PATH>/frontend/static/audio
sudo chown -R $USER:$USER <REMOTE_REPO_PATH>/.git
```

---

## Upload Data Files

**From local machine:**
```bash
cd /path/to/summra

# Database
gcloud compute scp data/database.db summra:<REMOTE_REPO_PATH>/data/ --zone=us-west1-b

# Audio files
gcloud compute scp --recurse frontend/static/audio/ summra:<REMOTE_REPO_PATH>/frontend/static/ --zone=us-west1-b

# Cover images
gcloud compute scp --recurse frontend/static/covers/ summra:<REMOTE_REPO_PATH>/frontend/static/ --zone=us-west1-b

# Fix permissions after upload
gcloud compute ssh summra --zone=us-west1-b -- \
    "sudo chown -R www-data:www-data <REMOTE_REPO_PATH>/data <REMOTE_REPO_PATH>/frontend/static"
```

---

## Nginx Configuration

### Config Structure

- Main config: `/etc/nginx/sites-available/summra`
- Common config: `/etc/nginx/snippets/summra-common.conf`
- Enabled link: `/etc/nginx/sites-enabled/summra`

### Verify Setup

```bash
# Ensure server_name is set (required for SSL)
grep server_name /etc/nginx/sites-available/summra

# Test config syntax
sudo nginx -t

# Test locally
curl http://localhost/health
```

### If server_name is Missing

```bash
sudo nano /etc/nginx/sites-available/summra
# Add after "listen 80;":
#   server_name summrabook.com www.summrabook.com;

sudo nginx -t && sudo systemctl reload nginx
```

---

## SSL Certificate Setup

### Prerequisites Checklist

Before running certbot, verify:

- [ ] DNS A record points to VM's IP: `dig +short summrabook.com`
- [ ] HTTP works externally: `curl http://summrabook.com/health`
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Nginx config has `server_name` directive
- [ ] Ports 80 and 443 open in GCP firewall

### Install Certificate

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d summrabook.com -d www.summrabook.com
```

### Verify SSL

```bash
curl https://summrabook.com/health
sudo certbot certificates
```

---

## SSL Auto-Renewal

Let's Encrypt certificates expire every 90 days. Certbot's systemd timer handles auto-renewal.

### Verify Auto-Renewal is Active

```bash
sudo systemctl status certbot.timer
sudo systemctl list-timers | grep certbot
```

### Enable Timer (if inactive)

```bash
sudo systemctl enable --now certbot.timer
```

### Add Nginx Reload Hook

Certbot renews the cert but nginx must reload to pick up the new cert:

```bash
sudo sh -c 'echo "#!/bin/bash
systemctl reload nginx" > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh'
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

### Test Renewal

```bash
sudo certbot renew --dry-run
```

### Renewal Troubleshooting

**Problem: "Could not bind TCP port 80"**

The `summrabook.com` cert must use the **nginx authenticator**, not standalone. If renewal fails with port 80 in use:

```bash
# Renew using the nginx plugin (works while nginx is running)
sudo certbot certonly --nginx -d summrabook.com -d www.summrabook.com --force-renewal
sudo systemctl reload nginx
```

**Problem: Old/dead certificates blocking renewal**

If `certbot renew` hangs on a cert with dead DNS (e.g., an old domain that no longer points to this server):

```bash
# List all certificates
sudo certbot certificates

# Delete the dead certificate
sudo certbot delete --cert-name old-domain.example.com --non-interactive

# Retry renewal
sudo certbot renew --dry-run
```

**Problem: "Another instance of Certbot is already running"**

```bash
sudo pkill -f certbot
sudo rm -f /var/lib/letsencrypt/.certbot.lock
```

### Manual Renewal

```bash
sudo certbot renew && sudo systemctl reload nginx
```

### Check Certificate Expiry

```bash
sudo certbot certificates
# Or from any machine:
echo | openssl s_client -connect summrabook.com:443 2>/dev/null | openssl x509 -noout -dates
```

---

## Service Management

### Summra Application

```bash
sudo systemctl start summra
sudo systemctl stop summra
sudo systemctl restart summra    # After code changes
sudo systemctl status summra
sudo systemctl enable summra     # Enable on boot

# Logs
sudo journalctl -u summra -f            # Follow real-time
sudo journalctl -u summra -n 100        # Last 100 lines
sudo journalctl -u summra --since today  # Today's logs
```

### Nginx

```bash
sudo nginx -t                    # Test config
sudo systemctl reload nginx      # Reload config (no downtime)
sudo systemctl restart nginx     # Full restart
sudo systemctl status nginx

# Logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Update Application Code

```bash
cd <REMOTE_REPO_PATH>
git pull origin main
sudo systemctl restart summra
curl http://localhost:5000/health
```

---

## Monitoring & Maintenance

### Health Check

```bash
# Services running
sudo systemctl is-active summra && echo "Summra: OK" || echo "Summra: DOWN"
sudo systemctl is-active nginx && echo "Nginx: OK" || echo "Nginx: DOWN"

# Ports listening
sudo netstat -tlnp | grep -E ':(80|443|5000)\s'

# Endpoint test
curl -s http://localhost/health

# Memory
free -h

# Disk
df -h
```

### System Updates

```bash
sudo apt update && sudo apt upgrade -y
# Reboot if kernel was updated
sudo reboot
```

---

## Troubleshooting

### Service Won't Start

```bash
sudo journalctl -u summra -n 100 --no-pager

# Test manually
cd <REMOTE_REPO_PATH>
source venv/bin/activate
gunicorn -c deploy/gunicorn_config.py backend.app_prod:app
# One config for both instance sizes now — GUNICORN_WORKERS/GUNICORN_THREADS
# in service.env control concurrency, not a separate e2-small config file.
```

### 502 Bad Gateway

Nginx can't reach Gunicorn:
```bash
sudo systemctl status summra
sudo netstat -tlnp | grep 5000
sudo systemctl restart summra && sudo systemctl restart nginx
```

### Port 5000 Already in Use

```bash
sudo pkill gunicorn
sudo systemctl restart summra
```

### Permission Denied Errors

```bash
sudo chown -R www-data:www-data <REMOTE_REPO_PATH>
sudo chmod -R 775 <REMOTE_REPO_PATH>/data
```

### Out of Memory (OOM)

```bash
free -h
dmesg | grep -i oom

# Enable swap if not already
sudo fallocate -l 1G /swapfile  # 1G for e2-micro, 2G for e2-small
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### SSH Fails with "Authentication Failed"

```bash
# Force key regeneration
gcloud compute ssh INSTANCE_NAME --zone=ZONE --project=PROJECT_ID --force-key-file-overwrite

# Or try IAP tunnel
gcloud compute ssh INSTANCE_NAME --zone=ZONE --project=PROJECT_ID --tunnel-through-iap

# Or enable OS Login
gcloud compute instances add-metadata INSTANCE_NAME --zone=ZONE --metadata=enable-oslogin=TRUE
```

### Static Files Return 404

```bash
ls -la <REMOTE_REPO_PATH>/frontend/static/
grep "location /static" /etc/nginx/sites-available/summra
sudo nginx -t && sudo systemctl reload nginx
```

### DNS Not Resolving

```bash
dig +short summrabook.com
# If wrong IP, update DNS A record and wait 5-30 min
# Flush local DNS cache (Mac): sudo dscacheutil -flushcache
```

---

## Security

### Firewall

Only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) should be open. GCP firewall rules handle this.

### SSH

```bash
# Disable password auth (use keys only)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd

# Install fail2ban
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
```

### Automatic Security Updates

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## Backup Strategy

### Automated Daily Backups

```bash
cat > <REMOTE_REPO_PATH>/backup.sh << 'SCRIPT'
#!/bin/bash
BACKUP_DIR="<REMOTE_REPO_PATH>/backups"
DATE=$(date +%Y%m%d)
mkdir -p $BACKUP_DIR
cp <REMOTE_REPO_PATH>/data/database.db $BACKUP_DIR/database_$DATE.db
cp <REMOTE_REPO_PATH>/.env $BACKUP_DIR/env_$DATE
find $BACKUP_DIR -type f -mtime +7 -delete
echo "Backup complete: $DATE"
SCRIPT
chmod +x <REMOTE_REPO_PATH>/backup.sh

# Run daily at 3 AM
(crontab -l 2>/dev/null; echo "0 3 * * * <REMOTE_REPO_PATH>/backup.sh") | crontab -
```

### Off-Site Backups to GCS

```bash
gsutil mb gs://summra-backups
gsutil cp data/database.db gs://summra-backups/database_$(date +%Y%m%d).db
```

---

## Cost & Upgrade Path

### e2-micro Cost Breakdown

```
Instance:  $0/month (FREE tier)
Storage:   $0/month (30GB free)
Egress:    $0-5/month (1GB free)
Total:     $0-5/month
```

### e2-small Cost Breakdown

```
Instance:  ~$13/month
Storage:   ~$2/month (50GB)
Egress:    ~$0-5/month
Total:     ~$15-20/month
```

### Upgrading e2-micro to e2-small

```bash
# Stop instance
gcloud compute instances stop summra --zone=us-west1-b

# Change machine type
gcloud compute instances set-machine-type summra \
    --machine-type=e2-small --zone=us-west1-b

# Start instance
gcloud compute instances start summra --zone=us-west1-b

# SSH in and raise the memory ceiling for the bigger instance —
# see deploy/systemd/override.example.conf (MemoryMax lives in a drop-in,
# not the main unit, since it's the one value that's genuinely per-host)
sudo -u summra $EDITOR ~/.config/systemd/user/summra.service.d/override.conf
sudo -u summra env XDG_RUNTIME_DIR=/run/user/$(id -u summra) systemctl --user daemon-reload
sudo -u summra env XDG_RUNTIME_DIR=/run/user/$(id -u summra) systemctl --user restart summra
```

### Memory Usage

**e2-micro (1GB):**
```
System:            ~250 MB
Nginx:             ~20 MB
Summra (1 worker): ~150-200 MB
Swap (if needed):  Up to 1GB
Free:              ~550-600 MB
```

**e2-small (2GB):**
```
System:             ~300 MB
Nginx:              ~20 MB
Summra (2 workers): ~600-800 MB
TTS (temporary):    ~400-600 MB
Buffer:             ~200 MB
```

---

## Quick Reference

### Current Production Setup

- **Domain:** summrabook.com
- **VM:** <GCP_INSTANCE>
- **Zone:** us-west1-b
- **Project:** <GCP_PROJECT_ID>
- **IP:** <VM_EXTERNAL_IP>
- **Machine type:** e2-micro
- **OS:** Debian 12 (bookworm)

### SSH Command

```bash
gcloud compute ssh <GCP_INSTANCE> \
    --zone=us-west1-b \
    --project=<GCP_PROJECT_ID>
```

### Key File Locations (on VM)

```
Application:     <REMOTE_REPO_PATH>/
Database:        <REMOTE_REPO_PATH>/data/database.db
Environment:     <REMOTE_REPO_PATH>/.env
Nginx config:    /etc/nginx/sites-available/summra
Service file:    /etc/systemd/system/summra.service
SSL certs:       /etc/letsencrypt/live/summrabook.com/
Certbot logs:    /var/log/letsencrypt/letsencrypt.log
Nginx logs:      /var/log/nginx/{access,error}.log
App logs:        sudo journalctl -u summra
```

---

## Incident Log

### 2026-05-10: SSL Certificate Expired (71 days)

**Symptoms:** Site not loading. Browser errors: `ERR_CERT_AUTHORITY_INVALID`, `ERR_FAILED` for all resources. Service worker returning network error responses.

**Root cause:** Let's Encrypt certificate for `summrabook.com` expired 2026-03-01. Auto-renewal failed for two reasons:
1. The `summrabook.com` cert was configured with the **standalone authenticator** (which needs port 80 free), but nginx was already running on port 80. Error: `Could not bind TCP port 80 because it is already in use`.
2. A dead certificate for `<OLD_DEAD_DOMAIN>` (old domain, DNS deleted) was also failing renewal with `NXDOMAIN`, causing `certbot renew` to report failures and exit early.

**Fix applied:**
```bash
# 1. Force-renewed using nginx plugin (works while nginx is running)
sudo certbot certonly --nginx -d summrabook.com -d www.summrabook.com --force-renewal
sudo systemctl reload nginx

# 2. Deleted dead certificate blocking future renewals
sudo certbot delete --cert-name <OLD_DEAD_DOMAIN> --non-interactive

# 3. Added nginx reload hook (was missing — nginx wouldn't pick up renewed certs)
sudo sh -c 'printf "#!/bin/bash\nsystemctl reload nginx\n" > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh'
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# 4. Verified auto-renewal works
sudo certbot renew --dry-run  # "Congratulations, all simulated renewals succeeded"
```

**Prevention:** The certbot timer was already active (runs twice daily). The fixes above ensure future renewals succeed by using the correct authenticator and removing the blocking dead cert. The reload hook ensures nginx picks up new certs automatically.

### 2026-05-11: GCP Console SSH "Authentication Failed"

**Symptoms:** Clicking "SSH" in the GCP Console UI always fails with "SSH authentication has failed." Same failure on personal computer (not VPN-related). CLI SSH via `gcloud compute ssh` with `--force-key-file-overwrite` worked intermittently.

**Root cause:** The `google-guest-agent` service was **disabled and not running**. This agent manages SSH key injection — when you click "SSH" in the GCP Console, Google injects a temporary SSH key via instance metadata, and the guest agent picks it up and adds it to `~/.ssh/authorized_keys`. Without the agent running, the injected keys are never written, so authentication fails.

**Fix applied:**
```bash
sudo systemctl enable --now google-guest-agent
```

**Prevention:** The agent is now enabled and will start automatically on boot. If SSH from the GCP Console ever breaks again, check this first:
```bash
sudo systemctl status google-guest-agent
```

---

**Last Updated:** 2026-05-11
**Tested On:** Debian 12 (bookworm), GCP e2-micro
