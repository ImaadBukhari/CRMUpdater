# backend/crm_service.py
import os
import requests
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

def get_perplexity_api_key():
    """Get Perplexity API key from environment variable."""
    # Cloud Run automatically injects secret as environment variable
    # Local development uses .env file
    api_key = os.getenv("PERPLEXITY_API_KEY").strip()
    if api_key:
        return api_key
    else:
        raise ValueError("PERPLEXITY_API_KEY environment variable not found")

PERPLEXITY_API_KEY = get_perplexity_api_key()
AFFINITY_LIST_ID = 315335
EMAIL_NOTIFY = "imaad@wyldvc.com"

# === Gmail helper for error reporting ===
def get_gmail_service():
    # Try mounted secret file first (Cloud Run)
    if os.path.exists("/secrets/token.json"):
        token_path = "/secrets/token.json"
    # Fall back to environment variable or local file
    else:
        token_path = os.getenv("TOKEN_PATH", "token.json")
    
    creds = Credentials.from_authorized_user_file(token_path)
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

# === Perplexity API for company URLs ===
def get_company_url(company_name: str):
    """Get company website URL using Perplexity API."""
    try:
        import re
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"What is the domain for {company_name} startup. Return only the site in full https format"
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "return_citations": False,
            "return_images": False
        }
        
        print(f"\n🔍 PERPLEXITY API REQUEST for '{company_name}'")
        print("-" * 50)
        print(f"Prompt: {prompt}")
        print(f"Model: {payload['model']}")
        print(f"Return Citations: {payload['return_citations']}")
        print(f"Return Images: {payload['return_images']}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error Response: {response.text}")
            raise Exception(f"Perplexity API failed ({response.status_code}): {response.text}")
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print(f"Raw Response Content: '{content}'")
        
        # Parse for URL starting with https and ending with space or end of string
        url_match = re.search(r'https://[^\s]+', content)
        if url_match:
            raw_url = url_match.group(0)
            print(f"🔍 Raw extracted URL: {raw_url}")
            
            # Clean citation markers and trailing punctuation
            # Remove patterns like **[1][5], **[1], [1], trailing periods, etc.
            cleaned_url = re.sub(r'\*\*\[[^\]]+\](\[[^\]]+\])*\.?$', '', raw_url)  # Remove **[1][5].
            cleaned_url = re.sub(r'\[[^\]]+\]\.?$', '', cleaned_url)              # Remove [1].
            cleaned_url = re.sub(r'[\.,;:!?\)]+$', '', cleaned_url)               # Remove trailing punctuation
            
            print(f"✅ Cleaned URL: {cleaned_url}")
            return cleaned_url
        else:
            print(f"❌ No valid URL found in response")
            raise Exception(f"No valid URL found in Perplexity response: {content}")
            
    except Exception as e:
        print(f"❌ PERPLEXITY ERROR for {company_name}: {str(e)}")
        raise Exception(f"Failed to get company URL for {company_name}: {str(e)}")

# === Email bot functions ===
def send_list_email(company_name: str, company_url: str):
    """Send email to Affinity list bot to add company to deals list."""
    try:
        service = get_gmail_service()
        
        subject = f"Add {company_name} to Deals List"
        body = f"{company_url}"
        to_email = f"lists+wyldvc+{AFFINITY_LIST_ID}@affinity.co"
        
        print("\n" + "="*60)
        print("📧 SENDING LIST EMAIL")
        print("="*60)
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:")
        print(f"'{body}'")
        print("="*60)
        
        message = MIMEText(body)
        message["to"] = to_email
        message["from"] = "me"
        message["subject"] = subject
        
        raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        service.users().messages().send(userId="me", body=raw).execute()
        
        print(f"✅ SUCCESSFULLY sent list email for {company_name}")
        print(f"   Email ID will be generated by Gmail")
        
    except Exception as e:
        print(f"❌ FAILED to send list email for {company_name}: {str(e)}")
        raise Exception(f"Failed to send list email for {company_name}: {str(e)}")

def send_notes_email(company_name: str, company_url: str, note_content: str):
    """Send email to Affinity notes bot to add note to company."""
    try:
        service = get_gmail_service()
        
        subject = f"Note for {company_name}"
        # Format: Line 1: URL, Line 2: blank, Line 3+: note content
        body = f"{company_url}\n\n{note_content}"
        to_email = "notes+wyldvc@affinity.co"
        
        print("\n" + "="*60)
        print("📝 SENDING NOTES EMAIL")
        print("="*60)
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:")
        print("--- Start of Body ---")
        print(repr(body))  # Shows escape characters
        print("--- Formatted Body ---")
        print(body)
        print("--- End of Body ---")
        print("="*60)
        
        message = MIMEText(body)
        message["to"] = to_email
        message["from"] = "me"  
        message["subject"] = subject
        
        raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        service.users().messages().send(userId="me", body=raw).execute()
        
        print(f"✅ SUCCESSFULLY sent notes email for {company_name}")
        print(f"   Note length: {len(note_content)} characters")
        
    except Exception as e:
        print(f"❌ FAILED to send notes email for {company_name}: {str(e)}")
        raise Exception(f"Failed to send notes email for {company_name}: {str(e)}")


# === Orchestrator ===
def upload_to_affinity(companies, notes=None, drive_links=None):
    """
    Main orchestrator called from gmail_service.
    Uses Perplexity to find company URLs and Affinity email bots for operations.
    - companies: list[str]
    - notes: list[str] or single string
    - drive_links: list[str]
    """
    # Normalize notes input
    if notes and isinstance(notes, str):
        notes = [notes]
    if not notes:
        notes = [None] * len(companies)
    if len(notes) < len(companies):
        notes += [None] * (len(companies) - len(notes))

    uploaded_info = []
    
    print("\n" + "🚀 STARTING COMPANY UPLOAD PROCESS")
    print("="*70)
    print(f"Companies to process: {companies}")
    print(f"Notes provided: {notes}")
    print(f"Drive links: {drive_links}")
    print("="*70)

    for i, company_name in enumerate(companies):
        try:
            print(f"\n📋 PROCESSING COMPANY {i+1}/{len(companies)}: {company_name}")
            print("-" * 40)
            
            # Step 1: Get company URL via Perplexity
            company_url = get_company_url(company_name)
            print(f"✅ Found URL for {company_name}: {company_url}")
            
            # Step 2: Send list addition email
            print(f"\n📤 Step 2: Adding {company_name} to deals list...")
            send_list_email(company_name, company_url)
            
            # Step 3: Send notes email if there's content
            note_text = notes[i]
            final_note = ""
            if note_text:
                final_note += note_text
            if drive_links:
                final_note += "\n\nAttachments:\n" + "\n".join(drive_links)

            if final_note.strip():
                print(f"\n📝 Step 3: Adding note to {company_name}...")
                send_notes_email(company_name, company_url, final_note)
            else:
                print(f"\n⏭️  Step 3: No notes to send for {company_name}")

            result_info = {
                "company": company_name, 
                "company_url": company_url,
                "notes_sent": bool(final_note.strip()),
                "list_email_sent": True
            }
            uploaded_info.append(result_info)
            
            print(f"\n✅ COMPLETED processing {company_name}")
            print(f"   Result: {result_info}")

        except Exception as e:
            print(f"\n❌ ERROR processing {company_name}: {str(e)}")
            err_subject = f"CRMUpdater: Email Bot Processing Failed for {company_name}"
            err_body = f"Error: {str(e)}\n\nCompany: {company_name}\nNote: {notes[i]}\nDrive links: {drive_links}"
            send_error_email(err_subject, err_body)
            print(f"⚠️ Error processing {company_name}: {e}")
    
    print("\n" + "🏁 UPLOAD PROCESS COMPLETE")
    print("="*70)
    print(f"Successfully processed: {len(uploaded_info)}/{len(companies)} companies")
    print(f"Final results: {uploaded_info}")
    print("="*70)

    return uploaded_info
