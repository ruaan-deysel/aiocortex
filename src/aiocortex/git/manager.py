"""Git versioning manager using dulwich (no git binary required).

Ported from ``app/services/git_manager.py`` in the HA Vibecode Agent add-on.
All GitPython / subprocess calls have been replaced with dulwich equivalents.

All public async methods delegate to synchronous helpers via
``asyncio.to_thread`` so that dulwich I/O never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dulwich import porcelain
from dulwich.repo import Repo

from ..exceptions import GitError, GitNotInitializedError
from .cleanup import truncate_history
from .sync import sync_config_to_shadow, sync_shadow_to_config

logger = logging.getLogger(__name__)

_AUTHOR = b"Cortex <cortex@homeassistant.local>"


class GitManager:
    """Manages a shadow git repository for HA config versioning.

    All git operations happen inside ``config_path / shadow_dir_name``.
    The constructor accepts plain values — no environment variables are read.
    """

    def __init__(
        self,
        config_path: Path,
        *,
        max_backups: int = 30,
        auto_commit: bool = True,
        shadow_dir_name: str = "cortex_git",
    ) -> None:
        self.config_path = config_path.resolve()
        self.shadow_root = self.config_path / shadow_dir_name
        self.shadow_dir_name = shadow_dir_name
        self.max_backups = max_backups
        self.auto_commit = auto_commit
        self.processing_request = False

        self._repo: Repo | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_repo_sync(self) -> None:
        """Synchronous init — called via ``asyncio.to_thread``."""
        self.shadow_root.mkdir(parents=True, exist_ok=True)
        if (self.shadow_root / ".git").exists():
            self._repo = Repo(str(self.shadow_root))
            logger.info("Git shadow repository loaded from %s", self.shadow_root)
        else:
            self._repo = Repo.init(str(self.shadow_root))
            # Configure user identity
            config = self._repo.get_config()
            config.set((b"user",), b"name", b"Cortex")
            config.set((b"user",), b"email", b"cortex@homeassistant.local")
            config.write_to_path()
            logger.info("Git shadow repository initialised in %s", self.shadow_root)

    async def init_repo(self) -> None:
        """Initialise (or load) the shadow repository."""
        try:
            await asyncio.to_thread(self._init_repo_sync)
        except Exception as exc:
            logger.error("Failed to initialise git: %s", exc)

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            raise GitNotInitializedError(
                "Shadow repository not initialised — call init_repo() first"
            )
        return self._repo

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _is_dirty(self) -> bool:
        """Return ``True`` if there are uncommitted changes in the shadow repo."""
        status = porcelain.status(str(self.shadow_root))
        staged = status.staged
        unstaged = status.unstaged
        untracked = status.untracked
        return bool(
            staged.get("add")
            or staged.get("delete")
            or staged.get("modify")
            or unstaged
            or untracked
        )

    def _commit_count(self) -> int:
        """Count first-parent commits reachable from HEAD."""
        try:
            head = self.repo.head()
        except KeyError:
            return 0

        count = 0
        current: bytes | None = head
        while current:
            count += 1
            commit = self.repo.get_object(current)
            current = commit.parents[0] if commit.parents else None
        return count

    # ------------------------------------------------------------------
    # Core: commit
    # ------------------------------------------------------------------

    def _commit_changes_sync(
        self,
        message: str | None = None,
        *,
        force: bool = False,
    ) -> str | None:
        """Synchronous commit — called via ``asyncio.to_thread``."""
        sync_config_to_shadow(
            self.config_path,
            self.shadow_root,
            shadow_dir_name=self.shadow_dir_name,
        )

        if not self._is_dirty():
            logger.debug("No changes to commit")
            return None

        if not self.auto_commit and not force:
            logger.debug("Auto-commit disabled, changes synced but not committed")
            return None

        # Stage all changes
        porcelain.add(str(self.shadow_root), paths=None)  # stages everything

        if not message:
            message = f"Auto-commit by Cortex at {datetime.now(UTC).isoformat()}"

        sha = porcelain.commit(
            str(self.shadow_root),
            message=message.encode("utf-8"),
            author=_AUTHOR,
            committer=_AUTHOR,
        )
        short_hash = sha.decode("ascii")[:8]
        logger.info("Committed changes: %s — %s", short_hash, message)

        # Cleanup if needed
        commit_count = self._commit_count()
        if commit_count >= self.max_backups:
            commits_to_keep = max(10, self.max_backups - 10)
            logger.info(
                "Cleanup triggered: %d commits >= max %d, keeping %d",
                commit_count,
                self.max_backups,
                commits_to_keep,
            )
            try:
                truncate_history(self.shadow_root, commits_to_keep)
                # Reload repo after truncation
                self._repo = Repo(str(self.shadow_root))
            except Exception as exc:
                logger.warning("Cleanup failed: %s", exc)

        return short_hash

    async def commit_changes(
        self,
        message: str | None = None,
        *,
        skip_if_processing: bool = False,
        force: bool = False,
    ) -> str | None:
        """Sync config → shadow and commit if there are changes.

        Returns the short commit hash, or ``None`` if nothing was committed.
        """
        if self._repo is None:
            return None

        if skip_if_processing and self.processing_request:
            logger.debug("Skipping auto-commit — request processing in progress")
            return None

        try:
            return await asyncio.to_thread(self._commit_changes_sync, message, force=force)
        except Exception as exc:
            logger.error("Failed to commit changes: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------

    async def create_checkpoint(self, user_request: str) -> dict[str, Any]:
        """Create a tagged checkpoint before a multi-step operation."""
        if self._repo is None:
            return {
                "success": False,
                "message": "Git versioning not enabled",
                "commit_hash": None,
                "tag": None,
            }

        try:
            commit_hash = await self.commit_changes(
                f"Checkpoint before: {user_request}",
                skip_if_processing=False,
                force=True,
            )

            if not commit_hash:
                try:
                    commit_hash = self.repo.head().decode("ascii")[:8]
                except Exception:
                    commit_hash = None

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            tag_name = f"checkpoint_{timestamp}"

            if commit_hash:
                try:
                    await asyncio.to_thread(
                        porcelain.tag_create,
                        str(self.shadow_root),
                        tag_name.encode("utf-8"),
                        message=f"Checkpoint before: {user_request}".encode(),
                        author=_AUTHOR,
                    )
                    logger.info("Created checkpoint tag: %s", tag_name)
                except Exception as exc:
                    logger.warning("Failed to create tag: %s", exc)

            self.processing_request = True

            return {
                "success": True,
                "message": f"Checkpoint created: {tag_name}",
                "commit_hash": commit_hash,
                "tag": tag_name,
                "timestamp": timestamp,
            }
        except Exception as exc:
            logger.error("Failed to create checkpoint: %s", exc)
            return {
                "success": False,
                "message": f"Failed to create checkpoint: {exc}",
                "commit_hash": None,
                "tag": None,
            }

    def end_request_processing(self) -> None:
        """Re-enable auto-commits after request processing."""
        self.processing_request = False

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _get_history_sync(self, limit: int = 20) -> list[dict[str, Any]]:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        commits: list[dict[str, Any]] = []
        walker = self.repo.get_walker(max_entries=limit)
        for entry in walker:
            commit = entry.commit
            commits.append(
                {
                    "hash": commit.id.decode("ascii")[:8],
                    "message": commit.message.decode("utf-8", errors="replace").strip(),
                    "author": commit.author.decode("utf-8", errors="replace"),
                    "date": datetime.fromtimestamp(commit.commit_time, tz=UTC).isoformat(),
                    "files_changed": len(commit.parents),  # Approximation
                }
            )
        return commits

    async def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the last *limit* commits."""
        if self._repo is None:
            return []

        try:
            return await asyncio.to_thread(self._get_history_sync, limit)
        except Exception as exc:
            logger.error("Failed to get history: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Pending changes
    # ------------------------------------------------------------------

    def _get_pending_changes_sync(self) -> dict[str, Any]:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        sync_config_to_shadow(
            self.config_path,
            self.shadow_root,
            shadow_dir_name=self.shadow_dir_name,
        )

        status = porcelain.status(str(self.shadow_root))

        files_modified: list[str] = []
        files_added: list[str] = []
        files_deleted: list[str] = []

        # Staged changes
        for p in status.staged.get("add", []):
            files_added.append(p.decode("utf-8", errors="replace"))
        for p in status.staged.get("delete", []):
            files_deleted.append(p.decode("utf-8", errors="replace"))
        for p in status.staged.get("modify", []):
            files_modified.append(p.decode("utf-8", errors="replace"))

        # Unstaged changes
        for p in status.unstaged:
            path_str = p.decode("utf-8", errors="replace")
            if path_str not in files_modified:
                files_modified.append(path_str)

        # Untracked files
        for p in status.untracked:
            path_str = p if isinstance(p, str) else p.decode("utf-8", errors="replace")
            if path_str not in files_added:
                files_added.append(path_str)

        has_changes = bool(files_modified or files_added or files_deleted)

        return {
            "has_changes": has_changes,
            "files_modified": files_modified,
            "files_added": files_added,
            "files_deleted": files_deleted,
            "summary": {
                "modified": len(files_modified),
                "added": len(files_added),
                "deleted": len(files_deleted),
                "total": len(files_modified) + len(files_added) + len(files_deleted),
            },
        }

    async def get_pending_changes(self) -> dict[str, Any]:
        """Return uncommitted changes between config and the last commit."""
        empty: dict[str, Any] = {
            "has_changes": False,
            "files_modified": [],
            "files_added": [],
            "files_deleted": [],
            "summary": {"modified": 0, "added": 0, "deleted": 0, "total": 0},
        }
        if self._repo is None:
            return empty

        try:
            result = await asyncio.to_thread(self._get_pending_changes_sync)

            if result["has_changes"]:
                try:
                    result["diff"] = await self.get_diff()
                except Exception:
                    result["diff"] = ""
            else:
                result["diff"] = ""

            return result
        except Exception as exc:
            logger.error("Failed to get pending changes: %s", exc)
            return {**empty, "error": str(exc)}

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def _get_diff_sync(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
    ) -> str:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        import io

        from dulwich.patch import write_tree_diff

        repo = self.repo
        buf = io.BytesIO()

        if commit1 and commit2:
            tree1 = repo.get_object(commit1.encode()).tree
            tree2 = repo.get_object(commit2.encode()).tree
            write_tree_diff(buf, repo.object_store, tree1, tree2)
        elif commit1:
            tree1 = repo.get_object(commit1.encode()).tree
            head_commit = repo.get_object(repo.head())
            write_tree_diff(buf, repo.object_store, tree1, head_commit.tree)
        else:
            # Diff against HEAD
            try:
                head_commit = repo.get_object(repo.head())
                head_tree = head_commit.tree
            except KeyError:
                return ""

            # Stage everything to get a complete diff
            porcelain.add(str(self.shadow_root), paths=None)
            index = repo.open_index()

            from dulwich.diff_tree import tree_changes

            index_tree = index.commit(repo.object_store)
            for change in tree_changes(repo.object_store, head_tree, index_tree):
                old_path = change.old.path.decode() if change.old.path else "/dev/null"
                new_path = change.new.path.decode() if change.new.path else "/dev/null"
                buf.write(f"diff --git a/{old_path} b/{new_path}\n".encode())

        return buf.getvalue().decode("utf-8", errors="replace")

    async def get_diff(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
    ) -> str:
        """Return a diff string.  Without arguments, returns uncommitted changes."""
        if self._repo is None:
            return ""

        try:
            return await asyncio.to_thread(self._get_diff_sync, commit1, commit2)
        except Exception as exc:
            logger.error("Failed to get diff: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _rollback_sync(self, commit_hash: str) -> dict[str, Any]:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        self._commit_changes_sync(f"Before rollback to {commit_hash}", force=True)

        porcelain.reset(
            str(self.shadow_root),
            "hard",
            treeish=commit_hash.encode("utf-8"),
        )

        sync_shadow_to_config(
            self.shadow_root,
            self.config_path,
            delete_missing=True,
            shadow_dir_name=self.shadow_dir_name,
        )

        logger.info("Rolled back to commit: %s", commit_hash)
        return {
            "success": True,
            "commit": commit_hash,
            "message": f"Rolled back to {commit_hash}",
        }

    async def rollback(self, commit_hash: str) -> dict[str, Any]:
        """Hard-reset the shadow repo to *commit_hash* and sync back to config."""
        if self._repo is None:
            raise GitNotInitializedError("Git versioning not enabled")

        try:
            return await asyncio.to_thread(self._rollback_sync, commit_hash)
        except (GitNotInitializedError, GitError):
            raise
        except Exception as exc:
            logger.error("Failed to rollback: %s", exc)
            raise GitError(f"Rollback failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Restore files from commit
    # ------------------------------------------------------------------

    def _restore_files_from_commit_sync(
        self,
        commit_hash: str | None = None,
        file_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        repo = self.repo
        if not commit_hash:
            commit_hash = repo.head().decode("ascii")

        commit_sha = commit_hash.encode("ascii") if len(commit_hash) < 40 else commit_hash.encode()
        # Resolve short hash
        full_sha = None
        for sha in repo.object_store:
            if sha.decode("ascii").startswith(commit_hash):
                full_sha = sha
                break
        if full_sha is None:
            full_sha = commit_sha

        commit_obj = repo.get_object(full_sha)
        tree = repo.get_object(commit_obj.tree)

        restored_files: list[str] = []

        def _walk_tree(tree_obj: Any, prefix: str = "") -> None:
            for item in tree_obj.items():
                name = item.path.decode("utf-8", errors="replace")
                full_name = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
                obj = repo.get_object(item.sha)
                if obj.type_name == b"tree":
                    _walk_tree(obj, full_name)
                elif obj.type_name == b"blob":
                    if file_patterns:
                        import fnmatch

                        if not any(fnmatch.fnmatch(full_name, p) for p in file_patterns):
                            return
                    # Write blob to shadow worktree
                    dest = self.shadow_root / full_name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(obj.data)
                    restored_files.append(full_name)

        _walk_tree(tree)

        # Sync to config
        sync_shadow_to_config(
            self.shadow_root,
            self.config_path,
            only_paths=restored_files if file_patterns else None,
            shadow_dir_name=self.shadow_dir_name,
        )

        return {
            "success": True,
            "commit": commit_hash,
            "restored_files": restored_files,
            "count": len(restored_files),
        }

    async def restore_files_from_commit(
        self,
        commit_hash: str | None = None,
        file_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Restore files from a specific commit into the shadow repo, then sync."""
        if self._repo is None:
            raise GitNotInitializedError("Git repository not available")

        try:
            return await asyncio.to_thread(
                self._restore_files_from_commit_sync, commit_hash, file_patterns
            )
        except (GitNotInitializedError, GitError):
            raise
        except Exception as exc:
            logger.error("Failed to restore files from commit: %s", exc)
            raise GitError(f"Restore failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_commits_sync(self) -> dict[str, Any]:
        """Synchronous implementation — called via ``asyncio.to_thread``."""
        commits_before = self._commit_count()
        if commits_before <= self.max_backups:
            return {
                "success": True,
                "message": (
                    f"No cleanup needed — {commits_before} commits (max: {self.max_backups})"
                ),
                "commits_before": commits_before,
                "commits_after": commits_before,
            }

        commits_after = truncate_history(self.shadow_root, self.max_backups)
        self._repo = Repo(str(self.shadow_root))
        logger.info("Manual cleanup: %d → %d commits", commits_before, commits_after)
        return {
            "success": True,
            "message": f"Cleanup complete: {commits_before} → {commits_after} commits",
            "commits_before": commits_before,
            "commits_after": commits_after,
        }

    async def cleanup_commits(self) -> dict[str, Any]:
        """Manually truncate history to *max_backups* commits."""
        if self._repo is None:
            return {
                "success": False,
                "message": "Git versioning not enabled",
                "commits_before": 0,
                "commits_after": 0,
            }

        try:
            return await asyncio.to_thread(self._cleanup_commits_sync)
        except Exception as exc:
            logger.error("Cleanup failed: %s", exc)
            return {
                "success": False,
                "message": f"Cleanup failed: {exc}",
                "commits_before": 0,
                "commits_after": 0,
            }
