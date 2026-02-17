"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aiocortex.models import (
    AutomationConfig,
    CheckpointResult,
    CleanupResult,
    CommitInfo,
    CortexResponse,
    FileAppendResult,
    FileDeleteResult,
    FileInfo,
    FileWriteResult,
    HelperSpec,
    PendingChanges,
    PendingChangesSummary,
    RestoreFilesResult,
    RollbackResult,
    ScriptConfig,
    ServiceCallSpec,
    TransactionOperation,
    TransactionState,
    TransactionValidationResult,
    YAMLConflict,
    YAMLPatchOperation,
    YAMLPatchPreview,
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


class TestFileOperationResults:
    def test_append_result(self) -> None:
        r = FileAppendResult(success=True, path="a.yaml", added_bytes=4, total_size=10)
        assert r.total_size == 10

    def test_delete_result(self) -> None:
        r = FileDeleteResult(success=True, path="a.yaml")
        assert r.success is True


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


class TestGitResultModels:
    def test_checkpoint_result(self) -> None:
        result = CheckpointResult(success=True, message="ok", commit_hash="abc", tag="checkpoint")
        assert result.success is True

    def test_rollback_result(self) -> None:
        result = RollbackResult(success=True, commit="abc", message="rolled back")
        assert result.commit == "abc"

    def test_restore_and_cleanup(self) -> None:
        restore = RestoreFilesResult(
            success=True,
            commit="abc",
            restored_files=["a.yaml"],
            count=1,
        )
        cleanup = CleanupResult(success=True, message="done", commits_before=10, commits_after=5)
        assert restore.count == 1
        assert cleanup.commits_after == 5


class TestTransactionModels:
    def test_operation_and_state(self) -> None:
        operation = TransactionOperation(op="write", path="configuration.yaml", content="x")
        state = TransactionState(
            transaction_id="tx1",
            operations=[operation],
            created_at="2026-02-17T00:00:00Z",
            updated_at="2026-02-17T00:00:00Z",
        )
        assert state.operations[0].op == "write"

    def test_validation(self) -> None:
        result = TransactionValidationResult(valid=False, errors=["bad path"])
        assert result.valid is False


class TestYamlPatchModels:
    def test_models(self) -> None:
        operation = YAMLPatchOperation(op="set", path=["homeassistant", "name"], value="New")
        conflict = YAMLConflict(path="homeassistant/name", reason="not found")
        preview = YAMLPatchPreview(
            success=False,
            operations_applied=0,
            conflicts=[conflict],
            patched_content="",
            diff="",
        )
        assert operation.op == "set"
        assert len(preview.conflicts) == 1
