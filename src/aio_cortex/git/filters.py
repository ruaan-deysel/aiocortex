"""Path filtering — decide which files should be tracked in the shadow repo.

Ported from ``GitManager._should_include_path()`` in the HA Vibecode Agent
add-on.  This module is pure logic with no git or filesystem side-effects.
"""

from __future__ import annotations

import fnmatch
import os

# Directories excluded at the top level of /config
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".storage",
        ".cloud",
        ".homeassistant",
        "www",
        "media",
        "storage",
        "tmp",
        "node_modules",
        "__pycache__",
    }
)

# Filename-level exclusion patterns
_SECRET_FILES: frozenset[str] = frozenset({"secrets.yaml", ".secrets.yaml"})
_SECRET_EXTS: tuple[str, ...] = ("*.pem", "*.key", "*.crt")
_DB_PATTERNS: tuple[str, ...] = (
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    "home-assistant_v2.db*",
)
_LOG_PATTERNS: tuple[str, ...] = ("*.log", "*.log.*", "home-assistant.log")
_BACKUP_PATTERNS: tuple[str, ...] = ("*.bak", "*.backup", "*.old", "*.tmp", "*.temp", "*~")
_DIR_PREFIXES: tuple[str, ...] = (
    ".storage/",
    ".cloud/",
    ".homeassistant/",
    "www/",
    "media/",
    "storage/",
    "tmp/",
)


def should_include_path(
    rel_path: str,
    is_dir: bool,
    *,
    shadow_dir_name: str = "cortex_git",
) -> bool:
    """Return ``True`` if *rel_path* (relative to ``/config``) should be tracked.

    Parameters
    ----------
    rel_path:
        Forward-slash normalised path relative to the HA config directory.
    is_dir:
        Whether the path represents a directory.
    shadow_dir_name:
        Name of the shadow-repo directory to exclude (default ``cortex_git``).
    """
    rel_path = rel_path.replace(os.sep, "/")
    parts = rel_path.split("/")

    # Skip shadow repo and any .git directories
    if parts[0] in (".git", shadow_dir_name):
        return False

    # Directory-level filtering
    if is_dir:
        return parts[0] not in _EXCLUDED_DIRS

    filename = parts[-1]

    # Secrets / keys
    if filename in _SECRET_FILES:
        return False
    if any(fnmatch.fnmatch(filename, pat) for pat in _SECRET_EXTS):
        return False

    # DB files
    if any(
        fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(rel_path, pat)
        for pat in _DB_PATTERNS
    ):
        return False

    # Logs
    if any(
        fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(rel_path, pat)
        for pat in _LOG_PATTERNS
    ):
        return False

    # Backup-like files
    if any(
        fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(rel_path, pat)
        for pat in _BACKUP_PATTERNS
    ):
        return False

    # Files inside heavy/internal dirs (if they weren't pruned at dir level)
    if any(rel_path.startswith(prefix) for prefix in _DIR_PREFIXES):
        return False

    return True
