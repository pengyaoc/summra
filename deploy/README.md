# Deployment Files for Summra

This directory contains all the necessary configuration files for deploying Summra to production.

## Files Overview

### For e2-small Deployment (Recommended)

| File | Purpose |
|------|---------|
| `DEPLOYMENT_E2SMALL.md` | **Complete deployment guide** - Start here! |
| `setup-e2small.sh` | **Automated setup script** - Run on VM |
| `requirements-prod-tts.txt` | Python dependencies with TTS |
| `gunicorn_config_e2small.py` | Gunicorn config (2 workers) |
| `systemd-summra-e2small.service` | Systemd service file |
| `nginx-summra-standalone.conf` | Main nginx config |
| `nginx-summra-common.conf` | Shared nginx config |

### For e2-micro Deployment (Budget Option)

| File | Purpose |
|------|---------|
| `DEPLOYMENT.md` | Deployment guide for e2-micro |
| `requirements-prod.txt` | Python dependencies WITHOUT TTS |
| `gunicorn_config.py` | Gunicorn config (1 worker) |
| `systemd-summra.service` | Systemd service file |
| `nginx-summra.conf` | Nginx config for e2-micro |
| `backend/app_prod.py` | Flask app with TTS disabled |

## Quick Start

### Deploying to e2-small (WITH TTS) - ~$13/month

This is the recommended approach for a production-ready deployment with full TTS support.

**Step 1: Create GCP Instance**
```bash
gcloud compute instances create summra \
    --machine-type=e2-small \
    --zone=us-central1-a \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --tags=http-server,https-server
```

**Step 2: Upload Code**
```bash
cd /Users/pengyao/Documents/dev/summra
gcloud compute scp --recurse . summra:/tmp/summra --zone=us-central1-a
```

**Step 3: SSH and Run Setup**
```bash
gcloud compute ssh summra --zone=us-central1-a
sudo mkdir -p /var/www/summra
sudo chown $USER:$USER /var/www/summra
cp -r /tmp/summra/* /var/www/summra/
cd /var/www/summra
chmod +x deploy/setup-e2small.sh
./deploy/setup-e2small.sh
```

**Step 4: Upload Data**
```bash
# From local machine
gcloud compute scp data/database.db summra:/var/www/summra/data/ --zone=us-central1-a
gcloud compute scp --recurse frontend/static/audio/ summra:/var/www/summra/frontend/static/ --zone=us-central1-a
gcloud compute scp --recurse frontend/static/covers/ summra:/var/www/summra/frontend/static/ --zone=us-central1-a
```

**Step 5: Set Up SSL**
```bash
gcloud compute ssh summra --zone=us-central1-a
sudo certbot --nginx -d summra.yourdomain.com
```

Done! Your app is live at `https://summra.yourdomain.com`

### Deploying to e2-micro (WITHOUT TTS) - FREE

For budget deployments or to run alongside a blog on the free tier.

Follow `DEPLOYMENT.md` for detailed instructions.

## Files Explained

### Configuration Files

**Gunicorn Config (`gunicorn_config_e2small.py`)**
- Production WSGI server configuration
- 2 workers for e2-small (2 GB RAM)
- Gevent async workers for better concurrency
- 5-minute timeout for TTS generation
- Automatic worker restarts to prevent memory leaks

**Nginx Config (`nginx-summra-standalone.conf` + `nginx-summra-common.conf`)**
- Reverse proxy to Gunicorn
- Static file serving (saves Flask resources)
- Rate limiting (10 req/s for API, 2 req/min for TTS)
- Gzip compression
- SSL/TLS support (after certbot setup)
- Long caching for static assets

**Systemd Service (`systemd-summra-e2small.service`)**
- Runs application as service
- Auto-restart on failure
- Memory limits (max 1.5GB for app)
- CPU limits (max 150% to leave room for system)
- Runs as www-data user for security

### Scripts

**Setup Script (`setup-e2small.sh`)**
- Automated installation of all dependencies
- Python environment setup
- TTS model download
- Nginx configuration
- Systemd service setup
- Firewall configuration
- Permissions setup

### Requirements Files

**Production with TTS (`requirements-prod-tts.txt`)**
```
Flask==3.0.0
Flask-CORS==4.0.0
google-genai>=0.1.0
python-dotenv==1.0.0
gunicorn==21.2.0
gevent==24.2.1
TTS>=0.22.0  # <-- Includes TTS
```

**Production without TTS (`requirements-prod.txt`)**
```
Flask==3.0.0
Flask-CORS==4.0.0
google-genai>=0.1.0
python-dotenv==1.0.0
gunicorn==21.2.0
gevent==24.2.1
# NO TTS library - saves ~800MB memory
```

## Architecture

```
Internet
    ↓
Nginx (Port 80/443)
    ├── Static files → /var/www/summra/frontend/static/
    ├── API requests → Gunicorn (Port 5000)
    └── TTS requests → Gunicorn (Port 5000, 5min timeout)
           ↓
    Gunicorn (2 workers)
           ↓
    Flask Application
           ↓
    ├── SQLite Database
    ├── Gemini API (summaries)
    └── TTS Model (audio generation)
```

## Resource Usage

### e2-small (Recommended)
- **CPU:** 2 vCPU (shared) - ~30-50% average, 100% during TTS
- **RAM:** 2 GB total
  - System: ~300 MB
  - Nginx: ~20 MB
  - Gunicorn (2 workers): ~600-800 MB
  - TTS generation: ~400-600 MB (temporary spike)
  - Buffer: ~200 MB
- **Disk:** 50 GB
  - OS: ~5 GB
  - Application: ~500 MB
  - Database: ~50 MB
  - Audio files: ~300 MB (grows over time)
  - TTS models: ~200 MB
  - Free space: ~44 GB

### e2-micro (Budget)
- **CPU:** 0.25-2 vCPU (burstable)
- **RAM:** 1 GB total (TIGHT!)
  - System: ~250 MB
  - Nginx: ~20 MB
  - Gunicorn (1 worker): ~150-200 MB
  - Blog: ~150-200 MB
  - Buffer: ~200 MB
- **Disk:** 30 GB

## Cost Comparison

| Instance Type | Monthly Cost | RAM | vCPU | TTS Support | Best For |
|---------------|--------------|-----|------|-------------|----------|
| **e2-small** | ~$13 | 2 GB | 2 | ✅ Yes | Production deployment |
| **e2-micro** | FREE* | 1 GB | 0.25-2 | ❌ No | Free tier, testing |
| **e2-medium** | ~$25 | 4 GB | 2 | ✅ Yes | Heavy traffic |

*e2-micro is free in us-central1, us-west1, or us-east1 (1 instance per billing account)

## Monitoring

### Check Application Status
```bash
sudo systemctl status summra
sudo journalctl -u summra -f
```

### Check Resource Usage
```bash
htop           # CPU and memory
free -h        # Memory
df -h          # Disk space
```

### Check Logs
```bash
# Application
sudo journalctl -u summra -n 100

# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Troubleshooting

### Application Won't Start
1. Check logs: `sudo journalctl -u summra -n 50`
2. Test manually: `cd /var/www/summra && source venv/bin/activate && gunicorn -c deploy/gunicorn_config_e2small.py backend.app:app`
3. Check permissions: `ls -la /var/www/summra`

### Out of Memory
1. Check usage: `free -h`
2. Enable swap: See `DEPLOYMENT_E2SMALL.md`
3. Reduce workers: `sudo nano /etc/systemd/system/summra.service`

### TTS Fails
1. Check model: `ls -lh ~/.local/share/tts/`
2. Test manually: `python3 -c "from TTS.api import TTS; TTS('tts_models/en/vctk/vits')"`

### Nginx Errors
1. Test config: `sudo nginx -t`
2. Check logs: `sudo tail -100 /var/log/nginx/error.log`

## Security

The deployment includes:
- Firewall (ufw) with only necessary ports open
- Rate limiting on API endpoints
- TTS endpoint rate limiting (prevent abuse)
- Memory and CPU limits (prevent resource exhaustion)
- Runs as www-data user (not root)
- SSL/TLS support with Let's Encrypt
- Automatic security updates (via unattended-upgrades)

## Backup

Backups are critical! The setup script includes:
- Daily automated database backups (kept 7 days)
- Optional Google Cloud Storage backups
- Easy restoration process

See `DEPLOYMENT_E2SMALL.md` for backup configuration.

## Maintenance

### Update Application
```bash
cd /var/www/summra
git pull
source venv/bin/activate
pip install -r requirements-prod-tts.txt
sudo systemctl restart summra
```

### Update System
```bash
sudo apt update
sudo apt upgrade -y
sudo systemctl restart summra  # If needed
```

### Renew SSL Certificate
```bash
sudo certbot renew
# Automatic renewal is configured via cron
```

## Support

For deployment issues:
1. Check the detailed guides: `DEPLOYMENT_E2SMALL.md` or `DEPLOYMENT.md`
2. Review logs for errors
3. Verify all steps completed successfully
4. Check the troubleshooting sections

Happy deploying! 🚀
