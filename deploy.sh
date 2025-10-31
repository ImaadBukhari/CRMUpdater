#!/bin/bash
# === deploy.sh ===

set -e

PROJECT_ID="crm-updater-475321"
REGION="us-central1"
SERVICE_NAME="crm-updater-backend"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Building Docker image..."
gcloud builds submit --tag $IMAGE_NAME --project $PROJECT_ID .

echo "🔧 Cleaning previous env var definitions (if any)..."
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --remove-env-vars=PERPLEXITY_API_KEY || true

echo "🚀 Updating Cloud Run with secrets..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --platform managed \
  --set-secrets=PERPLEXITY_API_KEY=perplexity-api-key:latest,/secrets/token.json=gmail-token:latest \
  --set-env-vars=GCP_PROJECT=$PROJECT_ID

echo "✅ Deployment complete!"
echo "🔗 Service URL:"
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format='value(status.url)'