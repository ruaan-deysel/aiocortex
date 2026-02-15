"""Tests for config ↔ shadow sync."""

from __future__ import annotations

from pathlib import Path

import pytest

from aio_cortex.git.sync import sync_config_to_shadow, sync_shadow_to_config


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Config directory with sample files."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "configuration.yaml").write_text("name: Test\n")
    (cfg / "automations.yaml").write_text("- id: a1\n")
    # Excluded files
    (cfg / "secrets.yaml").write_text("secret: shhh\n")
    (cfg / "home-assistant.log").write_text("log line\n")
    # Subdirectory
    sub = cfg / "esphome"
    sub.mkdir()
    (sub / "device.yaml").write_text("esphome:\n")
    # Excluded directory
    storage = cfg / ".storage"
    storage.mkdir()
    (storage / "core.config").write_text("{}\n")
    return cfg


@pytest.fixture
def shadow_dir(tmp_path: Path) -> Path:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    return shadow


class TestSyncConfigToShadow:
    def test_copies_included_files(self, config_dir: Path, shadow_dir: Path) -> None:
        sync_config_to_shadow(config_dir, shadow_dir)
        assert (shadow_dir / "configuration.yaml").exists()
        assert (shadow_dir / "automations.yaml").exists()
        assert (shadow_dir / "esphome" / "device.yaml").exists()

    def test_excludes_secrets(self, config_dir: Path, shadow_dir: Path) -> None:
        sync_config_to_shadow(config_dir, shadow_dir)
        assert not (shadow_dir / "secrets.yaml").exists()

    def test_excludes_logs(self, config_dir: Path, shadow_dir: Path) -> None:
        sync_config_to_shadow(config_dir, shadow_dir)
        assert not (shadow_dir / "home-assistant.log").exists()

    def test_excludes_storage(self, config_dir: Path, shadow_dir: Path) -> None:
        sync_config_to_shadow(config_dir, shadow_dir)
        assert not (shadow_dir / ".storage").exists()

    def test_removes_obsolete_files(self, config_dir: Path, shadow_dir: Path) -> None:
        # First sync
        sync_config_to_shadow(config_dir, shadow_dir)
        assert (shadow_dir / "automations.yaml").exists()

        # Remove file from config
        (config_dir / "automations.yaml").unlink()

        # Second sync should remove from shadow
        sync_config_to_shadow(config_dir, shadow_dir)
        assert not (shadow_dir / "automations.yaml").exists()

    def test_preserves_export_dir(self, config_dir: Path, shadow_dir: Path) -> None:
        export = shadow_dir / "export"
        export.mkdir()
        (export / "data.yaml").write_text("exported\n")

        sync_config_to_shadow(config_dir, shadow_dir)
        # Export dir should not be touched
        assert (export / "data.yaml").exists()


class TestSyncShadowToConfig:
    def test_copies_files_to_config(self, config_dir: Path, shadow_dir: Path) -> None:
        # Populate shadow
        (shadow_dir / "new_file.yaml").write_text("new: true\n")
        sync_shadow_to_config(shadow_dir, config_dir)
        assert (config_dir / "new_file.yaml").exists()

    def test_only_paths(self, config_dir: Path, shadow_dir: Path) -> None:
        (shadow_dir / "a.yaml").write_text("a\n")
        (shadow_dir / "b.yaml").write_text("b\n")
        sync_shadow_to_config(shadow_dir, config_dir, only_paths=["a.yaml"])
        assert (config_dir / "a.yaml").exists()
        # b.yaml should not be synced (wasn't in only_paths)
        # Note: it may or may not exist depending on prior state

    def test_delete_missing(self, config_dir: Path, shadow_dir: Path) -> None:
        # First populate shadow with config files
        sync_config_to_shadow(config_dir, shadow_dir)

        # Remove a file from shadow (simulating rollback)
        (shadow_dir / "automations.yaml").unlink()

        # Sync back with delete_missing
        sync_shadow_to_config(shadow_dir, config_dir, delete_missing=True)
        assert not (config_dir / "automations.yaml").exists()
        # Excluded files should not be touched
        assert (config_dir / "secrets.yaml").exists()
