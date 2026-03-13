"""Tests for preflight command checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.commands.preflight import (
    check_active_pointer,
    check_child_checkpoint,
    check_control_plane,
    check_cron_coverage,
    check_heartbeat,
    check_required_fields,
)
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronJob
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


# ---------------------------------------------------------------------------
# Additional individual check tests
# ---------------------------------------------------------------------------


class TestCheckChildCheckpoint:
    def test_no_child_execution(self, sample_state_data: dict[str, Any]) -> None:
        ok, detail = check_child_checkpoint(sample_state_data)
        assert ok is True
        assert "skipped" in detail

    def test_valid_checkpoint(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["child_execution"] = {"checkpoint": "step-3"}
        ok, _ = check_child_checkpoint(sample_state_data)
        assert ok is True

    def test_missing_checkpoint(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["child_execution"] = {}
        ok, detail = check_child_checkpoint(sample_state_data)
        assert ok is False
        assert "missing" in detail


class TestCheckCronCoverage:
    def test_no_cron_declared(self, sample_state_data: dict[str, Any]) -> None:
        """No cron jobs declared passes with informational message."""
        ok, detail = check_cron_coverage(sample_state_data, MagicMock())
        assert ok is True
        assert "no cron jobs" in detail

    def test_cron_present_and_enabled(self, sample_state_data: dict[str, Any]) -> None:
        """Declared cron jobs that exist and are enabled pass."""
        sample_state_data["control_plane"] = {"cron_jobs": [{"name": "watchdog-test"}]}
        mock_client = MagicMock()
        mock_client.list_jobs.return_value = [
            CronJob(id="j1", name="watchdog-test", enabled=True)
        ]
        ok, _ = check_cron_coverage(sample_state_data, mock_client)
        assert ok is True

    def test_cron_missing(self, sample_state_data: dict[str, Any]) -> None:
        """Declared cron job not found in live jobs fails."""
        sample_state_data["control_plane"] = {"cron_jobs": [{"name": "watchdog-test"}]}
        mock_client = MagicMock()
        mock_client.list_jobs.return_value = []
        ok, detail = check_cron_coverage(sample_state_data, mock_client)
        assert ok is False
        assert "not found" in detail


# ---------------------------------------------------------------------------
# CLI entry point tests
# ---------------------------------------------------------------------------


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    sf = state_dir / "test.json"
    sf.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return sf


class TestPreflightCmd:
    def test_pass_with_valid_state(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """preflight passes when state has all required fields."""
        # Add optional fields to avoid failures from heartbeat etc.
        sample_state_data["control_plane"] = {"cron_jobs": []}
        state_file = _write_state(tmp_path, sample_state_data)

        # Set up heartbeat and pointer for passing checks.
        config = LtkConfig(workspace=tmp_path)
        inject_heartbeat_entry(
            config.heartbeat_path,
            "2026-03-13-test-task",
            "Test",
            "active",
            "Goal",
            "2026-01-01",
        )
        config.pointer_path.parent.mkdir(parents=True, exist_ok=True)
        config.pointer_path.write_text('{"task_id": "t1"}')

        # Mock cron client to avoid external process calls.
        mock_client = MagicMock()
        mock_client.list_jobs.return_value = []

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.preflight.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                ["preflight", "--state", str(state_file)],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        # Exec-approvals is not present; at most one check may fail.
        # Required-fields + control-plane + heartbeat + pointer must pass.
        assert "PASS" in result.output or result.exit_code == 1
        # If FAIL, it should only be exec-approvals.
        if result.exit_code == 1:
            lines = result.output.strip().splitlines()
            fail_lines = [ln for ln in lines if "\u2717" in ln]
            assert all("exec-approvals" in fl for fl in fail_lines)

    def test_fail_with_invalid_state(self, tmp_path: Path) -> None:
        """preflight fails when required fields are missing."""
        state_file = _write_state(tmp_path, {"status": "active"})
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.list_jobs.return_value = []

        with patch(
            "openclaw_ltk.commands.preflight.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                ["preflight", "--state", str(state_file)],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_missing_state_file(self, tmp_path: Path) -> None:
        """preflight exits 2 when state file does not exist."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "preflight",
                "--state",
                str(tmp_path / "nope.json"),
            ],
        )
        assert result.exit_code == 2
