"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiocortex.models import (
    AutomationConfig,
    CommitInfo,
    CortexResponse,
    FileInfo,
    FileWriteResult,
    HelperSpec,
    PendingChanges,
    PendingChangesSummary,
    ScriptConfig,
    ServiceCallSpec,
)


class TestCortexResponse:
    def test_success(self) -> None:
        r = CortexResponse(success=True, message="ok")
        assert r.success is True
        assert r.message == "ok"
        assert r.data is None

    def test_with_data(self) -> None:
        r = CortexResponse(success=True, data={"count": 5})
        assert r.data == {"count": 5}


class TestAutomationConfig:
    def test_minimal(self) -> None:
        a = AutomationConfig(
            alias="Test",
            trigger=[{"platform": "state"}],
            action=[{"service": "light.turn_on"}],
        )
        assert a.alias == "Test"
        assert a.mode == "single"
        assert a.condition == []
        assert a.id is None

    def test_full(self) -> None:
        a = AutomationConfig(
            id="auto_1",
            alias="Full",
            description="desc",
            trigger=[{"platform": "time"}],
            condition=[{"condition": "state"}],
            action=[{"service": "switch.turn_off"}],
            mode="queued",
        )
        assert a.id == "auto_1"
        assert a.mode == "queued"

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            AutomationConfig(alias="No trigger")  # type: ignore[call-arg]


class TestScriptConfig:
    def test_minimal(self) -> None:
        s = ScriptConfig(alias="S", sequence=[{"service": "light.toggle"}])
        assert s.mode == "single"
        assert s.icon is None

    def test_full(self) -> None:
        s = ScriptConfig(
            alias="Full",
            sequence=[],
            mode="parallel",
            icon="mdi:play",
            description="A script",
        )
        assert s.icon == "mdi:play"


class TestHelperSpec:
    def test_valid(self) -> None:
        h = HelperSpec(type="input_boolean", config={"name": "Test Toggle"})
        assert h.type == "input_boolean"


class TestServiceCallSpec:
    def test_minimal(self) -> None:
        s = ServiceCallSpec(domain="light", service="turn_on")
        assert s.data == {}
        assert s.target is None

    def test_with_target(self) -> None:
        s = ServiceCallSpec(
            domain="climate",
            service="set_temperature",
            data={"temperature": 22},
            target={"entity_id": "climate.living_room"},
        )
        assert s.target is not None


class TestFileInfo:
    def test_valid(self) -> None:
        f = FileInfo(
            path="automations.yaml",
            name="automations.yaml",
            size=1024,
            modified=1700000000.0,
            is_yaml=True,
        )
        assert f.is_yaml is True


class TestFileWriteResult:
    def test_valid(self) -> None:
        r = FileWriteResult(success=True, path="test.yaml", size=42)
        assert r.backup is None


class TestCommitInfo:
    def test_valid(self) -> None:
        c = CommitInfo(
            hash="abc12345",
            message="Add automation",
            author="Cortex",
            date="2025-01-01T00:00:00",
            files_changed=3,
        )
        assert c.files_changed == 3


class TestPendingChanges:
    def test_defaults(self) -> None:
        p = PendingChanges()
        assert p.has_changes is False
        assert p.summary.total == 0

    def test_with_changes(self) -> None:
        p = PendingChanges(
            has_changes=True,
            files_modified=["a.yaml"],
            files_added=["b.yaml"],
            summary=PendingChangesSummary(modified=1, added=1, total=2),
        )
        assert p.summary.total == 2
