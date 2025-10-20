#!/bin/bash
# === setup_pubsub.sh ===
# Creates a Pub/Sub topic, subscription, and links it to your Cloud Run endpoint.

set -e

PROJECT_ID="crm-updater"
TOPIC_NAME="gmail-topic"
SUBSCRIPTION_NAME="gmail-to-cloudrun"
SERVICE_ACCOUNT="crm-updater-sa@crm-updater-475321.iam.gserviceaccount.com"
CLOUD_RUN_URL="https://crm-updater-xyz.a.run.app/pubsub"  # update after first deploy

echo "🚀 Creating Pub/Sub topic..."
gcloud pubsub topics create $TOPIC_NAME --project=$PROJECT_ID || true

echo "🔑 Granting Pub/Sub Invoker permissions..."
gcloud run services add-iam-policy-binding crm-updater \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" \
  --project=$PROJECT_ID

echo "📬 Creating Pub/Sub push subscription..."
gcloud pubsub subscriptions create $SUBSCRIPTION_NAME \
  --topic=$TOPIC_NAME \
  --push-endpoint=$CLOUD_RUN_URL \
  --push-auth-service-account=$SERVICE_ACCOUNT \
  --project=$PROJECT_ID || true

echo "✅ Pub/Sub setup complete."
