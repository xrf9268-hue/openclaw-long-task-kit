"""Tests for the ltk migrate command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.migration import CURRENT_SCHEMA_VERSION


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "test-task.json"
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_file


def _v0_state() -> dict[str, Any]:
    return {
        "task_id": "test-task",
        "title": "Test",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T01:00:00+00:00",
        "status": "active",
        "phase": "execute",
        "goal": "Test goal",
        "current_work_package": {
            "id": "WP-1",
            "goal": "g",
            "done_when": "d",
            "blockers": [],
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
        "control_plane": {"lock": {}, "cron_jobs": {}},
    }


class TestMigrateCmd:
    def test_migrate_v0_state(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _v0_state())
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "--state", str(state_file)])
        assert result.exit_code == 0
        assert "Migrated" in result.output

        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_migrate_already_current(self, tmp_path: Path) -> None:
        data = _v0_state()
        data["schema_version"] = CURRENT_SCHEMA_VERSION
        state_file = _write_state(tmp_path, data)
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "--state", str(state_file)])
        assert result.exit_code == 0
        out = result.output.lower()
        assert "already at" in out or "current" in out

    def test_migrate_dry_run(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _v0_state())
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "--state", str(state_file), "--dry-run"]
        )
        assert result.exit_code == 0

        # File should NOT be modified
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert "schema_version" not in reloaded

    def test_migrate_missing_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "--state", str(tmp_path / "missing.json")]
        )
        assert result.exit_code != 0
