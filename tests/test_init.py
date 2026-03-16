"""Tests for the ltk init command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner, Result

from openclaw_ltk.cli import main
from openclaw_ltk.commands.init import _build_state_data, _run_init_preflight


def _run_init(
    runner: CliRunner, tmp_path: Path, extra: list[str] | None = None
) -> Result:
    """Helper: invoke ltk init with standard args pointing at tmp workspace."""
    args = [
        "init",
        "--title",
        "Test Task",
        "--goal",
        "Test Goal",
        "--duration",
        "30",
        "--task-type",
        "research",
        "--first-wp-goal",
        "WP Goal",
        "--first-wp-done-when",
        "done",
        "--skip-cron",
    ]
    if extra:
        args.extend(extra)
    return runner.invoke(main, args, env={"LTK_WORKSPACE": str(tmp_path)})


class TestInitDryRun:
    def test_dry_run_exit_code(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _run_init(runner, tmp_path, ["--dry-run"])
        assert result.exit_code == 0


class TestInitSkipCron:
    def test_creates_state_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _run_init(runner, tmp_path)
        assert result.exit_code == 0
        # State file should exist somewhere under tmp_path.
        state_files = list((tmp_path / "tasks" / "state").glob("*.json"))
        assert len(state_files) == 1

    def test_state_has_required_fields(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _run_init(runner, tmp_path)
        state_files = list((tmp_path / "tasks" / "state").glob("*.json"))
        data = json.loads(state_files[0].read_text())
        assert "task_id" in data
        assert "goal" in data
        assert data["status"] == "launching"
        assert "control_plane" in data

    def test_writes_boot_agents_and_pointer(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _run_init(runner, tmp_path)
        assert result.exit_code == 0

        state_files = list((tmp_path / "tasks" / "state").glob("*.json"))
        assert len(state_files) == 1
        state_path = state_files[0]

        boot_text = (tmp_path / "BOOT.md").read_text(encoding="utf-8")
        agents_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        pointer_data = json.loads(
            (tmp_path / "tasks" / ".active-task-pointer.json").read_text(
                encoding="utf-8"
            )
        )

        assert str(state_path) in boot_text
        assert str(state_path) in agents_text
        assert pointer_data["state_path"] == str(state_path)
        assert pointer_data["task_id"] == state_path.stem

    def test_init_creates_memory_files(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _run_init(runner, tmp_path)
        assert result.exit_code == 0

        memory_index = tmp_path / "MEMORY.md"
        daily_files = list((tmp_path / "memory").glob("*.md"))

        assert memory_index.exists()
        assert len(daily_files) == 1
        assert "memory/" in memory_index.read_text(encoding="utf-8")
        daily_text = daily_files[0].read_text(encoding="utf-8")
        assert "Task initialised" in daily_text
        assert "Test Task" in daily_text


class TestBuildStateData:
    def test_required_fields_present(self) -> None:
        """_build_state_data returns a dict with all required fields."""
        data = _build_state_data(
            task_id="2026-03-13-test",
            title="Test",
            goal="Goal",
            first_wp_goal="WP Goal",
            first_wp_done_when="done",
            task_type="research",
            now_str="2026-03-13T00:00:00+08:00",
            next_report_due_str="2026-03-13T00:10:00+08:00",
            silence_budget_minutes=10,
        )
        assert data["task_id"] == "2026-03-13-test"
        assert data["status"] == "launching"
        assert data["current_work_package"]["id"] == "WP-1"
        assert data["current_work_package"]["blockers"] == []
        assert "control_plane" in data

    def test_task_type_in_notes(self) -> None:
        """task_type should appear in the notes list."""
        data = _build_state_data(
            task_id="t",
            title="T",
            goal="G",
            first_wp_goal="W",
            first_wp_done_when="D",
            task_type="coding",
            now_str="2026-01-01T00:00:00",
            next_report_due_str="2026-01-01T00:10:00",
            silence_budget_minutes=10,
        )
        assert "task_type=coding" in data["notes"]


class TestRunInitPreflight:
    def test_valid_data_passes(self, sample_state_data: dict[str, Any]) -> None:
        """_run_init_preflight returns valid=True for valid data."""
        result = _run_init_preflight(sample_state_data)
        assert result.valid is True

    def test_invalid_data_fails(self) -> None:
        """_run_init_preflight returns valid=False for empty data."""
        result = _run_init_preflight({})
        assert result.valid is False
        assert len(result.errors) > 0


class TestInitPreflightStatus:
    """Issue #7: init should record preflight_status in state."""

    def test_state_has_preflight_status(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _run_init(runner, tmp_path)
        state_files = list((tmp_path / "tasks" / "state").glob("*.json"))
        data = json.loads(state_files[0].read_text())
        assert data["preflight_status"] == "passed"

    def test_state_has_preflight_results(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _run_init(runner, tmp_path)
        state_files = list((tmp_path / "tasks" / "state").glob("*.json"))
        data = json.loads(state_files[0].read_text())
        assert "preflight" in data
        assert data["preflight"]["overall"] == "PASS"


class TestInitPostSaveValidation:
    """Issue #7: init should re-read saved state to verify disk integrity."""

    def test_output_confirms_post_save_validation(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _run_init(runner, tmp_path)
        assert result.exit_code == 0
        assert "post-save" in result.output.lower()


class TestInitPreventOverwrite:
    def test_second_run_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _run_init(runner, tmp_path)
        result = _run_init(runner, tmp_path)
        assert result.exit_code != 0

    def test_force_overwrites(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _run_init(runner, tmp_path)
        result = _run_init(runner, tmp_path, ["--force"])
        assert result.exit_code == 0
