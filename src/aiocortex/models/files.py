"""File-related models."""

from __future__ import annotations

from pydantic import BaseModel


class FileInfo(BaseModel):
    """Metadata for a single file."""

    path: str
    name: str
    size: int
    modified: float
    is_yaml: bool


class FileWriteResult(BaseModel):
    """Result of a file-write operation."""

    success: bool
    path: str
    size: int
    backup: str | None = None
