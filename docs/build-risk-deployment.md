# Build Risk UI - Deployment Guide

This guide covers deploying Build Risk UI with all infrastructure components including SonarQube integration.

## Prerequisites

- Ubuntu 20.04+ or similar Linux distribution
- Minimum 8GB RAM (16GB recommended for SonarQube)
- 50GB+ disk space
- Docker and Docker Compose

## Installation Steps

### 1. Initial Setup

```bash
# SSH into your instance
ssh -i your-key.pem ubuntu@your-server-ip

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Install Docker and Docker Compose

```bash
# Install Docker
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Enable Docker to start on boot
sudo systemctl enable docker

# Log out and back in for group changes to take effect
exit
# SSH back in
```

### 3. Install Docker Compose (standalone)

```bash
# Download Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make it executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 4. Install SonarQube Scanner

```bash
# Download and install sonar-scanner
cd /opt
sudo wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip
sudo unzip sonar-scanner-cli-5.0.1.3006-linux.zip
sudo mv sonar-scanner-5.0.1.3006-linux sonar-scanner
sudo ln -s /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner

# Verify installation
sonar-scanner --version
```

### 5. Clone Repository

```bash
# Clone your project
cd ~
git clone https://github.com/yourusername/build-risk-ui.git
cd build-risk-ui
```

### 6. Configure Environment Variables

```bash
# Create .env.docker from template
cp .env.docker.example .env.docker

# Set user permissions
export APP_UID=$(id -u)
export APP_GID=$(id -g)
echo "APP_UID=$APP_UID" >> .env.docker
echo "APP_GID=$APP_GID" >> .env.docker

# Edit .env.docker with your settings
nano .env.docker
```

**Required environment variables:**

```env
# Application
APP_UID=1000
APP_GID=1000

# SonarQube (will configure after startup)
SONAR_TOKEN=
SONAR_WEBHOOK_SECRET=change-me-to-secure-random-string
SONAR_WEBHOOK_PUBLIC_URL=https://your-domain.com/api/sonar/webhook

# GitHub OAuth App
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Security
SECRET_KEY=$(openssl rand -hex 32)
```

### 7. Create Backend .env File

```bash
# Create backend .env
cd backend
cp .env.example .env

# Edit with your settings
nano .env
```

**Backend .env example:**

```env
# Database
MONGODB_URI=mongodb://mongo:27017
MONGODB_DB_NAME=buildguard

# Celery / RabbitMQ
CELERY_BROKER_URL=amqp://myuser:mypass@rabbitmq:5672//
REDIS_URL=redis://redis:6379/0

# GitHub
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# SonarQube
SONAR_HOST_URL=http://sonarqube:9000
SONAR_TOKEN=
SONAR_DEFAULT_PROJECT_KEY=build-risk-ui
SONAR_WEBHOOK_SECRET=your-webhook-secret
SONAR_WEBHOOK_PUBLIC_URL=https://your-domain.com/api/sonar/webhook

# Security
SECRET_KEY=your-secret-key-here
```

### 8. Build and Start Services

```bash
# Return to project root
cd ~/build-risk-ui

# Build all Docker images (this may take 10-15 minutes)
docker-compose build

# Start infrastructure services first
docker-compose up -d mongo rabbitmq redis sonarqube sonar-db

# Wait for SonarQube to be ready (can take 2-3 minutes)
sleep 120

# Start application services
docker-compose up -d backend frontend celery-worker celery-beat

# Start monitoring (optional)
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 9. Configure SonarQube

```bash
# Wait for SonarQube to fully start
curl -f http://localhost:9000/api/system/status
# Should return: {"status":"UP"}

# Access SonarQube UI
# Open browser: http://your-server-ip:9000
# Default credentials: admin / admin
# Change password when prompted
```

**Generate SonarQube Token:**

1. Login to SonarQube (http://localhost:9000)
2. Go to: **My Account** → **Security**
3. Generate Token with name: `build-risk-ui`
4. Copy the token

**Create Webhook:**

```bash
# Replace YOUR_TOKEN with the token from above
curl -u "YOUR_TOKEN:" -X POST \
  "http://localhost:9000/api/webhooks/create" \
  -d "name=BuildRisk Webhook" \
  -d "url=http://backend:8000/api/sonar/webhook" \
  -d "secret=your-webhook-secret"
```

**Update Environment:**

```bash
# Update .env.docker with the SonarQube token
nano .env.docker
# Set SONAR_TOKEN=your_generated_token

# Restart services to apply token
docker-compose restart backend celery-worker
```

### 10. Setup GitHub App

1. Go to GitHub Settings → Developer Settings → GitHub Apps
2. Create New GitHub App with:
   - **Homepage URL**: `https://your-domain.com`
   - **Callback URL**: `https://your-domain.com/api/auth/github/callback`
   - **Webhook URL**: `https://your-domain.com/api/webhook/github`
   - **Webhook Secret**: Same as `GITHUB_WEBHOOK_SECRET`
   - **Permissions**:
     - Repository: Read & Write (Actions, Contents, Metadata)
     - Organization: Read (Members)
   - **Subscribe to events**: Workflow run, Push

3. Generate private key and download
4. Install the app on your repositories

### 11. Verify Installation

```bash
# Check all containers are running
docker-compose ps

# Test API
curl http://localhost:8000/api/health

# Test Frontend
curl http://localhost:3000

# Check SonarQube
curl http://localhost:9000/api/system/status

# Check RabbitMQ
curl http://localhost:15672
# Login: myuser / mypass

# View application logs
docker-compose logs -f backend celery-worker
```

### 12. Production Deployment

For production deployment, you should:

1. **Use Nginx reverse proxy**:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

2. **Setup SSL with Certbot**:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

3. **Configure Firewall**:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

4. **Setup Backup**:

```bash
# Backup MongoDB
docker exec build-risk-mongo mongodump --out /data/db/backup

# Backup volumes
docker run --rm -v build-risk-ui_mongo_data:/data -v $(pwd):/backup ubuntu tar czf /backup/mongo-backup.tar.gz /data
```

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | GitHub OAuth |
| Backend API | http://localhost:8000/api | - |
| API Docs | http://localhost:8000/api/docs | - |
| SonarQube | http://localhost:9000 | admin/admin |
| RabbitMQ | http://localhost:15672 | myuser/mypass |
| Grafana | http://localhost:3001 | admin/admin |

## Troubleshooting

### SonarQube fails to start

```bash
# Increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Celery worker not processing tasks

```bash
# Check RabbitMQ connection
docker-compose logs rabbitmq

# Restart worker
docker-compose restart celery-worker

# Check worker logs
docker-compose logs -f celery-worker
```

### Permission issues with volumes

```bash
# Fix ownership
sudo chown -R $USER:$USER ./data
sudo chown -R 1000:1000 ./backend
```

## Maintenance

### Update application

```bash
cd ~/build-risk-ui
git pull
docker-compose build
docker-compose up -d
```

### View logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

### Restart services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Clean up

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Clean Docker resources
docker system prune -a
```

## Security Checklist

- [ ] Changed all default passwords
- [ ] Set strong `SECRET_KEY`
- [ ] Configured SSL/TLS with valid certificates
- [ ] Restricted Docker API access
- [ ] Setup firewall rules
- [ ] Configured GitHub App with minimal permissions
- [ ] Enabled GitHub webhook secret validation
- [ ] Set secure `SONAR_WEBHOOK_SECRET`
- [ ] Regular backup schedule configured
- [ ] Monitoring and alerting setup

## Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Review configuration files
- Verify all environment variables are set correctly
