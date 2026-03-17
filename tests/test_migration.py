"""Tests for state file schema migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openclaw_ltk.migration import (
    CURRENT_SCHEMA_VERSION,
    migrate_state,
    needs_migration,
)
from openclaw_ltk.state import StateFile


def _make_v0_state() -> dict[str, Any]:
    """Build a minimal valid state dict WITHOUT schema_version (v0)."""
    return {
        "task_id": "test-task",
        "title": "Test Task",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T01:00:00+00:00",
        "status": "active",
        "phase": "execute",
        "goal": "Test goal",
        "current_work_package": {
            "id": "WP-1",
            "goal": "wp goal",
            "done_when": "wp done",
            "blockers": [],
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
        "control_plane": {"lock": {}, "cron_jobs": {}},
    }


def _make_v1_state() -> dict[str, Any]:
    """Build a state dict at current schema version."""
    state = _make_v0_state()
    state["schema_version"] = 1
    return state


class TestNeedsMigration:
    def test_missing_schema_version_needs_migration(self) -> None:
        state = _make_v0_state()
        assert needs_migration(state) is True

    def test_current_version_does_not_need_migration(self) -> None:
        state = _make_v1_state()
        assert needs_migration(state) is False

    def test_old_version_needs_migration(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = 0
        assert needs_migration(state) is True

    def test_future_version_does_not_need_migration(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = CURRENT_SCHEMA_VERSION + 1
        assert needs_migration(state) is False

    def test_non_int_schema_version_needs_migration(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = "0"
        assert needs_migration(state) is True

    def test_null_schema_version_needs_migration(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = None
        assert needs_migration(state) is True


class TestMigrateState:
    def test_v0_to_current(self) -> None:
        state = _make_v0_state()
        result = migrate_state(state)
        assert result.migrated is True
        assert result.from_version == 0
        assert result.to_version == CURRENT_SCHEMA_VERSION
        assert result.state["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_already_current_is_noop(self) -> None:
        state = _make_v1_state()
        result = migrate_state(state)
        assert result.migrated is False
        assert result.from_version == CURRENT_SCHEMA_VERSION
        assert result.to_version == CURRENT_SCHEMA_VERSION
        assert result.state is state  # same object, not copied

    def test_future_version_is_noop(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = 999
        result = migrate_state(state)
        assert result.migrated is False
        assert result.from_version == 999
        assert result.to_version == 999

    def test_v0_migration_preserves_all_fields(self) -> None:
        state = _make_v0_state()
        state["custom_field"] = "preserved"
        result = migrate_state(state)
        assert result.state["custom_field"] == "preserved"
        assert result.state["task_id"] == "test-task"

    def test_migration_result_messages(self) -> None:
        state = _make_v0_state()
        result = migrate_state(state)
        assert len(result.messages) > 0
        assert any("0" in msg and "1" in msg for msg in result.messages)

    def test_non_int_schema_version_migrates_as_v0(self) -> None:
        state = _make_v0_state()
        state["schema_version"] = "invalid"
        result = migrate_state(state)
        assert result.migrated is True
        assert result.from_version == 0
        assert result.state["schema_version"] == CURRENT_SCHEMA_VERSION


class TestLoadAndMigrate:
    def test_auto_migrates_v0_on_load(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(_make_v0_state(), indent=2), encoding="utf-8")
        sf = StateFile(state_file)
        data, result = sf.load_and_migrate()
        assert data["schema_version"] == CURRENT_SCHEMA_VERSION
        assert result is not None
        assert result.migrated is True

        # File should be updated on disk
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_current_version_no_write(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        v1 = _make_v1_state()
        state_file.write_text(json.dumps(v1, indent=2), encoding="utf-8")
        mtime_before = state_file.stat().st_mtime_ns

        sf = StateFile(state_file)
        data, result = sf.load_and_migrate()
        assert data["schema_version"] == CURRENT_SCHEMA_VERSION
        assert result is None  # no migration needed

        # File should NOT be rewritten
        assert state_file.stat().st_mtime_ns == mtime_before
