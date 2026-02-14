"""Common response model."""

from typing import Any

from pydantic import BaseModel


class CortexResponse(BaseModel):
    """Standard API response envelope."""

    success: bool
    message: str | None = None
    data: Any | None = None
