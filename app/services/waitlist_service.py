"""Waitlist service — thin adapter around the Supabase `waitlist` table."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.supabase_client import get_supabase
from app.schemas.waitlist import WaitlistResponse, WaitlistCountResponse


async def add_to_waitlist(email: str) -> WaitlistResponse:
    """
    Insert `email` into the waitlist table.
    Never raises — always returns WaitlistResponse (avoids 500).
    """
    try:
        settings = get_settings()
        if not (settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key)):
            return WaitlistResponse(success=False, message="Waitlist service is not configured. Please contact support.")

        client = get_supabase()
        result = (
            client.table("waitlist")
            .insert({"email": email})
            .execute()
        )
        if result.data:
            return WaitlistResponse(success=True, message="Added to waitlist")
        return WaitlistResponse(success=True, message="Added to waitlist")

    except Exception as exc:
        err = str(exc).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            return WaitlistResponse(success=False, message="Email already registered")
        return WaitlistResponse(success=False, message="Could not add to waitlist. Please try again later.")


async def get_waitlist_count() -> WaitlistCountResponse:
    """Return the total number of entries on the waitlist."""
    settings = get_settings()
    if not (settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key)):
        return WaitlistCountResponse(count=0)

    try:
        client = get_supabase()
        result = (
            client.table("waitlist")
            .select("id", count="exact")
            .execute()
        )
        count = result.count if result.count is not None else len(result.data or [])
        return WaitlistCountResponse(count=count)
    except Exception:
        return WaitlistCountResponse(count=0)
