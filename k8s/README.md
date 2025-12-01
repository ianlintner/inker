# Kubernetes Deployment Guide

## Quick Deploy

The easiest way to deploy Inker to the Azure Kubernetes cluster:

```bash
./deploy.sh
```

This script will:
1. Login to Azure Container Registry
2. Build the Docker image for Linux (amd64)
3. Push the image to ACR
4. Get AKS credentials
5. Create DNS A record for `inker.cat-herding.net`
6. Apply Kubernetes manifests
7. Wait for deployment to be ready

## Manual Deployment

### Prerequisites

1. Azure CLI installed and logged in
2. kubectl installed
3. Docker with buildx support
4. Access to the `nekoc` resource group and `bigboy` AKS cluster

### Step 1: Build and Push Image

```bash
# Login to ACR
az acr login --name gabby

# Build for Linux
docker buildx build --platform linux/amd64 \
  -t gabby.azurecr.io/inker:latest \
  -f Dockerfile . \
  --load

# Push to registry
docker push gabby.azurecr.io/inker:latest
```

### Step 2: Configure Kubernetes

```bash
# Get cluster credentials
az aks get-credentials --resource-group nekoc --name bigboy --overwrite-existing

# Create secrets
kubectl create secret generic inker-secrets -n default \
  --from-literal=OPENAI_API_KEY=your-openai-key \
  --from-literal=TAVILY_API_KEY=your-tavily-key \
  --from-literal=YOUTUBE_API_KEY=your-youtube-key \
  --from-literal=DATABASE_URL=postgresql://user:pass@host:5432/db \
  --from-literal=REDIS_URL=redis://host:6379/0
```

### Step 3: Create DNS Record

```bash
# Get ingress IP
INGRESS_IP=$(kubectl get svc -n aks-istio-ingress \
  aks-istio-ingressgateway-external \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Create A record
az network dns record-set a add-record \
  --resource-group nekoc \
  --zone-name cat-herding.net \
  --record-set-name inker \
  --ipv4-address ${INGRESS_IP}
```

### Step 4: Deploy to Kubernetes

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/virtualservice.yaml
```

### Step 5: Verify Deployment

```bash
# Check rollout status
kubectl rollout status deployment/inker -n default

# Check pods
kubectl get pods -n default -l app=inker

# Check logs
kubectl logs -n default -l app=inker --tail=100 -f
```

## Architecture

- **Single Container**: Combined frontend (nginx) and backend (Python/FastAPI)
- **Istio Integration**: Uses the shared `cat-herding-gateway` in `aks-istio-ingress` namespace
- **DNS**: `inker.cat-herding.net` with wildcard TLS certificate
- **Replicas**: 2 pods for high availability
- **Health Checks**: Configured for both liveness and readiness probes

## Kubernetes Resources

- `k8s/deployment.yaml` - Deployment with 2 replicas
- `k8s/service.yaml` - ClusterIP service on port 80
- `k8s/virtualservice.yaml` - Istio VirtualService for routing
- `k8s/secrets.yaml.template` - Template for secrets (DO NOT commit actual secrets)

## Access

Once deployed, the application is available at:
- **URL**: https://inker.cat-herding.net
- **Frontend**: Served by nginx on port 80
- **API**: Proxied through nginx to backend on `/api` prefix

## Troubleshooting

### Check pod status
```bash
kubectl get pods -n default -l app=inker
kubectl describe pod -n default -l app=inker
```

### View logs
```bash
# All containers
kubectl logs -n default -l app=inker --all-containers=true --tail=100

# Follow logs
kubectl logs -n default -l app=inker -f
```

### Test health endpoint
```bash
kubectl port-forward -n default svc/inker 8080:80
curl http://localhost:8080/health
```

### Check Istio routing
```bash
kubectl get virtualservice inker-virtualservice -n default -o yaml
kubectl get gateway cat-herding-gateway -n aks-istio-ingress -o yaml
```

### Restart deployment
```bash
kubectl rollout restart deployment/inker -n default
```

## Updating the Application

To deploy a new version:

```bash
# Build and push new image
./deploy.sh

# Or manually:
docker buildx build --platform linux/amd64 -t gabby.azurecr.io/inker:latest -f Dockerfile . --load
docker push gabby.azurecr.io/inker:latest

# Restart deployment to pull new image
kubectl rollout restart deployment/inker -n default
kubectl rollout status deployment/inker -n default
```
