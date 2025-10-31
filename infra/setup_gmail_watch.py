# === setup_gmail_watch.py ===
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = "crm-updater-475321"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-topic"

def get_gmail_service():
    # Try mounted secret file first (Cloud Run)
    if os.path.exists("/secrets/token.json"):
        token_path = "/secrets/token.json"
    # Fall back to environment variable or local file
    else:
        token_path = os.getenv("TOKEN_PATH", "token.json")
    
    # Use scopes embedded in token.json (send/readonly/modify as granted)
    creds = Credentials.from_authorized_user_file(token_path)
    return build("gmail", "v1", credentials=creds)

def register_watch():
    service = get_gmail_service()
    request_body = {
        "labelIds": ["INBOX"],          # watch only Inbox
        "topicName": TOPIC_NAME,
    }

    watch = service.users().watch(userId="me", body=request_body).execute()
    print("✅ Gmail watch registered")
    print("History ID:", watch.get("historyId"))

if __name__ == "__main__":
    register_watch()
