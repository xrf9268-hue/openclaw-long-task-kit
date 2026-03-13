"""Tests for the ltk doctor command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.errors import OpenClawError


def _write_openclaw_config(tmp_path: Path, payload: dict[str, object]) -> Path:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


class TestDoctorCmd:
    def test_runs_openclaw_doctor(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = _write_openclaw_config(
            tmp_path,
            {
                "agents": {
                    "defaults": {
                        "heartbeat": {"every": "10m", "target": "last"},
                    }
                }
            },
        )
        monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": []}

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ), patch(
            "platform.system",
            return_value="Darwin",
        ):
            result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        mock_openclaw.doctor.assert_called_once_with(repair=False, deep=False)
        mock_openclaw.gateway_status.assert_not_called()
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["checks"] == []
        heartbeat_check = next(
            check
            for check in payload["ltk_runtime_checks"]
            if check["name"] == "heartbeat-config"
        )
        assert heartbeat_check["ok"] is True

    def test_json_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = _write_openclaw_config(
            tmp_path,
            {
                "agents": {
                    "defaults": {
                        "heartbeat": {"every": "10m", "target": "last"},
                    }
                }
            },
        )
        monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": ["gateway"]}

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ), patch(
            "platform.system",
            return_value="Darwin",
        ):
            result = runner.invoke(main, ["doctor", "--repair", "--deep", "--json"])

        assert result.exit_code == 0
        mock_openclaw.doctor.assert_called_once_with(repair=True, deep=True)
        mock_openclaw.gateway_status.assert_not_called()
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["checks"] == ["gateway"]
        heartbeat_check = next(
            check
            for check in payload["ltk_runtime_checks"]
            if check["name"] == "heartbeat-config"
        )
        assert heartbeat_check["ok"] is True

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

    def test_doctor_reports_missing_heartbeat_block(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = _write_openclaw_config(
            tmp_path,
            {"agents": {"defaults": {}}},
        )
        monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": []}
        mock_openclaw.gateway_status.return_value = {"service": {"manager": "launchd"}}

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ), patch(
            "platform.system",
            return_value="Darwin",
        ):
            result = runner.invoke(main, ["doctor", "--json"])

        assert result.exit_code == 0
        mock_openclaw.gateway_status.assert_not_called()
        payload = json.loads(result.output)
        heartbeat_check = next(
            check
            for check in payload["ltk_runtime_checks"]
            if check["name"] == "heartbeat-config"
        )
        assert payload["ok"] is False
        assert heartbeat_check["ok"] is False
        assert "agents.defaults.heartbeat" in heartbeat_check["detail"]
        assert str(config_path) in heartbeat_check["detail"]

    def test_doctor_reports_linux_linger_hint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = _write_openclaw_config(
            tmp_path,
            {
                "agents": {
                    "defaults": {
                        "heartbeat": {"every": "10m", "target": "last"},
                    }
                }
            },
        )
        monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

        mock_openclaw = MagicMock()
        mock_openclaw.doctor.return_value = {"ok": True, "checks": []}
        mock_openclaw.gateway_status.return_value = {
            "service": {"installed": True, "scope": "user"}
        }

        runner = CliRunner()
        with patch(
            "openclaw_ltk.commands.doctor.OpenClawClient",
            return_value=mock_openclaw,
        ), patch(
            "platform.system",
            return_value="Linux",
        ):
            result = runner.invoke(main, ["doctor", "--json"])

        assert result.exit_code == 0
        mock_openclaw.gateway_status.assert_called_once_with()
        payload = json.loads(result.output)
        linger_check = next(
            check
            for check in payload["ltk_runtime_checks"]
            if check["name"] == "linux-linger"
        )
        assert payload["ok"] is False
        assert linger_check["ok"] is False
        assert "loginctl enable-linger" in linger_check["hint"]
        assert "systemd-user/openclaw-ltk.service.example" in linger_check["hint"]
