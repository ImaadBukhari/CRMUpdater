# CRM Updater

Event-driven automation: Gmail → Drive → Perplexity → Affinity (via email bots). No direct Affinity API calls.

---

## Overview

When an email contains the phrase "upload to affinity", the system:
1. Parses company names and optional notes from the email body
2. Uploads allowed attachments (PDF/DOC/DOCX/PPT/PPTX) to Google Drive and collects shareable links
3. Uses Perplexity to resolve each company's website URL
4. Sends two emails per company to Affinity bot addresses:
   - List add: `lists+wyldvc+315335@affinity.co` (body: company URL only)
   - Notes: `notes+wyldvc@affinity.co` (body: URL, blank line, note + Drive links)

Runs on Cloud Run, triggered by Gmail push (Pub/Sub) and kept alive via daily Scheduler refresh.

---

## Architecture

```
Gmail → Pub/Sub → Cloud Run (/pubsub)
            └→ Drive upload
            └→ Perplexity domain lookup
            └→ Gmail send to Affinity bots

Scheduler → Cloud Run (/refresh_watch) to renew Gmail watch
```

---

## Project Structure

```
backend/
  main.py            # FastAPI app: /refresh_watch, /pubsub
  gmail_service.py   # Gmail client, parsing, Drive upload, orchestrator call
  crm_service.py     # Perplexity lookup + Affinity bot email sending
  drive_service.py   # Drive upload utilities
  pubsub_handler.py  # Pub/Sub envelope → process_gmail_message
  requirements.txt
infra/
  setup_gmail_watch.py  # Register Gmail watch to Pub/Sub topic
  token_generator.py    # Generate token.json with required scopes
  cloudbuild.yaml       # Optional; not required for deploy.sh
Dockerfile           # Root Dockerfile for Cloud Run image
deploy.sh            # Build + deploy; maps secrets correctly
test_email_processing.py  # Local test harness
```

---

## Email Command Format

- Must contain the phrase: `upload to affinity` (case-insensitive)
- Companies should be on the same line as that phrase (before or around it). Examples:
  - `Please upload to affinity: OpenAI, Anthropic, Scale AI`
  - `[OpenAI, Anthropic, Scale AI] upload to affinity`
- Optional notes anywhere in the email using double quotes:
  - `Notes: "Some note text here"`

Notes email body format sent to Affinity:
```
{company_url}

{note_text_and_optional_section_below}

Attachments:
{drive_link_1}
{drive_link_2}
```

---

## Perplexity Integration

- Endpoint: `https://api.perplexity.ai/chat/completions`
- Model: `sonar`
- Params: `return_citations: false`, `return_images: false`
- Prompt: `What is the domain for {company} startup. Return only the site in full https format`
- Post-processing: trims whitespace and removes any trailing citation/punctuation artifacts

Configuration precedence for API key:
1. Cloud Run secret env var `PERPLEXITY_API_KEY`
2. Local `.env` (development)

---

## OAuth Token (token.json) and Scopes

Generate with `infra/token_generator.py`. Recommended scopes:
- Gmail: `gmail.readonly`, `gmail.send`, `gmail.modify`
- Drive: `drive.file`, `drive`

Token loading order:
1. Mounted secret file `/secrets/token.json` (Cloud Run)
2. `TOKEN_PATH` or `token.json` (local dev)
3. Secret Manager fallback (server-side)

---

## Local Development

1) Install deps
```bash
pip install -r backend/requirements.txt
```

2) .env
```env
PERPLEXITY_API_KEY=your_api_key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

3) Generate token.json (first time)
```bash
python infra/token_generator.py
```

4) Run API locally
```bash
uvicorn backend.main:app --reload --port 8000
# Endpoints: /refresh_watch, /pubsub
```

5) Quick end-to-end test without Gmail
```bash
python test_email_processing.py
```

---

## Deployment (Cloud Run)

Secrets required in Secret Manager:
- `gmail-token` (full token.json contents)
- `perplexity-api-key` (single-line value; add via printf to avoid newline)
```bash
printf '%s' 'pplx-...' | gcloud secrets versions add perplexity-api-key --data-file=- --project=$PROJECT_ID
```

Deploy:
```bash
./deploy.sh
```

deploy.sh actions:
- Builds image
- Removes any plain `PERPLEXITY_API_KEY` env var
- Maps secrets:
  - Env var: `PERPLEXITY_API_KEY=perplexity-api-key:latest`
  - File: `/secrets/token.json=gmail-token:latest`
- Sets `GCP_PROJECT`

---

## Cloud Scheduler (refresh Gmail watch)

Target: `GET /refresh_watch`

```bash
SERVICE_URL=$(gcloud run services describe crm-updater-backend \
  --region us-central1 --format='value(status.url)')
SERVICE_ACC=crm-updater-sa@crm-updater-475321.iam.gserviceaccount.com

gcloud run services add-iam-policy-binding crm-updater-backend \
  --region us-central1 \
  --member serviceAccount:$SERVICE_ACC \
  --role roles/run.invoker

gcloud scheduler jobs create http refresh-gmail-watch \
  --schedule="0 0 * * *" \
  --time-zone="Etc/UTC" \
  --uri="$SERVICE_URL/refresh_watch" \
  --http-method=GET \
  --oidc-service-account-email="$SERVICE_ACC" \
  --location=us-central1
```

Manual trigger:
```bash
TOKEN=$(gcloud auth print-identity-token)
SERVICE_URL=$(gcloud run services describe crm-updater-backend --region us-central1 --format='value(status.url)')
curl -sS -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/refresh_watch"
```

---

## Troubleshooting

- Perplexity 401 or header error: ensure secret env var is set and has no trailing newline (use `printf`), trimming is applied in code
- invalid_scope during /refresh_watch: regenerate `token.json` with scopes above or avoid forcing scopes when loading
- Module import errors: Dockerfile must copy both `backend/` and `infra/`; both have `__init__.py`
- Cloud Run deploy arg errors: only one of `--set-env-vars`/`--remove-env-vars` per command; `deploy.sh` sequences correctly

---

## Security

- Affinity interaction is via email bots; no Affinity API token used
- Secrets come from Secret Manager; never committed to repo
