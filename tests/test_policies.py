"""Tests for policy modules (continuation, deadman, exhaustion, progression)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from openclaw_ltk.policies.continuation import (
    build_continuation_prompt,
    should_continue,
)
from openclaw_ltk.policies.deadman import check_deadman
from openclaw_ltk.policies.exhaustion import evaluate_exhaustion
from openclaw_ltk.policies.progression import check_progression_stall

# ---------------------------------------------------------------------------
# continuation
# ---------------------------------------------------------------------------


class TestShouldContinueActive:
    def test_active(self, sample_state_data: dict[str, Any]) -> None:
        result = should_continue(sample_state_data)
        assert result.should_continue is True


class TestShouldContinueDone:
    def test_done(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["status"] = "done"
        result = should_continue(sample_state_data)
        assert result.should_continue is False


class TestShouldContinueNoGoal:
    def test_empty_goal(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["goal"] = ""
        result = should_continue(sample_state_data)
        assert result.should_continue is False


class TestBuildContinuationPrompt:
    def test_contains_task_info(self, sample_state_data: dict[str, Any]) -> None:
        prompt = build_continuation_prompt(sample_state_data)
        assert sample_state_data["task_id"] in prompt
        assert sample_state_data["goal"] in prompt


# ---------------------------------------------------------------------------
# deadman
# ---------------------------------------------------------------------------


class TestDeadmanAlive:
    def test_recent_update(self) -> None:
        now = datetime.now(UTC)
        state = {"updated_at": now.isoformat()}
        result = check_deadman(state, silence_budget_minutes=10)
        assert result.status == "alive"


class TestDeadmanStale:
    def test_stale(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=15)
        state = {"updated_at": past.isoformat()}
        result = check_deadman(
            state, silence_budget_minutes=10, dead_threshold_minutes=30
        )
        assert result.status == "stale"


class TestDeadmanDead:
    def test_dead(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=45)
        state = {"updated_at": past.isoformat()}
        result = check_deadman(
            state, silence_budget_minutes=10, dead_threshold_minutes=30
        )
        assert result.status == "dead"


class TestDeadmanMissingUpdatedAt:
    def test_missing(self) -> None:
        state: dict[str, Any] = {}
        result = check_deadman(state)
        assert result.status == "dead"


# ---------------------------------------------------------------------------
# exhaustion
# ---------------------------------------------------------------------------


class TestExhaustionContinue:
    def test_normal(self, sample_state_data: dict[str, Any]) -> None:
        result = evaluate_exhaustion(sample_state_data)
        assert result.action == "continue"


class TestExhaustionPause:
    def test_exhausted_status(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["status"] = "exhausted"
        result = evaluate_exhaustion(sample_state_data)
        assert result.action == "pause"
        assert "ltk resume" in result.suggested_next_step
        assert "init --force" not in result.suggested_next_step


class TestExhaustionEscalate:
    def test_too_many_errors(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["error_count"] = 10
        result = evaluate_exhaustion(sample_state_data)
        assert result.action == "escalate"


class TestExhaustionAbort:
    def test_too_many_retries(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["retry_count"] = 5
        result = evaluate_exhaustion(sample_state_data)
        assert result.action == "abort"


# ---------------------------------------------------------------------------
# progression stall detection (issue #13)
# ---------------------------------------------------------------------------


class TestProgressionStallDetected:
    def test_preflight_passed_but_phase_still_preflight(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
            "preflight_status": "passed",
            "preflight": {"overall": "PASS"},
        }
        result = check_progression_stall(state)
        assert result.stalled is True
        assert "phase" in result.reason.lower()

    def test_preflight_passed_with_stale_next_step(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
            "preflight_status": "passed",
            "next_step": "repair and rerun preflight",
        }
        result = check_progression_stall(state)
        assert result.stalled is True
        assert "next_step" in result.reason.lower() or "phase" in result.reason.lower()

    def test_suggested_repair_mentions_phase_update(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
            "preflight_status": "passed",
        }
        result = check_progression_stall(state)
        assert "phase" in result.suggested_action.lower()


class TestProgressionNoStall:
    def test_phase_advanced_beyond_preflight(self) -> None:
        state: dict[str, Any] = {
            "phase": "research",
            "preflight_status": "passed",
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_preflight_not_yet_passed(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
            "preflight_status": "failed",
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_no_preflight_status(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_no_phase(self) -> None:
        state: dict[str, Any] = {
            "preflight_status": "passed",
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_terminal_status_not_stalled(self) -> None:
        """Closed/done/failed tasks should not report stall."""
        for status in ("closed", "done", "failed"):
            state: dict[str, Any] = {
                "phase": "preflight",
                "preflight_status": "passed",
                "status": status,
            }
            result = check_progression_stall(state)
            assert result.stalled is False, f"status={status} should not stall"


# ---------------------------------------------------------------------------
# generalised stall detection (issues #8-#12)
# ---------------------------------------------------------------------------


class TestGeneralisedStallDetection:
    def test_research_done_but_phase_not_advanced(self) -> None:
        """Issue #12: research evidence exists but phase is still 'research'."""
        state: dict[str, Any] = {
            "phase": "research",
            "status": "active",
            "phase_evidence": {
                "research": {
                    "artifacts": ["notes.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is True
        assert "research" in result.reason.lower()

    def test_spec_done_but_phase_not_advanced(self) -> None:
        state: dict[str, Any] = {
            "phase": "spec",
            "status": "active",
            "phase_evidence": {
                "spec": {
                    "artifacts": ["spec.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is True

    def test_no_evidence_no_stall(self) -> None:
        state: dict[str, Any] = {"phase": "research", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_execute_no_stall_without_evidence(self) -> None:
        state: dict[str, Any] = {"phase": "execute", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_done_phase_no_stall(self) -> None:
        state: dict[str, Any] = {"phase": "done", "status": "done"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_terminal_status_with_evidence_no_stall(self) -> None:
        state: dict[str, Any] = {
            "phase": "research",
            "status": "cancelled",
            "phase_evidence": {
                "research": {"artifacts": ["x"], "completed_at": "2026-01-01"},
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_unknown_phase_no_stall(self) -> None:
        state: dict[str, Any] = {"phase": "custom-thing", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_suggested_action_mentions_advance(self) -> None:
        state: dict[str, Any] = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "passed",
        }
        result = check_progression_stall(state)
        assert result.stalled is True
        assert "advance" in result.suggested_action.lower()

    def test_non_string_phase_no_crash(self) -> None:
        """P1: non-string phase should not crash."""
        state: dict[str, Any] = {"phase": ["bad"], "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_dict_phase_no_crash(self) -> None:
        state: dict[str, Any] = {"phase": {"x": 1}, "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_launch_phase_not_stalled(self) -> None:
        """P2: launch has always-allow guard, should not be flagged."""
        state: dict[str, Any] = {"phase": "launch", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_review_phase_not_stalled(self) -> None:
        """P2: review has always-allow guard, should not be flagged."""
        state: dict[str, Any] = {"phase": "review", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False
