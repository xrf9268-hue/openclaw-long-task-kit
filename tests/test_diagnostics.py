"""Tests for the unified diagnostics event model."""

from __future__ import annotations

import json
from pathlib import Path

from openclaw_ltk.diagnostics import CheckResult, DiagnosticEvent, emit


class TestDiagnosticEvent:
    def test_to_dict_basic(self) -> None:
        ev = DiagnosticEvent(ts="2026-01-01T00:00:00Z", event="test_event")
        d = ev.to_dict()
        assert d["ts"] == "2026-01-01T00:00:00Z"
        assert d["event"] == "test_event"

    def test_to_dict_with_data(self) -> None:
        ev = DiagnosticEvent(
            ts="2026-01-01T00:00:00Z",
            event="test_event",
            data={"command": "doctor", "repair": True},
        )
        d = ev.to_dict()
        assert d["command"] == "doctor"
        assert d["repair"] is True
        assert d["ts"] == "2026-01-01T00:00:00Z"

    def test_data_keys_merged_flat(self) -> None:
        """Extra data keys appear at top level, not nested under 'data'."""
        ev = DiagnosticEvent(ts="t", event="e", data={"foo": "bar"})
        d = ev.to_dict()
        assert "data" not in d
        assert d["foo"] == "bar"


class TestCheckResult:
    def test_to_dict_minimal(self) -> None:
        cr = CheckResult(name="heartbeat", ok=True, detail="ok")
        d = cr.to_dict()
        assert d == {"name": "heartbeat", "ok": True, "detail": "ok"}

    def test_to_dict_with_hint_and_source(self) -> None:
        cr = CheckResult(
            name="linux-linger",
            ok=False,
            detail="no lingering",
            hint="enable linger",
            source="gateway status",
        )
        d = cr.to_dict()
        assert d["hint"] == "enable linger"
        assert d["source"] == "gateway status"

    def test_to_dict_omits_none_hint_and_source(self) -> None:
        cr = CheckResult(name="test", ok=True, detail="fine")
        d = cr.to_dict()
        assert "hint" not in d
        assert "source" not in d


class TestEmit:
    def test_creates_parent_dirs_and_appends(self, tmp_path: Path) -> None:
        log_path = tmp_path / "sub" / "diagnostics.jsonl"
        ev = DiagnosticEvent(ts="t1", event="e1", data={"k": "v"})
        emit(log_path, ev)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event"] == "e1"
        assert parsed["k"] == "v"

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        log_path = tmp_path / "diagnostics.jsonl"
        emit(log_path, DiagnosticEvent(ts="t1", event="first"))
        emit(log_path, DiagnosticEvent(ts="t2", event="second"))
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "first"
        assert json.loads(lines[1])["event"] == "second"
