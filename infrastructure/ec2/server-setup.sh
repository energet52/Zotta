#!/bin/bash
# =============================================================
# Zotta EC2 Server Setup Script
# Run this ON the EC2 instance after SSH-ing in.
# It installs Docker, clones the repo, and starts everything.
# =============================================================
set -e

echo "========================================"
echo "  Zotta Server Setup"
echo "========================================"

# 1. Update system
echo "[1/6] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. Install Docker
echo "[2/6] Installing Docker..."
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add current user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# 3. Install git
echo "[3/6] Installing git..."
sudo apt-get install -y git

# 4. Clone the repo
echo "[4/6] Cloning Zotta repository..."
cd /home/ubuntu
if [ -d "Zotta" ]; then
    cd Zotta && git pull && cd ..
else
    git clone https://github.com/energet52/Zotta.git
fi

# 5. Generate production secrets
echo "[5/6] Setting up production environment..."
cd /home/ubuntu/Zotta

# Generate a real secret key
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

# Create production env file from template
cp .env.production .env.production.bak 2>/dev/null || true
cat > .env.production << ENVEOF
# Generated on $(date)
POSTGRES_USER=zotta
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=zotta
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=*
CREDIT_BUREAU_PROVIDER=mock
ID_VERIFICATION_PROVIDER=mock
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=10
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
ENVEOF

echo "  Secret key and DB password generated automatically."

# 6. Build and start
echo "[6/6] Building and starting Zotta..."
sudo docker compose -f docker-compose.prod.yml up -d --build

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 15

# Seed the database
echo "Seeding database with test data..."
sudo docker compose -f docker-compose.prod.yml exec -T backend python seed.py

echo ""
echo "========================================"
echo "  Zotta is running!"
echo "========================================"
echo ""
echo "  Open in browser: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_IP')"
echo ""
echo "  Login credentials:"
echo "    Admin:      admin@zotta.tt / Admin123!"
echo "    Underwriter: sarah.uw@zotta.tt / Underwriter1!"
echo "    Applicant:  john.doe@email.com / Applicant1!"
echo ""
echo "  Useful commands:"
echo "    View logs:     cd ~/Zotta && sudo docker compose -f docker-compose.prod.yml logs -f"
echo "    Stop:          cd ~/Zotta && sudo docker compose -f docker-compose.prod.yml down"
echo "    Restart:       cd ~/Zotta && sudo docker compose -f docker-compose.prod.yml restart"
echo "    Update:        cd ~/Zotta && git pull && sudo docker compose -f docker-compose.prod.yml up -d --build"
echo ""
