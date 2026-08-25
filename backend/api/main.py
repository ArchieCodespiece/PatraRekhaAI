"""
PatraRekhaAI FastAPI Backend

Responsibilities:

- Authentication through Supabase
- Document listing/upload/deletion
- Semantic document search
- PDF chat using Pinecone + LLM
- Conversation persistence
- Recent chat history
- Loading previous conversations
- Gmail connection
- Webhook/document queue integration
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.supabase_client import supabase

from webhooks.router import router as webhooks_router
from webhooks.service.document_queue import document_queue


# ============================================================================
# PATHS / ENVIRONMENT
# ============================================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

AI_PIPELINE_DIR = REPO_ROOT / "AI pipeline"

if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main import run_pipeline


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await document_queue.start()

    try:
        yield
    finally:
        await document_queue.stop()


app = FastAPI(
    title="PatraRekha API",
    description="PatraRekhaAI document intelligence backend",
    lifespan=lifespan,
)


# ============================================================================
# CORS
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# WEBHOOKS
# ============================================================================

app.include_router(webhooks_router)


# ============================================================================
# ROUTERS
# ============================================================================

from api.health import router as health_router
from api.conversations import router as conversations_router
from api.documents import router as document_router
from api.chat import router as chat_router
from api.calendar import router as calendar_router
from api.gmail import router as gmail_router

app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(document_router)
app.include_router(chat_router)
app.include_router(calendar_router)
app.include_router(gmail_router)
