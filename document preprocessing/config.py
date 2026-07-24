"""
config.py

Central configuration file for the OCR pipeline.
Modify paths and parameters here only.
"""

import os

# ==========================================================
# PATHS
# ==========================================================

# Poppler installation path (required by pdf2image on Windows)
POPPLER_PATH = r"/usr/bin"

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