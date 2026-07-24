# PatraRekhaAI Backend Start Guide

Use this one backend start command everywhere. The real FastAPI app lives in:

```text
backend/api/main.py
```

## 1. Check backend env

Make sure this file exists:

```bash
backend/.env
```

Minimum required values:

```env
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_FILE_STORAGE_BUCKET=file_storage
SUPABASE_FILES_TABLE=files
```

Optional webhook/queue values:

```env
WEBHOOK_SECRET=change-this-secret
WEBHOOK_QUEUE_MAX_SIZE=100
WEBHOOK_QUEUE_WORKERS=2
WEBHOOK_QUEUE_MAX_ATTEMPTS=3
WEBHOOK_QUEUE_RETRY_DELAY_SECONDS=2
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

Install backend dependencies into the backend venv:

```bash
cd backend
.venv/bin/python -m pip install -r requirements.txt
```

The webhook worker runs the root `main.py` pipeline using the project root `.venv`, because the OCR/Paddle stack needs Python 3.12. Check it with:

```bash
cd ..
.venv/bin/python --version
.venv/bin/python -c "import pdfplumber, paddleocr, google.genai, pinecone; print('pipeline env ok')"
```

If your pipeline Python lives somewhere else, set this in `backend/.env`:

```env
PIPELINE_PYTHON=/absolute/path/to/python
```

## 2. Start the FastAPI backend

Run from the project root:

```bash
cd backend
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8010
```

Backend URL:

```text
http://127.0.0.1:8010
```

Do not use multiple different start paths unless needed. Prefer `api.main:app` because it directly starts `backend/api/main.py`.

## 3. Start email ingestion

Open another terminal and run from the project root:

```bash
cd backend/email-ingestion
.venv/bin/python ingest.py
```

This starts the IMAP email poller. When a new unread email has an attachment, `ingest.py` uploads the file to Supabase Storage bucket `file_storage` and inserts a row into `public.files`.

That insert is what triggers the Supabase webhook:

```text
/webhooks/supabase/files
```

## 4. Start backend and ingestion together for local dev

If you want one command that starts both processes, run this from the project root:

```bash
(cd backend && .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8010) &
(cd backend/email-ingestion && .venv/bin/python ingest.py) &
wait
```

Stop both with `Ctrl+C`.

For less confusion while debugging, the two-terminal method is easier because backend logs and ingestion logs stay separate.

## 5. Verify normal document APIs

In another terminal:

```bash
curl http://127.0.0.1:8010/get-documents
```

For one document:

```bash
curl http://127.0.0.1:8010/get-documents/<file_id>
```

## 6. Verify webhook queue is running

```bash
curl http://127.0.0.1:8010/webhooks/queue/status
```

Expected shape:

```json
{
  "queued": 0,
  "max_size": 100,
  "workers": 2,
  "processed": 0,
  "failed": 0,
  "started": true
}
```

## 7. Supabase webhook URL

In Supabase, create a Database Webhook for:

```text
table: public.files
event: INSERT
method: POST
url: https://your-backend-url/webhooks/supabase/files
```

For local testing with a tunnel, use:

```text
https://your-tunnel-url/webhooks/supabase/files
```

If `WEBHOOK_SECRET` is set in `backend/.env`, send either:

```text
X-Webhook-Secret: change-this-secret
```

or:

```text
Authorization: Bearer change-this-secret
```

## 8. Local webhook test

This only tests that the webhook accepts a payload and pushes it into the queue.
Use a real `file_id` from Supabase if you want the pipeline worker to successfully download and process the file.

```bash
curl -X POST http://127.0.0.1:8010/webhooks/supabase/files \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-this-secret" \
  -d '{
    "type": "INSERT",
    "table": "files",
    "record": {
      "file_id": "00000000-0000-0000-0000-000000000001",
      "filename": "sample.pdf",
      "file_url": "https://example.com/sample.pdf",
      "file_type": "application/pdf",
      "file_size": 123
    }
  }'
```

Expected response:

```json
{
  "accepted": true,
  "file_id": "00000000-0000-0000-0000-000000000001",
  "queue": {
    "queued": 1,
    "max_size": 100,
    "workers": 2,
    "processed": 0,
    "failed": 0,
    "started": true
  }
}
```

If the `file_id` is fake, the worker will retry and then mark it failed. That is okay for a webhook acceptance test.

## 9. What happens after everything is running

Flow:

```text
ingest.py polls email inbox
  -> email attachment found
  -> stored in Supabase bucket file_storage
  -> row inserted in public.files
  -> Supabase calls /webhooks/supabase/files
  -> backend accepts job into bounded queue
  -> queue worker fetches DB row and downloads file from file_storage
  -> queue worker saves the PDF to /tmp/patrarekha-webhook-pdfs
  -> backend runs .venv/bin/python main.py temp_pdf_path --cleanup-input
  -> main.py runs OCR, chunking, embeddings, and Pinecone upload
  -> temp PDF and generated temp JSON are deleted
```

Pipeline handoff:

```text
backend/webhooks/service/processor.py -> run_document_pipeline(document, content)
main.py -> run_pipeline(pdf_path, cleanup_input=True)
```
