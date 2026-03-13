"""Tests for the ltk status command (brief and full modes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.clock import now_utc_iso


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a state file and return its path."""
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "test-task.json"
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_file


def _fresh_state() -> dict[str, Any]:
    """Return a valid state dict with a recent timestamp."""
    return {
        "task_id": "2026-03-13-test-task",
        "title": "Test Task",
        "created_at": now_utc_iso(),
        "updated_at": now_utc_iso(),
        "status": "active",
        "phase": "executing",
        "goal": "Test the status command",
        "current_work_package": {
            "id": "WP-1",
            "goal": "test wp",
            "done_when": "done",
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
    }


class TestBriefMode:
    def test_brief_output(self, tmp_path: Path) -> None:
        """--brief outputs a single pipe-separated line."""
        state_file = _write_state(tmp_path, _fresh_state())
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--state", str(state_file), "--brief"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0
        assert "|" in result.output
        assert "2026-03-13-test-task" in result.output
        assert "active" in result.output

    def test_brief_missing_state(self, tmp_path: Path) -> None:
        """--brief with missing state file exits non-zero."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--state", str(tmp_path / "nope.json"), "--brief"],
        )
        assert result.exit_code != 0
        assert "ERROR" in result.output


class TestFullMode:
    def test_full_output(self, tmp_path: Path) -> None:
        """Full mode outputs task details, deadman, and validation."""
        state_file = _write_state(tmp_path, _fresh_state())
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--state", str(state_file)],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0
        assert "Task:" in result.output
        assert "Status:" in result.output
        assert "Deadman:" in result.output
        assert "Validation:" in result.output

    def test_full_with_stale_timestamp(self, tmp_path: Path) -> None:
        """Full mode detects stale/dead tasks from old timestamps."""
        data = _fresh_state()
        data["updated_at"] = "2020-01-01T00:00:00+00:00"
        state_file = _write_state(tmp_path, data)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--state", str(state_file)],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0
        assert "dead" in result.output.lower()

    def test_full_with_warnings(self, tmp_path: Path) -> None:
        """Full mode still works when optional fields are missing."""
        data = _fresh_state()
        # Missing optional fields should just yield warnings
        data.pop("control_plane", None)
        state_file = _write_state(tmp_path, data)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--state", str(state_file)],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0
        assert "Validation:" in result.output
