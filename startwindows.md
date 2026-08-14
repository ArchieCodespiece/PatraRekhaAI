# PatraRekhaAI — Windows Setup Guide

Tested on Windows 10/11 with Python 3.12.

## 1. Install system dependencies

Install Python 3.12 from https://www.python.org/downloads/release/python-3129/
Check "Add Python to PATH" during installation.
Install Node.js 18+ from https://nodejs.org/ (for the frontend).
Install poppler for Windows:
Download from https://github.com/oschwartz10612/poppler-windows/releases
Extract to C:\poppler
Add C:\poppler\Library\bin to your System PATH
Verify in PowerShell: pdftoppm -v

## 2. Clone / copy the project

```bash
cd $HOME
git clone <your-repo-url> PatraRekhaAI
cd PatraRekhaAI
```

## 3. Create virtual environments

```bash
py -3.12 -m venv .venv          # pipeline venv (root)
py -3.12 -m venv backend\.venv  # backend venv
```

Verify:

```bash
.venv\Scripts\python.exe --version
backend\.venv\Scripts\python.exe --version
```

Both should show Python 3.12.x.

## 4. Install Python dependencies

Backend:

```bash
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Pipeline:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the OCR stack fails:

```bash
.venv\Scripts\python.exe -m pip install paddlepaddle paddleocr
```

## 5. Configure .env

backend\.env — replace placeholders with real values:

```env
POLL_INTERVAL_SECONDS=120
GMAIL_FETCH_BATCH_SIZE=100
GMAIL_LOOKBACK_DAYS=30
STORAGE_DIR=./data
MAX_ATTACHMENT_BYTES=26214400
ALLOWED_SENDERS=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=<your-key>
WEBHOOK_SECRET=
WEBHOOK_QUEUE_MAX_SIZE=100
WEBHOOK_QUEUE_WORKERS=1
WEBHOOK_QUEUE_MAX_ATTEMPTS=3
WEBHOOK_QUEUE_RETRY_DELAY_SECONDS=2
WEBHOOK_QUEUE_COMPLETED_TTL_SECONDS=60
PIPELINE_PYTHON=C:\Users\<your-user>\PatraRekhaAI\.venv\Scripts\python.exe
GROQ_API_KEY=<your-key>
GROQ_MODEL=llama-3.1-8b-instant
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8001/gmail/connect/callback
FRONTEND_GMAIL_CONNECT_REDIRECT=http://localhost:3000/dashboard
GMAIL_OAUTH_STATE_SECRET=
GMAIL_OAUTH_SCOPES=
```

### frontend/.env.local

VITE_BACKEND_API_URL=http://localhost:8001
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
Critical: PIPELINE_PYTHON must point to the Windows venv path shown above. If left unset, the system auto-detects it.

.env (project root):

GEMINI_API_KEY=<your-key>
PINECONE_API_KEY=<your-key>
GROQ_API_KEY=<your-key>
GROQ_MODEL=llama-3.1-8b-instant
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=<your-key>
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8001/gmail/connect/callback
FRONTEND_GMAIL_CONNECT_REDIRECT=http://localhost:3000/dashboard

## 6. Start the backend API

```bash
cd C:\Users\<your-user>\PatraRekhaAI
backend\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --app-dir backend
```

Verify:

```bash
curl http://127.0.0.1:8001/get-documents
```

7. Start email ingestion

```bash
cd C:\Users\<your-user>\PatraRekhaAI\backend\email-ingestion
..\..\backend\.venv\Scripts\python.exe ingest.py
```

You should see:

```
Watching connected Gmail accounts (polling ALL messages every cycle)
[HH:MM:SS] No connected Gmail accounts found. Skipping sync.
```

## 8. Start the frontend

```bash
cd C:\Users\<your-user>\PatraRekhaAI\frontend
npm install
npm run dev
```

Open http://localhost:3000.

## 9. Connect Gmail

Sign in with Google
Click "Connect Gmail" in the dashboard
Authorize in Google's OAuth consent screen
For multi-user testing, use different browsers or incognito windows.

## 10. Run the pipeline directly (optional)

```bash
cd C:\Users\<your-user>\PatraRekhaAI
.venv\Scripts\python.exe main.py <path-to-pdf>
```

## 11. Useful checks

```bash
curl http://127.0.0.1:8001/get-documents
curl http://127.0.0.1:8001/webhooks/queue/status
curl "http://127.0.0.1:8001/gmail/connect/status?owner_email=<email>"
```

## Important notes

1. Python: Use 3.12. Newer versions may break paddleocr.
2. Poppler: If you get PDFInfoNotInstalledError, ensure C:\poppler\Library\bin is in PATH and restart PowerShell.
3. Ports: Backend=8001, frontend=3000, ingest=8002.
4. ngrok: Not needed for local development.
5. Secrets: Never commit .env files.
6. Multi-user: Each browser/profile has its own localStorage. Logging out from one browser only disconnects that user — others are unaffected.
7. Stopping: Press Ctrl+C in each terminal.
