# CRMUpdater

Automates adding companies to Affinity via their email bots (no Affinity API calls) using:
- Gmail ingestion (attachments → Drive, parse email body)
- Perplexity to resolve a company's website URL
- Affinity list and notes email bots to add to lists and attach notes
- Cloud Run + Cloud Scheduler for hosted operation

## High-level Flow
1. A Gmail message arrives (manually or via watch). Attachments are uploaded to Google Drive.
2. The email body is parsed for a command and optional notes.
3. For each company name, Perplexity returns a website URL.
4. Two emails are sent to Affinity bots per company:
   - List add: `lists+wyldvc+315335@affinity.co` (body: company URL)
   - Notes: `notes+wyldvc@affinity.co` (body: URL, blank line, note + Drive links)

## Repository Structure
```
backend/
  main.py                # FastAPI app (/refresh_watch, /pubsub)
  gmail_service.py       # Gmail client, parsing, Drive upload, orchestrator entry
  crm_service.py         # Perplexity + Affinity email bot sending (core logic)
  drive_service.py       # Upload attachment bytes to Drive (link returned)
  pubsub_handler.py      # Pub/Sub push handler for Gmail watch notifications
  requirements.txt
infra/
  setup_gmail_watch.py   # Registers Gmail watch (HTTP target to Pub/Sub topic)
  token_generator.py     # Generates token.json with proper OAuth scopes
  cloudbuild.yaml        # Optional: Cloud Build pipeline (not required)
Dockerfile               # Container runtime for Cloud Run
deploy.sh                # Build + deploy to Cloud Run with secrets
test_email_processing.py # Simple local test harness
```

## Email Command Format (what the parser expects)
- Trigger phrase (case-insensitive) must appear in a line: `upload to affinity`
- Companies must appear on the same line, before or around the phrase. Examples:
  - `Please upload to affinity: OpenAI, Anthropic, Scale AI`
  - `[OpenAI, Anthropic, Scale AI] upload to affinity`
- Optional notes anywhere in the email, captured with double quotes:
  - `Notes: "Some note text here"`

Notes formatting sent to Affinity notes bot:
```
{company_url}

{note_text}

Attachments:
{drive_link_1}
{drive_link_2}
```

## Perplexity Integration
- API endpoint: `https://api.perplexity.ai/chat/completions`
- Model: `sonar`
- Request parameters: `return_citations: false`, `return_images: false`
- Prompt: `What is the domain for {company} startup. Return only the site in full https format`
- Post-processing: trailing citations/punctuation are stripped; the token is trimmed.

Configuration source (priority):
1. Cloud Run secret injected as env var `PERPLEXITY_API_KEY`
2. Local `.env` for development

## OAuth Token (token.json) and Scopes
Generated once using `infra/token_generator.py` and stored as a Secret Manager secret (`gmail-token`).

Requested scopes (recommended):
- Gmail: `gmail.readonly`, `gmail.send`, `gmail.modify`
- Drive: `drive.file`, `drive`

The app loads the token from (in order):
1. Cloud Run secret mounted at `/secrets/token.json`
2. Local `TOKEN_PATH` env or `token.json` in repo
3. Secret Manager fallback (server-side only)

## Local Development
1. Python deps
   ```bash
   pip install -r backend/requirements.txt
   ```

2. .env
   ```env
   PERPLEXITY_API_KEY=your_api_key
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

3. Generate token.json (first time only)
   ```bash
   python infra/token_generator.py
   ```

4. Run FastAPI locally
   ```bash
   uvicorn backend.main:app --reload --port 8000
   # Endpoints: /refresh_watch, /pubsub
   ```

5. Quick test without Gmail
   ```bash
   python test_email_processing.py
   ```

## Deployment (Cloud Run)
Requirements:
- Secrets in Secret Manager:
  - `gmail-token` (contents of token.json)
  - `perplexity-api-key` (value only; add via printf to avoid newline)
    ```bash
    printf '%s' 'pplx-...' | gcloud secrets versions add perplexity-api-key --data-file=- --project=$PROJECT_ID
    ```

Deploy:
```bash
./deploy.sh
```

What deploy.sh does:
- Builds container
- Ensures `PERPLEXITY_API_KEY` is not set as a plain env var
- Sets secrets:
  - Env var: `PERPLEXITY_API_KEY=perplexity-api-key:latest`
  - File: `/secrets/token.json=gmail-token:latest`
- Sets `GCP_PROJECT`

## Cloud Scheduler (refresh Gmail watch)
Target endpoint: `GET /refresh_watch`

Create a daily job (example midnight UTC):
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

## Troubleshooting
- 401 from Perplexity: ensure `PERPLEXITY_API_KEY` is set from secret (Cloud Run → Revisions → Variables & Secrets) and has no trailing newline. Prefer adding with `printf`.
- `invalid_scope`: regenerate `token.json` with the listed scopes or remove explicit scopes from code paths and rely on token’s embedded scopes.
- "No module named 'infra'": ensure Dockerfile copies `infra/` and both `backend/` and `infra/` have `__init__.py`.
- Cloud Run deploy arg errors: only one of `--set-env-vars`, `--remove-env-vars`, etc., per command. The provided `deploy.sh` sequences these correctly.

## Security Notes
- No Affinity API token is used; interaction is via Affinity email bot addresses.
- Secrets are sourced from Secret Manager at deploy/runtime and not committed.

---
Maintainer tips:
- Prefer a single orchestration path: `backend.crm_service.upload_to_affinity()` for batch actions.
- For local end-to-end testing without Gmail, use `test_email_processing.py`.
