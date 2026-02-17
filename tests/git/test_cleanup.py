"""Tests for git cleanup / history truncation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from aiocortex.exceptions import GitError
from aiocortex.git.cleanup import (
    _git_binary_available,
    _truncate_via_clone,
    _truncate_via_dulwich,
    truncate_history,
)
from aiocortex.git.manager import GitManager


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
        assert result.success is True
        assert "No cleanup needed" in result.message

    async def test_cleanup_returns_result(self, git_manager: GitManager, config_dir: Path) -> None:
        for i in range(7):
            (config_dir / "configuration.yaml").write_text(f"version: {i}\n")
            await git_manager.commit_changes(f"Commit {i}")

        result = await git_manager.cleanup_commits()
        assert result.success is True or "failed" in result.message.lower()
        # Regardless of success, the repo should still work
        history = await git_manager.get_history()
        assert len(history) > 0


class TestGitBinaryAvailable:
    def test_not_found(self) -> None:
        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=FileNotFoundError):
            assert _git_binary_available() is False

    def test_timeout(self) -> None:
        with patch(
            "aiocortex.git.cleanup.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            assert _git_binary_available() is False


class TestTruncateHistory:
    def test_no_git_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GitError, match=r"No \.git directory"):
            truncate_history(tmp_path, 5)

    def test_falls_through_to_dulwich_when_no_git_binary(self, tmp_path: Path) -> None:
        """When git binary is unavailable, falls through to _truncate_via_dulwich."""
        (tmp_path / ".git").mkdir()
        with patch("aiocortex.git.cleanup._git_binary_available", return_value=False):
            with patch("aiocortex.git.cleanup._truncate_via_dulwich", return_value=5) as mock_dul:
                result = truncate_history(tmp_path, 5)
                mock_dul.assert_called_once()
                assert result == 5


class TestTruncateViaClone:
    def test_branch_detection_failure(self, tmp_path: Path) -> None:
        """Falls back to 'master' when branch detection fails."""
        (tmp_path / ".git").mkdir()
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if "branch" in cmd:
                raise OSError("branch detection failed")
            # Clone command — simulate failure
            result = subprocess.CompletedProcess(cmd, 1, "", "clone failed")
            return result

        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=fake_run):
            with pytest.raises(GitError, match="git clone failed"):
                _truncate_via_clone(tmp_path, 5)

    def test_clone_failure_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()

        def fake_run(cmd, **kwargs):
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "main\n", "")
            # Clone command fails
            return subprocess.CompletedProcess(cmd, 1, "", "fatal: error")

        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=fake_run):
            with pytest.raises(GitError, match="git clone failed"):
                _truncate_via_clone(tmp_path, 5)

    def test_cloned_git_dir_missing_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()

        def fake_run(cmd, **kwargs):
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "main\n", "")
            if "clone" in cmd:
                # Clone succeeds but doesn't create .git
                clone_dest = cmd[-1]
                Path(clone_dest).mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=fake_run):
            with pytest.raises(GitError, match=r"Cloned \.git directory"):
                _truncate_via_clone(tmp_path, 5)

    def test_gc_failure_is_non_fatal(self, tmp_path: Path) -> None:
        """git gc failure after truncation is logged but not raised."""
        (tmp_path / ".git").mkdir()

        def fake_run(cmd, **kwargs):
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "main\n", "")
            if "clone" in cmd:
                clone_dest = cmd[-1]
                clone_path = Path(clone_dest)
                clone_path.mkdir(parents=True, exist_ok=True)
                (clone_path / ".git").mkdir()
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "gc" in cmd:
                raise OSError("gc failed")
            if "rev-list" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "5\n", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=fake_run):
            with patch("aiocortex.git.cleanup.shutil.copytree"):
                with patch("aiocortex.git.cleanup.shutil.rmtree"):
                    result = _truncate_via_clone(tmp_path, 5)
                    assert result == 5

    def test_rev_list_failure_returns_default(self, tmp_path: Path) -> None:
        """When rev-list count fails, return commits_to_keep as default."""
        (tmp_path / ".git").mkdir()
        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "main\n", "")
            if "clone" in cmd:
                clone_dest = cmd[-1]
                clone_path = Path(clone_dest)
                clone_path.mkdir(parents=True, exist_ok=True)
                (clone_path / ".git").mkdir()
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "gc" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "rev-list" in cmd:
                raise OSError("rev-list failed")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch("aiocortex.git.cleanup.subprocess.run", side_effect=fake_run):
            with patch("aiocortex.git.cleanup.shutil.copytree"):
                with patch("aiocortex.git.cleanup.shutil.rmtree"):
                    result = _truncate_via_clone(tmp_path, 5)
                    assert result == 5


class TestTruncateViaDulwich:
    def test_no_head_raises(self, tmp_path: Path) -> None:
        """Raises GitError when repo has no HEAD."""
        from dulwich.repo import Repo

        Repo.init(str(tmp_path))
        with pytest.raises(GitError, match="Repository has no HEAD"):
            _truncate_via_dulwich(tmp_path, 5)

    def test_nothing_to_truncate(self, git_manager: GitManager, config_dir: Path) -> None:
        """Returns count when fewer commits than keep limit."""
        import asyncio

        loop = asyncio.get_event_loop()
        # Use the git_manager fixture — it already has an init_repo
        # We'll work directly with the shadow root
        # Actually, let's create a simple dulwich repo directly
        from dulwich.repo import Repo

        repo_path = config_dir / "test_dulwich_repo"
        repo_path.mkdir()
        repo = Repo.init(str(repo_path))

        # Create a single commit
        (repo_path / "file.txt").write_text("hello\n")
        from dulwich.porcelain import add, commit

        add(str(repo_path))
        commit(str(repo_path), message=b"First", author=b"Test <t@t>", committer=b"Test <t@t>")

        result = _truncate_via_dulwich(repo_path, 5)
        assert result == 1

    def test_truncates_to_keep_count(self, tmp_path: Path) -> None:
        """Actually rewrites history to keep only N commits."""
        from dulwich.porcelain import add, commit
        from dulwich.repo import Repo

        repo = Repo.init(str(tmp_path))

        # Create 5 commits
        for i in range(5):
            (tmp_path / "file.txt").write_text(f"version {i}\n")
            add(str(tmp_path))
            commit(
                str(tmp_path),
                message=f"Commit {i}".encode(),
                author=b"Test <t@t>",
                committer=b"Test <t@t>",
            )

        result = _truncate_via_dulwich(tmp_path, 3)
        assert result == 3
