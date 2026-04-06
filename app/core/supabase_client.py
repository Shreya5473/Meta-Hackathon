"""Supabase client singleton."""
from __future__ import annotations

from functools import lru_cache

from supabase import create_client, Client

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached Supabase client instance. Prefers service_role key for server-side inserts."""
    settings = get_settings()
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    return create_client(settings.supabase_url, key)
