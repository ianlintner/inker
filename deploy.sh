#!/bin/bash
set -e

# Configuration
REGISTRY="gabby.azurecr.io"
IMAGE_NAME="inker"
TAG="${1:-latest}"
RESOURCE_GROUP="nekoc"
CLUSTER_NAME="bigboy"
NAMESPACE="default"

echo "🚀 Deploying Inker to Azure Kubernetes..."

# Step 1: Login to ACR
echo "📦 Logging into Azure Container Registry..."
az acr login --name gabby

# Step 2: Build the Docker image for Linux
echo "🏗️  Building Docker image for linux/amd64..."
docker buildx build --platform linux/amd64 \
  -t ${REGISTRY}/${IMAGE_NAME}:${TAG} \
  -f Dockerfile . \
  --load

# Step 3: Push to ACR
echo "⬆️  Pushing image to ACR..."
docker push ${REGISTRY}/${IMAGE_NAME}:${TAG}

# Step 4: Get AKS credentials
echo "🔑 Getting AKS credentials..."
az aks get-credentials --resource-group ${RESOURCE_GROUP} --name ${CLUSTER_NAME} --overwrite-existing

# Step 5: Create DNS A record
echo "🌐 Creating DNS A record for inker.cat-herding.net..."
INGRESS_IP=$(kubectl get svc -n aks-istio-ingress aks-istio-ingressgateway-external -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "   Ingress IP: ${INGRESS_IP}"

az network dns record-set a delete \
  --resource-group ${RESOURCE_GROUP} \
  --zone-name cat-herding.net \
  --name inker \
  --yes 2>/dev/null || true

az network dns record-set a add-record \
  --resource-group ${RESOURCE_GROUP} \
  --zone-name cat-herding.net \
  --record-set-name inker \
  --ipv4-address ${INGRESS_IP}

# Step 6: Apply Kubernetes manifests
echo "📝 Applying Kubernetes manifests..."

# Check if secret exists, if not create from template
if ! kubectl get secret inker-secrets -n ${NAMESPACE} &>/dev/null; then
  echo "⚠️  Secret 'inker-secrets' not found. Please create it manually:"
  echo "   kubectl create secret generic inker-secrets -n ${NAMESPACE} \\"
  echo "     --from-literal=OPENAI_API_KEY=your-key \\"
  echo "     --from-literal=TAVILY_API_KEY=your-key \\"
  echo "     --from-literal=YOUTUBE_API_KEY=your-key"
  echo ""
  read -p "Press Enter once you've created the secret, or Ctrl+C to cancel..."
fi

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/virtualservice.yaml

# Step 7: Wait for deployment
echo "⏳ Waiting for deployment to be ready..."
kubectl rollout status deployment/inker -n ${NAMESPACE} --timeout=300s

# Step 8: Verify
echo "✅ Deployment complete!"
echo ""
echo "🔍 Status:"
kubectl get pods -n ${NAMESPACE} -l app=inker
echo ""
echo "🌐 Access your app at: https://inker.cat-herding.net"
echo ""
echo "📊 View logs with:"
echo "   kubectl logs -n ${NAMESPACE} -l app=inker --tail=100 -f"
