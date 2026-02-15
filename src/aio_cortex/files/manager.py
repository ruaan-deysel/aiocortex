"""Async file manager for Home Assistant configuration files.

Ported from ``app/services/file_manager.py`` in the HA Vibecode Agent add-on.
This version is *HA-independent*: it receives ``config_path`` via its
constructor and never imports git — the integration layer is responsible for
orchestrating git commits after file operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiofiles
import yaml

from ..exceptions import FileError, PathSecurityError, YAMLParseError

logger = logging.getLogger(__name__)


class AsyncFileManager:
    """Safe async file operations restricted to a *config_path* directory."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.resolve()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_full_path(self, relative_path: str) -> Path:
        """Return the absolute path, ensuring it stays within *config_path*.

        Raises :class:`PathSecurityError` if the resolved path escapes the
        allowed directory tree.
        """
        if relative_path in ("", "/"):
            return self.config_path

        # Strip leading slash — treat as relative
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]

        full_path = (self.config_path / relative_path).resolve()

        if not str(full_path).startswith(str(self.config_path)):
            raise PathSecurityError(f"Path outside config directory: {relative_path}")

        return full_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_files(
        self,
        directory: str = "",
        pattern: str = "*",
    ) -> list[dict[str, object]]:
        """List files in *directory* matching *pattern* (recursive glob)."""
        try:
            dir_path = self._get_full_path(directory)

            if not dir_path.exists():
                return []

            files: list[dict[str, object]] = []
            for item in dir_path.rglob(pattern):
                if item.is_file():
                    rel_path = item.relative_to(self.config_path)
                    stat = item.stat()
                    files.append(
                        {
                            "path": str(rel_path),
                            "name": item.name,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "is_yaml": item.suffix in (".yaml", ".yml"),
                        }
                    )

            return sorted(files, key=lambda x: str(x["path"]))
        except PathSecurityError:
            raise
        except Exception as exc:
            logger.error("Error listing files: %s", exc)
            raise FileError(str(exc)) from exc

    async def read_file(self, file_path: str) -> str:
        """Read and return the UTF-8 contents of *file_path*."""
        try:
            full_path = self._get_full_path(file_path)

            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            async with aiofiles.open(full_path, encoding="utf-8") as fh:
                content = await fh.read()

            logger.info("Read file: %s (%d bytes)", file_path, len(content))
            return content
        except (FileNotFoundError, PathSecurityError):
            raise
        except Exception as exc:
            logger.error("Error reading file %s: %s", file_path, exc)
            raise FileError(str(exc)) from exc

    async def write_file(self, file_path: str, content: str) -> dict[str, object]:
        """Write *content* to *file_path*, creating parent directories as needed.

        Returns a result dict with *success*, *path*, and *size*.

        .. note::

            This method does **not** interact with git.  The integration layer
            should call ``GitManager.commit_changes()`` afterwards if desired.
        """
        try:
            full_path = self._get_full_path(file_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(full_path, "w", encoding="utf-8") as fh:
                await fh.write(content)

            logger.info("Wrote file: %s (%d bytes)", file_path, len(content))

            return {"success": True, "path": file_path, "size": len(content)}
        except PathSecurityError:
            raise
        except Exception as exc:
            logger.error("Error writing file %s: %s", file_path, exc)
            raise FileError(str(exc)) from exc

    async def append_file(self, file_path: str, content: str) -> dict[str, object]:
        """Append *content* to *file_path*, creating it if it doesn't exist."""
        try:
            full_path = self._get_full_path(file_path)

            if not full_path.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.touch()

            async with aiofiles.open(full_path, encoding="utf-8") as fh:
                existing = await fh.read()

            new_content = (existing + "\n" + content) if existing else content

            async with aiofiles.open(full_path, "w", encoding="utf-8") as fh:
                await fh.write(new_content)

            logger.info("Appended to file: %s (%d bytes)", file_path, len(content))

            return {
                "success": True,
                "path": file_path,
                "added_bytes": len(content),
                "total_size": len(new_content),
            }
        except PathSecurityError:
            raise
        except Exception as exc:
            logger.error("Error appending to file %s: %s", file_path, exc)
            raise FileError(str(exc)) from exc

    async def delete_file(self, file_path: str) -> dict[str, object]:
        """Delete *file_path*.

        Returns a result dict with *success* and *path*.
        """
        try:
            full_path = self._get_full_path(file_path)

            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            full_path.unlink()
            logger.info("Deleted file: %s", file_path)

            return {"success": True, "path": file_path}
        except (FileNotFoundError, PathSecurityError):
            raise
        except Exception as exc:
            logger.error("Error deleting file %s: %s", file_path, exc)
            raise FileError(str(exc)) from exc

    async def parse_yaml(self, file_path: str) -> dict[str, Any]:
        """Parse a YAML file and return its contents as a dict."""
        try:
            content = await self.read_file(file_path)
            data = yaml.safe_load(content)
            return data or {}
        except yaml.YAMLError as exc:
            logger.error("YAML parse error in %s: %s", file_path, exc)
            raise YAMLParseError(f"Invalid YAML: {exc}") from exc
