"""Tests for the ltk init command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from openclaw_ltk.cli import main


def _run_init(
    runner: CliRunner, tmp_path: Path, extra: list[str] | None = None
) -> object:
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
