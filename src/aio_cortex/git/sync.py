"""Config ↔ Shadow-repo file synchronisation.

Ported from ``GitManager._sync_config_to_shadow()`` and
``GitManager._sync_shadow_to_config()`` in the HA Vibecode Agent add-on.
Filesystem-only — no git operations.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from .filters import should_include_path

logger = logging.getLogger(__name__)


def sync_config_to_shadow(
    config_path: Path,
    shadow_root: Path,
    *,
    shadow_dir_name: str = "cortex_git",
) -> None:
    """Copy trackable files from *config_path* into *shadow_root*.

    Files that were in the shadow tree but no longer exist in config are
    removed (except for ``export/`` and ``.git/``).
    """
    shadow_root.mkdir(parents=True, exist_ok=True)

    included_paths: set[str] = set()

    # ---- Copy config → shadow ----
    for root, dirs, files in os.walk(config_path):
        rel_root = os.path.relpath(root, config_path)
        if rel_root == ".":
            rel_root = ""

        # Prune directories
        for d in list(dirs):
            rel_dir = os.path.join(rel_root, d) if rel_root else d
            if not should_include_path(rel_dir, is_dir=True, shadow_dir_name=shadow_dir_name):
                dirs.remove(d)

        for filename in files:
            rel_path = os.path.join(rel_root, filename) if rel_root else filename
            rel_path_norm = os.path.normpath(rel_path)
            if not should_include_path(rel_path_norm, is_dir=False, shadow_dir_name=shadow_dir_name):
                continue

            src = config_path / rel_path_norm
            dst = shadow_root / rel_path_norm
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                included_paths.add(rel_path_norm.replace(os.sep, "/"))
            except Exception as exc:
                logger.warning("Failed to copy %s to shadow repo: %s", src, exc)

    # ---- Remove obsolete files from shadow ----
    for root, dirs, files in os.walk(shadow_root):
        if ".git" in dirs:
            dirs.remove(".git")
        if "export" in dirs:
            dirs.remove("export")

        rel_root = os.path.relpath(root, shadow_root)
        if rel_root == ".":
            rel_root = ""

        if rel_root.startswith("export"):
            continue

        for filename in files:
            rel_path = os.path.join(rel_root, filename) if rel_root else filename
            rel_path_norm = os.path.normpath(rel_path).replace(os.sep, "/")
            if rel_path_norm not in included_paths:
                try:
                    os.remove(os.path.join(root, filename))
                except Exception as exc:
                    logger.warning(
                        "Failed to remove obsolete file from shadow repo: %s: %s",
                        rel_path_norm,
                        exc,
                    )


def sync_shadow_to_config(
    shadow_root: Path,
    config_path: Path,
    *,
    only_paths: list[str] | None = None,
    delete_missing: bool = False,
    shadow_dir_name: str = "cortex_git",
) -> None:
    """Copy files from *shadow_root* back into *config_path*.

    Parameters
    ----------
    only_paths:
        If given, only these relative paths are synced.
    delete_missing:
        If ``True``, tracked files present in *config_path* but absent from
        the shadow worktree are deleted.
    """

    def _copy_single(rel_path: str) -> None:
        rel_path_norm = os.path.normpath(rel_path)
        src = shadow_root / rel_path_norm
        dst = config_path / rel_path_norm
        if not src.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except Exception as exc:
            logger.warning("Failed to restore %s to config: %s", rel_path_norm, exc)

    if only_paths:
        for p in only_paths:
            _copy_single(p)
    else:
        for root, dirs, files in os.walk(shadow_root):
            if ".git" in dirs:
                dirs.remove(".git")
            if "export" in dirs:
                dirs.remove("export")
            rel_root = os.path.relpath(root, shadow_root)
            if rel_root == ".":
                rel_root = ""
            if rel_root.startswith("export"):
                continue
            for filename in files:
                rel_path = os.path.join(rel_root, filename) if rel_root else filename
                _copy_single(rel_path)

    if delete_missing:
        shadow_paths: set[str] = set()
        for root, dirs, files in os.walk(shadow_root):
            if ".git" in dirs:
                dirs.remove(".git")
            if "export" in dirs:
                dirs.remove("export")
            rel_root = os.path.relpath(root, shadow_root)
            if rel_root == ".":
                rel_root = ""
            if rel_root.startswith("export"):
                continue
            for filename in files:
                rel_path = os.path.join(rel_root, filename) if rel_root else filename
                shadow_paths.add(os.path.normpath(rel_path).replace(os.sep, "/"))

        config_paths: set[str] = set()
        for root, dirs, files in os.walk(config_path):
            for skip_dir in (".git", shadow_dir_name):
                if skip_dir in dirs:
                    dirs.remove(skip_dir)
            rel_root = os.path.relpath(root, config_path)
            if rel_root == ".":
                rel_root = ""
            for filename in files:
                rel_path = os.path.join(rel_root, filename) if rel_root else filename
                rel_path_norm = os.path.normpath(rel_path)
                if not should_include_path(rel_path_norm, is_dir=False, shadow_dir_name=shadow_dir_name):
                    continue
                config_paths.add(rel_path_norm.replace(os.sep, "/"))

        for rel_path in config_paths:
            if rel_path not in shadow_paths:
                try:
                    os.remove(config_path / rel_path)
                    logger.info("Removed file from config during rollback: %s", rel_path)
                except Exception as exc:
                    logger.warning(
                        "Failed to remove %s from config during rollback: %s",
                        rel_path,
                        exc,
                    )
