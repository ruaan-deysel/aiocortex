"""Common response model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CortexResponse(BaseModel):
    """Standard API response envelope."""

    success: bool
    message: str | None = None
    data: Any | None = None
