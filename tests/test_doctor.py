"""Tests for the ltk doctor command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from openclaw_ltk.cli import main


class TestDoctorCmd:
    def test_runs_openclaw_doctor(self) -> None:
        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": []}

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ):
            result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        mock_openclaw.doctor.assert_called_once_with(repair=False, deep=False)
        assert '"ok": true' in result.output.lower()

    def test_json_output(self) -> None:
        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": ["gateway"]}

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ):
            result = runner.invoke(main, ["doctor", "--repair", "--deep", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.output) == {"ok": True, "checks": ["gateway"]}
        mock_openclaw.doctor.assert_called_once_with(repair=True, deep=True)
