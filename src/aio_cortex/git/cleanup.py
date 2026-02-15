"""History truncation for the shadow git repository.

Uses dulwich for commit-chain rewriting where possible.  Falls back to
``git clone --depth`` via subprocess if the ``git`` binary is available.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dulwich.repo import Repo

from ..exceptions import GitError

logger = logging.getLogger(__name__)


def _git_binary_available() -> bool:
    """Return ``True`` if the ``git`` CLI is on ``$PATH``."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def truncate_history(
    repo_path: Path,
    commits_to_keep: int,
) -> int:
    """Truncate the repository at *repo_path* to at most *commits_to_keep* commits.

    Returns the number of commits after truncation.

    The strategy is:

    1. If the ``git`` binary is available, use ``git clone --depth`` into a
       temp dir, then swap ``.git`` directories.  This is the most reliable
       approach on HA OS (where git is available in the container).
    2. Otherwise raise :class:`GitError` — pure-dulwich history rewriting is
       a future enhancement.
    """
    repo_path = repo_path.resolve()
    git_dir = repo_path / ".git"

    if not git_dir.is_dir():
        raise GitError(f"No .git directory at {repo_path}")

    # --- Strategy 1: git clone --depth ---
    if _git_binary_available():
        return _truncate_via_clone(repo_path, commits_to_keep)

    # --- Strategy 2: dulwich-native (basic orphan graft) ---
    return _truncate_via_dulwich(repo_path, commits_to_keep)


def _truncate_via_clone(repo_path: Path, commits_to_keep: int) -> int:
    """Clone with ``--depth`` and swap ``.git`` directories."""
    git_dir = repo_path / ".git"

    # Detect current branch
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        branch = result.stdout.strip() or "master"
    except Exception:
        branch = "master"

    with tempfile.TemporaryDirectory() as tmpdir:
        clone_path = os.path.join(tmpdir, "cloned_repo")
        repo_url = f"file://{repo_path}"

        logger.info(
            "Cloning repository with depth=%d from %s ...", commits_to_keep, repo_url
        )
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                str(commits_to_keep),
                "--branch",
                branch,
                "--single-branch",
                repo_url,
                clone_path,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise GitError(f"git clone failed: {result.stderr}")

        cloned_git_dir = os.path.join(clone_path, ".git")
        if not os.path.isdir(cloned_git_dir):
            raise GitError("Cloned .git directory does not exist")

        # Swap .git
        backup_git = os.path.join(tmpdir, "git_backup")
        shutil.copytree(str(git_dir), backup_git)
        shutil.rmtree(str(git_dir))
        shutil.copytree(cloned_git_dir, str(git_dir))

        logger.info("Replaced .git directory with shallow clone")

    # Optional gc
    try:
        subprocess.run(
            ["git", "gc", "--prune=now", "--quiet"],
            cwd=str(repo_path),
            capture_output=True,
            timeout=600,
        )
    except Exception as exc:
        logger.warning("git gc after truncation failed: %s", exc)

    # Return final count
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "--first-parent", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return int(result.stdout.strip())
    except Exception:
        return commits_to_keep


def _truncate_via_dulwich(repo_path: Path, commits_to_keep: int) -> int:
    """Basic dulwich-native truncation using orphan commit grafting.

    Walks the commit chain, keeps *commits_to_keep* most recent commits,
    and rewrites the oldest-kept commit to have no parents (orphan root).
    Then packs and prunes unreachable objects.
    """
    repo = Repo(str(repo_path))

    try:
        head_sha = repo.head()
    except KeyError:
        raise GitError("Repository has no HEAD") from None

    # Walk the first-parent chain
    chain: list[bytes] = []
    current = head_sha
    while current and len(chain) < commits_to_keep + 1:
        chain.append(current)
        commit = repo.get_object(current)
        current = commit.parents[0] if commit.parents else None

    if len(chain) <= commits_to_keep:
        # Nothing to truncate
        return len(chain)

    # Rewrite the oldest kept commit to have no parents
    oldest_kept_sha = chain[commits_to_keep - 1]
    oldest_kept = repo.get_object(oldest_kept_sha).copy()
    oldest_kept.parents = []

    # Store the rewritten commit
    repo.object_store.add_object(oldest_kept)

    # Rewrite the chain from oldest-kept to HEAD
    sha_map: dict[bytes, bytes] = {oldest_kept_sha: oldest_kept.id}

    for i in range(commits_to_keep - 2, -1, -1):
        old_sha = chain[i]
        commit = repo.get_object(old_sha).copy()
        # Replace parent references
        new_parents = []
        for p in commit.parents:
            new_parents.append(sha_map.get(p, p))
        commit.parents = new_parents
        repo.object_store.add_object(commit)
        sha_map[old_sha] = commit.id

    # Update HEAD/refs to point to new chain
    new_head = sha_map.get(head_sha, head_sha)
    for ref in repo.get_refs():
        if repo.get_refs()[ref] == head_sha:
            repo.refs[ref] = new_head

    repo.close()

    return commits_to_keep
