# Quick Start: Deploy Summra to e2-micro (FREE tier)

This is the fastest way to deploy Summra to your existing e2-micro instance.

## Prerequisites

✅ You have an e2-micro instance running Debian 12 (bookworm) or Ubuntu 22.04
✅ You can SSH into the instance
✅ You have your Gemini API key
✅ (Optional) You have a domain name pointed to the instance

## Deploy in 5 Steps

### Step 1: Upload Code to Your Instance

From your local machine:

```bash
cd /Users/pengyao/Documents/dev/summra

# Option A: If using gcloud
gcloud compute scp --recurse . YOUR_INSTANCE_NAME:/tmp/summra --zone=YOUR_ZONE

# Option B: If using rsync
rsync -avz --exclude 'venv' --exclude '*.db' --exclude 'frontend/static/audio' \
    . YOUR_USER@YOUR_IP:/tmp/summra/

# Option C: If using scp
scp -r . YOUR_USER@YOUR_IP:/tmp/summra/
```

### Step 2: SSH into Your Instance

```bash
# Option A: If using gcloud
gcloud compute ssh YOUR_INSTANCE_NAME --zone=YOUR_ZONE

# Option B: Regular SSH
ssh YOUR_USER@YOUR_IP
```

### Step 3: Move Code and Run Setup

```bash
# Move code to proper location
sudo mkdir -p /var/www/summra
sudo chown $USER:$USER /var/www/summra
cp -r /tmp/summra/* /var/www/summra/
cd /var/www/summra

# Run the setup script
chmod +x deploy/setup-e2micro.sh
./deploy/setup-e2micro.sh
```

The script will prompt you for:
- **Domain name** (e.g., summra.yourdomain.com or just use the IP for now)
- **Gemini API key** (your Google AI API key)

Then it will automatically:
1. Install all system dependencies
2. Create Python virtual environment
3. Install Python packages (NO TTS to save memory)
4. Configure environment variables
5. Set up Nginx
6. Create systemd service
7. Enable 1GB swap file (critical for e2-micro!)
8. Configure firewall
9. Start the application

**Time: ~10 minutes**

### Step 4: Upload Your Data Files

From your local machine:

```bash
cd /Users/pengyao/Documents/dev/summra

# Upload database
gcloud compute scp data/database.db YOUR_INSTANCE:/var/www/summra/data/ --zone=YOUR_ZONE
# OR: scp data/database.db YOUR_USER@YOUR_IP:/var/www/summra/data/

# Upload pre-generated audio files (REQUIRED - no TTS on e2-micro)
gcloud compute scp --recurse frontend/static/audio/ YOUR_INSTANCE:/var/www/summra/frontend/static/ --zone=YOUR_ZONE
# OR: rsync -avz frontend/static/audio/ YOUR_USER@YOUR_IP:/var/www/summra/frontend/static/

# Upload cover images
gcloud compute scp --recurse frontend/static/covers/ YOUR_INSTANCE:/var/www/summra/frontend/static/ --zone=YOUR_ZONE
# OR: rsync -avz frontend/static/covers/ YOUR_USER@YOUR_IP:/var/www/summra/frontend/static/

# Fix permissions after upload
ssh YOUR_USER@YOUR_IP
sudo chown -R www-data:www-data /var/www/summra/data /var/www/summra/frontend/static
```

### Step 5: Set Up SSL (Optional but Recommended)

On your instance:

```bash
# Make sure your domain is pointed to this IP first!
# Check: dig summra.yourdomain.com

# Run certbot
sudo certbot --nginx -d summra.yourdomain.com

# Follow the prompts:
# - Enter your email
# - Agree to terms
# - Choose to redirect HTTP to HTTPS
```

## Done! 🎉

Your app is now live at:
- **HTTP:** `http://YOUR_DOMAIN` or `http://YOUR_IP`
- **HTTPS:** `https://YOUR_DOMAIN` (if you set up SSL)

## Verify Deployment

```bash
# Check service status
sudo systemctl status summra

# View logs
sudo journalctl -u summra -f

# Check memory usage (IMPORTANT!)
free -h

# Test health endpoint
curl http://localhost:5000/health
```

## Important Notes for e2-micro

### Memory Limitations

❗ **TTS is DISABLED** - The e2-micro only has 1GB RAM, which is not enough for TTS generation.
✅ **Swap is enabled** - 1GB swap file helps prevent out-of-memory crashes.
⚠️ **Monitor memory** - Use `free -h` or `htop` to watch memory usage.

### What This Means

- ✅ All existing audio files will play normally
- ✅ Users can browse books and read summaries
- ❌ Users CANNOT generate NEW audio files on-the-fly
- 💡 Pre-generate all audio files locally before uploading

### Expected Memory Usage

```
System:           ~250 MB
Nginx:            ~20 MB
Summra (1 worker): ~150-200 MB
Swap (if needed):  Up to 1GB
-----------------------
Total used:       ~420-470 MB / 1024 MB
Free:             ~550-600 MB ✅
```

## If Running Alongside a Blog

Total memory budget:

```
System:           ~250 MB
Nginx:            ~20 MB
Summra:           ~180 MB
Static blog:      ~50 MB    (Hugo/Jekyll)
OR Ghost blog:    ~150 MB   (might be tight!)
OR WordPress:     ~250 MB   (likely won't work)
-----------------------
Total:            ~500-650 MB ✅
```

**Recommendation:** Static site generators (Hugo, Jekyll, 11ty) work best alongside Summra on e2-micro.

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u summra -n 50

# Test manually
cd /var/www/summra
source venv/bin/activate
python backend/app_prod.py
```

### Out of Memory

```bash
# Check current usage
free -h

# Check if swap is enabled
swapon --show

# If no swap, enable it
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Nginx Error

```bash
# Test config
sudo nginx -t

# Check logs
sudo tail -50 /var/log/nginx/error.log

# Restart
sudo systemctl restart nginx
```

### Domain Not Working

```bash
# Check DNS
dig YOUR_DOMAIN

# Check if domain is in nginx config
grep server_name /etc/nginx/sites-available/summra

# Update domain
sudo nano /etc/nginx/sites-available/summra
# Change server_name line
sudo systemctl reload nginx
```

## Monitoring & Maintenance

### Check Memory Regularly

```bash
# One-time check
free -h

# Real-time monitoring
htop

# Watch memory every 2 seconds
watch -n 2 free -h
```

### View Application Logs

```bash
# Real-time logs
sudo journalctl -u summra -f

# Last 100 lines
sudo journalctl -u summra -n 100

# Today's logs
sudo journalctl -u summra --since today
```

### Restart Application

```bash
# Restart service
sudo systemctl restart summra

# Check status
sudo systemctl status summra
```

### Update Application

```bash
# On your instance
cd /var/www/summra
git pull
source venv/bin/activate
pip install -r requirements-prod.txt
sudo systemctl restart summra
```

## Cost

**e2-micro in FREE tier zones (us-central1, us-west1, us-east1):**
- Instance: **$0/month** ✅ FREE
- Storage (30GB): **$0/month** ✅ FREE
- Bandwidth (1GB): **$0/month** ✅ FREE
- Additional bandwidth: ~$0.12/GB

**Total: $0-5/month** (depending on traffic)

## Upgrade Path

If you need TTS or more memory:

```bash
# Stop instance
gcloud compute instances stop YOUR_INSTANCE --zone=YOUR_ZONE

# Upgrade to e2-small (~$13/month)
gcloud compute instances set-machine-type YOUR_INSTANCE \
    --machine-type=e2-small \
    --zone=YOUR_ZONE

# Start instance
gcloud compute instances start YOUR_INSTANCE --zone=YOUR_ZONE

# SSH back in and switch to TTS-enabled version
cd /var/www/summra
source venv/bin/activate
pip install -r requirements-prod-tts.txt

# Update systemd service
sudo cp deploy/systemd-summra-e2small.service /etc/systemd/system/summra.service
sudo systemctl daemon-reload

# Update app to use TTS-enabled version
sudo nano /etc/systemd/system/summra.service
# Change: backend.app_prod:app -> backend.app:app

sudo systemctl restart summra
```

## Getting Help

If something goes wrong:

1. **Check the logs:**
   ```bash
   sudo journalctl -u summra -n 100
   ```

2. **Check memory:**
   ```bash
   free -h
   ```

3. **Verify files uploaded:**
   ```bash
   ls -lh /var/www/summra/data/database.db
   ls -lh /var/www/summra/frontend/static/audio/ | head
   ```

4. **Test manually:**
   ```bash
   cd /var/www/summra
   source venv/bin/activate
   python backend/app_prod.py
   ```

5. **Read full docs:**
   - See `deploy/DEPLOYMENT.md` for detailed information

Good luck! 🚀
