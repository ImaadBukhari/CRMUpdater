# backend/drive_service.py
import os
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
DRIVE_PARENT_FOLDER_ID = os.getenv("DRIVE_PARENT_FOLDER_ID", None)  # optional

def get_drive_service():
    """Build Google Drive API client."""
    creds = Credentials.from_authorized_user_file("token.json")
    return build("drive", "v3", credentials=creds)

def upload_attachment_to_drive(filename: str, file_data_b64: str, mime_type: str) -> str:
    """
    Uploads a file (PDF, Word, PPT) to Google Drive and sets domain-wide sharing.
    Returns: the shareable link
    """
    service = get_drive_service()
    file_bytes = base64.urlsafe_b64decode(file_data_b64)
    fh = BytesIO(file_bytes)

    metadata = {"name": filename}
    if DRIVE_PARENT_FOLDER_ID:
        metadata["parents"] = [DRIVE_PARENT_FOLDER_ID]

    media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True)
    uploaded_file = service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = uploaded_file.get("id")

    # Set sharing permissions: domain-wide read access for wyldvc.com
    permission = {
        "type": "domain",
        "role": "reader",
        "domain": "wyldvc.com",
        "allowFileDiscovery": False,
    }
    service.permissions().create(fileId=file_id, body=permission, fields="id").execute()

    # Generate a sharable link
    file = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return file.get("webViewLink")
