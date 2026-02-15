"""Tests for AsyncFileManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aiocortex.exceptions import FileError, PathSecurityError, YAMLParseError
from aiocortex.files import AsyncFileManager

# -- Path security -----------------------------------------------------------


class TestPathSecurity:
    def test_root_path(self, file_manager: AsyncFileManager, tmp_config_dir: Path) -> None:
        assert file_manager._get_full_path("") == tmp_config_dir
        assert file_manager._get_full_path("/") == tmp_config_dir

    def test_relative_path(self, file_manager: AsyncFileManager, tmp_config_dir: Path) -> None:
        result = file_manager._get_full_path("automations.yaml")
        assert result == tmp_config_dir / "automations.yaml"

    def test_leading_slash_stripped(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        result = file_manager._get_full_path("/automations.yaml")
        assert result == tmp_config_dir / "automations.yaml"

    def test_traversal_blocked(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(PathSecurityError):
            file_manager._get_full_path("../../etc/passwd")

    def test_nested_traversal_blocked(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(PathSecurityError):
            file_manager._get_full_path("subdir/../../..")


# -- list_files ---------------------------------------------------------------


class TestListFiles:
    async def test_list_all(self, file_manager: AsyncFileManager) -> None:
        files = await file_manager.list_files()
        paths = [f["path"] for f in files]
        assert "configuration.yaml" in paths
        assert "automations.yaml" in paths

    async def test_list_subdirectory(self, file_manager: AsyncFileManager) -> None:
        files = await file_manager.list_files("custom_components")
        assert len(files) == 1
        assert files[0]["name"] == "test.yaml"

    async def test_list_with_pattern(self, file_manager: AsyncFileManager) -> None:
        files = await file_manager.list_files(pattern="*.yaml")
        assert all(f["is_yaml"] for f in files)

    async def test_list_nonexistent_directory(self, file_manager: AsyncFileManager) -> None:
        files = await file_manager.list_files("nonexistent")
        assert files == []

    async def test_file_info_fields(self, file_manager: AsyncFileManager) -> None:
        files = await file_manager.list_files()
        for f in files:
            assert "path" in f
            assert "name" in f
            assert "size" in f
            assert "modified" in f
            assert "is_yaml" in f

    async def test_list_generic_exception(self, file_manager: AsyncFileManager) -> None:
        """Generic exceptions in list_files raise FileError."""
        with patch.object(Path, "rglob", side_effect=OSError("permission denied")):
            with pytest.raises(FileError, match="permission denied"):
                await file_manager.list_files()

    async def test_list_path_security_reraise(self, file_manager: AsyncFileManager) -> None:
        """PathSecurityError re-raised from list_files."""
        with pytest.raises(PathSecurityError):
            await file_manager.list_files("../../etc")


# -- read_file ---------------------------------------------------------------


class TestReadFile:
    async def test_read_existing(self, file_manager: AsyncFileManager) -> None:
        content = await file_manager.read_file("configuration.yaml")
        assert "name: Test Home" in content

    async def test_read_not_found(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(FileNotFoundError):
            await file_manager.read_file("nonexistent.yaml")

    async def test_read_path_traversal(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(PathSecurityError):
            await file_manager.read_file("../../etc/passwd")

    async def test_read_generic_exception(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        """Generic exceptions in read_file raise FileError."""

        with patch("aiofiles.open", side_effect=OSError("disk error")):
            with pytest.raises(FileError, match="disk error"):
                await file_manager.read_file("configuration.yaml")


# -- write_file ---------------------------------------------------------------


class TestWriteFile:
    async def test_write_new(self, file_manager: AsyncFileManager, tmp_config_dir: Path) -> None:
        result = await file_manager.write_file("new_file.yaml", "key: value\n")
        assert result["success"] is True
        assert result["size"] == 11
        assert (tmp_config_dir / "new_file.yaml").read_text() == "key: value\n"

    async def test_write_creates_parents(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        result = await file_manager.write_file("deep/nested/file.yaml", "a: 1\n")
        assert result["success"] is True
        assert (tmp_config_dir / "deep" / "nested" / "file.yaml").exists()

    async def test_write_overwrite(self, file_manager: AsyncFileManager) -> None:
        await file_manager.write_file("configuration.yaml", "new: content\n")
        content = await file_manager.read_file("configuration.yaml")
        assert content == "new: content\n"

    async def test_write_path_security_reraise(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(PathSecurityError):
            await file_manager.write_file("../../bad.yaml", "data\n")

    async def test_write_generic_exception(self, file_manager: AsyncFileManager) -> None:
        """Generic exceptions in write_file raise FileError."""
        with patch("aiofiles.open", side_effect=OSError("disk full")):
            with pytest.raises(FileError, match="disk full"):
                await file_manager.write_file("configuration.yaml", "data\n")


# -- append_file --------------------------------------------------------------


class TestAppendFile:
    async def test_append_existing(self, file_manager: AsyncFileManager) -> None:
        result = await file_manager.append_file("scripts.yaml", "script_1:\n  alias: S\n")
        assert result["success"] is True
        content = await file_manager.read_file("scripts.yaml")
        assert "script_1:" in content

    async def test_append_creates_file(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        result = await file_manager.append_file("brand_new.yaml", "hello: world\n")
        assert result["success"] is True
        assert (tmp_config_dir / "brand_new.yaml").exists()

    async def test_append_path_security_reraise(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(PathSecurityError):
            await file_manager.append_file("../../bad.yaml", "data\n")

    async def test_append_generic_exception(self, file_manager: AsyncFileManager) -> None:
        """Generic exceptions in append_file raise FileError."""
        with patch("aiofiles.open", side_effect=OSError("disk error")):
            with pytest.raises(FileError, match="disk error"):
                await file_manager.append_file("configuration.yaml", "data\n")


# -- delete_file --------------------------------------------------------------


class TestDeleteFile:
    async def test_delete_existing(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        result = await file_manager.delete_file("scripts.yaml")
        assert result["success"] is True
        assert not (tmp_config_dir / "scripts.yaml").exists()

    async def test_delete_not_found(self, file_manager: AsyncFileManager) -> None:
        with pytest.raises(FileNotFoundError):
            await file_manager.delete_file("no_such_file.yaml")

    async def test_delete_generic_exception(
        self, file_manager: AsyncFileManager, tmp_config_dir: Path
    ) -> None:
        """Generic exceptions in delete_file raise FileError."""
        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            with pytest.raises(FileError, match="permission denied"):
                await file_manager.delete_file("configuration.yaml")


# -- parse_yaml ---------------------------------------------------------------


class TestParseYaml:
    async def test_parse_valid(self, file_manager: AsyncFileManager) -> None:
        data = await file_manager.parse_yaml("configuration.yaml")
        assert data["homeassistant"]["name"] == "Test Home"

    async def test_parse_empty(self, file_manager: AsyncFileManager) -> None:
        data = await file_manager.parse_yaml("scripts.yaml")
        assert data == {}

    async def test_parse_invalid(self, file_manager: AsyncFileManager) -> None:
        await file_manager.write_file("bad.yaml", ":\n  - :\n    bad: [")
        with pytest.raises(YAMLParseError):
            await file_manager.parse_yaml("bad.yaml")
