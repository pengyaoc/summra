# Deploying Summra to e2-micro (Alongside Blog)

## Prerequisites

- GCP e2-micro instance running Ubuntu 22.04
- Your blog already running (assuming on port 3000 or similar)
- Domain name (optional, can use subdomain for Summra)

## Deployment Steps

### 1. Connect to Your VM

```bash
gcloud compute ssh your-instance-name --zone=us-central1-a
```

### 2. Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and tools
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git

# Install system dependencies for audio (for serving pre-generated files)
sudo apt install -y libsndfile1
```

### 3. Deploy Application

```bash
# Create directory
sudo mkdir -p /var/www/summra
sudo chown $USER:$USER /var/www/summra

# Clone or upload your code
cd /var/www/summra
git clone https://github.com/yourusername/summra.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install production dependencies (NO TTS library!)
pip install -r requirements-prod.txt

# Set up environment variables
cat > .env << 'EOF'
GEMINI_API_KEY=your_api_key_here
FLASK_ENV=production
DATABASE_PATH=data/database.db
EOF

# Copy your pre-generated data
# Upload database.db, audio files, and covers from local machine
# You can use: gcloud compute scp --recurse data/ your-instance:/var/www/summra/
# Or rsync

# Set permissions
sudo chown -R www-data:www-data /var/www/summra
sudo chmod -R 755 /var/www/summra
```

### 4. Configure Nginx

```bash
# Copy nginx config
sudo cp deploy/nginx-summra.conf /etc/nginx/sites-available/summra

# Update the config with your domain
sudo nano /etc/nginx/sites-available/summra
# Change: server_name summra.yourdomain.com;

# Enable site
sudo ln -s /etc/nginx/sites-available/summra /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 5. Set Up Systemd Service

```bash
# Copy service file
sudo cp deploy/systemd-summra.service /etc/systemd/system/summra.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable summra
sudo systemctl start summra

# Check status
sudo systemctl status summra
```

### 6. Monitor Memory Usage

```bash
# Check memory
free -h

# Watch memory in real-time
watch -n 2 free -h

# Check process memory
sudo systemctl status summra
```

## Memory Optimization Tips

### If Running Out of Memory:

**1. Enable Swap (Emergency Memory)**
```bash
# Create 1GB swap file
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```

**2. Reduce Workers**
```bash
# Edit service file
sudo nano /etc/systemd/system/summra.service

# Change: Environment="GUNICORN_WORKERS=1"
# Restart: sudo systemctl restart summra
```

**3. Limit Memory**
```bash
# Already set in service file:
# MemoryMax=400M
# MemoryHigh=350M

# Adjust if needed
```

## Nginx Configuration for Multiple Apps

If running blog on same server, edit `/etc/nginx/sites-available/default`:

```nginx
# Blog on main domain
server {
    listen 80 default_server;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;  # Your blog port
        # ... proxy headers
    }
}

# Summra on subdomain (uses summra.conf)
# No changes needed - already configured
```

## Uploading Pre-Generated Data

### From Local Machine:

```bash
# Upload database
gcloud compute scp data/database.db your-instance:/var/www/summra/data/ --zone=us-central1-a

# Upload audio files (may take a while - 266MB)
gcloud compute scp --recurse frontend/static/audio/ your-instance:/var/www/summra/frontend/static/ --zone=us-central1-a

# Upload covers
gcloud compute scp --recurse frontend/static/covers/ your-instance:/var/www/summra/frontend/static/ --zone=us-central1-a

# Fix permissions after upload
gcloud compute ssh your-instance --zone=us-central1-a
sudo chown -R www-data:www-data /var/www/summra/data /var/www/summra/frontend/static
```

## Maintenance

### View Logs:
```bash
# Application logs
sudo journalctl -u summra -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Restart Service:
```bash
sudo systemctl restart summra
```

### Update Code:
```bash
cd /var/www/summra
git pull
source venv/bin/activate
pip install -r requirements-prod.txt
sudo systemctl restart summra
```

## Troubleshooting

### App Won't Start:
```bash
# Check logs
sudo journalctl -u summra -n 50

# Test manually
cd /var/www/summra
source venv/bin/activate
gunicorn -c gunicorn_config.py backend.app_prod:app
```

### Out of Memory:
```bash
# Check memory
free -h

# Enable swap (see above)
# Reduce workers to 1
# Consider upgrading to e2-small
```

### High CPU:
```bash
# Check processes
htop

# If blog is heavy, consider separating servers
```

## Cost Estimate

**e2-micro (Free Tier):**
- Instance: $0/month (1 free in us-central1/us-west1/us-east1)
- Storage (30GB): $0/month (free tier includes 30GB standard persistent disk)
- Egress: $0-5/month (1GB free, then ~$0.12/GB for next 10TB)

**Total: $0-5/month** depending on traffic

## Upgrade Path

If e2-micro is too slow or runs out of memory:

```bash
# Stop instance
gcloud compute instances stop your-instance --zone=us-central1-a

# Change machine type to e2-small ($13/month)
gcloud compute instances set-machine-type your-instance \
    --machine-type=e2-small \
    --zone=us-central1-a

# Start instance
gcloud compute instances start your-instance --zone=us-central1-a

# Update worker count
sudo nano /etc/systemd/system/summra.service
# Change: Environment="GUNICORN_WORKERS=2"
# Change: MemoryMax=800M
sudo systemctl daemon-reload
sudo systemctl restart summra
```
