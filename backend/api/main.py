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

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
# RATE LIMITING
# ============================================================================

RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")

limiter = Limiter(key_func=get_remote_address)


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded. {exc.detail}",
        },
    )


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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# ============================================================================
# CORS
# ============================================================================

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
