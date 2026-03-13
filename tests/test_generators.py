"""Tests for generator modules (cron_matrix, heartbeat_entry)."""

from __future__ import annotations

from pathlib import Path

from openclaw_ltk.generators.agents_directive import generate_agents_directive
from openclaw_ltk.generators.boot_entry import generate_boot_entry
from openclaw_ltk.generators.cron_matrix import (
    build_all_specs,
    build_closure_check_spec,
    build_continuation_spec,
    build_deadman_spec,
    build_watchdog_spec,
)
from openclaw_ltk.generators.heartbeat_entry import (
    generate_entry,
    inject_heartbeat_entry,
    remove_heartbeat_entry,
)

# ---------------------------------------------------------------------------
# cron_matrix
# ---------------------------------------------------------------------------


class TestBuildWatchdogSpec:
    def test_basic_fields(self) -> None:
        spec = build_watchdog_spec("task-1", "2026-03-13T12:00:00+08:00")
        assert spec["name"] == "watchdog-task-1"
        assert spec["schedule"]["kind"] == "at"
        assert spec["deleteAfterRun"] is True
        assert spec["lightContext"] is True
        assert spec["sessionTarget"] == "main"


class TestBuildContinuationSpec:
    def test_basic_fields(self) -> None:
        spec = build_continuation_spec("task-1", interval_minutes=5)
        assert spec["name"] == "continuation-task-1"
        assert spec["schedule"]["kind"] == "every"
        assert "5" in spec["schedule"]["interval"]
        assert spec.get("failureAlert") is not None
        assert spec["lightContext"] is True


class TestBuildDeadmanSpec:
    def test_basic_fields(self) -> None:
        spec = build_deadman_spec("task-1", interval_minutes=20)
        assert spec["name"] == "deadman-task-1"
        assert spec["schedule"]["kind"] == "every"
        assert spec["delivery"]["mode"] == "announce"
        assert spec["lightContext"] is True


class TestBuildClosureCheckSpec:
    def test_basic_fields(self) -> None:
        spec = build_closure_check_spec(
            "task-1",
            duration_minutes=60,
            at_iso="2026-03-13T12:00:00+08:00",
        )
        assert spec["name"] == "closure-check-task-1"
        assert spec["schedule"]["kind"] == "at"
        assert spec["deleteAfterRun"] is True


class TestBuildAllSpecs:
    def test_returns_four(self) -> None:
        specs = build_all_specs(
            task_id="task-1",
            duration_minutes=60,
            watchdog_at_iso="2026-03-13T12:00:00+08:00",
            closure_at_iso="2026-03-13T12:00:00+08:00",
        )
        assert len(specs) == 4
        names = {s["name"] for s in specs}
        assert "watchdog-task-1" in names
        assert "continuation-task-1" in names
        assert "deadman-task-1" in names
        assert "closure-check-task-1" in names


# ---------------------------------------------------------------------------
# heartbeat_entry
# ---------------------------------------------------------------------------


class TestGenerateEntry:
    def test_contains_markers(self) -> None:
        entry = generate_entry(
            task_id="task-1",
            title="Test",
            status="active",
            goal="Do stuff",
            updated_at="2026-03-13T00:00:00",
        )
        assert "## LTK: task-1" in entry
        assert "<!-- ltk:end -->" in entry
        assert "Test" in entry


class TestInjectHeartbeatEntry:
    def test_create_new_file(self, tmp_path: Path) -> None:
        hb = tmp_path / "HEARTBEAT.md"
        inject_heartbeat_entry(hb, "t1", "Title", "active", "Goal", "2026-01-01")
        assert hb.exists()
        text = hb.read_text()
        assert "## LTK: t1" in text

    def test_idempotent_update(self, tmp_path: Path) -> None:
        hb = tmp_path / "HEARTBEAT.md"
        inject_heartbeat_entry(hb, "t1", "Title", "active", "Goal", "2026-01-01")
        inject_heartbeat_entry(hb, "t1", "Title", "done", "Goal", "2026-01-02")
        text = hb.read_text()
        # Should have only one entry.
        assert text.count("## LTK: t1") == 1
        assert "done" in text


class TestRemoveHeartbeatEntry:
    def test_remove_existing(self, tmp_path: Path) -> None:
        hb = tmp_path / "HEARTBEAT.md"
        inject_heartbeat_entry(hb, "t1", "Title", "active", "Goal", "2026-01-01")
        remove_heartbeat_entry(hb, "t1")
        text = hb.read_text()
        assert "## LTK: t1" not in text

    def test_remove_missing_is_noop(self, tmp_path: Path) -> None:
        hb = tmp_path / "HEARTBEAT.md"
        # No error on missing file.
        remove_heartbeat_entry(hb, "t1")


# ---------------------------------------------------------------------------
# agents_directive
# ---------------------------------------------------------------------------


class TestGenerateAgentsDirective:
    def test_contains_task_id(self) -> None:
        result = generate_agents_directive("task-42", "/path/to/state.json")
        assert "task-42" in result
        assert "/path/to/state.json" in result

    def test_includes_timeout_hint(self) -> None:
        result = generate_agents_directive(
            "task-42",
            "/path/to/state.json",
            config_hints={"timeout_seconds": 3600},
        )
        assert "3600" in result

    def test_no_config_hints(self) -> None:
        result = generate_agents_directive("task-42", "/path/to/state.json")
        # Should not raise and should contain directive header
        assert "Long Task Directive" in result

    def test_empty_config_hints(self) -> None:
        result = generate_agents_directive(
            "task-42", "/path/to/state.json", config_hints={}
        )
        assert "Long Task Directive" in result


# ---------------------------------------------------------------------------
# boot_entry
# ---------------------------------------------------------------------------


class TestGenerateBootEntry:
    def test_contains_task_info(self) -> None:
        result = generate_boot_entry(
            task_id="task-42",
            title="Test Task",
            goal="Test goal",
            state_path="/path/to/state.json",
        )
        assert "task-42" in result
        assert "Test Task" in result
        assert "Test goal" in result
        assert "/path/to/state.json" in result

    def test_default_recovery_steps(self) -> None:
        result = generate_boot_entry(
            task_id="t",
            title="T",
            goal="G",
            state_path="/s.json",
        )
        assert "Load state file" in result
        assert "Run preflight" in result
        assert "Resume work" in result

    def test_custom_recovery_steps(self) -> None:
        result = generate_boot_entry(
            task_id="t",
            title="T",
            goal="G",
            state_path="/s.json",
            recovery_steps=["Check logs", "Restart service"],
        )
        assert "4. Check logs" in result
        assert "5. Restart service" in result
