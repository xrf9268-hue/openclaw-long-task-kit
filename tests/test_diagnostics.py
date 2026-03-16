"""Tests for the unified diagnostics event model."""

from __future__ import annotations

from openclaw_ltk.diagnostics import DiagnosticEvent


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
