"""Tests for the ltk doctor command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.errors import OpenClawError


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

    def test_doctor_emits_jsonl_event_when_probe_fails(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        diagnostics_path = tmp_path / "diagnostics.jsonl"
        monkeypatch.setenv("LTK_DIAGNOSTICS_LOG_PATH", str(diagnostics_path))

        mock_openclaw = MagicMock()
        mock_openclaw.doctor.side_effect = OpenClawError(
            "doctor probe failed",
            detail="upstream gateway unavailable",
        )

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ):
            result = runner.invoke(main, ["doctor", "--deep"])

        assert result.exit_code == 2
        events = [
            json.loads(line)
            for line in diagnostics_path.read_text(encoding="utf-8").splitlines()
        ]
        assert len(events) == 1
        assert events[0]["event"] == "doctor_probe_failed"
        assert events[0]["command"] == "doctor"
        assert events[0]["deep"] is True
        assert events[0]["repair"] is False
        assert events[0]["error"] == "doctor probe failed"
        assert events[0]["detail"] == "upstream gateway unavailable"
