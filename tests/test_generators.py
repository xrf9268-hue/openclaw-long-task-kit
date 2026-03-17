"""Tests for generator modules (cron_matrix, heartbeat_entry)."""

from __future__ import annotations

from pathlib import Path

import pytest

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
from openclaw_ltk.generators.workspace_bootstrap import (
    inject_agents_directive,
    inject_boot_entry,
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

    def test_rejects_none_at_iso(self) -> None:
        with pytest.raises(ValueError, match="absolute ISO 8601"):
            build_closure_check_spec("task-1", duration_minutes=60, at_iso=None)

    def test_rejects_relative_placeholder(self) -> None:
        with pytest.raises(ValueError, match="absolute ISO 8601"):
            build_closure_check_spec(
                "task-1", duration_minutes=60, at_iso="<start_time> + 90min"
            )


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

    def test_rejects_none_closure_at_iso(self) -> None:
        with pytest.raises(ValueError, match="absolute ISO 8601"):
            build_all_specs(
                task_id="task-1",
                duration_minutes=60,
                watchdog_at_iso="2026-03-13T12:00:00+08:00",
                closure_at_iso=None,
            )


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


class TestInjectAgentsDirective:
    def test_create_new_file(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        inject_agents_directive(agents, "task-1", "/tmp/task.json")
        text = agents.read_text(encoding="utf-8")
        assert "Long Task Directive: task-1" in text
        assert "/tmp/task.json" in text

    def test_updates_existing_block_without_duplication(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        agents.write_text("# Existing Rules\n", encoding="utf-8")
        inject_agents_directive(agents, "task-1", "/tmp/one.json")
        inject_agents_directive(agents, "task-1", "/tmp/two.json")
        text = agents.read_text(encoding="utf-8")
        assert text.count("Long Task Directive: task-1") == 1
        assert "/tmp/two.json" in text
        assert "# Existing Rules" in text


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


class TestInjectBootEntry:
    def test_create_new_file(self, tmp_path: Path) -> None:
        boot = tmp_path / "BOOT.md"
        inject_boot_entry(
            boot,
            task_id="task-1",
            title="Title",
            goal="Goal",
            state_path="/tmp/task.json",
        )
        text = boot.read_text(encoding="utf-8")
        assert "Recovery: task-1" in text
        assert "/tmp/task.json" in text

    def test_updates_existing_block_without_duplication(self, tmp_path: Path) -> None:
        boot = tmp_path / "BOOT.md"
        boot.write_text("# Boot Notes\n", encoding="utf-8")
        inject_boot_entry(
            boot,
            task_id="task-1",
            title="Title",
            goal="Goal",
            state_path="/tmp/one.json",
        )
        inject_boot_entry(
            boot,
            task_id="task-1",
            title="Title",
            goal="Goal",
            state_path="/tmp/two.json",
        )
        text = boot.read_text(encoding="utf-8")
        assert text.count("Recovery: task-1") == 1
        assert "/tmp/two.json" in text
        assert "# Boot Notes" in text


# ---------------------------------------------------------------------------
# Version tags in injection blocks (Issue #27)
# ---------------------------------------------------------------------------


class TestVersionTagHeartbeat:
    def test_entry_contains_version(self) -> None:
        entry = generate_entry(
            task_id="t1",
            title="T",
            status="active",
            goal="G",
            updated_at="2026-01-01",
        )
        assert "version=0.1.0" in entry

    def test_inject_replaces_old_block_without_version(self, tmp_path: Path) -> None:
        """Old blocks (no version tag) must be matched and replaced."""
        hb = tmp_path / "HEARTBEAT.md"
        old_block = (
            "## LTK: t1\n"
            "<!-- ltk:meta task_id=t1 status=active -->\n"
            "- **Task**: T\n"
            "<!-- ltk:end -->"
        )
        hb.write_text(old_block + "\n", encoding="utf-8")
        inject_heartbeat_entry(hb, "t1", "T", "done", "G", "2026-01-02")
        text = hb.read_text(encoding="utf-8")
        assert text.count("## LTK: t1") == 1
        assert "version=0.1.0" in text
        assert "done" in text


class TestVersionTagBoot:
    def test_boot_block_contains_version(self, tmp_path: Path) -> None:
        boot = tmp_path / "BOOT.md"
        inject_boot_entry(
            boot,
            task_id="t1",
            title="T",
            goal="G",
            state_path="/s.json",
        )
        text = boot.read_text(encoding="utf-8")
        assert "version=0.1.0" in text

    def test_replaces_old_block_without_version(self, tmp_path: Path) -> None:
        boot = tmp_path / "BOOT.md"
        old_block = "<!-- ltk:boot task_id=t1 -->\nbody\n<!-- ltk:boot:end -->"
        boot.write_text(old_block + "\n", encoding="utf-8")
        inject_boot_entry(
            boot,
            task_id="t1",
            title="T",
            goal="G",
            state_path="/s.json",
        )
        text = boot.read_text(encoding="utf-8")
        assert text.count("ltk:boot task_id=t1") == 1
        assert "version=0.1.0" in text


class TestVersionTagAgents:
    def test_agents_block_contains_version(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        inject_agents_directive(agents, "t1", "/s.json")
        text = agents.read_text(encoding="utf-8")
        assert "version=0.1.0" in text

    def test_replaces_old_block_without_version(self, tmp_path: Path) -> None:
        agents = tmp_path / "AGENTS.md"
        old_block = "<!-- ltk:agents task_id=t1 -->\nbody\n<!-- ltk:agents:end -->"
        agents.write_text(old_block + "\n", encoding="utf-8")
        inject_agents_directive(agents, "t1", "/s.json")
        text = agents.read_text(encoding="utf-8")
        assert text.count("ltk:agents task_id=t1") == 1
        assert "version=0.1.0" in text
