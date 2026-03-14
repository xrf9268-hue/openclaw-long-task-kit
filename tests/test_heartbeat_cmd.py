"""Tests for the ltk heartbeat helper command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from openclaw_ltk.cli import main


def _write_openclaw_config(tmp_path: Path, payload: dict[str, object]) -> Path:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def test_heartbeat_command_prints_minimal_config() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["heartbeat"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "agents": {
            "defaults": {
                "heartbeat": {
                    "every": "10m",
                    "target": "last",
                }
            }
        }
    }


def test_heartbeat_validate_reports_missing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_openclaw_config(
        tmp_path,
        {
            "agents": {
                "defaults": {
                    "heartbeat": {
                        "every": "10m",
                    }
                }
            }
        },
    )
    monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

    runner = CliRunner()
    result = runner.invoke(main, ["heartbeat", "validate"])

    assert result.exit_code == 1
    assert (
        "agents.defaults.heartbeat.target must be a non-empty string"
        in result.output
    )


def test_heartbeat_apply_upserts_config_without_clobbering_other_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_openclaw_config(
        tmp_path,
        {
            "gateway": {"port": 3456},
            "agents": {"defaults": {"model": "gpt-5"}},
        },
    )
    monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["heartbeat", "apply", "--every", "15m", "--target", "next"],
    )

    assert result.exit_code == 0
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["gateway"] == {"port": 3456}
    assert payload["agents"]["defaults"]["model"] == "gpt-5"
    assert payload["agents"]["defaults"]["heartbeat"] == {
        "every": "15m",
        "target": "next",
    }
    assert f"Updated heartbeat config in {config_path}" in result.output
