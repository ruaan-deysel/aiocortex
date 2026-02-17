"""Git-related models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    files_modified: list[str] = Field(default_factory=list)
    files_added: list[str] = Field(default_factory=list)
    files_deleted: list[str] = Field(default_factory=list)
    summary: PendingChangesSummary = Field(default_factory=PendingChangesSummary)
    diff: str = ""
    error: str | None = None


class CheckpointResult(BaseModel):
    """Result for checkpoint creation."""

    success: bool
    message: str
    commit_hash: str | None = None
    tag: str | None = None
    timestamp: str | None = None


class RollbackResult(BaseModel):
    """Result of a rollback action."""

    success: bool
    commit: str
    message: str


class RestoreFilesResult(BaseModel):
    """Result of restoring files from a commit."""

    success: bool
    commit: str
    restored_files: list[str] = Field(default_factory=list)
    count: int = 0


class CleanupResult(BaseModel):
    """Result of history cleanup."""

    success: bool
    message: str
    commits_before: int
    commits_after: int


class TransactionOperation(BaseModel):
    """A staged file operation within a transaction."""

    op: Literal["write", "delete"]
    path: str
    content: str | None = None


class TransactionRollbackMetadata(BaseModel):
    """Rollback metadata emitted for consumers."""

    backup_files: list[str] = Field(default_factory=list)
    created_files: list[str] = Field(default_factory=list)
    touched_paths: list[str] = Field(default_factory=list)


class TransactionState(BaseModel):
    """Persistent transaction state."""

    transaction_id: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: Literal["open", "validated", "committed", "aborted", "failed"] = "open"
    operations: list[TransactionOperation] = Field(default_factory=list)
    rollback_metadata: TransactionRollbackMetadata = Field(
        default_factory=TransactionRollbackMetadata
    )
    created_at: datetime
    updated_at: datetime


class TransactionValidationResult(BaseModel):
    """Validation result before applying a transaction."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


class TransactionCommitResult(BaseModel):
    """Result returned after commit or failed commit attempt."""

    success: bool
    transaction: TransactionState
    commit_hash: str | None = None
    rollback_metadata: TransactionRollbackMetadata = Field(
        default_factory=TransactionRollbackMetadata
    )
    error: str | None = None


class TransactionAbortResult(BaseModel):
    """Result returned when aborting a transaction."""

    success: bool
    transaction: TransactionState
