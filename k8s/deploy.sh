#!/bin/bash
# Quick Kubernetes deployment script
# Usage: ./k8s/deploy.sh [namespace]

set -e

NAMESPACE=${1:-default}
VERSION=$(grep VERSION ../version.txt | cut -d'=' -f2 | tr -d ' ')

echo "🚀 Capacity Chatbot Service - Kubernetes Deployment"
echo "===================================================="
echo "Namespace: $NAMESPACE"
echo "Version: $VERSION"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if connected to cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Error: Not connected to Kubernetes cluster"
    echo "   Please configure kubectl first"
    exit 1
fi

# Create namespace if it doesn't exist
if [ "$NAMESPACE" != "default" ]; then
    echo "📦 Creating namespace: $NAMESPACE"
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
fi

# Update deployment with current version
echo "📝 Updating deployment with version: $VERSION"
sed -i.bak "s|image:.*appointment-capacity-chatbot:.*|image: 578061096415.dkr.ecr.us-east-1.amazonaws.com/appointment-capacity-chatbot:$VERSION|" deployment.yaml
sed -i.bak "s|namespace:.*|namespace: $NAMESPACE|" *.yaml

# Check if secrets exist
echo "🔍 Checking for secrets..."
if ! kubectl get secret appointment-capacity-chatbot-secrets -n $NAMESPACE &> /dev/null; then
    echo "⚠️  Warning: Secret 'appointment-capacity-chatbot-secrets' not found!"
    echo "   Please create it first:"
    echo "   kubectl create secret generic appointment-capacity-chatbot-secrets \\"
    echo "     --from-literal=openai-api-key='...' \\"
    echo "     --from-literal=langsmith-api-key='...' \\"
    echo "     --from-literal=mykaarma-mkid='...' \\"
    echo "     --from-literal=default-department-uuid='...' \\"
    echo "     --from-literal=default-dealer-uuid='...' \\"
    echo "     -n $NAMESPACE"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if ECR secret exists
echo "🔍 Checking for ECR registry secret..."
if ! kubectl get secret ecr-registry-secret -n $NAMESPACE &> /dev/null; then
    echo "⚠️  Warning: ECR secret 'ecr-registry-secret' not found!"
    echo "   If image pull fails, create it:"
    echo "   ECR_TOKEN=\$(aws ecr get-login-password --region us-east-1)"
    echo "   kubectl create secret docker-registry ecr-registry-secret \\"
    echo "     --docker-server=578061096415.dkr.ecr.us-east-1.amazonaws.com \\"
    echo "     --docker-username=AWS \\"
    echo "     --docker-password=\$ECR_TOKEN \\"
    echo "     -n $NAMESPACE"
fi

# Apply manifests
echo ""
echo "📦 Applying Kubernetes manifests..."

echo "  → ConfigMap"
kubectl apply -f configmap.yaml -n $NAMESPACE

echo "  → PersistentVolumeClaim"
kubectl apply -f pvc.yaml -n $NAMESPACE

echo "  → Deployment"
kubectl apply -f deployment.yaml -n $NAMESPACE

echo "  → Service"
kubectl apply -f service.yaml -n $NAMESPACE

# Wait for deployment
echo ""
echo "⏳ Waiting for deployment to be ready..."
kubectl rollout status deployment/appointment-capacity-chatbot -n $NAMESPACE --timeout=300s

# Show status
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Status:"
kubectl get pods -l app=appointment-capacity-chatbot -n $NAMESPACE
echo ""
kubectl get service appointment-capacity-chatbot -n $NAMESPACE
echo ""

# Show logs
echo "📋 Recent logs (last 20 lines):"
kubectl logs -l app=appointment-capacity-chatbot -n $NAMESPACE --tail=20

echo ""
echo "🔗 Useful commands:"
echo "   View logs:    kubectl logs -f -l app=appointment-capacity-chatbot -n $NAMESPACE"
echo "   Get pods:     kubectl get pods -l app=appointment-capacity-chatbot -n $NAMESPACE"
echo "   Port forward: kubectl port-forward service/appointment-capacity-chatbot 8000:8000 -n $NAMESPACE"
echo "   Restart:      kubectl rollout restart deployment/appointment-capacity-chatbot -n $NAMESPACE"

# Restore backup files
rm -f *.bak

