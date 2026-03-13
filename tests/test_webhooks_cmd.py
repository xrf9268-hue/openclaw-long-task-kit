"""Tests for the ltk webhooks helper command."""

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


def test_webhooks_command_prints_minimal_hook_config() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["webhooks"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "hooks": {
            "enabled": True,
            "token": "REPLACE_WITH_SHARED_SECRET",
            "path": "/hooks",
        }
    }


def test_webhooks_validate_reports_missing_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_openclaw_config(
        tmp_path,
        {
            "hooks": {
                "enabled": True,
                "path": "/hooks",
            }
        },
    )
    monkeypatch.setenv("LTK_OPENCLAW_CONFIG_PATH", str(config_path))

    runner = CliRunner()
    result = runner.invoke(main, ["webhooks", "validate"])

    assert result.exit_code == 1
    assert "hooks.token is required when hooks.enabled=true" in result.output
