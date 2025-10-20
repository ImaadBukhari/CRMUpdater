# === infra/token_generator.py ===
#Only run this once to generate token.json for Gmail + Drive access

import os

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv
import pathlib

env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
print(f"Loaded .env from: {env_path.resolve()}")
print(f"GOOGLE_CLIENT_ID = {os.getenv('GOOGLE_CLIENT_ID')}")

# Scopes: Gmail read/send + Drive file operations
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def generate_token():
    """
    Run this once locally to create token.json for Gmail + Drive access.
    """
    creds = None
    if os.path.exists("token.json"):
        print("✅ token.json already exists. Delete it first if you want to refresh.")
        return

    credentials = {
        "installed": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uris": ["http://localhost:8080"],
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }


    flow = InstalledAppFlow.from_client_config(credentials, SCOPES)
    creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')

    with open("token.json", "w") as token:
        token.write(creds.to_json())

    print("✅ token.json generated successfully!")

if __name__ == "__main__":
    generate_token()
