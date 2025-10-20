# backend/crm_service.py
import os
import requests
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

AFFINITY_API_KEY = os.getenv("AFFINITY_API_KEY")
AFFINITY_BASE_URL = "https://api.affinity.co/v2"
AFFINITY_LIST_ID = 315335
EMAIL_NOTIFY = "imaad@wyldvc.com"

HEADERS = {
    "Authorization": f"Bearer {AFFINITY_API_KEY}",
    "Content-Type": "application/json"
}

# === Gmail helper for error reporting ===
def get_gmail_service():
    creds = Credentials.from_authorized_user_file("token.json")
    return build("gmail", "v1", credentials=creds)

def send_error_email(subject: str, body: str):
    """Send an error alert email to Imaad."""
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = EMAIL_NOTIFY
        message["from"] = "me"
        message["subject"] = subject
        raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        service.users().messages().send(userId="me", body=raw).execute()
    except Exception as e:
        print(f"⚠️ Failed to send error email: {e}")

# === Affinity helper functions ===
def search_company(company_name: str):
    url = f"{AFFINITY_BASE_URL}/companies"
    params = {"filter": f'name=~"{company_name}"', "limit": 1}
    res = requests.get(url, headers=HEADERS, params=params)
    if res.status_code != 200:
        raise Exception(f"Affinity search failed ({res.status_code}): {res.text}")
    data = res.json()
    companies = data.get("data", [])
    return companies[0] if companies else None

def create_company(company_name: str):
    url = f"{AFFINITY_BASE_URL}/companies"
    payload = {"name": company_name}
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code not in (200, 201):
        raise Exception(f"Affinity create failed: {res.text}")
    return res.json()

def get_list_entries():
    url = f"{AFFINITY_BASE_URL}/lists/{AFFINITY_LIST_ID}/list-entries"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        raise Exception(f"List fetch failed: {res.text}")
    return [entry.get("company", {}).get("id") for entry in res.json().get("data", [])]

def add_company_to_list(company_id: int):
    url = f"{AFFINITY_BASE_URL}/lists/{AFFINITY_LIST_ID}/list-entries"
    payload = {"companyId": company_id}
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code not in (200, 201):
        raise Exception(f"Add to list failed: {res.text}")
    return res.json()

def add_company_note(company_id: int, text: str):
    url = f"{AFFINITY_BASE_URL}/companies/{company_id}/notes"
    payload = {"content": text}
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code not in (200, 201):
        raise Exception(f"Add note failed: {res.text}")
    return res.json()

# === Orchestrator ===
def upload_to_affinity(companies, notes=None, drive_links=None):
    """
    Main orchestrator called from gmail_service.
    - companies: list[str]
    - notes: list[str] or single string
    - drive_links: list[str]
    """
    try:
        list_company_ids = get_list_entries()
    except Exception as e:
        send_error_email("Affinity List Fetch Failed", str(e))
        return []

    if notes and isinstance(notes, str):
        notes = [notes]
    if not notes:
        notes = [None] * len(companies)
    if len(notes) < len(companies):
        notes += [None] * (len(companies) - len(notes))

    uploaded_info = []

    for i, company_name in enumerate(companies):
        try:
            note_text = notes[i]
            company = search_company(company_name)
            if not company:
                company = create_company(company_name)
            company_id = company.get("id")

            if company_id not in list_company_ids:
                add_company_to_list(company_id)

            final_note = ""
            if note_text:
                final_note += note_text
            if drive_links:
                final_note += "\n\nAttachments:\n" + "\n".join(drive_links)

            if final_note.strip():
                add_company_note(company_id, final_note)

            uploaded_info.append({"company": company_name, "company_id": company_id})

        except Exception as e:
            err_subject = f"CRMUpdater: Affinity Upload Failed for {company_name}"
            err_body = f"Error: {str(e)}\n\nCompany: {company_name}\nNote: {notes[i]}\nDrive links: {drive_links}"
            send_error_email(err_subject, err_body)
            print(f"⚠️ Error uploading {company_name}: {e}")

    return uploaded_info
