"""
Configuration settings for the embedding pipeline.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# Gemini API
# =============================================================================

# Gemini API Key (stored in .env)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from the .env file.")


# =============================================================================
# Embedding Model
# =============================================================================

# Gemini embedding model
EMBEDDING_MODEL = "gemini-embedding-001"


# =============================================================================
# Embedding Parameters
# =============================================================================

# Number of chunks to send in one batch
# (You can tune this later based on API limits.)
BATCH_SIZE = 16

# Normalize embeddings before storing in Pinecone
NORMALIZE_EMBEDDINGS = True


# =============================================================================
# Cache Settings
# =============================================================================

# Cache generated embeddings locally to avoid repeated API calls
ENABLE_CACHE = False

CACHE_DIR = "cache"

CACHE_EXTENSION = ".pkl"