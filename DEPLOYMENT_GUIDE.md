# Deployment Guide for GVM (Google Virtual Machine)

This guide covers deploying the `capacity-chatbot-service` to a Google Virtual Machine (GVM).

## 🎯 Quick Navigation

- **Kubernetes Deployment** (Recommended if your GVM uses Kubernetes): See [k8s/KUBERNETES_DEPLOYMENT.md](./k8s/KUBERNETES_DEPLOYMENT.md)
- **Docker Compose Deployment** (Simple standalone): Continue reading below

## 📋 Prerequisites

- A Google Cloud VM instance running
- Docker installed on the GVM
- Docker Compose installed on the GVM (optional, but recommended)
- Access to your GVM (SSH or console access)
- Required API keys and environment variables

## 🚀 Deployment Options

### Option 1: GitHub + Clone on GVM (Recommended for First-Time)

**Do you need GitHub?** Yes, for this approach. It's the simplest way to get your code onto the GVM.

#### Step 1: Push Code to GitHub

1. **Initialize Git** (if not already done):
```bash
cd /Users/soahamsundram/Documents/GitHub/capacity-chatbot-service
git init
git add .
git commit -m "Initial commit for deployment"
```

2. **Create a GitHub repository** (if you don't have one):
   - Go to https://github.com/new
   - Create a new repository (e.g., `capacity-chatbot-service`)
   - **Don't** initialize with README if you already have one

3. **Push to GitHub**:
```bash
git remote add origin https://github.com/YOUR_USERNAME/capacity-chatbot-service.git
git branch -M main
git push -u origin main
```

#### Step 2: Prepare Environment Variables

Create a `.env` file with your configuration. You'll need:

```bash
# Create .env file
cat > .env << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
MODEL=gpt-4o-mini

# LangSmith Configuration (optional but recommended)
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=capacity-chatbot

# KAppointment API Configuration
KAPPOINTMENT_API_BASE_URL=https://your-kappointment-api-url.com
MYKAARMA_MKID=your-mkid-here

# Required UUIDs
DEFAULT_DEPARTMENT_UUID=your-department-uuid
DEFAULT_DEALER_UUID=your-dealer-uuid

# Logging
LOG_LEVEL=INFO

# Port Configuration
BACKEND_PORT=8000
EOF
```

**⚠️ Important**: Add `.env` to `.gitignore` to avoid committing secrets:
```bash
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"
git push
```

#### Step 3: Deploy on GVM

1. **SSH into your GVM**:
```bash
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE
# Or use regular SSH if you have it configured
```

2. **Install Docker and Docker Compose** (if not already installed):
```bash
# Update package list
sudo apt-get update

# Install Docker
sudo apt-get install -y docker.io docker-compose

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

3. **Clone your repository**:
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/capacity-chatbot-service.git
cd capacity-chatbot-service
```

4. **Create .env file on GVM**:
```bash
nano .env
# Paste your environment variables (from Step 2)
# Save and exit (Ctrl+X, then Y, then Enter)
```

5. **Build and run with Docker Compose**:
```bash
# Build and start the container
docker-compose up -d --build

# Check if it's running
docker-compose ps

# View logs
docker-compose logs -f backend
```

6. **Verify the service is running**:
```bash
# Check if port 8000 is listening
curl http://localhost:8000/health
# Or check the container logs
docker-compose logs backend
```

#### Step 4: Configure Firewall (if needed)

If you need to access the service from outside the GVM:

```bash
# Allow traffic on port 8000
gcloud compute firewall-rules create allow-capacity-chatbot \
    --allow tcp:8000 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow capacity chatbot service"
```

---

### Option 2: Build Locally and Push to Google Container Registry

**Do you need GitHub?** No, but you need Docker and gcloud CLI.

#### Step 1: Build Docker Image Locally

```bash
cd /Users/soahamsundram/Documents/GitHub/capacity-chatbot-service

# Build the image
docker build -t capacity-chatbot-service:latest .
```

#### Step 2: Tag and Push to Google Container Registry

```bash
# Authenticate with Google Cloud
gcloud auth configure-docker

# Tag the image for GCR
docker tag capacity-chatbot-service:latest \
    gcr.io/YOUR_PROJECT_ID/capacity-chatbot-service:latest

# Push to GCR
docker push gcr.io/YOUR_PROJECT_ID/capacity-chatbot-service:latest
```

#### Step 3: Pull and Run on GVM

1. **SSH into your GVM**

2. **Authenticate Docker with GCR**:
```bash
gcloud auth configure-docker
```

3. **Pull the image**:
```bash
docker pull gcr.io/YOUR_PROJECT_ID/capacity-chatbot-service:latest
```

4. **Create .env file** (same as Option 1, Step 2)

5. **Run the container**:
```bash
docker run -d \
  --name capacity-chatbot-backend \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  gcr.io/YOUR_PROJECT_ID/capacity-chatbot-service:latest
```

---

### Option 3: Use Docker Compose with Pre-built Image

If you've pushed to a registry (GCR, Docker Hub, etc.):

1. **Modify docker-compose.yml** to use the image instead of building:
```yaml
services:
  backend:
    image: gcr.io/YOUR_PROJECT_ID/capacity-chatbot-service:latest
    # Remove the 'build:' section
    container_name: capacity-chatbot-backend
    # ... rest of config
```

2. **On GVM, pull and run**:
```bash
docker-compose pull
docker-compose up -d
```

---

## 🔧 Post-Deployment

### Check Service Status

```bash
# View running containers
docker ps

# View logs
docker-compose logs -f backend

# Check service health
curl http://localhost:8000/health
```

### Update the Service

If you make code changes:

1. **Push changes to GitHub**:
```bash
git add .
git commit -m "Update service"
git push
```

2. **On GVM, pull and rebuild**:
```bash
cd ~/capacity-chatbot-service
git pull
docker-compose up -d --build
```

### Stop the Service

```bash
docker-compose down
# Or if using plain Docker:
docker stop capacity-chatbot-backend
docker rm capacity-chatbot-backend
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

---

## 🐛 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Check if port is already in use
sudo netstat -tulpn | grep 8000

# Check Docker status
sudo systemctl status docker
```

### Environment variables not working

```bash
# Verify .env file exists and has correct format
cat .env

# Check if variables are being loaded
docker-compose config
```

### Permission issues

```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker

# Fix file permissions
sudo chown -R $USER:$USER ~/capacity-chatbot-service
```

### Database/SQLite issues

```bash
# Check if data directory exists and is writable
ls -la data/
chmod 755 data/

# Check SQLite database
sqlite3 data/checkpoints.sqlite ".tables"
```

---

## 📝 Quick Reference Commands

```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# View logs
docker-compose logs -f backend

# Rebuild after code changes
docker-compose up -d --build

# Restart service
docker-compose restart backend

# Check status
docker-compose ps

# Execute command in container
docker-compose exec backend bash
```

---

## 🔒 Security Best Practices

1. **Never commit .env files** - Always use `.gitignore`
2. **Use Google Secret Manager** for production secrets:
   ```bash
   # Store secrets in Secret Manager
   gcloud secrets create openai-api-key --data-file=- <<< "your-key"
   
   # Access in container
   # (Requires additional setup in docker-compose.yml)
   ```
3. **Restrict firewall rules** - Only allow necessary IPs
4. **Use HTTPS** - Set up a reverse proxy (nginx) for production
5. **Regular updates** - Keep Docker images and dependencies updated

---

## 📞 Need Help?

- Check the main [README.md](./README.md) for service details
- Review [FLOW_EXPLANATION.md](./FLOW_EXPLANATION.md) for architecture
- Check container logs: `docker-compose logs backend`

