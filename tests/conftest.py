"""Shared pytest fixtures for openclaw-long-task-kit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Return a temporary directory suitable for holding state files."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def sample_state_data() -> dict[str, Any]:
    """Return a valid minimal task state dict with all required fields."""
    return {
        "task_id": "2026-03-13-test-task",
        "title": "Test Task",
        "created_at": "2026-03-13T00:00:00+08:00",
        "updated_at": "2026-03-13T00:00:00+08:00",
        "status": "active",
        "phase": "executing",
        "goal": "Test goal",
        "current_work_package": {
            "id": "WP-1",
            "goal": "test wp",
            "done_when": "done",
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
    }


@pytest.fixture
def state_file_on_disk(tmp_state_dir: Path, sample_state_data: dict[str, Any]) -> Path:
    """Write sample state to disk and return the path."""
    import json

    p = tmp_state_dir / "test-task.json"
    p.write_text(json.dumps(sample_state_data, indent=2), encoding="utf-8")
    return p
