"""Tests for the instructions module (sync and async loaders)."""

from __future__ import annotations

import pytest

from aiocortex.instructions import (
    DOCS_DIR,
    async_load_all_instructions,
    async_load_instruction_file,
    get_instruction_files,
    load_all_instructions,
    load_instruction_file,
)

# ------------------------------------------------------------------
# Sync helpers
# ------------------------------------------------------------------


class TestGetInstructionFiles:
    """Tests for ``get_instruction_files``."""

    def test_returns_sorted_list(self) -> None:
        files = get_instruction_files()
        assert isinstance(files, list)
        assert len(files) >= 8
        assert files == sorted(files)

    def test_all_files_are_markdown(self) -> None:
        for name in get_instruction_files():
            assert name.endswith(".md")


class TestLoadInstructionFile:
    """Tests for ``load_instruction_file``."""

    def test_loads_existing_file(self) -> None:
        content = load_instruction_file("00_overview.md")
        assert len(content) > 0
        assert "<!--" not in content  # Not the fallback

    def test_missing_file_returns_comment(self) -> None:
        content = load_instruction_file("nonexistent.md")
        assert "not found" in content
        assert "<!--" in content

    def test_each_doc_file_loadable(self) -> None:
        for name in get_instruction_files():
            content = load_instruction_file(name)
            assert len(content) > 0


class TestLoadAllInstructions:
    """Tests for ``load_all_instructions``."""

    def test_combines_all_files(self) -> None:
        combined = load_all_instructions()
        assert len(combined) > 100
        # Should contain section separators
        assert "---" in combined

    def test_version_parameter_accepted(self) -> None:
        combined = load_all_instructions(version="2.5.0")
        assert len(combined) > 100

    def test_default_version(self) -> None:
        combined = load_all_instructions()
        assert len(combined) > 100


# ------------------------------------------------------------------
# Async variants
# ------------------------------------------------------------------


class TestAsyncLoadInstructionFile:
    """Tests for ``async_load_instruction_file``."""

    @pytest.mark.asyncio
    async def test_loads_existing_file(self) -> None:
        content = await async_load_instruction_file("00_overview.md")
        assert len(content) > 0
        assert "<!--" not in content

    @pytest.mark.asyncio
    async def test_missing_file_returns_comment(self) -> None:
        content = await async_load_instruction_file("nonexistent.md")
        assert "not found" in content
        assert "<!--" in content

    @pytest.mark.asyncio
    async def test_matches_sync_variant(self) -> None:
        for name in get_instruction_files():
            sync_content = load_instruction_file(name)
            async_content = await async_load_instruction_file(name)
            assert sync_content == async_content


class TestAsyncLoadAllInstructions:
    """Tests for ``async_load_all_instructions``."""

    @pytest.mark.asyncio
    async def test_combines_all_files(self) -> None:
        combined = await async_load_all_instructions()
        assert len(combined) > 100
        assert "---" in combined

    @pytest.mark.asyncio
    async def test_version_parameter_accepted(self) -> None:
        combined = await async_load_all_instructions(version="3.0.0")
        assert len(combined) > 100

    @pytest.mark.asyncio
    async def test_matches_sync_variant(self) -> None:
        sync_result = load_all_instructions(version="1.0.0")
        async_result = await async_load_all_instructions(version="1.0.0")
        assert sync_result == async_result


class TestDocsDirectory:
    """Tests for the docs directory structure."""

    def test_docs_dir_exists(self) -> None:
        assert DOCS_DIR.exists()
        assert DOCS_DIR.is_dir()

    def test_expected_files_present(self) -> None:
        expected = {
            "00_overview.md",
            "01_explain_before_executing.md",
            "02_output_formatting.md",
            "03_critical_safety.md",
            "04_dashboard_generation.md",
            "05_api_summary.md",
            "06_conditional_cards.md",
            "99_final_reminder.md",
        }
        actual = set(get_instruction_files())
        assert expected.issubset(actual)
