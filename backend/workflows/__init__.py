"""
Agentic workflow layer for the chat endpoint.

Contains the compare / export workflows that turn the single-shot RAG
chatbot into an orchestratable pipeline:

    PLAN -> RETRIEVE -> COMPARE -> VERIFY -> canonical result -> render

The LLM is only used where reasoning is required; every output format
(chat markdown, PDF, XLSX, future UI) consumes a canonical result object
from ``workflows.models``.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
AI_PIPELINE_DIR = PROJECT_ROOT / "AI pipeline"

for _path in (AI_PIPELINE_DIR, BACKEND_DIR, PROJECT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))