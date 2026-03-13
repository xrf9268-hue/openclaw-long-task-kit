"""Tests for preflight command checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_ltk.commands.preflight import (
    check_active_pointer,
    check_control_plane,
    check_heartbeat,
    check_required_fields,
)
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.generators.heartbeat_entry import inject_heartbeat_entry


class TestCheckRequiredFields:
    def test_pass(self, sample_state_data: dict[str, Any]) -> None:
        ok, _ = check_required_fields(sample_state_data)
        assert ok is True

    def test_fail_missing_task_id(self, sample_state_data: dict[str, Any]) -> None:
        del sample_state_data["task_id"]
        ok, detail = check_required_fields(sample_state_data)
        assert ok is False
        assert "task_id" in detail


class TestCheckControlPlane:
    def test_pass_with_control_plane(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["control_plane"] = {"lock": {}}
        ok, _ = check_control_plane(sample_state_data)
        assert ok is True

    def test_pass_without_control_plane(
        self, sample_state_data: dict[str, Any]
    ) -> None:
        # Optional field — absence should not fail.
        ok, _ = check_control_plane(sample_state_data)
        assert ok is True


class TestCheckHeartbeat:
    def test_pass(self, tmp_path: Path) -> None:
        config = LtkConfig(workspace=tmp_path)
        inject_heartbeat_entry(
            config.heartbeat_path, "t1", "T", "active", "G", "2026-01-01"
        )
        ok, _ = check_heartbeat(config)
        assert ok is True

    def test_fail_no_file(self, tmp_path: Path) -> None:
        config = LtkConfig(workspace=tmp_path)
        ok, _ = check_heartbeat(config)
        assert ok is False


class TestCheckActivePointer:
    def test_pass(self, tmp_path: Path) -> None:
        config = LtkConfig(workspace=tmp_path)
        config.pointer_path.parent.mkdir(parents=True, exist_ok=True)
        config.pointer_path.write_text('{"task_id": "t1"}')
        ok, _ = check_active_pointer(config)
        assert ok is True

    def test_fail(self, tmp_path: Path) -> None:
        config = LtkConfig(workspace=tmp_path)
        ok, _ = check_active_pointer(config)
        assert ok is False
