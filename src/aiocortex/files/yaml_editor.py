"""YAML editor utility for safe YAML file modifications.

Ported from ``app/utils/yaml_editor.py`` in the HA Vibecode Agent add-on.
"""

from __future__ import annotations

import copy
import difflib
import re
from typing import Any

import yaml

from ..models.files import YAMLConflict, YAMLPatchOperation, YAMLPatchPreview


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

    @staticmethod
    def _get_path(data: Any, path: list[str | int]) -> tuple[bool, Any]:
        current = data
        for segment in path:
            if isinstance(segment, int):
                if not isinstance(current, list) or segment >= len(current):
                    return False, None
                current = current[segment]
                continue

            if not isinstance(current, dict) or segment not in current:
                return False, None
            current = current[segment]

        return True, current

    @staticmethod
    def _ensure_parent(data: Any, path: list[str | int]) -> tuple[bool, Any]:
        current = data
        for segment in path[:-1]:
            if isinstance(segment, int):
                if not isinstance(current, list):
                    return False, None
                if segment >= len(current):
                    return False, None
                current = current[segment]
            else:
                if not isinstance(current, dict):
                    return False, None
                if segment not in current or not isinstance(current[segment], (dict, list)):
                    current[segment] = {}
                current = current[segment]

        return True, current

    @staticmethod
    def _set_path(data: Any, path: list[str | int], value: Any) -> bool:
        if not path:
            return False

        ok, parent = YAMLEditor._ensure_parent(data, path)
        if not ok:
            return False

        leaf = path[-1]
        if isinstance(leaf, int):
            if not isinstance(parent, list):
                return False
            if leaf == len(parent):
                parent.append(value)
                return True
            if 0 <= leaf < len(parent):
                parent[leaf] = value
                return True
            return False

        if not isinstance(parent, dict):
            return False
        parent[leaf] = value
        return True

    @staticmethod
    def _remove_path(data: Any, path: list[str | int]) -> bool:
        if not path:
            return False

        ok, parent = YAMLEditor._ensure_parent(data, path)
        if not ok:
            return False

        leaf = path[-1]
        if isinstance(leaf, int):
            if not isinstance(parent, list) or not (0 <= leaf < len(parent)):
                return False
            del parent[leaf]
            return True

        if not isinstance(parent, dict) or leaf not in parent:
            return False
        del parent[leaf]
        return True

    @staticmethod
    def _merge_list_item(data: Any, path: list[str | int], value: Any, merge_key: str) -> bool:
        ok, current = YAMLEditor._get_path(data, path)
        if not ok or not isinstance(current, list) or not isinstance(value, dict):
            return False

        key_value = value.get(merge_key)
        if key_value is None:
            return False

        for index, item in enumerate(current):
            if isinstance(item, dict) and item.get(merge_key) == key_value:
                current[index] = {**item, **value}
                return True

        current.append(value)
        return True

    @staticmethod
    def normalized_diff(before: str, after: str) -> str:
        """Return deterministic unified diff output for content comparisons."""
        before_lines = before.rstrip().splitlines()
        after_lines = after.rstrip().splitlines()
        return "\n".join(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile="before.yaml",
                tofile="after.yaml",
                lineterm="",
            )
        )

    @staticmethod
    def preview_patch(
        content: str,
        operations: list[YAMLPatchOperation],
    ) -> YAMLPatchPreview:
        """Preview semantic YAML mutations and report conflicts before apply."""
        try:
            parsed = yaml.safe_load(content) if content.strip() else {}
        except yaml.YAMLError as exc:
            return YAMLPatchPreview(
                success=False,
                operations_applied=0,
                conflicts=[YAMLConflict(path="<root>", reason=f"Invalid YAML: {exc}")],
                patched_content=content,
                diff="",
            )

        data = parsed or {}
        mutated = copy.deepcopy(data)
        conflicts: list[YAMLConflict] = []
        applied = 0

        for operation in operations:
            if operation.op == "set":
                ok = YAMLEditor._set_path(mutated, operation.path, operation.value)
            elif operation.op == "remove":
                ok = YAMLEditor._remove_path(mutated, operation.path)
            elif not operation.merge_key:
                ok = False
            else:
                ok = YAMLEditor._merge_list_item(
                    mutated,
                    operation.path,
                    operation.value,
                    operation.merge_key,
                )

            if ok:
                applied += 1
            else:
                conflicts.append(
                    YAMLConflict(
                        path="/".join(str(part) for part in operation.path),
                        reason=f"Could not apply operation '{operation.op}'",
                    )
                )

        patched_content = yaml.safe_dump(mutated, sort_keys=True, allow_unicode=True)
        return YAMLPatchPreview(
            success=not conflicts,
            operations_applied=applied,
            conflicts=conflicts,
            patched_content=patched_content,
            diff=YAMLEditor.normalized_diff(content, patched_content),
        )

    @staticmethod
    def apply_patch(content: str, operations: list[YAMLPatchOperation]) -> YAMLPatchPreview:
        """Apply semantic YAML mutations, returning final content and diff metadata."""
        return YAMLEditor.preview_patch(content, operations)
