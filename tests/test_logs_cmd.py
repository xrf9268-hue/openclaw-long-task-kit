"""Tests for the ltk logs command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main


class TestLogsCmd:
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
