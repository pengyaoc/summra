# Summra Production Deployment Guide (GCP e2-micro)

Complete step-by-step guide for deploying Summra to Google Cloud Platform e2-micro instance (1GB RAM, Debian 12).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial VM Setup](#initial-vm-setup)
3. [DNS Configuration](#dns-configuration)
4. [Static IP Setup](#static-ip-setup)
5. [Deployment Steps](#deployment-steps)
6. [Nginx Configuration](#nginx-configuration)
7. [SSL Certificate Setup](#ssl-certificate-setup)
8. [Service Management](#service-management)
9. [Troubleshooting](#troubleshooting)
10. [Common Issues](#common-issues)

---

## Prerequisites

### Local Machine Requirements
- Git installed
- SSH access configured
- GitHub personal access token (if using private repo)
- Access to domain DNS settings

### GCP Requirements
- GCP account with billing enabled
- e2-micro instance created (Debian 12 bookworm recommended)
- Project with Compute Engine API enabled
- gcloud CLI installed (optional, for command-line management)

### Domain Requirements
- Domain name registered
- Access to DNS management console

---

## Initial VM Setup

### 1. Create GCP e2-micro Instance

**Via GCP Console:**
1. Go to Compute Engine → VM Instances
2. Click "Create Instance"
3. Configure:
   - **Name**: `summra-instance` (or your choice)
   - **Region**: Choose closest to your users (e.g., `us-west1`)
   - **Zone**: Any zone in selected region (e.g., `us-west1-b`)
   - **Machine type**: `e2-micro` (1 vCPU, 1GB RAM)
   - **Boot disk**: Debian GNU/Linux 12 (bookworm), 10GB standard persistent disk
   - **Firewall**: Check "Allow HTTP traffic" and "Allow HTTPS traffic"
4. Click "Create"

**Via gcloud CLI:**
```bash
gcloud compute instances create summra-instance \
    --machine-type=e2-micro \
    --zone=us-west1-b \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=10GB \
    --tags=http-server,https-server
```

### 2. SSH Access

```bash
# Via gcloud
gcloud compute ssh summra-instance --zone=us-west1-b

# Or via SSH with external IP
ssh username@EXTERNAL_IP
```

---

## DNS Configuration

### Critical: DNS Must Point to Correct IP

**Problem:** If your VM has an ephemeral (temporary) IP, it changes every time the VM restarts, breaking DNS.

**Solution Options:**

#### Option A: Reserve Static IP (Recommended)

**Via GCP Console:**
1. Go to VPC Network → IP Addresses
2. Find your VM's current external IP
3. Click the three dots → "Reserve"
4. Name: `summra-static-ip`
5. Confirm reservation

**Via gcloud:**
```bash
# Reserve current IP as static
gcloud compute addresses create summra-static-ip \
    --addresses=YOUR_CURRENT_IP \
    --region=us-west1

# Detach current ephemeral IP
gcloud compute instances delete-access-config summra-instance \
    --zone=us-west1-b \
    --access-config-name="External NAT"

# Attach static IP
gcloud compute instances add-access-config summra-instance \
    --zone=us-west1-b \
    --access-config-name="External NAT" \
    --address=summra-static-ip
```

#### Option B: Dynamic DNS Updates

If you don't want to pay for static IP (~$3/month when VM is off):
- Set up a cron job to update DNS when IP changes
- Use a dynamic DNS service
- Accept that you'll need to update DNS manually after restarts

### Configure DNS A Record

Point your domain to the VM's external IP:

**Example for subdomain:**
```
Type: A
Name: summra
Value: YOUR_VM_EXTERNAL_IP (e.g., 34.82.3.27)
TTL: 300 (5 minutes for faster propagation during setup)
```

**Verify DNS propagation:**
```bash
# Check from local machine
dig +short summra.yourdomain.com
nslookup summra.yourdomain.com

# Should return your VM's IP address
```

**⚠️ CRITICAL:** Wait for DNS to propagate (5-30 minutes) before running certbot for SSL.

---

## Static IP Setup

### Why You Need a Static IP

**Problem:**
- Ephemeral IPs change when VM restarts/stops
- Breaks DNS configuration
- SSL certificates fail
- Service becomes unreachable

**Costs:**
- Static IP while VM is running: **FREE**
- Static IP while VM is stopped: **~$3/month** (to prevent this, delete static IP before stopping VM for extended periods)

### Reserve Static IP (Detailed Steps)

1. **Check current IP:**
   ```bash
   # On VM
   curl ifconfig.me

   # Or from GCP console
   gcloud compute instances describe summra-instance --zone=us-west1-b | grep natIP
   ```

2. **Reserve it:**
   - Go to VPC Network → External IP addresses
   - Find your ephemeral IP
   - Click "Type" column dropdown → "Static"
   - Enter name: `summra-static-ip`
   - Confirm

3. **Verify:**
   ```bash
   gcloud compute addresses list
   # Should show your IP as RESERVED
   ```

---

## Deployment Steps

### 1. Install Git (if not already installed)

```bash
# Update system
sudo apt update

# Install git
sudo apt install -y git

# Verify
git --version
```

### 2. Clone Repository

**For public repositories:**
```bash
cd /var/www
sudo mkdir -p summra
sudo chown $USER:$USER summra
git clone https://github.com/yourusername/summra.git summra
```

**For private repositories (requires personal access token):**

1. **Create GitHub Personal Access Token:**
   - Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (full control of private repositories)
   - Generate and copy token (you won't see it again!)

2. **Clone with token:**
   ```bash
   cd /var/www
   sudo mkdir -p summra
   sudo chown $USER:$USER summra
   git clone https://YOUR_TOKEN@github.com/yourusername/summra.git summra
   ```

**⚠️ Common Issue:** Permission denied errors
```bash
# Fix ownership
sudo chown -R $USER:$USER /var/www/summra
```

### 3. Fix Line Endings (if deploying from Windows)

**Problem:** Setup script may have Windows CRLF line endings that cause execution errors.

**Symptoms:**
```bash
-bash: ./deploy/setup-e2micro.sh: cannot execute: required file not found
```

**Fix:**
```bash
cd /var/www/summra

# Install dos2unix
sudo apt install -y dos2unix

# Convert line endings
dos2unix deploy/setup-e2micro.sh

# Make executable
chmod +x deploy/setup-e2micro.sh
```

### 4. Run Setup Script

```bash
cd /var/www/summra
./deploy/setup-e2micro.sh
```

**Script prompts for:**
- Domain name (e.g., `summra.yourdomain.com`)
- Gemini API key (for LLM summaries)

**What the script does:**
1. Detects OS (Debian 12 or Ubuntu 22.04)
2. Updates system packages
3. Installs Python, Nginx, dependencies
4. Creates virtual environment
5. Installs Python packages (without TTS to save memory)
6. Sets up systemd service
7. Configures Nginx
8. Enables 1GB swap file
9. Attempts to configure firewall (may fail - see below)
10. Starts services

**⚠️ Expected Failure: UFW Firewall**

The script tries to configure UFW firewall, which isn't installed by default on Debian:

```
sudo: ufw: command not found
```

**This is OK!** GCP uses its own firewall. Continue to next section.

### 5. Fix File Permissions

The setup script may set restrictive permissions that prevent the app from writing logs/data.

```bash
# Fix ownership to www-data (nginx user)
sudo chown -R www-data:www-data /var/www/summra

# Ensure app can write to data directories
sudo chmod -R 775 /var/www/summra/data
sudo chmod -R 775 /var/www/summra/frontend/static/audio

# Allow your user to manage git
sudo chown -R $USER:$USER /var/www/summra/.git
```

### 6. Configure GCP Firewall

**⚠️ CRITICAL:** Without this, your site won't be accessible from the internet.

**Via GCP Console (Recommended):**

1. Go to: https://console.cloud.google.com/networking/firewalls/list
2. Click "CREATE FIREWALL RULE"
3. Configure rule 1 (HTTP):
   - Name: `allow-http`
   - Targets: `All instances in the network`
   - Source IPv4 ranges: `0.0.0.0/0`
   - Protocols and ports: TCP `80`
   - Click "CREATE"

4. Click "CREATE FIREWALL RULE" again
5. Configure rule 2 (HTTPS):
   - Name: `allow-https`
   - Targets: `All instances in the network`
   - Source IPv4 ranges: `0.0.0.0/0`
   - Protocols and ports: TCP `443`
   - Click "CREATE"

**Via gcloud CLI:**

```bash
# From local machine with gcloud installed
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTP traffic"

gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTPS traffic"
```

**Verify firewall rules:**
```bash
gcloud compute firewall-rules list | grep allow-http
```

**Test connectivity:**
```bash
# From local machine
curl http://YOUR_VM_IP/health
# Should return: {"status":"healthy"}
```

---

## Nginx Configuration

### Understanding the Config Structure

Nginx config is split across multiple files:
- `/etc/nginx/nginx.conf` - Main config
- `/etc/nginx/sites-available/summra` - Summra site config
- `/etc/nginx/sites-enabled/summra` - Symlink to enable site

### Verify Nginx Setup

```bash
# Check if config exists
cat /etc/nginx/sites-available/summra

# Check if it's enabled
ls -la /etc/nginx/sites-enabled/ | grep summra

# Test config syntax
sudo nginx -t

# Check Nginx status
sudo systemctl status nginx
```

### Fix Missing server_name (Required for SSL)

**Problem:** Certbot can't install SSL certificates without `server_name` directive.

**Check current config:**
```bash
cat /etc/nginx/sites-available/summra
```

**Should contain:**
```nginx
server {
    listen 80;
    server_name summra.yourdomain.com;  # <-- MUST BE PRESENT

    # Serve static files directly
    location /static/ {
        alias /var/www/summra/frontend/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /covers/ {
        alias /var/www/summra/frontend/static/covers/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /audio/ {
        alias /var/www/summra/frontend/static/audio/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy all other requests to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**If `server_name` is missing, add it:**
```bash
sudo nano /etc/nginx/sites-available/summra
```

Add this line after `listen 80;`:
```nginx
server_name summra.yourdomain.com;
```

**Reload Nginx:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Test Nginx Locally

```bash
# Test root endpoint
curl http://localhost/

# Test API endpoint
curl http://localhost/health

# Test static files
curl -I http://localhost/static/css/style.css

# Check what's listening on port 80
sudo netstat -tlnp | grep :80
# Should show: nginx
```

### Test Nginx Externally

```bash
# From local machine
curl http://YOUR_VM_IP/
curl http://YOUR_VM_IP/health
curl http://YOUR_VM_IP/api/books
```

---

## SSL Certificate Setup

### Prerequisites Checklist

Before running certbot, verify ALL of these:

- [ ] DNS A record points to correct IP
- [ ] DNS has propagated (wait 5-30 minutes after DNS change)
- [ ] GCP firewall allows ports 80 and 443
- [ ] Nginx is running: `sudo systemctl status nginx`
- [ ] Nginx config has `server_name` directive
- [ ] HTTP works: `curl http://YOUR_DOMAIN/health` returns 200
- [ ] No other service is using port 443

### Install Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### Run Certbot

```bash
sudo certbot --nginx -d summra.yourdomain.com
```

**Prompts:**
1. Email address: `your@email.com` (for renewal reminders)
2. Agree to Terms of Service: `Y`
3. Share email with EFF: `Y` or `N` (optional)

### Successful Output

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/summra.yourdomain.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/summra.yourdomain.com/privkey.pem
This certificate expires on 2026-XX-XX.
Certbot has set up a scheduled task to automatically renew this certificate.

Deploying certificate
Successfully deployed certificate for summra.yourdomain.com to /etc/nginx/sites-enabled/summra
Congratulations! You have successfully enabled HTTPS on https://summra.yourdomain.com
```

### If Certbot Can't Install Certificate

**Error:**
```
Could not automatically find a matching server block for summra.yourdomain.com.
Set the `server_name` directive to use the Nginx installer.
```

**Fix:**
1. Edit Nginx config to add `server_name`:
   ```bash
   sudo nano /etc/nginx/sites-available/summra
   # Add: server_name summra.yourdomain.com;
   ```

2. Test and reload Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

3. Install certificate manually:
   ```bash
   sudo certbot install --cert-name summra.yourdomain.com
   ```

### Verify SSL

```bash
# From local machine
curl https://summra.yourdomain.com/health

# Check certificate expiry
sudo certbot certificates

# Test SSL configuration
curl -I https://summra.yourdomain.com
```

### Auto-Renewal

Certbot automatically sets up a systemd timer for renewal.

**Verify auto-renewal:**
```bash
# Check timer is active
sudo systemctl status certbot.timer

# Dry run renewal test
sudo certbot renew --dry-run
```

**Manual renewal (if needed):**
```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## Service Management

### Summra Application Service

The app runs as a systemd service managed by Gunicorn.

**Service file location:** `/etc/systemd/system/summra.service`

### Common Commands

```bash
# Check status
sudo systemctl status summra

# Start service
sudo systemctl start summra

# Stop service
sudo systemctl stop summra

# Restart service (after code changes)
sudo systemctl restart summra

# Enable on boot
sudo systemctl enable summra

# Disable on boot
sudo systemctl disable summra

# View logs (last 50 lines)
sudo journalctl -u summra -n 50 --no-pager

# Follow logs in real-time
sudo journalctl -u summra -f

# View logs since last boot
sudo journalctl -u summra -b
```

### Check Service Health

```bash
# Check if process is running
ps aux | grep gunicorn

# Check memory usage
sudo systemctl status summra | grep Memory

# Check port binding
sudo netstat -tlnp | grep 5000
# Should show: gunicorn listening on 127.0.0.1:5000
```

### After Code Changes

```bash
cd /var/www/summra

# Pull latest changes
git pull origin main

# Restart service to load new code
sudo systemctl restart summra

# Check it started successfully
sudo systemctl status summra

# Test endpoints
curl http://localhost:5000/health
```

### Nginx Service

```bash
# Check status
sudo systemctl status nginx

# Test config before reloading
sudo nginx -t

# Reload (for config changes)
sudo systemctl reload nginx

# Restart (if reload doesn't work)
sudo systemctl restart nginx

# View error log
sudo tail -f /var/log/nginx/error.log

# View access log
sudo tail -f /var/log/nginx/access.log
```

---

## Troubleshooting

### Service Won't Start

**1. Check logs:**
```bash
sudo journalctl -u summra -n 100 --no-pager
```

**2. Common errors:**

#### ModuleNotFoundError: No module named 'config'
**Cause:** Python can't find the config module.

**Fix:** Ensure app is started from correct directory:
```bash
cat /etc/systemd/system/summra.service | grep WorkingDirectory
# Should be: WorkingDirectory=/var/www/summra
```

#### ImportError: cannot import name 'init_db'
**Cause:** Old version of app_prod.py with incorrect imports.

**Fix:**
```bash
cd /var/www/summra
git pull origin main  # Get latest fixed version
sudo systemctl restart summra
```

#### Port already in use
**Cause:** Old gunicorn process still running.

**Fix:**
```bash
# Find and kill the process
sudo pkill gunicorn

# Or find specific PID
sudo lsof -i :5000
sudo kill -9 <PID>

# Restart service
sudo systemctl restart summra
```

#### Permission denied errors
**Cause:** Wrong file ownership/permissions.

**Fix:**
```bash
sudo chown -R www-data:www-data /var/www/summra
sudo chmod -R 775 /var/www/summra/data
sudo chmod -R 775 /var/www/summra/frontend/static/audio
```

### Nginx Issues

#### 502 Bad Gateway
**Cause:** Nginx can't reach Gunicorn backend.

**Fix:**
```bash
# Check if summra service is running
sudo systemctl status summra

# Check if port 5000 is listening
sudo netstat -tlnp | grep 5000

# Restart both services
sudo systemctl restart summra
sudo systemctl restart nginx
```

#### 504 Gateway Timeout
**Cause:** Request timeout, or backend not responding.

**Fix:**
```bash
# Increase timeout in Nginx config
sudo nano /etc/nginx/sites-available/summra

# Add these lines in location / block:
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;

# Reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

#### Static files not loading (404)
**Cause:** Wrong path in Nginx config.

**Fix:**
```bash
# Verify static files exist
ls -la /var/www/summra/frontend/static/

# Check Nginx config
cat /etc/nginx/sites-available/summra | grep static

# Should have:
# location /static/ {
#     alias /var/www/summra/frontend/static/;
# }
```

### SSL Certificate Issues

#### Certificate not renewing
**Cause:** Renewal timer not running, or DNS issues.

**Fix:**
```bash
# Check timer
sudo systemctl status certbot.timer

# Enable timer
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

#### "Could not bind to port 443"
**Cause:** Another process using port 443, or certificate already installed.

**Fix:**
```bash
# Check what's using port 443
sudo lsof -i :443

# If it's Nginx, stop it temporarily
sudo systemctl stop nginx
sudo certbot install --cert-name summra.yourdomain.com
sudo systemctl start nginx
```

### DNS Issues

#### Domain doesn't resolve
**Check DNS propagation:**
```bash
dig +short summra.yourdomain.com
nslookup summra.yourdomain.com

# Check from multiple locations
# https://www.whatsmydns.net/
```

**Wait:** DNS can take 5 minutes to 48 hours to propagate globally. Typically:
- 5-10 minutes for most DNS providers
- 30 minutes for conservative propagation
- 24-48 hours for complete worldwide propagation

#### Domain resolves to wrong IP
**Cause:** DNS not updated, or old cache.

**Fix:**
```bash
# Flush local DNS cache (on Mac)
sudo dscacheutil -flushcache

# On Linux
sudo systemd-resolve --flush-caches

# On Windows
ipconfig /flushdns

# Verify DNS from VM
dig @8.8.8.8 summra.yourdomain.com
```

### External Access Issues

#### Site works locally but not externally
**Checklist:**
```bash
# 1. Test locally (from VM)
curl http://localhost/health
# Should return: {"status":"healthy"}

# 2. Test via IP (from local machine)
curl http://YOUR_VM_IP/health
# Should return: {"status":"healthy"}

# 3. If step 2 fails, check firewall
gcloud compute firewall-rules list | grep allow-http

# 4. If firewall exists, check if Nginx is listening
sudo netstat -tlnp | grep :80

# 5. Check GCP tags on instance
gcloud compute instances describe summra-instance --zone=us-west1-b | grep tags
# Should have: http-server, https-server
```

#### Browser shows "Connection refused"
**Cause:** Firewall blocking, or Nginx not running.

**Fix:**
```bash
# Check Nginx
sudo systemctl status nginx

# Check firewall (from GCP console)
# VPC Network → Firewall → Look for allow-http and allow-https rules

# Test with curl to isolate browser issues
curl -I http://YOUR_VM_IP
```

#### Browser auto-redirects to HTTPS before certificate is installed
**Cause:** Browser HSTS cache from previous SSL site, or browser security settings.

**Fix:**
- Use incognito/private browsing mode
- Clear browser cache and HSTS settings
- Use curl for testing: `curl http://YOUR_VM_IP`
- Install SSL certificate (see SSL section)

### Memory Issues

#### Out of Memory (OOM) Killer
**Symptoms:** Service randomly stops, dmesg shows OOM messages.

**Check:**
```bash
# Check memory usage
free -h

# Check swap
swapon --show

# Check OOM logs
dmesg | grep -i oom
sudo journalctl | grep -i oom
```

**Fix:**
```bash
# Ensure swap is enabled (1GB recommended)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Reduce memory usage
# Edit service file to limit workers
sudo nano /etc/systemd/system/summra.service
# Change: workers = 1 in gunicorn_config.py

sudo systemctl daemon-reload
sudo systemctl restart summra
```

---

## Common Issues

### Issue: "Permission denied (publickey)" when SSHing

**Cause:** SSH keys not configured.

**Fix:**
```bash
# Use gcloud SSH helper
gcloud compute ssh summra-instance --zone=us-west1-b

# Or add SSH key via GCP console
# Compute Engine → Metadata → SSH Keys → Add SSH key
```

### Issue: Git operations fail with "Permission denied"

**Cause:** Wrong ownership on .git directory.

**Fix:**
```bash
sudo chown -R $USER:$USER /var/www/summra/.git
```

### Issue: "Address already in use" on port 5000

**Cause:** Old Gunicorn process still running.

**Fix:**
```bash
# Find and kill
sudo lsof -i :5000
sudo kill -9 <PID>

# Or kill all gunicorn
sudo pkill gunicorn

# Restart service
sudo systemctl restart summra
```

### Issue: Static files return 404

**Cause:** Nginx config wrong, or files don't exist.

**Fix:**
```bash
# Verify files exist
ls -la /var/www/summra/frontend/static/css/

# Check Nginx config
cat /etc/nginx/sites-available/summra | grep "location /static"

# Should have correct alias
location /static/ {
    alias /var/www/summra/frontend/static/;
}

# Reload Nginx
sudo nginx -t
sudo systemctl reload nginx
```

### Issue: API returns empty response or 500 error

**Cause:** Application error, database issue, or import error.

**Check logs:**
```bash
sudo journalctl -u summra -n 100 --no-pager
```

**Common fixes:**
```bash
# Ensure database exists
ls -la /var/www/summra/data/database.db

# Check file permissions
sudo chown -R www-data:www-data /var/www/summra/data

# Restart service
sudo systemctl restart summra

# Test locally
curl http://localhost:5000/api/books
```

### Issue: Certbot fails with connection timeout

**Causes:**
1. DNS not pointing to correct IP
2. Firewall blocking port 80
3. Nginx not running
4. Wrong server_name in Nginx config

**Debug:**
```bash
# 1. Check DNS
dig +short summra.yourdomain.com
# Must return your VM's external IP

# 2. Check firewall
gcloud compute firewall-rules list | grep allow-http

# 3. Check Nginx
sudo systemctl status nginx
curl http://localhost/.well-known/acme-challenge/test

# 4. Check server_name
cat /etc/nginx/sites-available/summra | grep server_name
# Must match your domain exactly
```

### Issue: VM IP changed after restart

**Cause:** Using ephemeral (temporary) IP instead of static IP.

**Fix:** See [Static IP Setup](#static-ip-setup) section above.

**Quick workaround:**
1. Note new IP: `curl ifconfig.me`
2. Update DNS A record to new IP
3. Wait for propagation (5-30 min)
4. Renew SSL: `sudo certbot renew --force-renewal`

**Permanent fix:** Reserve a static IP.

### Issue: Service won't start after VM reboot

**Cause:** Service not enabled on boot.

**Fix:**
```bash
# Enable service
sudo systemctl enable summra
sudo systemctl enable nginx

# Start now
sudo systemctl start summra
sudo systemctl start nginx
```

### Issue: Database locked or permission denied

**Cause:** Wrong ownership or multiple processes accessing DB.

**Fix:**
```bash
# Stop service
sudo systemctl stop summra

# Fix ownership
sudo chown www-data:www-data /var/www/summra/data/database.db

# Fix permissions
sudo chmod 664 /var/www/summra/data/database.db

# Ensure directory is writable
sudo chmod 775 /var/www/summra/data

# Start service
sudo systemctl start summra
```

---

## Performance Monitoring

### Check Resource Usage

```bash
# CPU and memory
top
htop  # More user-friendly (install with: sudo apt install htop)

# Disk usage
df -h
du -sh /var/www/summra/*

# Memory details
free -h
sudo systemctl status summra | grep Memory

# Network connections
sudo netstat -tlnp
```

### Monitor Logs

```bash
# Follow all logs
sudo journalctl -f

# Follow summra logs
sudo journalctl -u summra -f

# Follow nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check for errors
sudo journalctl -u summra -p err
```

### Service Health Check

```bash
# Quick health check script
#!/bin/bash
echo "=== Summra Health Check ==="
echo ""
echo "1. Summra Service:"
sudo systemctl is-active summra && echo "✓ Running" || echo "✗ Not running"
echo ""
echo "2. Nginx Service:"
sudo systemctl is-active nginx && echo "✓ Running" || echo "✗ Not running"
echo ""
echo "3. Port 5000 (Gunicorn):"
sudo netstat -tlnp | grep :5000 && echo "✓ Listening" || echo "✗ Not listening"
echo ""
echo "4. Port 80 (HTTP):"
sudo netstat -tlnp | grep :80 && echo "✓ Listening" || echo "✗ Not listening"
echo ""
echo "5. Port 443 (HTTPS):"
sudo netstat -tlnp | grep :443 && echo "✓ Listening" || echo "✗ Not listening"
echo ""
echo "6. HTTP Endpoint:"
curl -s http://localhost/health && echo " ✓" || echo "✗ Failed"
echo ""
echo "7. Memory Usage:"
free -h | grep Mem
echo ""
echo "=== End Health Check ==="
```

---

## Maintenance

### Update Application Code

```bash
cd /var/www/summra

# Pull latest changes
git pull origin main

# Restart service
sudo systemctl restart summra

# Verify
curl http://localhost:5000/health
```

### Update System Packages

```bash
# Update package list
sudo apt update

# Upgrade packages
sudo apt upgrade -y

# Reboot if kernel was updated
sudo reboot
```

### Backup Important Files

```bash
# Backup database
sudo cp /var/www/summra/data/database.db /var/www/summra/data/database.db.backup-$(date +%Y%m%d)

# Backup nginx config
sudo cp /etc/nginx/sites-available/summra /var/www/summra/deploy/nginx-summra.conf.backup

# Backup SSL certificates (before renewal)
sudo cp -r /etc/letsencrypt /root/letsencrypt-backup-$(date +%Y%m%d)
```

### Certificate Renewal

Automatic renewal happens via systemd timer, but you can manually renew:

```bash
# Check expiry
sudo certbot certificates

# Renew all certificates
sudo certbot renew

# Reload nginx
sudo systemctl reload nginx
```

---

## Security Recommendations

### 1. Firewall

- Only allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- Use GCP firewall rules to restrict source IPs if possible
- Consider using Cloud Armor for DDoS protection

### 2. SSH

- Use SSH keys instead of passwords
- Disable root login
- Use fail2ban to block brute force attempts

### 3. Application

- Keep dependencies updated
- Use environment variables for secrets (never commit `.env`)
- Regularly backup database
- Monitor logs for suspicious activity

### 4. SSL

- Use strong ciphers (Let's Encrypt defaults are good)
- Enable HSTS (already configured in Nginx)
- Monitor certificate expiry

---

## Summary Checklist

**Before Deployment:**
- [ ] GCP e2-micro instance created
- [ ] Static IP reserved
- [ ] DNS A record configured
- [ ] Domain propagated (verify with `dig`)

**During Deployment:**
- [ ] Git repository cloned
- [ ] Line endings fixed (if needed)
- [ ] Setup script run successfully
- [ ] File permissions fixed
- [ ] GCP firewall configured (ports 80, 443)
- [ ] Nginx config has `server_name`

**After Deployment:**
- [ ] HTTP works: `curl http://YOUR_DOMAIN/health`
- [ ] SSL certificate installed
- [ ] HTTPS works: `curl https://YOUR_DOMAIN/health`
- [ ] Service enabled on boot
- [ ] Auto-renewal configured

**Final Verification:**
- [ ] Visit site in browser: `https://your domain.com`
- [ ] Check service status: `sudo systemctl status summra`
- [ ] Check logs for errors: `sudo journalctl -u summra -n 50`
- [ ] Verify memory usage: `free -h`
- [ ] Test all endpoints (/, /api/books, /health)

---

## Support and Resources

### Logs Locations

- Application: `sudo journalctl -u summra`
- Nginx access: `/var/log/nginx/access.log`
- Nginx error: `/var/log/nginx/error.log`
- Certbot: `/var/log/letsencrypt/letsencrypt.log`
- System: `sudo journalctl`

### Useful Commands Reference

```bash
# Service management
sudo systemctl {start|stop|restart|status|enable|disable} summra
sudo systemctl {start|stop|restart|status|reload} nginx

# Logs
sudo journalctl -u summra -f  # Follow logs
sudo journalctl -u summra -n 100  # Last 100 lines
sudo journalctl -u summra --since "1 hour ago"

# Testing
curl http://localhost:5000/health  # Local test
curl http://YOUR_IP/health  # External test
curl https://YOUR_DOMAIN/health  # SSL test

# Debugging
sudo netstat -tlnp  # Show listening ports
sudo lsof -i :5000  # Show what's using port 5000
ps aux | grep gunicorn  # Show gunicorn processes
sudo nginx -t  # Test nginx config
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-25
**Tested On:** Debian 12 (bookworm), GCP e2-micro
