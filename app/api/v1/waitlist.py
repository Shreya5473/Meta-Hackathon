"""Waitlist API router — POST /waitlist and GET /waitlist/count."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.waitlist import WaitlistRequest, WaitlistResponse, WaitlistCountResponse
from app.services.waitlist_service import add_to_waitlist, get_waitlist_count

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistResponse)
async def join_waitlist(body: WaitlistRequest) -> WaitlistResponse:
    """
    Add an email address to the waitlist.

    - Validates email format automatically via Pydantic's `EmailStr`.
    - Returns `success: false` (HTTP 200) for duplicates or Supabase errors; never 500.
    """
    return await add_to_waitlist(body.email)


@router.get("/count", response_model=WaitlistCountResponse)
async def waitlist_count() -> WaitlistCountResponse:
    """Return the total number of people on the waitlist."""
    return await get_waitlist_count()
