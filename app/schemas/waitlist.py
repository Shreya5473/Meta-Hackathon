"""Pydantic schemas for the waitlist feature."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class WaitlistRequest(BaseModel):
    email: EmailStr


class WaitlistResponse(BaseModel):
    success: bool
    message: str


class WaitlistCountResponse(BaseModel):
    count: int
