"""
Configuration for the VectorStore module.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------
# Pinecone Credentials
# ---------------------------------------------------------------------

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    raise ValueError(
        "PINECONE_API_KEY not found in environment variables."
    )


# ---------------------------------------------------------------------
# Pinecone Index Configuration
# ---------------------------------------------------------------------

PINECONE_INDEX_NAME = "patrarekha-2"

PINECONE_CLOUD = "aws"

PINECONE_REGION = "us-east-1"


# ---------------------------------------------------------------------
# Vector Configuration
# ---------------------------------------------------------------------

VECTOR_DIMENSION = 3072

DISTANCE_METRIC = "cosine"


# ---------------------------------------------------------------------
# Upload Configuration
# ---------------------------------------------------------------------

UPSERT_BATCH_SIZE = 100


# ---------------------------------------------------------------------
# Namespace Configuration
# ---------------------------------------------------------------------

# Pinecone namespaces provide per-user isolation within a single index.
# When USE_NAMESPACES is True, every upsert/query/delete operation is
# scoped to a namespace derived from the owner_email.  Set to "true" or
# "false" to enable/disable the feature without changing call sites.
USE_NAMESPACES = os.getenv("USE_PINECONE_NAMESPACES", "true").lower() in (
    "1", "true", "yes",
)