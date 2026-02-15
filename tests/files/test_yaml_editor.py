"""Tests for YAMLEditor."""

from __future__ import annotations

from aiocortex.files import YAMLEditor


class TestRemoveLinesFromEnd:
    def test_basic(self) -> None:
        content = "line1\nline2\nline3\nline4\n"
        result = YAMLEditor.remove_lines_from_end(content, 2)
        assert result == "line1\nline2\n"

    def test_remove_all(self) -> None:
        content = "line1\nline2\n"
        assert YAMLEditor.remove_lines_from_end(content, 5) == ""

    def test_remove_one(self) -> None:
        content = "line1\nline2\nline3\n"
        result = YAMLEditor.remove_lines_from_end(content, 1)
        assert "line1" in result
        assert "line2" in result
        assert "line3" not in result


class TestRemoveEmptyYamlSection:
    def test_remove_with_comment(self) -> None:
        content = "something: true\n\n# Lovelace\nlovelace:\n  dashboards:\nnext_section: true\n"
        result = YAMLEditor.remove_empty_yaml_section(content, "lovelace")
        assert "lovelace:" not in result
        assert "next_section: true" in result

    def test_remove_without_comment(self) -> None:
        content = "something: true\n\nlovelace:\n  dashboards:\nnext_section: true\n"
        result = YAMLEditor.remove_empty_yaml_section(content, "lovelace")
        assert "lovelace:" not in result

    def test_no_match(self) -> None:
        content = "homeassistant:\n  name: Test\n"
        result = YAMLEditor.remove_empty_yaml_section(content, "lovelace")
        assert result == content


class TestRemoveYamlEntry:
    def test_remove_existing(self) -> None:
        content = (
            "lovelace:\n"
            "  dashboards:\n"
            "    ai-dashboard:\n"
            "      mode: yaml\n"
            "      title: AI\n"
            "next: true\n"
        )
        modified, found = YAMLEditor.remove_yaml_entry(content, "lovelace", "ai-dashboard")
        assert found is True
        assert "ai-dashboard:" not in modified
        assert "next: true" in modified

    def test_remove_nonexistent(self) -> None:
        content = "lovelace:\n  dashboards:\n    real:\n      mode: yaml\n"
        modified, found = YAMLEditor.remove_yaml_entry(content, "lovelace", "fake")
        assert found is False
        assert modified == content
