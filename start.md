# PatraRekhaAI Start Guide

This repo was written with Linux-style paths in a few places, but it can run on Windows with Python 3.12 after the compatibility fixes in `main.py` and `backend/webhooks/service/processor.py`.

## 1. Create the environments

Use Python 3.12 for both the backend and the pipeline.

```powershell
py -3.12 -m venv .venv
py -3.12 -m venv backend\.venv
```

## 2. Install dependencies

Backend:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Pipeline:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the OCR stack needs extra packages on your machine, install them in the root `.venv` only.

## 3. Configure environment variables

Create these files if they do not already exist:

```text
backend\.env.env
```

Put the API keys and settings from the pasted note into the matching file.

Recommended split:

```env
# backend\.env
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
WEBHOOK_SECRET=...
PIPELINE_PYTHON=D:\pat\PatraRekhaAI\.venv\Scripts\python.exe

IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=...
IMAP_PASSWORD=...
IMAP_MAILBOX=INBOX
POLL_INTERVAL_SECONDS=5
STORAGE_DIR=./data
MAX_ATTACHMENT_BYTES=26214400
ALLOWED_SENDERS=
```

```env
# .env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
GEMINI_API_KEY=...
PINECONE_API_KEY=...
SUPABASE_URL=...
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## 4. Start the backend

Run this from the repo root:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8010 --app-dir backend
```

If you prefer to start from inside `backend`, this also works:

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8010
```

## 5. Start email ingestion

```powershell
cd backend\email-ingestion
..\..\.\venv\Scripts\python.exe ingest.py
```

If you run into path issues there, use the full path:

```powershell
D:\pat\PatraRekhaAI\backend\.venv\Scripts\python.exe ingest.py
```

## 6. Run the pipeline directly

To test the PDF pipeline on a local file:

```powershell
.venv\Scripts\python.exe main.py ingestion\Quality_Auditor_Tender_to_be_uploaded.pdf
```

Or use the default sample PDF:

```powershell
.venv\Scripts\python.exe main.py
```

## 7. Useful checks

Verify the Python versions:

```powershell
.venv\Scripts\python.exe --version
backend\.venv\Scripts\python.exe --version
```

Verify the backend:

```powershell
curl http://127.0.0.1:8010/get-documents
```

Verify the webhook queue:

```powershell
curl http://127.0.0.1:8010/webhooks/queue/status
```

## 8. Important note about the pasted secrets

The pasted setup note contains live-looking credentials. If those are real, rotate them and move them into your local `.env` files instead of keeping them in chat or committed to git.
