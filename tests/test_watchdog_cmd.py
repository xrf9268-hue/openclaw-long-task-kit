"""Tests for the ltk watchdog command (arm, disarm, renew)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.cron import CronJob
from openclaw_ltk.errors import CronError


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a minimal state file and return its path."""
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "test-task.json"
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_file


def _minimal_state() -> dict[str, Any]:
    return {
        "task_id": "2026-03-13-test-task",
        "title": "Test",
        "created_at": "2026-03-13T00:00:00+08:00",
        "updated_at": "2026-03-13T00:00:00+08:00",
        "status": "active",
        "phase": "executing",
        "goal": "Test",
        "current_work_package": {
            "id": "WP-1",
            "goal": "g",
            "done_when": "d",
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
    }


class TestArmCmd:
    def test_arm_creates_job(self, tmp_path: Path) -> None:
        """arm creates a watchdog cron job and exits 0."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.add_job.return_value = "job-123"

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                [
                    "watchdog",
                    "arm",
                    "--state",
                    str(state_file),
                    "--at",
                    "2026-03-13T12:00:00+08:00",
                ],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 0
        assert "ARMED" in result.output
        mock_client.add_job.assert_called_once()

    def test_arm_cron_unavailable(self, tmp_path: Path) -> None:
        """arm exits non-zero when openclaw is not available."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                [
                    "watchdog",
                    "arm",
                    "--state",
                    str(state_file),
                    "--at",
                    "2026-03-13T12:00:00+08:00",
                ],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code != 0
        assert "ERROR" in result.output


class TestDisarmCmd:
    def test_disarm_removes_job(self, tmp_path: Path) -> None:
        """disarm removes an existing watchdog job."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = [
            CronJob(
                id="job-456",
                name="watchdog-2026-03-13-test-task",
                enabled=True,
            )
        ]
        mock_client.remove_job.return_value = True

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                ["watchdog", "disarm", "--state", str(state_file)],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 0
        assert "DISARMED" in result.output
        mock_client.remove_job.assert_called_once_with("job-456")

    def test_disarm_no_job(self, tmp_path: Path) -> None:
        """disarm is a no-op when no watchdog job exists."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = []

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                ["watchdog", "disarm", "--state", str(state_file)],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 0
        assert "no-op" in result.output


class TestRenewCmd:
    def test_renew_replaces_job(self, tmp_path: Path) -> None:
        """renew removes old job and creates a new one."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = [
            CronJob(
                id="old-job",
                name="watchdog-2026-03-13-test-task",
                enabled=True,
            )
        ]
        mock_client.remove_job.return_value = True
        mock_client.add_job.return_value = "new-job"

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                [
                    "watchdog",
                    "renew",
                    "--state",
                    str(state_file),
                    "--at",
                    "2026-03-13T14:00:00+08:00",
                ],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 0
        assert "RENEWED" in result.output
        mock_client.remove_job.assert_called_once_with("old-job")
        mock_client.add_job.assert_called_once()

    def test_renew_add_failure(self, tmp_path: Path) -> None:
        """renew exits non-zero when add_job fails."""
        state_file = _write_state(tmp_path, _minimal_state())
        runner = CliRunner()

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = []
        mock_client.add_job.side_effect = CronError("add failed")

        with patch(
            "openclaw_ltk.commands.watchdog.CronClient",
            return_value=mock_client,
        ):
            result = runner.invoke(
                main,
                [
                    "watchdog",
                    "renew",
                    "--state",
                    str(state_file),
                    "--at",
                    "2026-03-13T14:00:00+08:00",
                ],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code != 0
        assert "ERROR" in result.output
