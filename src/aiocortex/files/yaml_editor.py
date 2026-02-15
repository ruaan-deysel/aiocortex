"""YAML editor utility for safe YAML file modifications.

Ported from ``app/utils/yaml_editor.py`` in the HA Vibecode Agent add-on.
"""

from __future__ import annotations

import re


class YAMLEditor:
    """Utility for editing YAML files while preserving structure."""

    @staticmethod
    def remove_lines_from_end(content: str, num_lines: int) -> str:
        """Remove *num_lines* from the end of *content*."""
        lines = content.rstrip().split("\n")
        if num_lines >= len(lines):
            return ""
        return "\n".join(lines[:-num_lines]) + "\n"

    @staticmethod
    def remove_empty_yaml_section(content: str, section_name: str) -> str:
        """Remove an empty YAML section (e.g. ``lovelace:`` with only empty sub-keys)."""
        # Pattern: comment + section with only empty subsections
        pattern = rf"\n# .*{section_name.title()}.*\n{section_name}:\s*\n\s+\w+:\s*\n(?=\S|\Z)"
        content = re.sub(pattern, "\n", content, flags=re.IGNORECASE)

        # Also try without a preceding comment
        pattern = rf"\n{section_name}:\s*\n\s+\w+:\s*\n(?=\S|\Z)"
        content = re.sub(pattern, "\n", content, flags=re.IGNORECASE)

        return content

    @staticmethod
    def remove_yaml_entry(
        content: str,
        section: str,
        key: str,
    ) -> tuple[str, bool]:
        """Remove a specific entry from a YAML section.

        Returns ``(modified_content, was_found)``.
        """
        pattern = rf"    {re.escape(key)}:\s*\n(?:      .*\n)*"

        if re.search(pattern, content):
            modified = re.sub(pattern, "", content)
            modified = YAMLEditor.remove_empty_yaml_section(modified, section)
            return modified, True

        return content, False
