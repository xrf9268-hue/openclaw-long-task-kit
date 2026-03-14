"""Tests for the ltk notify command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.clock import now_utc_iso


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "notify.json"
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_path


def _fresh_state() -> dict[str, Any]:
    return {
        "task_id": "2026-03-14-notify-task",
        "title": "Notify Task",
        "created_at": now_utc_iso(),
        "updated_at": now_utc_iso(),
        "status": "active",
        "phase": "executing",
        "goal": "Exercise the notify command",
        "current_work_package": {
            "id": "WP-1",
            "goal": "ship summary bridge",
            "done_when": "tests pass",
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
    }


def test_notify_summary_formats_exhaustion_alert(tmp_path: Path) -> None:
    data = _fresh_state()
    data["retry_count"] = 3
    state_path = _write_state(tmp_path, data)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["notify", "--state", str(state_path)],
        env={"LTK_WORKSPACE": str(tmp_path)},
    )

    assert result.exit_code == 0
    assert "Notify Task" in result.output
    assert "Continuation: action=continue" in result.output
    assert "Exhaustion: action=abort" in result.output


def test_notify_telegram_preview_uses_config_chat_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = _write_state(tmp_path, _fresh_state())
    monkeypatch.setenv("LTK_TELEGRAM_CHAT_ID", "123456")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["notify", "--state", str(state_path), "--format", "telegram-json"],
        env={"LTK_WORKSPACE": str(tmp_path)},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["chat_id"] == "123456"
    assert "2026-03-14-notify-task" in payload["text"]
