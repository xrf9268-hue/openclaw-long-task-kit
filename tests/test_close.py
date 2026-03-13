"""Tests for the close command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main


class TestCloseCronUnavailable:
    @patch("openclaw_ltk.commands.close.CronClient")
    def test_exit_code_3(
        self, mock_cron_cls: MagicMock, state_file_on_disk: Path
    ) -> None:
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_cron_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(main, ["close", "--state", str(state_file_on_disk)])
        assert result.exit_code == 3


class TestCloseSuccess:
    @patch("openclaw_ltk.commands.close.CronClient")
    def test_closed(self, mock_cron_cls: MagicMock, state_file_on_disk: Path) -> None:
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = []
        mock_cron_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(main, ["close", "--state", str(state_file_on_disk)])
        # No cron jobs to remove — still CLOSED.
        assert result.exit_code == 0
        assert "CLOSED" in result.output

    @patch("openclaw_ltk.commands.close.remove_heartbeat_entry")
    @patch("openclaw_ltk.commands.close.CronClient")
    def test_close_handles_heartbeat_remove_failure(
        self,
        mock_cron_cls: MagicMock,
        mock_remove_heartbeat: MagicMock,
        state_file_on_disk: Path,
    ) -> None:
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.list_jobs.return_value = []
        mock_cron_cls.return_value = mock_client
        mock_remove_heartbeat.side_effect = OSError("permission denied")

        runner = CliRunner()
        result = runner.invoke(main, ["close", "--state", str(state_file_on_disk)])

        assert result.exit_code == 1
        assert "PARTIAL" in result.output
        assert "could not remove heartbeat entry" in result.output
