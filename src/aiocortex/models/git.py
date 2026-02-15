"""Git-related models."""

from __future__ import annotations

from pydantic import BaseModel


class CommitInfo(BaseModel):
    """A single commit in the history."""

    hash: str
    message: str
    author: str
    date: str
    files_changed: int


class PendingChangesSummary(BaseModel):
    """Counts of uncommitted changes."""

    modified: int = 0
    added: int = 0
    deleted: int = 0
    total: int = 0


class PendingChanges(BaseModel):
    """Full detail of uncommitted changes in the shadow repository."""

    has_changes: bool = False
    files_modified: list[str] = []
    files_added: list[str] = []
    files_deleted: list[str] = []
    summary: PendingChangesSummary = PendingChangesSummary()
    diff: str = ""
    error: str | None = None
