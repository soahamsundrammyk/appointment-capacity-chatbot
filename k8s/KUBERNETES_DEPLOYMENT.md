# Kubernetes Deployment Guide for Capacity Chatbot Service

This guide covers deploying the `capacity-chatbot-service` to Kubernetes on your GVM, following the same pattern as your other services (like `appointment-ui-client`).

## 📋 Prerequisites

- Kubernetes cluster running on your GVM
- `kubectl` configured to access your cluster
- Docker image built and pushed to ECR (via Jenkins pipeline)
- Access to create ConfigMaps, Secrets, and Deployments in your namespace

## 🏗️ Architecture Overview

Your service will be deployed with:
- **Deployment**: Manages the pod replicas
- **Service**: Exposes the service within the cluster
- **ConfigMap**: Non-sensitive configuration
- **Secret**: Sensitive data (API keys, UUIDs)
- **PVC**: Persistent volume for SQLite database

## 🚀 Deployment Steps

### Step 1: Build and Push Docker Image

The Jenkins pipeline will handle this automatically, but you can also trigger it manually:

1. **Push your code to GitHub** (if not already done):
```bash
cd /Users/soahamsundram/Documents/GitHub/capacity-chatbot-service
git add .
git commit -m "Prepare for Kubernetes deployment"
git push origin main
```

2. **Trigger Jenkins build**:
   - Go to your Jenkins pipeline for `appointment-capacity-chatbot`
   - Build with the appropriate branch
   - Wait for the image to be pushed to ECR: `578061096415.dkr.ecr.us-east-1.amazonaws.com/appointment-capacity-chatbot:VERSION`

3. **Verify image exists**:
```bash
# If you have AWS CLI configured
aws ecr describe-images \
  --repository-name appointment-capacity-chatbot \
  --region us-east-1
```

### Step 2: Create ECR Registry Secret (if needed)

If your Kubernetes cluster needs to authenticate with ECR:

```bash
# Get ECR login token
ECR_TOKEN=$(aws ecr get-login-password --region us-east-1)

# Create Kubernetes secret
kubectl create secret docker-registry ecr-registry-secret \
  --docker-server=578061096415.dkr.ecr.us-east-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$ECR_TOKEN \
  --namespace=default
```

**Note**: This secret may already exist if other services use ECR. Check with:
```bash
kubectl get secrets | grep ecr
```

### Step 3: Create ConfigMap

Update `k8s/configmap.yaml` with your configuration, then apply:

```bash
kubectl apply -f k8s/configmap.yaml
```

**Important**: Update the `kappointment-api-base-url` to match your kappointment-api service name in Kubernetes. If it's a service, use the format: `http://service-name:port/`

### Step 4: Create Secrets

**⚠️ NEVER commit actual secrets to Git!**

Create the secret using one of these methods:

#### Option A: From Command Line (Recommended)

```bash
kubectl create secret generic capacity-chatbot-secrets \
  --from-literal=openai-api-key='your-openai-key' \
  --from-literal=langsmith-api-key='your-langsmith-key' \
  --from-literal=mykaarma-mkid='your-mkid' \
  --from-literal=default-department-uuid='your-dept-uuid' \
  --from-literal=default-dealer-uuid='your-dealer-uuid' \
  --namespace=default
```

#### Option B: From File

Create a directory with your secrets:
```bash
mkdir -p k8s/secrets
echo -n 'your-openai-key' > k8s/secrets/openai-api-key.txt
echo -n 'your-langsmith-key' > k8s/secrets/langsmith-api-key.txt
echo -n 'your-mkid' > k8s/secrets/mykid.txt
echo -n 'your-dept-uuid' > k8s/secrets/dept-uuid.txt
echo -n 'your-dealer-uuid' > k8s/secrets/dealer-uuid.txt

# Create secret
kubectl create secret generic capacity-chatbot-secrets \
  --from-file=k8s/secrets/ \
  --namespace=default

# Clean up (don't commit these files!)
rm -rf k8s/secrets
```

#### Option C: From YAML (Base64 encoded)

```bash
# Encode your secrets
echo -n 'your-openai-key' | base64
echo -n 'your-langsmith-key' | base64
# ... etc

# Create secrets.yaml with base64 values, then:
kubectl apply -f k8s/secrets.yaml
```

### Step 5: Create Persistent Volume Claim

```bash
kubectl apply -f k8s/pvc.yaml
```

This creates a 5GB persistent volume for the SQLite database. Adjust the size in `pvc.yaml` if needed.

### Step 6: Update Deployment with Correct Image Version

Edit `k8s/deployment.yaml` and update the image tag:

```yaml
image: 578061096415.dkr.ecr.us-east-1.amazonaws.com/appointment-capacity-chatbot:0.1.0
```

Replace `0.1.0` with the version from your `version.txt` file.

### Step 7: Deploy the Service

```bash
# Apply all manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Or apply all at once
kubectl apply -f k8s/
```

### Step 8: Verify Deployment

```bash
# Check deployment status
kubectl get deployment capacity-chatbot-service

# Check pods
kubectl get pods -l app=capacity-chatbot-service

# Check service
kubectl get service capacity-chatbot-service

# View logs
kubectl logs -l app=capacity-chatbot-service --tail=50 -f

# Describe pod (if issues)
kubectl describe pod -l app=capacity-chatbot-service
```

### Step 9: Test the Service

```bash
# Port forward to test locally
kubectl port-forward service/capacity-chatbot-service 8000:8000

# In another terminal, test the service
curl http://localhost:8000/health
```

## 🔄 Updating the Service

### Update Image Version

1. **Update version in `version.txt`**:
```bash
echo "VERSION=0.1.1" > version.txt
```

2. **Commit and push**:
```bash
git add version.txt
git commit -m "Bump version to 0.1.1"
git push
```

3. **Trigger Jenkins build** to build and push new image

4. **Update deployment**:
```bash
# Update the image in deployment.yaml
kubectl set image deployment/capacity-chatbot-service \
  capacity-chatbot-backend=578061096415.dkr.ecr.us-east-1.amazonaws.com/appointment-capacity-chatbot:0.1.1

# Or edit and reapply
kubectl edit deployment capacity-chatbot-service
```

5. **Watch rollout**:
```bash
kubectl rollout status deployment/capacity-chatbot-service
```

### Update Configuration

```bash
# Update ConfigMap
kubectl edit configmap capacity-chatbot-config

# Restart pods to pick up changes
kubectl rollout restart deployment/capacity-chatbot-service
```

### Update Secrets

```bash
# Update secret
kubectl edit secret capacity-chatbot-secrets

# Restart pods to pick up changes
kubectl rollout restart deployment/capacity-chatbot-service
```

## 🔍 Monitoring and Debugging

### View Logs

```bash
# All pods
kubectl logs -l app=capacity-chatbot-service --tail=100 -f

# Specific pod
kubectl logs <pod-name> -f

# Previous container (if crashed)
kubectl logs <pod-name> --previous
```

### Check Resource Usage

```bash
# Pod resource usage
kubectl top pods -l app=capacity-chatbot-service

# Node resource usage
kubectl top nodes
```

### Debug Pod Issues

```bash
# Describe pod
kubectl describe pod <pod-name>

# Execute into pod
kubectl exec -it <pod-name> -- /bin/bash

# Check environment variables
kubectl exec <pod-name> -- env | grep -E 'OPENAI|LANG|KAPPOINTMENT'
```

### Check Service Connectivity

```bash
# Get service details
kubectl get svc capacity-chatbot-service -o yaml

# Test from another pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://capacity-chatbot-service:8000/health
```

## 🛠️ Common Issues and Solutions

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -l app=capacity-chatbot-service

# Check events
kubectl get events --sort-by='.lastTimestamp' | grep capacity-chatbot

# Common issues:
# - ImagePullBackOff: Check ECR secret and image name
# - CrashLoopBackOff: Check logs for application errors
# - Pending: Check PVC and resource requests
```

### Image Pull Errors

```bash
# Verify ECR secret exists
kubectl get secret ecr-registry-secret

# If missing, recreate (see Step 2)
# If exists but still failing, check token expiration
```

### Database/PVC Issues

```bash
# Check PVC status
kubectl get pvc capacity-chatbot-pvc

# Check if PVC is bound
kubectl describe pvc capacity-chatbot-pvc

# If not bound, check storage class and available storage
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints capacity-chatbot-service

# If no endpoints, pods aren't ready
# Check pod readiness probes
kubectl describe pod <pod-name> | grep -A 5 "Readiness"
```

## 📊 Scaling

### Manual Scaling

```bash
# Scale to 3 replicas
kubectl scale deployment capacity-chatbot-service --replicas=3
```

### Auto-scaling (HPA)

Create `k8s/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: capacity-chatbot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: capacity-chatbot-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

Apply:
```bash
kubectl apply -f k8s/hpa.yaml
```

## 🔒 Security Best Practices

1. **Never commit secrets** - Use Kubernetes Secrets
2. **Use RBAC** - Limit access to secrets and deployments
3. **Rotate secrets regularly** - Update ECR tokens and API keys
4. **Use network policies** - Restrict pod-to-pod communication
5. **Enable audit logging** - Monitor access to secrets

## 📝 Quick Reference

```bash
# Deploy everything
kubectl apply -f k8s/

# Check status
kubectl get all -l app=capacity-chatbot-service

# View logs
kubectl logs -f -l app=capacity-chatbot-service

# Update deployment
kubectl rollout restart deployment/capacity-chatbot-service

# Delete everything
kubectl delete -f k8s/

# Port forward for testing
kubectl port-forward service/capacity-chatbot-service 8000:8000
```

## 🔗 Integration with Other Services

If your `kappointment-api` is also in Kubernetes, update the ConfigMap:

```yaml
kappointment-api-base-url: "http://kappointment-api-service.default.svc.cluster.local:2828/"
```

Replace `default` with your namespace if different.

## 📞 Need Help?

- Check pod logs: `kubectl logs -l app=capacity-chatbot-service`
- Check events: `kubectl get events --sort-by='.lastTimestamp'`
- Describe resources: `kubectl describe <resource-type> <resource-name>`

