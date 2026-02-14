"""Shared fixtures for aio-cortex tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from aio_cortex.files import AsyncFileManager


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with sample files."""
    # Create sample YAML files
    (tmp_path / "configuration.yaml").write_text(
        "homeassistant:\n  name: Test Home\n"
    )
    (tmp_path / "automations.yaml").write_text(
        "- id: 'test_auto'\n  alias: Test Automation\n  trigger: []\n  action: []\n"
    )
    (tmp_path / "scripts.yaml").write_text("")

    # Create a sub-directory with files
    subdir = tmp_path / "custom_components"
    subdir.mkdir()
    (subdir / "test.yaml").write_text("key: value\n")

    # Create a themes directory
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "dark.yaml").write_text(
        "dark_theme:\n  primary-color: '#000'\n"
    )

    return tmp_path


@pytest.fixture
def file_manager(tmp_config_dir: Path) -> AsyncFileManager:
    """Return an AsyncFileManager bound to the temporary config dir."""
    return AsyncFileManager(tmp_config_dir)
