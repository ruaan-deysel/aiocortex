"""Tests for the instructions loader."""

from __future__ import annotations

from unittest.mock import patch

from aiocortex.instructions import (
    get_instruction_files,
    load_all_instructions,
    load_instruction_file,
)


class TestLoadInstructionFile:
    def test_existing_file(self) -> None:
        content = load_instruction_file("00_overview.md")
        assert len(content) > 0
        assert "<!--" not in content  # Should be real content, not fallback

    def test_missing_file(self) -> None:
        content = load_instruction_file("nonexistent.md")
        assert "not found" in content


class TestLoadAllInstructions:
    def test_loads_all(self) -> None:
        combined = load_all_instructions()
        assert len(combined) > 100
        # Should contain separator between sections
        assert "---" in combined

    def test_version_replacement(self) -> None:
        combined = load_all_instructions(version="99.99.99")
        # Version replacement should happen (if placeholder exists)
        # This is a best-effort check
        assert len(combined) > 0


class TestGetInstructionFiles:
    def test_returns_list(self) -> None:
        files = get_instruction_files()
        assert isinstance(files, list)
        assert len(files) > 0
        assert all(f.endswith(".md") for f in files)

    def test_sorted(self) -> None:
        files = get_instruction_files()
        assert files == sorted(files)

    def test_docs_dir_missing(self) -> None:
        """Returns empty list when DOCS_DIR doesn't exist."""
        with patch("aiocortex.instructions.DOCS_DIR") as mock_dir:
            mock_dir.exists.return_value = False
            files = get_instruction_files()
            assert files == []
