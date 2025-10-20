# === setup_gmail_watch.py ===
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = "crm-updater-475321"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-topic"

def get_gmail_service():
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.modify"])
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
