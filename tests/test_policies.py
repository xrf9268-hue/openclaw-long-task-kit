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
