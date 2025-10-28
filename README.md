# CRM Updater

An event-driven automation that monitors incoming Gmail messages for specific instructions, extracts company names, notes, and attachments, and automatically updates the Wyld VC Affinity CRM.  
It seamlessly connects Gmail → Google Drive → Affinity to create notes and upload files without manual intervention.

---

## 🌟 Overview

**CRM Updater** listens for new emails in your Gmail inbox and reacts whenever an email contains phrases like  
`upload to Affinity`.  

When detected, it automatically:
1. Extracts company names and any associated notes from the email body.  
2. Uploads valid attachments (PDFs, Word, PowerPoint) to Google Drive and sets domain-wide access.  
3. Checks whether the company exists in the target Affinity list (ID `315335`).  
4. Creates notes and file links for each company accordingly.

This automation runs entirely serverlessly on **Google Cloud Run**, with **Gmail Push Notifications via Pub/Sub**, and stays active through a daily **Cloud Scheduler refresh**.

---

## 🎯 Key Features

- **Automatic Gmail Parsing** — Listens for specific email commands (`upload to affinity`)  
- **Attachment Uploads** — Uploads valid document types to Google Drive and generates shareable links  
- **CRM Syncing** — Updates or creates company records and notes in Affinity automatically  
- **Error Notifications** — Emails you (`imaad@wyldvc.com`) if parsing or uploads fail  
- **Fully Serverless** — Runs continuously using Cloud Run, Pub/Sub, and Cloud Scheduler  
- **Secure Token Handling** — Stores Gmail OAuth tokens in Secret Manager, never in source control  

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Gmail Inbox    │ ← Email with "upload to Affinity"
└────────┬────────┘
         │ Push Notification
         ▼
┌─────────────────┐
│  Pub/Sub Topic  │ ← gmail-topic
└────────┬────────┘
         │ Webhook
         ▼
┌─────────────────┐
│  Cloud Run      │ ← FastAPI Backend
│  /pubsub        │
└────────┬────────┘
         │
    ┌────┴─────┬──────────┬───────────┐
    ▼          ▼          ▼           ▼
┌────────┐ ┌──────┐ ┌──────────┐ ┌────────┐
│ Gmail  │ │Drive │ │ Secret   │ │Affinity│
│  API   │ │ API  │ │ Manager  │ │  CRM   │
└────────┘ └──────┘ └──────────┘ └────────┘
         ▲
         │ Daily (4 AM)
    ┌────┴────────┐
    │   Cloud     │
    │ Scheduler   │
    └─────────────┘
```

### 🔄 Flow Summary

1. Gmail sends a push event to the Pub/Sub topic when a new email arrives.  
2. Pub/Sub triggers the `/pubsub` endpoint on Cloud Run.  
3. The backend fetches the message, decodes attachments, and parses the body.  
4. Valid attachments are uploaded to Drive and made shareable.  
5. Company and note data are posted to the Affinity CRM via API.  
6. Any issues trigger an error email notification to `imaad@wyldvc.com`.

---

## 📁 Project Structure

```
CRMUpdater/
├── backend/                    # FastAPI backend application
│   ├── main.py                # Main API endpoints and Pub/Sub webhook
│   ├── gmail_service.py       # Gmail API integration and parsing
│   ├── drive_service.py       # Google Drive upload and permissions
│   ├── crm_service.py         # Affinity CRM integration
│   ├── pubsub_handler.py      # Pub/Sub notification processing
│   └── requirements.txt       # Python dependencies
│
├── infra/                     # Infrastructure and deployment
│   ├── Dockerfile            # Container configuration
│   ├── cloudbuild.yaml       # Cloud Build pipeline
│   ├── deploy.sh             # Deployment script
│   ├── setup_gmail_watch.py  # Gmail watch registration
│   └── token_generator.py    # OAuth token generator
│
├── .env                       # Environment variables (not committed)
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

---

## 🔑 Key Files Explained

### `backend/main.py`

Defines the FastAPI application and `/pubsub` webhook:
- Receives Gmail Pub/Sub events  
- Parses message envelopes  
- Calls `handle_pubsub_message()` to process new emails  
- Returns health responses for Cloud Run logs  

### `backend/gmail_service.py`

Handles:
- Gmail authentication (`token.json` or Secret Manager)
- Email parsing and validation
- Detecting "upload to affinity" triggers
- Extracting companies, notes, and attachments
- Sending error notifications when parsing fails  

**Important:**  
The Gmail watch expires daily, so Cloud Scheduler re-runs `setup_gmail_watch.py` to renew it.

### `backend/drive_service.py`

Handles Google Drive file uploads:
- Uploads attachments from Gmail (PDF, DOCX, PPTX)
- Skips invalid MIME types (e.g. PNG, JPG)
- Applies domain-wide read access (`wyldvc.com`)
- Returns shareable Drive links  

### `backend/crm_service.py`

Communicates with Affinity:
- Searches companies by name  
- Adds missing companies to list `315335`  
- Appends notes and Drive links to existing records  

### `backend/pubsub_handler.py`

Processes Pub/Sub notifications and calls Gmail processing with the correct `historyId`.

### `infra/setup_gmail_watch.py`

Registers the Gmail → Pub/Sub watch:
- Defines which labels to monitor (`INBOX`)  
- Pushes to the `gmail-topic` Pub/Sub topic  
- Should be called once daily via Cloud Scheduler  

### `infra/token_generator.py`

Performs one-time local OAuth authorization using the client ID and secret from `.env`, generating a `token.json` containing the refresh and access tokens. This file is later uploaded to Secret Manager for secure use in production.

### `infra/Dockerfile`

Defines a minimal Python 3.12 container image that installs dependencies, exposes port 8080, and runs the FastAPI service.

### `infra/cloudbuild.yaml`

Automates the build-and-deploy pipeline on Google Cloud Build.

### `infra/deploy.sh`

Builds and deploys to Cloud Run:
- Builds the image with Cloud Build  
- Sets the secret mount for `token.json`  
- Deploys to the specified region (`us-central1`)  

---

## 🚀 Deployment Instructions

### 1️⃣ Enable required APIs

```bash
gcloud services enable gmail.googleapis.com drive.googleapis.com pubsub.googleapis.com run.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com cloudbuild.googleapis.com
```

### 2️⃣ Generate OAuth token locally

```bash
python infra/token_generator.py
```

### 3️⃣ Upload token to Secret Manager

```bash
gcloud secrets create gmail-token --replication-policy=automatic
gcloud secrets versions add gmail-token --data-file=token.json
```

### 4️⃣ Deploy to Cloud Run

```bash
./deploy.sh
```

### 5️⃣ Set up Gmail watch renewal (Cloud Scheduler)

```bash
gcloud scheduler jobs create http gmail-watch-refresh \
  --schedule="0 4 * * *" \
  --uri="https://crm-updater-backend-<your-region>.a.run.app/refresh_watch" \
  --http-method=GET \
  --oidc-service-account-email=crm-updater-sa@crm-updater-475321.iam.gserviceaccount.com
```

---

## 📧 Email Format

Each email is treated as a structured instruction set:
- **Text before "upload to Affinity"** specifies the company or companies  
- **"notes:"** defines the text to attach  
- **Attachments** provide supplemental files (PDFs, Word, PowerPoint)

Invalid formats trigger automatic error notifications to `imaad@wyldvc.com`.

---

## 🔐 Security

- OAuth credentials retrieved from local `token.json` or Google Secret Manager
- Gmail token secret mounted in Cloud Run
- Domain-wide sharing permissions set to `wyldvc.com`
- `.env` and `token.json` excluded from version control via `.gitignore`

---

## 📝 Architecture Details

The system's architecture links Gmail → Pub/Sub → Cloud Run → Drive → Affinity, with Secret Manager handling secure credential access. Cloud Scheduler triggers `setup_gmail_watch.py` daily to renew Gmail's watch (which expires roughly every 24 hours). This design ensures continuous, event-driven CRM updates without manual logins, safely bridging email workflows, file management, and CRM synchronization in a fully automated cloud-native stack.
