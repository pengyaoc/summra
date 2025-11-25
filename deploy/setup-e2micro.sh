#!/bin/bash
# Setup script for deploying Summra on e2-micro (WITHOUT TTS)
# Compatible with Debian 12 (bookworm) and Ubuntu 22.04
# Run this script on the VM after uploading your code

set -e  # Exit on error

echo "========================================="
echo "Summra Deployment Setup for e2-micro"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run as root. Run as regular user (will sudo when needed)${NC}"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
    echo -e "${GREEN}Detected OS: $OS $VER${NC}"
else
    echo -e "${YELLOW}Cannot detect OS, assuming Debian/Ubuntu${NC}"
fi

# Get domain name
read -p "Enter your domain name (e.g., summra.yourdomain.com) or press Enter to use IP: " DOMAIN
if [ -z "$DOMAIN" ]; then
    DOMAIN=$(hostname -I | awk '{print $1}')
    echo "Using IP address: $DOMAIN"
fi
read -p "Enter your Gemini API key: " GEMINI_API_KEY

echo -e "\n${GREEN}Step 1: Updating system packages${NC}"
sudo apt update
sudo apt upgrade -y

echo -e "\n${GREEN}Step 2: Installing dependencies (NO TTS to save memory)${NC}"
# Debian 12 comes with Python 3.11 by default
sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    nginx \
    git \
    htop \
    certbot \
    python3-certbot-nginx

echo -e "\n${GREEN}Step 3: Creating application directory${NC}"
sudo mkdir -p /var/www/summra
sudo chown $USER:$USER /var/www/summra

# If we're already in summra directory, copy files
if [ -f "backend/app_prod.py" ]; then
    echo "Copying application files..."
    cp -r . /var/www/summra/
else
    echo -e "${YELLOW}Application files not found. Please upload them to /var/www/summra${NC}"
fi

cd /var/www/summra

echo -e "\n${GREEN}Step 4: Creating Python virtual environment${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "\n${GREEN}Step 5: Installing Python dependencies (WITHOUT TTS)${NC}"
pip install --upgrade pip
pip install -r requirements-prod.txt

echo -e "\n${GREEN}Step 6: Setting up environment variables${NC}"
cat > .env << EOF
GEMINI_API_KEY=$GEMINI_API_KEY
FLASK_ENV=production
DATABASE_PATH=data/database.db
PORT=5000
EOF

echo -e "\n${GREEN}Step 7: Creating necessary directories${NC}"
mkdir -p data
mkdir -p frontend/static/audio
mkdir -p frontend/static/covers
mkdir -p logs

echo -e "\n${GREEN}Step 8: Setting up Nginx${NC}"
# Copy site config
sudo cp deploy/nginx-summra.conf /etc/nginx/sites-available/summra

# Update domain in config
sudo sed -i "s/summra.yourdomain.com/$DOMAIN/g" /etc/nginx/sites-available/summra

# Enable site
sudo ln -sf /etc/nginx/sites-available/summra /etc/nginx/sites-enabled/

# Remove default site if it exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

echo -e "\n${GREEN}Step 9: Setting up systemd service${NC}"
sudo cp deploy/systemd-summra.service /etc/systemd/system/summra.service

# Update paths in service file
sudo sed -i "s|/var/www/summra|$(pwd)|g" /etc/systemd/system/summra.service

# Reload systemd
sudo systemctl daemon-reload

# Set permissions
echo -e "\n${GREEN}Step 10: Setting permissions${NC}"
sudo chown -R www-data:www-data /var/www/summra
sudo chmod -R 755 /var/www/summra

# Allow current user to write to logs and data
sudo chown -R $USER:www-data /var/www/summra/logs /var/www/summra/data /var/www/summra/frontend/static
sudo chmod -R 775 /var/www/summra/logs /var/www/summra/data /var/www/summra/frontend/static

echo -e "\n${GREEN}Step 11: Setting up swap (IMPORTANT for e2-micro!)${NC}"
if [ ! -f /swapfile ]; then
    echo "Creating 1GB swap file to prevent out-of-memory issues..."
    sudo fallocate -l 1G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo -e "${GREEN}Swap enabled!${NC}"
else
    echo "Swap file already exists, skipping..."
fi

echo -e "\n${GREEN}Step 12: Setting up firewall${NC}"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
echo "y" | sudo ufw enable || true

echo -e "\n${GREEN}Step 13: Enabling and starting service${NC}"
sudo systemctl enable summra
sudo systemctl start summra

# Wait a moment for service to start
sleep 3

# Check status
sudo systemctl status summra --no-pager || true

echo -e "\n${GREEN}Step 14: Testing deployment${NC}"
sleep 2
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Application is running!${NC}"
else
    echo -e "${RED}✗ Application health check failed${NC}"
    echo "Check logs with: sudo journalctl -u summra -n 50"
fi

echo -e "\n========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "IMPORTANT: TTS generation is DISABLED to conserve memory."
echo "Make sure to upload pre-generated audio files!"
echo ""
echo "Next steps:"
echo "1. Upload your database and pre-generated media files:"
echo "   From your local machine, run:"
echo "   gcloud compute scp data/database.db YOUR_INSTANCE:/var/www/summra/data/"
echo "   gcloud compute scp --recurse frontend/static/audio/ YOUR_INSTANCE:/var/www/summra/frontend/static/"
echo "   gcloud compute scp --recurse frontend/static/covers/ YOUR_INSTANCE:/var/www/summra/frontend/static/"
echo ""
echo "2. Set up SSL (HTTPS):"
echo "   sudo certbot --nginx -d $DOMAIN"
echo ""
echo "3. Monitor the application:"
echo "   sudo systemctl status summra"
echo "   sudo journalctl -u summra -f"
echo ""
echo "4. Check memory usage (IMPORTANT for e2-micro!):"
echo "   free -h"
echo "   htop"
echo ""
echo "Your app should be accessible at: http://$DOMAIN"
echo ""
echo -e "${YELLOW}Memory usage tips:${NC}"
echo "- Keep swap enabled (already configured)"
echo "- Monitor with: free -h"
echo "- If running alongside a blog, watch total memory carefully"
echo ""
