1. # Backend API

cd D:\Patrarekhav3\PatraRekhaAI\backend
..\backend\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --app-dir backend


# 2. Email ingestion

cd D:\Patrarekhav3\PatraRekhaAI\backend\email-ingestion
..\..\backend\.venv\Scripts\python.exe ingest.py

# 3. Frontend

cd D:\Patrarekhav3\PatraRekhaAI\frontend
npm run dev

# 4. ngrok tunnel for Supabase webhook

ngrok http 8001