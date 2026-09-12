"""Tunable configuration for the workflow layer."""

from __future__ import annotations

import os

# LLM used for planning / structured extraction / verification.
WORKFLOW_LLM_MODEL = os.getenv(
    "WORKFLOW_LLM_MODEL",
    "openai/gpt-oss-120b",
)

# Per-stage model configuration. The core comparison (and its focused
# re-retrieve re-run) keeps the quality model; supporting LLM work —
# claim verification and overview synthesis — may drop to a faster/
# cheaper model without affecting the quality of the comparison itself.
COMPARE_MODEL = os.getenv(
    "COMPARE_MODEL",
    "openai/gpt-oss-120b",
)
FAST_COMPARE_MODEL = os.getenv(
    "FAST_COMPARE_MODEL",
    "openai/gpt-oss-20b",
)
VERIFY_MODEL = os.getenv(
    "VERIFY_MODEL",
    "openai/gpt-oss-20b",
)
OVERVIEW_MODEL = os.getenv(
    "OVERVIEW_MODEL",
    "openai/gpt-oss-20b",
)

# How many sections/verification batches may run concurrently. Kept at 2
# to stay safely under Groq RPM/rate limits; bump after profiling a real
# workload rather than guessing.
COMPARE_MAX_WORKERS = int(
    os.getenv("COMPARE_MAX_WORKERS", "2")
)

# Number of rows verified per batched LLM verification call.
COMPARE_VERIFY_BATCH_SIZE = int(
    os.getenv("COMPARE_VERIFY_BATCH_SIZE", "5")
)

# Semantic top-k used for per-section sub-queries (higher than chat's 4).
WORKFLOW_TOP_K_PER_DOCUMENT = int(
    os.getenv("WORKFLOW_TOP_K_PER_DOCUMENT", "8")
)

# Hard cap on how many chunks we pull per document for exhaustive coverage.
# Coverage beyond this is "selective" and flagged in the workflow result.
MAX_COVERAGE_CHUNKS = int(
    os.getenv("MAX_COVERAGE_CHUNKS", "100")
)

# Maximum number of comparison sections a planner may emit.
MAX_WORKFLOW_SECTIONS = int(
    os.getenv("MAX_WORKFLOW_SECTIONS", "8")
)

# Context budget passed to any single LLM call.
WORKFLOW_MAX_CONTEXT_CHARS = int(
    os.getenv("WORKFLOW_MAX_CONTEXT_CHARS", "16000")
)

# Number of repair attempts when the LLM returns invalid structured JSON.
COMPARE_REPAIR_ATTEMPTS = int(
    os.getenv("COMPARE_REPAIR_ATTEMPTS", "2")
)

# Evidence attached per document per row before synthesis.
EVIDENCE_PER_ROW_PER_DOCUMENT = 2

# Keyword-overlap ratio that is cheap enough to skip the LLM verifier.
MIN_KEYWORD_OVERLAP = float(
    os.getenv("MIN_KEYWORD_OVERLAP", "0.3")
)

# Default export format when a compare/export command does not name one.
DEFAULT_EXPORT_FORMAT = os.getenv(
    "DEFAULT_EXPORT_FORMAT",
    "xlsx",
)

# Signed-URL lifetime for generated export files.
EXPORT_LIFETIME_SECONDS = int(
    os.getenv("EXPORT_LIFETIME_SECONDS", str(60 * 60 * 24))
)

# Neutral phrase embedded once to enumerate all chunks of a document.
NEUTRAL_COVERAGE_QUERY = (
    "headings sections topics details facts entities names "
    "dates amounts responsibilities obligations rights terms"
)

# Seeded comparison sections used to prime the planner.
SEEDED_SECTIONS = [
    "Parties",
    "Dates",
    "Pricing",
    "Responsibilities",
    "Termination",
    "Penalties",
    "Confidentiality",
    "Liability",
    "Governing Law",
]

# Neutral scaffold used only when a document has no detectable headings,
# no content preview and no usable query terms. Never contract-biased.
NEUTRAL_SCAFFOLD_SECTIONS = [
    "Overview",
    "Key Details",
    "Notable Differences",
    "Facts & Figures",
]

# Unicode PDF font fallback for multilingual reports.
PDF_UNICODE_FONT = os.getenv(
    "PDF_UNICODE_FONT",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)