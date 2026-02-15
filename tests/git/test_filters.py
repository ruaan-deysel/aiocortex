"""Tests for git path filters."""

from __future__ import annotations

from aio_cortex.git.filters import should_include_path


class TestDirectoryFiltering:
    def test_git_excluded(self) -> None:
        assert should_include_path(".git", is_dir=True) is False

    def test_shadow_dir_excluded(self) -> None:
        assert should_include_path("cortex_git", is_dir=True) is False

    def test_custom_shadow_name(self) -> None:
        assert should_include_path("my_shadow", is_dir=True, shadow_dir_name="my_shadow") is False
        assert should_include_path("cortex_git", is_dir=True, shadow_dir_name="my_shadow") is True

    def test_storage_excluded(self) -> None:
        assert should_include_path(".storage", is_dir=True) is False

    def test_www_excluded(self) -> None:
        assert should_include_path("www", is_dir=True) is False

    def test_media_excluded(self) -> None:
        assert should_include_path("media", is_dir=True) is False

    def test_pycache_excluded(self) -> None:
        assert should_include_path("__pycache__", is_dir=True) is False

    def test_normal_dir_included(self) -> None:
        assert should_include_path("custom_components", is_dir=True) is True
        assert should_include_path("esphome", is_dir=True) is True


class TestFileFiltering:
    def test_yaml_included(self) -> None:
        assert should_include_path("configuration.yaml", is_dir=False) is True
        assert should_include_path("automations.yaml", is_dir=False) is True

    def test_secrets_excluded(self) -> None:
        assert should_include_path("secrets.yaml", is_dir=False) is False
        assert should_include_path(".secrets.yaml", is_dir=False) is False

    def test_key_files_excluded(self) -> None:
        assert should_include_path("cert.pem", is_dir=False) is False
        assert should_include_path("server.key", is_dir=False) is False
        assert should_include_path("ssl.crt", is_dir=False) is False

    def test_db_files_excluded(self) -> None:
        assert should_include_path("home-assistant_v2.db", is_dir=False) is False
        assert should_include_path("test.sqlite3", is_dir=False) is False
        assert should_include_path("data.db-wal", is_dir=False) is False

    def test_log_files_excluded(self) -> None:
        assert should_include_path("home-assistant.log", is_dir=False) is False
        assert should_include_path("error.log", is_dir=False) is False
        assert should_include_path("app.log.1", is_dir=False) is False

    def test_backup_files_excluded(self) -> None:
        assert should_include_path("config.bak", is_dir=False) is False
        assert should_include_path("old.backup", is_dir=False) is False
        assert should_include_path("test.tmp", is_dir=False) is False
        assert should_include_path("editor~", is_dir=False) is False

    def test_files_in_excluded_dirs(self) -> None:
        assert should_include_path(".storage/core.config", is_dir=False) is False
        assert should_include_path("www/style.css", is_dir=False) is False
        assert should_include_path("media/photo.jpg", is_dir=False) is False

    def test_nested_yaml_included(self) -> None:
        assert should_include_path("custom_components/test/manifest.json", is_dir=False) is True
        assert should_include_path("esphome/device.yaml", is_dir=False) is True
