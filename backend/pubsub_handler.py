# backend/pubsub_handler.py
import base64
import json
from backend.gmail_service import process_gmail_message

async def handle_pubsub_message(envelope: dict):
    """Handles the Pub/Sub message, triggered by Gmail watch events."""
    message = envelope.get("message", {})
    data = message.get("data")

    if not data:
        raise ValueError("No data in Pub/Sub message")

    decoded = base64.b64decode(data).decode("utf-8")
    payload = json.loads(decoded)

    # Gmail push payload includes 'emailAddress' and 'historyId'
    history_id = payload.get("historyId")
    if not history_id:
        raise ValueError("Missing historyId in Gmail payload")

    # Delegate to gmail_service
    process_gmail_message(history_id)
