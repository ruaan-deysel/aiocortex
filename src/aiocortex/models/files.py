"""File-related models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FilePathResult(BaseModel):
    """Base result for operations that target a single file path."""

    success: bool
    path: str


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


class FileAppendResult(FilePathResult):
    """Result of an append operation."""

    added_bytes: int
    total_size: int


class FileDeleteResult(FilePathResult):
    """Result of a delete operation."""


class YAMLConflict(BaseModel):
    """A semantic conflict encountered while preparing a YAML patch."""

    path: str
    reason: str


class YAMLPatchOperation(BaseModel):
    """Single semantic YAML mutation operation."""

    op: Literal["set", "remove", "merge_item"]
    path: list[str | int]
    value: Any | None = None
    merge_key: str | None = None


class YAMLPatchPreview(BaseModel):
    """Preview result for semantic YAML mutations before apply."""

    success: bool
    operations_applied: int = 0
    conflicts: list[YAMLConflict] = Field(default_factory=list)
    patched_content: str
    diff: str
