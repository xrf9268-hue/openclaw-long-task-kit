"""Tests for the ltk resume command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.generators.heartbeat_entry import inject_heartbeat_entry


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "resume.json"
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_path


class TestResumeCmd:
    def test_runs_preflight_refreshes_bootstrap_and_prints_prompt(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        sample_state_data["control_plane"] = {"cron_jobs": []}
        state_path = _write_state(tmp_path, sample_state_data)

        config = LtkConfig(
            workspace=tmp_path,
            openclaw_state_dir=tmp_path / "host-state",
        )
        inject_heartbeat_entry(
            config.heartbeat_path,
            sample_state_data["task_id"],
            sample_state_data["title"],
            sample_state_data["status"],
            sample_state_data["goal"],
            sample_state_data["updated_at"],
        )
        config.pointer_path.parent.mkdir(parents=True, exist_ok=True)
        config.pointer_path.write_text("{}", encoding="utf-8")
        config.exec_approvals_path.parent.mkdir(parents=True, exist_ok=True)
        config.exec_approvals_path.write_text("{}", encoding="utf-8")

        mock_cron = MagicMock()
        mock_cron.list_jobs.return_value = []
        mock_openclaw = MagicMock()
        mock_openclaw.health.return_value = {"ok": True}

        runner = CliRunner()
        with (
            patch("openclaw_ltk.commands.resume.CronClient", return_value=mock_cron),
            patch(
                "openclaw_ltk.commands.resume.OpenClawClient",
                return_value=mock_openclaw,
            ),
        ):
            result = runner.invoke(
                main,
                ["resume", "--state", str(state_path)],
                env={
                    "LTK_WORKSPACE": str(tmp_path),
                    "OPENCLAW_STATE_DIR": str(config.openclaw_state_dir),
                },
            )

        assert result.exit_code == 0
        assert "[TASK RESUME]" in result.output
        assert sample_state_data["task_id"] in result.output
        assert str(state_path) in (tmp_path / "BOOT.md").read_text(encoding="utf-8")
        assert str(state_path) in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

        pointer_data = json.loads(config.pointer_path.read_text(encoding="utf-8"))
        assert pointer_data["state_path"] == str(state_path)

    def test_fails_when_preflight_fails(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        sample_state_data["control_plane"] = {"cron_jobs": []}
        state_path = _write_state(tmp_path, sample_state_data)

        mock_cron = MagicMock()
        mock_cron.list_jobs.return_value = []
        mock_openclaw = MagicMock()
        mock_openclaw.health.return_value = {"ok": True}

        runner = CliRunner()
        with (
            patch("openclaw_ltk.commands.resume.CronClient", return_value=mock_cron),
            patch(
                "openclaw_ltk.commands.resume.OpenClawClient",
                return_value=mock_openclaw,
            ),
        ):
            result = runner.invoke(
                main,
                ["resume", "--state", str(state_path)],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 1
        assert "Preflight failed" in result.output
