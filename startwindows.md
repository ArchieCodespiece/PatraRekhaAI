1. # Backend API

cd D:\pat\PatraRekhaAI\backend
..\backend\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --app-dir backend


# 2. Email ingestion

cd D:\pat\PatraRekhaAI\backend\email-ingestion
..\..\backend\.venv\Scripts\python.exe ingest.py

# 3. Frontend

cd D:\pat\PatraRekhaAI\frontend
npm run dev

# 4. ngrok tunnel for Supabase webhook

ngrok http 8001