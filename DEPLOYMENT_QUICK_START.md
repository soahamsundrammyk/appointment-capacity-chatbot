# 🚀 Quick Deployment Guide

## Do You Need GitHub?

**For Kubernetes Deployment**: **YES** - Your Jenkins pipeline builds from GitHub and pushes to ECR.

**For Docker Compose**: Optional, but recommended for easier updates.

## 🎯 Which Deployment Method?

Based on your GVM setup:

### ✅ Use Kubernetes (Recommended)
If your other services (like `appointment-ui-client`) run in Kubernetes pods, use this method.

**Quick Steps:**
1. Push code to GitHub
2. Trigger Jenkins build (builds & pushes to ECR)
3. Create secrets: `kubectl create secret generic capacity-chatbot-secrets --from-literal=...`
4. Deploy: `./k8s/deploy.sh`

**Full Guide**: See [k8s/KUBERNETES_DEPLOYMENT.md](./k8s/KUBERNETES_DEPLOYMENT.md)

### Use Docker Compose
If you're running containers directly on the GVM (not in Kubernetes).

**Quick Steps:**
1. Push code to GitHub (or copy files to GVM)
2. SSH into GVM
3. Clone repo: `git clone ...`
4. Create `.env` file
5. Deploy: `./deploy.sh`

**Full Guide**: See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

## 📋 What I've Created For You

### Kubernetes Deployment Files
- `k8s/deployment.yaml` - Kubernetes Deployment manifest
- `k8s/service.yaml` - Kubernetes Service manifest
- `k8s/configmap.yaml` - Non-sensitive configuration
- `k8s/secrets.yaml.example` - Template for secrets (DO NOT commit actual secrets!)
- `k8s/pvc.yaml` - Persistent volume for SQLite database
- `k8s/deploy.sh` - Automated deployment script
- `k8s/KUBERNETES_DEPLOYMENT.md` - Complete Kubernetes guide

### Docker Compose Files
- `docker-compose.yml` - Already exists
- `deploy.sh` - Quick deployment script
- `DEPLOYMENT_GUIDE.md` - Complete Docker Compose guide

## 🔑 Required Secrets/Environment Variables

You'll need to provide:

1. **OpenAI API Key** - `OPENAI_API_KEY`
2. **LangSmith API Key** (optional) - `LANGSMITH_API_KEY`
3. **MyKaarma MKID** - `MYKAARMA_MKID`
4. **Department UUID** - `DEFAULT_DEPARTMENT_UUID`
5. **Dealer UUID** - `DEFAULT_DEALER_UUID`

## 🚦 Next Steps

1. **Choose your deployment method** (Kubernetes or Docker Compose)
2. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Add Kubernetes deployment files"
   git push origin main
   ```
3. **Follow the appropriate guide**:
   - Kubernetes: `k8s/KUBERNETES_DEPLOYMENT.md`
   - Docker Compose: `DEPLOYMENT_GUIDE.md`
4. **Create secrets/config** with your actual values
5. **Deploy!**

## 💡 Pro Tips

- **Never commit secrets** - Use Kubernetes Secrets or `.env` files (in `.gitignore`)
- **Check your Jenkins pipeline** - Make sure it's building the right image
- **Verify ECR access** - Your Kubernetes cluster needs to pull from ECR
- **Test locally first** - Use `docker-compose up` to test before deploying to K8s

## 🆘 Need Help?

- Kubernetes issues? Check `k8s/KUBERNETES_DEPLOYMENT.md` troubleshooting section
- Docker Compose issues? Check `DEPLOYMENT_GUIDE.md` troubleshooting section
- Check pod logs: `kubectl logs -l app=capacity-chatbot-service`
- Check container logs: `docker-compose logs backend`

