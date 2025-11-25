# Deploying Summra to GCP e2-small (Standalone with TTS)

Complete guide for deploying Summra on a dedicated GCP e2-small instance with TTS generation enabled.

## Instance Specifications

**e2-small:**
- 2 vCPU (shared)
- 2 GB RAM
- 30-50 GB storage
- **Cost: ~$13/month** (us-central1, us-west1, or us-east1)

## Quick Start

### 1. Create GCP Instance

```bash
# Create e2-small instance
gcloud compute instances create summra \
    --machine-type=e2-small \
    --zone=us-central1-a \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-standard \
    --tags=http-server,https-server

# Configure firewall rules
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --target-tags http-server \
    --description="Allow HTTP traffic"

gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags https-server \
    --description="Allow HTTPS traffic"
```

### 2. Upload Code to Instance

```bash
# From your local machine
cd /Users/pengyao/Documents/dev/summra

# Upload entire project
gcloud compute scp --recurse . summra:/tmp/summra --zone=us-central1-a

# SSH into instance
gcloud compute ssh summra --zone=us-central1-a

# Move code to proper location
sudo mkdir -p /var/www/summra
sudo chown $USER:$USER /var/www/summra
cp -r /tmp/summra/* /var/www/summra/
cd /var/www/summra
```

### 3. Run Setup Script

```bash
# Make executable and run
chmod +x deploy/setup-e2small.sh
./deploy/setup-e2small.sh

# Follow prompts:
# - Enter your domain name (e.g., summra.example.com)
# - Enter your Gemini API key
```

The script will:
- Install all system dependencies
- Set up Python environment
- Install application dependencies
- Download TTS model
- Configure Nginx
- Set up systemd service
- Configure firewall
- Start the application

### 4. Upload Data Files

```bash
# From your local machine
cd /Users/pengyao/Documents/dev/summra

# Upload database
gcloud compute scp data/database.db summra:/var/www/summra/data/ --zone=us-central1-a

# Upload audio files (this may take a while - 266MB)
gcloud compute scp --recurse frontend/static/audio/ summra:/var/www/summra/frontend/static/ --zone=us-central1-a

# Upload cover images
gcloud compute scp --recurse frontend/static/covers/ summra:/var/www/summra/frontend/static/ --zone=us-central1-a

# Fix permissions
gcloud compute ssh summra --zone=us-central1-a
sudo chown -R www-data:www-data /var/www/summra/data /var/www/summra/frontend/static
```

### 5. Set Up Domain (Optional but Recommended)

```bash
# Point your domain to the instance IP
gcloud compute instances describe summra --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# Add A record in your DNS:
# Type: A
# Name: summra (or @)
# Value: [IP from above]
# TTL: 300

# Wait for DNS propagation (5-30 minutes)
```

### 6. Set Up SSL with Let's Encrypt

```bash
# SSH into instance
gcloud compute ssh summra --zone=us-central1-a

# Run certbot
sudo certbot --nginx -d summra.yourdomain.com

# Follow prompts:
# - Enter email address
# - Agree to terms
# - Choose to redirect HTTP to HTTPS (recommended)

# Verify auto-renewal
sudo certbot renew --dry-run

# Reload nginx
sudo systemctl reload nginx
```

### 7. Verify Deployment

```bash
# Check service status
sudo systemctl status summra

# Check logs
sudo journalctl -u summra -n 50

# Check nginx status
sudo systemctl status nginx

# Test health endpoint
curl http://localhost:5000/health

# Test from outside
curl https://summra.yourdomain.com/health
```

## Manual Setup (Alternative)

If you prefer not to use the setup script:

### Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git htop \
    certbot python3-certbot-nginx libsndfile1 ffmpeg build-essential python3.11-dev
```

### Create Virtual Environment

```bash
cd /var/www/summra
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-prod-tts.txt
```

### Pre-download TTS Model

```bash
python3 << 'EOF'
from TTS.api import TTS
tts = TTS("tts_models/en/vctk/vits")
print("TTS model ready!")
EOF
```

### Configure Environment

```bash
cat > .env << 'EOF'
GEMINI_API_KEY=your_api_key_here
FLASK_ENV=production
DATABASE_PATH=data/database.db
TTS_MODEL_NAME=tts_models/en/vctk/vits
TTS_OUTPUT_DIR=frontend/static/audio
PORT=5000
EOF
```

### Set Up Nginx

```bash
# Copy configs
sudo mkdir -p /etc/nginx/snippets
sudo cp deploy/nginx-summra-common.conf /etc/nginx/snippets/
sudo cp deploy/nginx-summra-standalone.conf /etc/nginx/sites-available/summra

# Update domain
sudo nano /etc/nginx/sites-available/summra
# Change: server_name summra.yourdomain.com;

# Enable site
sudo ln -s /etc/nginx/sites-available/summra /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

### Set Up Systemd Service

```bash
sudo cp deploy/systemd-summra-e2small.service /etc/systemd/system/summra.service
sudo systemctl daemon-reload
sudo systemctl enable summra
sudo systemctl start summra
```

## Performance Tuning

### Monitor Resource Usage

```bash
# Real-time monitoring
htop

# Memory usage
free -h

# Disk usage
df -h

# Service resource usage
systemctl status summra

# Detailed service stats
sudo systemd-cgtop
```

### Adjust Worker Count

```bash
# Edit service file
sudo nano /etc/systemd/system/summra.service

# Change worker count based on load:
# Light traffic: GUNICORN_WORKERS=2
# Medium traffic: GUNICORN_WORKERS=3 (may use more RAM)

# Restart
sudo systemctl daemon-reload
sudo systemctl restart summra
```

### Enable Swap (If Needed)

```bash
# Create 2GB swap file
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```

### Optimize TTS Performance

```bash
# Limit concurrent TTS requests in app
# Edit backend/config.py
nano backend/config.py

# Add:
# MAX_CONCURRENT_TTS = 2

# Restart
sudo systemctl restart summra
```

## Monitoring & Maintenance

### View Logs

```bash
# Application logs (real-time)
sudo journalctl -u summra -f

# Last 100 lines
sudo journalctl -u summra -n 100

# Nginx access log
sudo tail -f /var/log/nginx/access.log

# Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
# Restart application
sudo systemctl restart summra

# Restart nginx
sudo systemctl restart nginx

# Reload nginx config (no downtime)
sudo systemctl reload nginx
```

### Update Application

```bash
# Pull latest code
cd /var/www/summra
git pull origin main

# Update dependencies if needed
source venv/bin/activate
pip install -r requirements-prod-tts.txt

# Restart service
sudo systemctl restart summra
```

### Database Maintenance

```bash
# Backup database
cp data/database.db data/database.db.backup.$(date +%Y%m%d)

# Optimize database
sqlite3 data/database.db 'VACUUM;'

# Check database size
du -h data/database.db
```

### Clean Up Old Audio Files

```bash
# Find files older than 90 days
find frontend/static/audio/ -type f -mtime +90

# Delete old files
find frontend/static/audio/ -type f -mtime +90 -delete

# Check space
df -h
```

## Troubleshooting

### Application Won't Start

```bash
# Check logs
sudo journalctl -u summra -n 100

# Test manually
cd /var/www/summra
source venv/bin/activate
gunicorn -c gunicorn_config_e2small.py backend.app:app

# Check permissions
ls -la /var/www/summra
```

### TTS Generation Fails

```bash
# Check TTS model is downloaded
ls -lh ~/.local/share/tts/

# Test TTS manually
cd /var/www/summra
source venv/bin/activate
python3 << 'EOF'
from TTS.api import TTS
tts = TTS("tts_models/en/vctk/vits")
tts.tts_to_file(text="Hello world", file_path="test.wav")
print("Success!")
EOF
```

### High Memory Usage

```bash
# Check current usage
free -h

# Check what's using memory
ps aux --sort=-%mem | head -20

# Reduce workers
sudo nano /etc/systemd/system/summra.service
# Change to: GUNICORN_WORKERS=1

# Restart
sudo systemctl daemon-reload
sudo systemctl restart summra
```

### Nginx Errors

```bash
# Test config
sudo nginx -t

# Check error log
sudo tail -100 /var/log/nginx/error.log

# Restart nginx
sudo systemctl restart nginx
```

### SSL Certificate Issues

```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

## Cost Optimization

### Current Cost Breakdown

```
e2-small instance:        ~$13.00/month
50GB storage:             ~$2.00/month
Egress (first 1GB free):  ~$0.00-5.00/month
-----------------------------------------
Total:                    ~$15-20/month
```

### Reduce Costs

1. **Use preemptible instance** (~70% cheaper, but may be terminated)
2. **Reduce disk size** to 30GB (~$1.20/month savings)
3. **Use committed use discount** (1 or 3 year commitment = 30-50% off)
4. **Schedule downtime** (stop instance when not in use)

### Set Up Budget Alerts

```bash
# In GCP Console:
# 1. Go to Billing > Budgets & Alerts
# 2. Create budget: $20/month
# 3. Set alert at 50%, 90%, 100%
```

## Backup Strategy

### Automated Daily Backups

```bash
# Create backup script
cat > /var/www/summra/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/www/summra/backups"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Backup database
cp /var/www/summra/data/database.db $BACKUP_DIR/database_$DATE.db

# Backup .env
cp /var/www/summra/.env $BACKUP_DIR/env_$DATE

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup complete: $DATE"
EOF

chmod +x /var/www/summra/backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /var/www/summra/backup.sh") | crontab -
```

### Off-Site Backups to GCS

```bash
# Install gsutil
sudo apt install -y google-cloud-sdk

# Authenticate
gcloud auth login

# Create bucket
gsutil mb gs://summra-backups

# Upload backup
gsutil cp data/database.db gs://summra-backups/database_$(date +%Y%m%d).db

# Automate with cron
(crontab -l; echo "0 4 * * 0 gsutil cp /var/www/summra/data/database.db gs://summra-backups/database_\$(date +\%Y\%m\%d).db") | crontab -
```

## Security Best Practices

### Firewall Configuration

```bash
# Only allow necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Check status
sudo ufw status
```

### Secure SSH

```bash
# Disable password authentication (use keys only)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no

# Restart SSH
sudo systemctl restart sshd
```

### Keep System Updated

```bash
# Enable automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades

# Manual update
sudo apt update && sudo apt upgrade -y
```

### Monitor Failed Login Attempts

```bash
# Install fail2ban
sudo apt install -y fail2ban

# Configure
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Success Checklist

- [ ] Instance created and running
- [ ] Code uploaded to /var/www/summra
- [ ] Dependencies installed
- [ ] TTS model downloaded
- [ ] Environment variables configured
- [ ] Database and media files uploaded
- [ ] Nginx configured and running
- [ ] Systemd service enabled and running
- [ ] Domain DNS configured
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Application accessible via HTTPS
- [ ] Backups configured
- [ ] Monitoring set up
- [ ] Budget alerts configured

## Support

If you encounter issues:

1. Check application logs: `sudo journalctl -u summra -f`
2. Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify service status: `sudo systemctl status summra`
4. Test health endpoint: `curl http://localhost:5000/health`
5. Check resource usage: `htop` and `free -h`

Happy deploying! 🚀
