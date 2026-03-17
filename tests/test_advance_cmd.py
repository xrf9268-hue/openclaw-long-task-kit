"""Tests for the ltk advance command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from openclaw_ltk.cli import main


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "test-task.json"
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_file


def _base_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "task_id": "test-task",
        "title": "Test",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T01:00:00+00:00",
        "status": "active",
        "phase": "launch",
        "goal": "Test goal",
        "schema_version": 1,
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
    base.update(overrides)
    return base


class TestAdvanceCmd:
    def test_advance_launch_to_preflight(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "preflight"]
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_records_transition_log(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "preflight"]
        )
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        log = reloaded.get("phase_transitions", [])
        assert len(log) == 1
        assert log[0]["from"] == "launch"
        assert log[0]["to"] == "preflight"
        assert "at" in log[0]

    def test_advance_blocked_by_guard(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="preflight"))
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "research"]
        )
        assert result.exit_code != 0
        assert "preflight" in result.output.lower()
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_dry_run(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["advance", "--state", str(state_file), "--to", "preflight", "--dry-run"],
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "launch"

    def test_advance_next_infers_target(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(main, ["advance", "--state", str(state_file), "--next"])
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_backward_blocked(self, tmp_path: Path) -> None:
        state_file = _write_state(
            tmp_path, _base_state(phase="research", preflight_status="passed")
        )
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "launch"]
        )
        assert result.exit_code != 0

    def test_advance_no_target_no_next_errors(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(main, ["advance", "--state", str(state_file)])
        assert result.exit_code != 0


class TestRecordEvidence:
    def test_record_evidence_stores_artifacts(self, tmp_path: Path) -> None:
        state_file = _write_state(
            tmp_path,
            _base_state(phase="research", preflight_status="passed"),
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "advance",
                "--state",
                str(state_file),
                "--record-evidence",
                "research",
                "--artifact",
                "notes.md",
                "--artifact",
                "findings.md",
            ],
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        ev = reloaded["phase_evidence"]["research"]
        assert ev["artifacts"] == ["notes.md", "findings.md"]
        assert "completed_at" in ev

    def test_record_evidence_then_advance(self, tmp_path: Path) -> None:
        state_file = _write_state(
            tmp_path,
            _base_state(phase="research", preflight_status="passed"),
        )
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "advance",
                "--state",
                str(state_file),
                "--record-evidence",
                "research",
                "--artifact",
                "notes.md",
            ],
        )
        result = runner.invoke(
            main,
            ["advance", "--state", str(state_file), "--to", "spec"],
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "spec"

    def test_record_evidence_without_artifact_errors(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="research"))
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "advance",
                "--state",
                str(state_file),
                "--record-evidence",
                "research",
            ],
        )
        assert result.exit_code != 0
