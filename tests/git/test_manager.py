"""Tests for the dulwich-based GitManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from aio_cortex.git.manager import GitManager


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

    async def test_detects_file_changes(
        self, git_manager: GitManager, config_dir: Path
    ) -> None:
        await git_manager.commit_changes("First")
        (config_dir / "new_file.yaml").write_text("new: content\n")
        sha = await git_manager.commit_changes("Added new file")
        assert sha is not None


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


class TestCleanup:
    async def test_no_cleanup_needed(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Only commit")
        result = await git_manager.cleanup_commits()
        assert result["success"] is True
        assert "No cleanup needed" in result["message"]
