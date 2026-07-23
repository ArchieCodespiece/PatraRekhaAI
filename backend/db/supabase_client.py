"""Initialized Supabase client for backend scripts."""

import os

from supabase import Client, create_client


def get_supabase_client() -> Client:
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(supabase_url, supabase_key)


supabase = get_supabase_client()
