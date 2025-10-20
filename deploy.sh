#!/bin/bash
# === deploy.sh ===

set -e

PROJECT_ID="crm-updater-475321"
REGION="us-central1"
SERVICE_NAME="crm-updater-backend"

echo "🚀 Building and deploying $SERVICE_NAME to Cloud Run..."

gcloud builds submit --config infra/cloudbuild.yaml --project $PROJECT_ID .

echo "✅ Deployment complete!"
echo "🔗 Service URL:"
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format='value(status.url)'
