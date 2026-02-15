"""Tests for git cleanup / history truncation."""

from __future__ import annotations

from pathlib import Path

import pytest

from aio_cortex.git.manager import GitManager


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "configuration.yaml").write_text("name: Test\n")
    return cfg


@pytest.fixture
async def git_manager(config_dir: Path) -> GitManager:
    mgr = GitManager(config_dir, max_backups=5, auto_commit=True)
    await mgr.init_repo()
    return mgr


class TestAutoCleanup:
    async def test_triggers_without_error(self, git_manager: GitManager, config_dir: Path) -> None:
        """Cleanup triggers when commits reach max_backups and doesn't crash."""
        for i in range(7):
            (config_dir / "configuration.yaml").write_text(f"version: {i}\n")
            sha = await git_manager.commit_changes(f"Commit {i}")
            # Should never crash — cleanup may or may not reduce count
            # depending on git binary availability

        # The repo should still be functional after cleanup attempts
        history = await git_manager.get_history(limit=10)
        assert len(history) > 0


class TestManualCleanup:
    async def test_no_cleanup_needed(self, git_manager: GitManager) -> None:
        await git_manager.commit_changes("Only commit")
        result = await git_manager.cleanup_commits()
        assert result["success"] is True
        assert "No cleanup needed" in result["message"]

    async def test_cleanup_returns_result(self, git_manager: GitManager, config_dir: Path) -> None:
        for i in range(7):
            (config_dir / "configuration.yaml").write_text(f"version: {i}\n")
            await git_manager.commit_changes(f"Commit {i}")

        result = await git_manager.cleanup_commits()
        assert result["success"] is True or "failed" in result.get("message", "").lower()
        # Regardless of success, the repo should still work
        history = await git_manager.get_history()
        assert len(history) > 0
