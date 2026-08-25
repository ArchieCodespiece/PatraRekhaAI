"""Initialized Supabase client for backend scripts."""

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


# Always load the backend-specific .env file.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def get_supabase_client() -> Client:
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    return create_client(supabase_url, supabase_key)


supabase = get_supabase_client()