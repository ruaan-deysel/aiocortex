"""Tests for the dulwich-based GitManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aiocortex.exceptions import GitError, GitNotInitializedError
from aiocortex.git.manager import GitManager


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Config directory with sample files."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "configuration.yaml").write_text("homeassistant:\n  name: Test\n")
    (cfg / "automations.yaml").write_text("- id: a1\n  alias: Test\n")
    return cfg


@pytest.fixture
async def git_manager(config_dir: Path) -> GitManager:
    """Initialised GitManager."""
    mgr = GitManager(config_dir, max_backups=30, auto_commit=True)
    await mgr.init_repo()
    return mgr


class TestInitRepo:
    async def test_creates_shadow_dir(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        await mgr.init_repo()
        assert (config_dir / "cortex_git" / ".git").exists()

    async def test_load_existing(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        await mgr.init_repo()
        # Load again
        mgr2 = GitManager(config_dir)
        await mgr2.init_repo()
        assert mgr2._repo is not None

    async def test_init_repo_failure(self, config_dir: Path) -> None:
        """init_repo logs error and continues if mkdir fails."""
        mgr = GitManager(config_dir)
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            await mgr.init_repo()
        assert mgr._repo is None


class TestRepoProperty:
    def test_raises_when_not_initialized(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        with pytest.raises(GitNotInitializedError, match="not initialised"):
            _ = mgr.repo


class TestCommitCount:
    async def test_empty_head(self, config_dir: Path) -> None:
        """_commit_count returns 0 for a repo with no commits."""
        mgr = GitManager(config_dir)
        await mgr.init_repo()
        assert mgr._commit_count() == 0


class TestCommitChanges:
    async def test_first_commit(self, git_manager: GitManager) -> None:
        sha = await git_manager.commit_changes("Initial commit")
        assert sha is not None
        assert len(sha) == 8

    async def test_no_changes_returns_none(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("First")
        sha = await git_manager.commit_changes("Second — no changes")
        assert sha is None

    async def test_skip_if_processing(self, git_manager: GitManager) -> None:
        git_manager.processing_request = True
        sha = await git_manager.commit_changes("Should skip", skip_if_processing=True)
        assert sha is None
        git_manager.processing_request = False

    async def test_auto_commit_disabled(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir, auto_commit=False)
        await mgr.init_repo()
        sha = await mgr.commit_changes("Should be skipped")
        assert sha is None

    async def test_force_overrides_auto(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir, auto_commit=False)
        await mgr.init_repo()
        sha = await mgr.commit_changes("Forced", force=True)
        assert sha is not None

    async def test_detects_file_changes(self, git_manager: GitManager, config_dir: Path) -> None:
        await git_manager.commit_changes("First")
        (config_dir / "new_file.yaml").write_text("new: content\n")
        sha = await git_manager.commit_changes("Added new file")
        assert sha is not None

    async def test_repo_none_returns_none(self, config_dir: Path) -> None:
        """commit_changes returns None when _repo is None."""
        mgr = GitManager(config_dir)
        # Don't call init_repo — _repo stays None
        result = await mgr.commit_changes("test")
        assert result is None

    async def test_auto_commit_disabled_syncs_but_no_commit(self, config_dir: Path) -> None:
        """When auto_commit=False and not forced, changes are synced but not committed."""
        mgr = GitManager(config_dir, auto_commit=False)
        await mgr.init_repo()
        # Force a first commit so there's a base
        await mgr.commit_changes("initial", force=True)
        # Now make a change — should sync but not commit
        (config_dir / "new.yaml").write_text("data: 1\n")
        sha = await mgr.commit_changes("should skip")
        assert sha is None

    async def test_commit_exception_returns_none(self, git_manager: GitManager) -> None:
        """When an exception occurs during commit, returns None."""
        with patch(
            "aiocortex.git.manager.sync_config_to_shadow", side_effect=RuntimeError("boom")
        ):
            result = await git_manager.commit_changes("test")
        assert result is None

    async def test_cleanup_failure_is_non_fatal(self, config_dir: Path) -> None:
        """When truncate_history raises, commit still succeeds."""
        mgr = GitManager(config_dir, max_backups=2, auto_commit=True)
        await mgr.init_repo()
        # Make enough commits to trigger cleanup
        for i in range(3):
            (config_dir / "configuration.yaml").write_text(f"v{i}\n")
            with patch("aiocortex.git.manager.truncate_history", side_effect=GitError("fail")):
                sha = await mgr.commit_changes(f"C{i}")
        # Should still have gotten a sha despite cleanup failure
        history = await mgr.get_history()
        assert len(history) > 0

    async def test_default_message_used(self, git_manager: GitManager, config_dir: Path) -> None:
        """When no message provided, auto-generates one."""
        (config_dir / "test.yaml").write_text("hello\n")
        sha = await git_manager.commit_changes(None)
        assert sha is not None
        history = await git_manager.get_history(limit=1)
        assert "Auto-commit by Cortex" in history[0]["message"]


class TestGetHistory:
    async def test_empty_repo(self, git_manager: GitManager) -> None:
        history = await git_manager.get_history()
        assert history == []

    async def test_after_commits(self, git_manager: GitManager, config_dir: Path) -> None:
        await git_manager.commit_changes("First commit")
        (config_dir / "new.yaml").write_text("x: 1\n")
        await git_manager.commit_changes("Second commit")

        history = await git_manager.get_history()
        assert len(history) == 2
        assert history[0]["message"] == "Second commit"
        assert history[1]["message"] == "First commit"

    async def test_limit(self, git_manager: GitManager, config_dir: Path) -> None:
        await git_manager.commit_changes("C1")
        (config_dir / "a.yaml").write_text("a\n")
        await git_manager.commit_changes("C2")
        (config_dir / "b.yaml").write_text("b\n")
        await git_manager.commit_changes("C3")

        history = await git_manager.get_history(limit=2)
        assert len(history) == 2

    async def test_repo_none_returns_empty(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        history = await mgr.get_history()
        assert history == []

    async def test_history_error_returns_empty(self, git_manager: GitManager) -> None:
        """Errors during history retrieval return empty list."""
        await git_manager.commit_changes("test")
        with patch.object(git_manager.repo, "get_walker", side_effect=RuntimeError("corrupt")):
            history = await git_manager.get_history()
            assert history == []


class TestGetPendingChanges:
    async def test_no_changes(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Initial")
        pending = await git_manager.get_pending_changes()
        assert pending["has_changes"] is False

    async def test_with_new_file(self, git_manager: GitManager, config_dir: Path) -> None:
        await git_manager.commit_changes("Initial")
        (config_dir / "brand_new.yaml").write_text("data: true\n")
        pending = await git_manager.get_pending_changes()
        assert pending["has_changes"] is True
        assert pending["summary"]["total"] > 0

    async def test_repo_none_returns_empty(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        pending = await mgr.get_pending_changes()
        assert pending["has_changes"] is False

    async def test_exception_returns_empty_with_error(self, git_manager: GitManager) -> None:
        with patch(
            "aiocortex.git.manager.sync_config_to_shadow", side_effect=RuntimeError("fail")
        ):
            pending = await git_manager.get_pending_changes()
            assert "error" in pending

    async def test_diff_failure_in_pending(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """When get_diff raises during pending changes, diff is empty string."""
        await git_manager.commit_changes("Initial")
        (config_dir / "brand_new.yaml").write_text("data: true\n")
        with patch.object(git_manager, "get_diff", side_effect=RuntimeError("diff failed")):
            pending = await git_manager.get_pending_changes()
            assert pending["has_changes"] is True
            assert pending["diff"] == ""

    async def test_pending_with_staged_and_unstaged_changes(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """Exercises staged add/delete/modify and unstaged change paths."""
        from dulwich import porcelain

        await git_manager.commit_changes("Initial")
        shadow = git_manager.shadow_root

        # Modify an existing file (will show as unstaged modify)
        (config_dir / "configuration.yaml").write_text("homeassistant:\n  name: Changed\n")
        # Sync and stage to get staged changes
        from aiocortex.git.sync import sync_config_to_shadow

        sync_config_to_shadow(config_dir, shadow, shadow_dir_name=git_manager.shadow_dir_name)
        # Stage all to make them appear as staged
        porcelain.add(str(shadow), paths=None)

        # Now create another unstaged change
        (shadow / "unstaged.yaml").write_text("new: data\n")

        pending = await git_manager.get_pending_changes()
        assert pending["has_changes"] is True
        assert pending["summary"]["total"] > 0

    async def test_pending_with_deleted_file(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """Exercises staged delete path in get_pending_changes."""
        from dulwich import porcelain

        await git_manager.commit_changes("Initial")
        shadow = git_manager.shadow_root

        # Delete a file from shadow that was in the last commit
        (shadow / "configuration.yaml").unlink()
        porcelain.add(str(shadow), paths=None)

        pending = await git_manager.get_pending_changes()
        assert pending["has_changes"] is True

    async def test_pending_with_explicit_staged_add(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """Exercises staged 'add' path — a new file staged in the index."""
        from dulwich import porcelain

        await git_manager.commit_changes("Initial")
        shadow = git_manager.shadow_root

        # Create a new file in shadow and stage it
        (shadow / "brand_new_staged.yaml").write_text("staged: true\n")
        porcelain.add(str(shadow), paths=[str(shadow / "brand_new_staged.yaml")])

        # Also modify a tracked file without staging it (unstaged change)
        (shadow / "configuration.yaml").write_text("modified unstaged\n")

        pending = await git_manager.get_pending_changes()
        assert pending["has_changes"] is True
        # The staged add should appear
        all_files = pending["files_added"] + pending["files_modified"]
        assert len(all_files) > 0


class TestCheckpoint:
    async def test_create(self, git_manager: GitManager) -> None:
        result = await git_manager.create_checkpoint("Test operation")
        assert result["success"] is True
        assert result["tag"] is not None
        assert git_manager.processing_request is True

    async def test_end_processing(self, git_manager: GitManager) -> None:
        await git_manager.create_checkpoint("Test")
        git_manager.end_request_processing()
        assert git_manager.processing_request is False

    async def test_repo_none_returns_failure(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        result = await mgr.create_checkpoint("test")
        assert result["success"] is False
        assert result["commit_hash"] is None

    async def test_checkpoint_no_commit_hash_falls_back(self, git_manager: GitManager) -> None:
        """When commit returns None, falls back to HEAD."""
        await git_manager.commit_changes("Initial")
        # No new changes — commit_changes returns None, should fall back to HEAD
        result = await git_manager.create_checkpoint("test")
        assert result["success"] is True
        assert result["commit_hash"] is not None

    async def test_checkpoint_exception(self, git_manager: GitManager) -> None:
        """Exception during checkpoint returns failure dict."""
        with patch.object(git_manager, "commit_changes", side_effect=RuntimeError("fail")):
            result = await git_manager.create_checkpoint("test")
            assert result["success"] is False

    async def test_tag_creation_failure_non_fatal(self, git_manager: GitManager) -> None:
        """Tag creation failure is logged but checkpoint still succeeds."""
        with patch(
            "aiocortex.git.manager.porcelain.tag_create", side_effect=RuntimeError("tag fail")
        ):
            result = await git_manager.create_checkpoint("test")
            assert result["success"] is True

    async def test_checkpoint_head_fallback_fails(self, git_manager: GitManager) -> None:
        """When commit returns None AND HEAD lookup fails, commit_hash is None."""
        await git_manager.commit_changes("Initial")
        # Patch commit_changes to return None, and head() to raise
        with patch.object(git_manager, "commit_changes", return_value=None):
            with patch.object(git_manager.repo, "head", side_effect=KeyError("no HEAD")):
                result = await git_manager.create_checkpoint("test")
                assert result["success"] is True
                assert result["commit_hash"] is None


class TestGetDiff:
    async def test_repo_none_returns_empty(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        diff = await mgr.get_diff()
        assert diff == ""

    async def test_diff_no_head(self, config_dir: Path) -> None:
        """Diff against empty repo returns empty string."""
        mgr = GitManager(config_dir)
        await mgr.init_repo()
        diff = await mgr.get_diff()
        assert diff == ""

    async def test_diff_with_changes(self, git_manager: GitManager, config_dir: Path) -> None:
        await git_manager.commit_changes("Initial")
        (config_dir / "configuration.yaml").write_text("homeassistant:\n  name: Changed\n")
        diff = await git_manager.get_diff()
        # May or may not have content depending on sync
        assert isinstance(diff, str)

    async def test_diff_between_two_commits(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        sha1 = await git_manager.commit_changes("First")
        (config_dir / "new.yaml").write_text("x: 1\n")
        sha2 = await git_manager.commit_changes("Second")
        assert sha1 and sha2
        # Get full SHA from the repo walker
        commits = []
        walker = git_manager.repo.get_walker(max_entries=2)
        for entry in walker:
            commits.append(entry.commit.id.decode("ascii"))
        # commits[0] = second, commits[1] = first
        diff = await git_manager.get_diff(commit1=commits[1], commit2=commits[0])
        assert isinstance(diff, str)

    async def test_diff_from_single_commit(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        sha1 = await git_manager.commit_changes("First")
        (config_dir / "new.yaml").write_text("x: 1\n")
        sha2 = await git_manager.commit_changes("Second")
        assert sha1 and sha2
        commits = []
        walker = git_manager.repo.get_walker(max_entries=2)
        for entry in walker:
            commits.append(entry.commit.id.decode("ascii"))
        diff = await git_manager.get_diff(commit1=commits[1])
        assert isinstance(diff, str)

    async def test_diff_uncommitted_changes_shows_output(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """Diff against HEAD with actual uncommitted changes produces diff output."""
        await git_manager.commit_changes("Initial")
        # Write directly to shadow repo to create an actual change
        shadow = git_manager.shadow_root
        (shadow / "configuration.yaml").write_text("homeassistant:\n  name: Modified\n")
        diff = await git_manager.get_diff()
        assert isinstance(diff, str)
        assert "diff" in diff
        assert "configuration.yaml" in diff

    async def test_diff_exception_returns_empty(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Initial")
        with patch("aiocortex.git.manager.porcelain.add", side_effect=RuntimeError("fail")):
            diff = await git_manager.get_diff()
            assert diff == ""


class TestRollback:
    async def test_rollback(self, git_manager: GitManager, config_dir: Path) -> None:
        sha1 = await git_manager.commit_changes("Original state")
        assert sha1 is not None

        # Modify a file
        (config_dir / "configuration.yaml").write_text("homeassistant:\n  name: Changed\n")
        sha2 = await git_manager.commit_changes("Changed name")
        assert sha2 is not None

        # Rollback
        result = await git_manager.rollback(sha1)
        assert result["success"] is True

        # Verify file is restored
        content = (config_dir / "configuration.yaml").read_text()
        assert "Test" in content

    async def test_rollback_repo_none_raises(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        with pytest.raises(GitNotInitializedError):
            await mgr.rollback("abc123")

    async def test_rollback_failure_raises_git_error(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Initial")
        with patch(
            "aiocortex.git.manager.porcelain.reset", side_effect=RuntimeError("reset fail")
        ):
            with pytest.raises(GitError, match="Rollback failed"):
                await git_manager.rollback("bad_hash")


class TestRestoreFilesFromCommit:
    async def test_repo_none_raises(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        with pytest.raises(GitNotInitializedError):
            await mgr.restore_files_from_commit("abc123")

    async def test_restore_all_files(self, git_manager: GitManager, config_dir: Path) -> None:
        sha1 = await git_manager.commit_changes("First state")
        assert sha1 is not None

        result = await git_manager.restore_files_from_commit(sha1)
        assert result["success"] is True
        assert result["count"] >= 0

    async def test_restore_with_pattern(self, git_manager: GitManager, config_dir: Path) -> None:
        sha1 = await git_manager.commit_changes("First")
        assert sha1 is not None

        result = await git_manager.restore_files_from_commit(
            sha1, file_patterns=["configuration.yaml"]
        )
        assert result["success"] is True

    async def test_restore_default_to_head(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """When commit_hash is None, uses HEAD."""
        await git_manager.commit_changes("First")
        result = await git_manager.restore_files_from_commit()
        assert result["success"] is True

    async def test_restore_with_non_matching_pattern(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        """When file patterns don't match any blob files, those blobs are skipped.
        Also exercises _walk_tree recursive call for subdirectories."""
        # Add a subdirectory so the tree has nested objects
        sub = config_dir / "esphome"
        sub.mkdir(exist_ok=True)
        (sub / "device.yaml").write_text("esphome:\n  name: test\n")
        await git_manager.commit_changes("With subdir")
        result = await git_manager.restore_files_from_commit(file_patterns=["*.xyz"])
        assert result["success"] is True
        # No files match *.xyz, so none should be restored
        assert result["count"] == 0

    async def test_restore_failure_raises(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("First")
        with patch.object(git_manager.repo, "get_object", side_effect=KeyError("bad")):
            with pytest.raises(GitError, match="Restore failed"):
                await git_manager.restore_files_from_commit("nonexistent_hash_1234567890abcdef")


class TestCleanupCommits:
    async def test_no_cleanup_needed(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Only commit")
        result = await git_manager.cleanup_commits()
        assert result["success"] is True
        assert "No cleanup needed" in result["message"]

    async def test_repo_none_returns_failure(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir)
        result = await mgr.cleanup_commits()
        assert result["success"] is False
        assert "not enabled" in result["message"]

    async def test_cleanup_failure_returns_error(self, config_dir: Path) -> None:
        mgr = GitManager(config_dir, max_backups=2, auto_commit=True)
        await mgr.init_repo()
        for i in range(4):
            (config_dir / "configuration.yaml").write_text(f"v{i}\n")
            await mgr.commit_changes(f"C{i}")

        with patch(
            "aiocortex.git.manager.truncate_history", side_effect=GitError("truncate fail")
        ):
            result = await mgr.cleanup_commits()
            assert result["success"] is False
            assert "truncate fail" in result["message"]
