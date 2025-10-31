# backend/gmail_service.py
import os
import re
import base64
import smtplib
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

from .drive_service import upload_attachment_to_drive
from .crm_service import upload_to_affinity

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "application/vnd.ms-powerpoint",  # .ppt
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
}

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://developers.google.com/oauthplayground"  # replace if needed
EMAIL_NOTIFY = "imaad@wyldvc.com"

def get_gmail_service():
    """Build a Gmail API client from stored credentials."""
    # Try mounted secret file first (Cloud Run)
    if os.path.exists("/secrets/token.json"):
        token_path = "/secrets/token.json"
    # Fall back to environment variable (local development)
    else:
        token_path = os.getenv("TOKEN_PATH", "token.json")
    
    # If still not found, try Secret Manager as last resort
    if not os.path.exists(token_path):
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv("GCP_PROJECT", "crm-updater-475321")
            secret_name = f"projects/{project_id}/secrets/gmail-token/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            token_data = response.payload.data.decode("UTF-8")
            
            # Write to temp file
            with open("/tmp/token.json", "w") as f:
                f.write(token_data)
            token_path = "/tmp/token.json"
        except Exception as e:
            raise FileNotFoundError(f"Could not load token.json: {e}")
    
    creds = Credentials.from_authorized_user_file(token_path)
    return build("gmail", "v1", credentials=creds)

def process_gmail_message(history_id):
    service = get_gmail_service()
    results = service.users().messages().list(userId="me", maxResults=1).execute()
    messages = results.get("messages", [])
    if not messages:
        return

    msg_id = messages[0]["id"]
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})
    body = ""
    drive_links = []

    # --- Recursive part extraction ---
    def extract_parts(payload):
        """Recursively traverse Gmail parts and yield attachments + body text."""
        nonlocal body
        if not payload:
            return
        mime_type = payload.get("mimeType")
        filename = payload.get("filename")
        body_data = payload.get("body", {})

        # Capture text body
        if mime_type == "text/plain" and "data" in body_data:
            data = body_data["data"]
            body += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        # Capture attachments (only valid MIME types)
        elif filename and mime_type in ALLOWED_MIME_TYPES and "attachmentId" in body_data:
            att_id = body_data["attachmentId"]
            att = service.users().messages().attachments().get(
                userId="me", messageId=msg_id, id=att_id
            ).execute()
            yield filename, att["data"], mime_type

        # Recurse if multipart
        for part in payload.get("parts", []):
            yield from extract_parts(part)

    # --- Collect attachments ---
    attachments = list(extract_parts(payload))

    # --- Upload valid files ---
    for filename, file_data_b64, mime_type in attachments:
        try:
            link = upload_attachment_to_drive(filename, file_data_b64, mime_type)
            drive_links.append(link)
            print(f"✅ Uploaded {filename}: {link}")
        except Exception as e:
            send_error_email(f"Drive upload failed for {filename}: {e}", body)

    # --- Parse and upload to Affinity ---
    try:
        companies, notes = parse_email_body(body)
        print(f"✅ Parsed companies: {companies}")
        print(f"✅ Parsed notes: {notes}")
        print(f"✅ Drive links: {drive_links}")
        uploaded = upload_to_affinity(companies, notes, drive_links)
        print(f"✅ Uploaded to Affinity: {uploaded}")
    except Exception as e:
        send_error_email(str(e), body)


def parse_email_body(text: str):
    """Extracts companies and notes from email text."""
    # Lowercase check for 'upload to affinity'
    if "upload to affinity" not in text.lower():
        raise ValueError("Keyword 'upload to affinity' not found.")

    # Find the line containing 'upload to affinity'
    lines = text.splitlines()
    upload_line = None
    for line in lines:
        if "upload to affinity" in line.lower():
            upload_line = line.strip()
            break

    if not upload_line:
        raise ValueError("Could not locate upload line.")

    # Extract company list (before 'upload to affinity')
    before = upload_line.lower().split("upload to affinity")[0].strip()
    company_text = re.sub(r"[\[\]]", "", before).strip()
    company_list = [c.strip() for c in company_text.split(",") if c.strip()]

    # Extract notes if they exist
    notes_match = re.search(r'notes:\s*"(.*?)"', text, re.IGNORECASE | re.DOTALL)
    notes = notes_match.group(1).strip() if notes_match else None

    return company_list, notes

def send_error_email(error_msg, original_body):
    """Send an alert email to Imaad if parsing fails."""
    # Use same token path logic as get_gmail_service
    if os.path.exists("/secrets/token.json"):
        token_path = "/secrets/token.json"
    elif os.path.exists("/tmp/token.json"):
        token_path = "/tmp/token.json"
    else:
        token_path = os.getenv("TOKEN_PATH", "token.json")

    creds = Credentials.from_authorized_user_file(token_path)
    service = build("gmail", "v1", credentials=creds)


