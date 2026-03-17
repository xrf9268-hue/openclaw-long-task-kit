"""Tests for phase definitions and transition guards."""

from __future__ import annotations

from openclaw_ltk.phases import (
    KNOWN_PHASES,
    GuardResult,
    check_transition,
    is_known_phase,
    next_phase,
    phase_index,
)


class TestPhaseOrdering:
    def test_known_phases_ordered(self) -> None:
        assert KNOWN_PHASES == (
            "launch",
            "preflight",
            "research",
            "spec",
            "execute",
            "review",
            "done",
        )

    def test_phase_index(self) -> None:
        assert phase_index("launch") == 0
        assert phase_index("done") == 6

    def test_phase_index_unknown_returns_none(self) -> None:
        assert phase_index("custom-phase") is None

    def test_is_known_phase(self) -> None:
        assert is_known_phase("preflight") is True
        assert is_known_phase("banana") is False

    def test_next_phase(self) -> None:
        assert next_phase("launch") == "preflight"
        assert next_phase("execute") == "review"

    def test_next_phase_done_returns_none(self) -> None:
        assert next_phase("done") is None

    def test_next_phase_unknown_returns_none(self) -> None:
        assert next_phase("custom") is None


class TestGuardResult:
    def test_allowed_result(self) -> None:
        r = GuardResult(allowed=True, reason="ok")
        assert r.allowed is True

    def test_blocked_result(self) -> None:
        r = GuardResult(allowed=False, reason="preflight not passed")
        assert r.allowed is False


class TestCheckTransition:
    def test_launch_to_preflight_always_allowed(self) -> None:
        state = {"phase": "launch", "status": "launching"}
        result = check_transition(state, "preflight")
        assert result.allowed is True

    def test_preflight_to_research_requires_preflight_passed(self) -> None:
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "failed",
        }
        result = check_transition(state, "research")
        assert result.allowed is False
        assert "preflight" in result.reason.lower()

    def test_preflight_to_research_allowed_when_passed(self) -> None:
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "passed",
        }
        result = check_transition(state, "research")
        assert result.allowed is True

    def test_preflight_to_research_allowed_via_overall(self) -> None:
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight": {"overall": "PASS"},
        }
        result = check_transition(state, "research")
        assert result.allowed is True

    def test_research_to_spec_requires_evidence(self) -> None:
        state = {"phase": "research", "status": "active"}
        result = check_transition(state, "spec")
        assert result.allowed is False
        assert "evidence" in result.reason.lower()

    def test_research_to_spec_allowed_with_evidence(self) -> None:
        state = {
            "phase": "research",
            "status": "active",
            "phase_evidence": {
                "research": {
                    "artifacts": ["notes.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_transition(state, "spec")
        assert result.allowed is True

    def test_spec_to_execute_requires_evidence(self) -> None:
        state = {"phase": "spec", "status": "active"}
        result = check_transition(state, "execute")
        assert result.allowed is False

    def test_spec_to_execute_allowed_with_evidence(self) -> None:
        state = {
            "phase": "spec",
            "status": "active",
            "phase_evidence": {
                "spec": {
                    "artifacts": ["spec.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_transition(state, "execute")
        assert result.allowed is True

    def test_execute_to_review_requires_evidence(self) -> None:
        state = {"phase": "execute", "status": "active"}
        result = check_transition(state, "review")
        assert result.allowed is False

    def test_execute_to_review_allowed_with_wp_complete(self) -> None:
        state = {
            "phase": "execute",
            "status": "active",
            "current_work_package": {"status": "complete"},
        }
        result = check_transition(state, "review")
        assert result.allowed is True

    def test_execute_to_review_allowed_with_evidence(self) -> None:
        state = {
            "phase": "execute",
            "status": "active",
            "phase_evidence": {
                "execute": {
                    "artifacts": ["build.log"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_transition(state, "review")
        assert result.allowed is True

    def test_backward_transition_blocked(self) -> None:
        state = {"phase": "execute", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False
        assert "backward" in result.reason.lower()

    def test_skip_transition_blocked(self) -> None:
        state = {"phase": "launch", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False

    def test_unknown_current_phase_blocked(self) -> None:
        state = {"phase": "custom", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False

    def test_unknown_target_phase_blocked(self) -> None:
        state = {"phase": "launch", "status": "active"}
        result = check_transition(state, "banana")
        assert result.allowed is False

    def test_terminal_status_blocks_transition(self) -> None:
        state = {"phase": "research", "status": "done"}
        result = check_transition(state, "spec")
        assert result.allowed is False
        assert "terminal" in result.reason.lower()
