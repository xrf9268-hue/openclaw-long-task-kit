"""Tests for the ltk logs command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.config import LtkConfig


class TestLogsCmd:
    def test_log_path_defaults_under_openclaw_state_dir(self) -> None:
        cfg = LtkConfig(
            workspace=Path("/tmp/workspace"),
            openclaw_state_dir=Path("/srv/openclaw-state"),
        )

        assert cfg.diagnostics_log_path == (
            Path("/srv/openclaw-state") / "ltk-diagnostics.jsonl"
        )

    def test_passes_flags_through_to_openclaw(self) -> None:
        mock_openclaw = MagicMock()
        mock_openclaw.logs.return_value = 0

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.logs.OpenClawClient",
            return_value=mock_openclaw,
        ):
            result = runner.invoke(
                main,
                ["logs", "--follow", "--json", "--limit", "25", "--local-time"],
            )

        assert result.exit_code == 0
        mock_openclaw.logs.assert_called_once_with(
            follow=True,
            json_output=True,
            limit=25,
            local_time=True,
        )

    def test_logs_records_wrapper_activity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diagnostics_path = tmp_path / "diagnostics.jsonl"
        monkeypatch.setenv("LTK_DIAGNOSTICS_LOG_PATH", str(diagnostics_path))

        mock_openclaw = MagicMock()
        mock_openclaw.logs.return_value = 0

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.logs.OpenClawClient",
            return_value=mock_openclaw,
        ):
            result = runner.invoke(main, ["logs", "--follow", "--limit", "5"])

        assert result.exit_code == 0
        events = [
            json.loads(line)
            for line in diagnostics_path.read_text(encoding="utf-8").splitlines()
        ]
        assert len(events) == 1
        assert events[0]["event"] == "logs_wrapper_invoked"
        assert events[0]["command"] == "logs"
        assert events[0]["follow"] is True
        assert events[0]["json_output"] is False
        assert events[0]["limit"] == 5
        assert events[0]["local_time"] is False
