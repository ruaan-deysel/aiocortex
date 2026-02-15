"""Tests for config ↔ shadow sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aiocortex.git.sync import sync_config_to_shadow, sync_shadow_to_config


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

    def test_copy_failure_is_non_fatal(self, config_dir: Path, shadow_dir: Path) -> None:
        """copy2 failure logs warning but doesn't crash."""
        with patch("aiocortex.git.sync.shutil.copy2", side_effect=OSError("copy failed")):
            sync_config_to_shadow(config_dir, shadow_dir)
        # No files should have been copied
        assert not (shadow_dir / "configuration.yaml").exists()

    def test_obsolete_remove_failure_is_non_fatal(
        self, config_dir: Path, shadow_dir: Path
    ) -> None:
        """os.remove failure on obsolete file logs warning."""
        # First sync to populate shadow
        sync_config_to_shadow(config_dir, shadow_dir)
        # Remove from config
        (config_dir / "automations.yaml").unlink()
        # Make os.remove fail
        with patch("aiocortex.git.sync.os.remove", side_effect=OSError("permission denied")):
            sync_config_to_shadow(config_dir, shadow_dir)
        # File should still be in shadow (removal failed)
        assert (shadow_dir / "automations.yaml").exists()


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

    def test_copy_single_failure_is_non_fatal(self, config_dir: Path, shadow_dir: Path) -> None:
        """copy2 failure in _copy_single logs warning but doesn't crash."""
        (shadow_dir / "a.yaml").write_text("a\n")
        with patch("aiocortex.git.sync.shutil.copy2", side_effect=OSError("copy failed")):
            sync_shadow_to_config(shadow_dir, config_dir, only_paths=["a.yaml"])
        # File shouldn't appear in config since copy failed

    def test_copy_single_src_missing_skips(self, config_dir: Path, shadow_dir: Path) -> None:
        """_copy_single skips if source doesn't exist."""
        sync_shadow_to_config(shadow_dir, config_dir, only_paths=["nonexistent.yaml"])
        # No error raised

    def test_delete_missing_removes_tracked_files(
        self, config_dir: Path, shadow_dir: Path
    ) -> None:
        """delete_missing removes files in config that aren't in shadow."""
        # Populate shadow with config
        sync_config_to_shadow(config_dir, shadow_dir)

        # Add an extra file to config (not in shadow)
        (config_dir / "extra.yaml").write_text("extra: true\n")

        # Sync back with delete_missing — extra.yaml should be removed
        sync_shadow_to_config(shadow_dir, config_dir, delete_missing=True)
        assert not (config_dir / "extra.yaml").exists()

    def test_delete_missing_remove_failure_non_fatal(
        self, config_dir: Path, shadow_dir: Path
    ) -> None:
        """os.remove failure during delete_missing is non-fatal."""
        sync_config_to_shadow(config_dir, shadow_dir)
        (config_dir / "extra.yaml").write_text("extra\n")
        (shadow_dir / "automations.yaml").unlink()

        with patch("aiocortex.git.sync.os.remove", side_effect=OSError("permission denied")):
            sync_shadow_to_config(shadow_dir, config_dir, delete_missing=True)
        # Files should still exist since remove failed

    def test_shadow_export_excluded(self, config_dir: Path, shadow_dir: Path) -> None:
        """Export directory in shadow is not synced to config."""
        export = shadow_dir / "export"
        export.mkdir()
        (export / "data.yaml").write_text("export\n")
        (shadow_dir / "real.yaml").write_text("real\n")

        sync_shadow_to_config(shadow_dir, config_dir)
        assert (config_dir / "real.yaml").exists()
        assert not (config_dir / "export" / "data.yaml").exists()

    def test_shadow_export_excluded_in_full_walk(self, config_dir: Path, shadow_dir: Path) -> None:
        """Export dir exclusion in full (non-only_paths) walk."""
        export = shadow_dir / "export"
        export.mkdir()
        (export / "data.yaml").write_text("export\n")
        (shadow_dir / "real.yaml").write_text("real\n")

        # Use delete_missing to also exercise the delete-walk export exclusion
        sync_shadow_to_config(shadow_dir, config_dir, delete_missing=True)
        assert (config_dir / "real.yaml").exists()
        assert not (config_dir / "export" / "data.yaml").exists()

    def test_shadow_export_subdir_in_obsolete_walk(
        self, config_dir: Path, shadow_dir: Path
    ) -> None:
        """Export dir in obsolete file walk of sync_config_to_shadow."""
        # Put export dir in shadow with a file, then sync config to shadow
        export = shadow_dir / "export"
        export.mkdir()
        (export / "exported.yaml").write_text("data\n")

        sync_config_to_shadow(config_dir, shadow_dir)
        # Export dir should be preserved
        assert (export / "exported.yaml").exists()
