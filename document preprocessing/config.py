"""
config.py

Central configuration file for the OCR pipeline.
Modify paths and parameters here only.
"""

import os
import sys
import tempfile

# ==========================================================
# PATHS
# ==========================================================

# Poppler installation path (required by pdf2image on Windows)
if sys.platform == "win32":
    POPPLER_PATH = r"D:\Patrarekhav3\PatraRekhaAI\tools\poppler\Library\bin"
else:
    POPPLER_PATH = "/usr/bin"

# Base directory for per-user checkpoint files.
# Each checkpoint file is namespaced by owner_email and file_id to avoid
# lock conflicts when multiple pipelines run concurrently.
CHECKPOINT_DIR = os.path.join(
    os.getenv("OCR_CHECKPOINT_DIR", tempfile.gettempdir()),
    "patrarekha-checkpoints",
)


def get_checkpoint_path(file_id: str | None = None, owner_email: str | None = None) -> str:
    """Build a unique checkpoint path per user + document.

    Falls back to the legacy relative path when neither ``file_id`` nor
    ``owner_email`` is provided (backward compatibility with ad-hoc CLI usage).
    """
    if not file_id:
        # Legacy behaviour: relative checkpoint in CWD
        return "paddle2_checkpoint.json"

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    parts = []
    if owner_email:
        safe_owner = owner_email.replace("@", "_at_").replace(".", "_dot_").replace("/", "_")
        parts.append(safe_owner)
    parts.append(f"{file_id}_checkpoint.json")
    return os.path.join(CHECKPOINT_DIR, *parts)

# ==========================================================
# OCR SETTINGS
# ==========================================================

# OCR language
OCR_LANGUAGE = "en"

# Minimum confidence score for accepted OCR text
OCR_CONFIDENCE_THRESHOLD = 0.60

# ==========================================================
# PDF PROCESSING
# ==========================================================

# Image conversion DPI
DPI = 200

# Number of OCR pages processed in one batch
BATCH_SIZE = 10

# ==========================================================
# CHECKPOINT
# ==========================================================

# Temporary checkpoint file
CHECKPOINT = "paddle2_checkpoint.json"

# ==========================================================
# OUTPUT
# ==========================================================

# Default output JSON filename
DEFAULT_OUTPUT_JSON = "paddle_output.json"

# ==========================================================
# TABLE EXTRACTION
# ==========================================================

MIN_TABLE_COLUMNS = 2
MIN_TABLE_ROWS = 2

# ==========================================================
# FIELD EXTRACTION
# ==========================================================

# Minimum words required for a line to be considered a heading
MIN_HEADLINE_WORDS = 2

# ==========================================================
# IMAGE PREPROCESSING
# ==========================================================

GAUSSIAN_BLUR_KERNEL = (3, 3)

# ==========================================================
# OCR FILTERS
# ==========================================================

# Ignore OCR detections below this confidence
MIN_OCR_CONFIDENCE = 0.60