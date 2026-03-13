"""Continuation policy — decides whether a long-running task should keep running."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openclaw_ltk.clock import minutes_since

# Statuses that unconditionally stop execution.
_TERMINAL_STATUSES = {"done", "failed", "cancelled", "closed"}

# Statuses that suspend execution without being terminal.
_PAUSED_STATUSES = {"paused"}


@dataclass
class ContinuationDecision:
    should_continue: bool
    reason: str


def should_continue(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> ContinuationDecision:
    """Evaluate whether the task should continue running.

    Returns should_continue=False when:
    - status is 'done', 'failed', 'cancelled', or 'closed'
    - status is 'paused'
    - goal is empty or missing
    - current_work_package is missing or empty

    Returns should_continue=True otherwise with a reason explaining why.

    config can contain:
    - max_duration_minutes: int (if elapsed > max, stop)
    """
    cfg = config or {}

    status: str = state.get("status", "")
    goal: str = state.get("goal", "")
    work_package: Any = state.get("current_work_package")

    # --- Terminal status check ---
    if status in _TERMINAL_STATUSES:
        return ContinuationDecision(
            should_continue=False,
            reason=f"Task status is '{status}' — execution has ended.",
        )

    # --- Paused status check ---
    if status in _PAUSED_STATUSES:
        return ContinuationDecision(
            should_continue=False,
            reason="Task is paused — waiting for external signal to resume.",
        )

    # --- Goal check ---
    if not goal or not goal.strip():
        return ContinuationDecision(
            should_continue=False,
            reason="Task goal is empty — nothing to work towards.",
        )

    # --- Work package check ---
    if not work_package:
        return ContinuationDecision(
            should_continue=False,
            reason="current_work_package is missing or empty — no active unit of work.",
        )

    # --- Duration budget check (optional) ---
    max_duration: int | None = cfg.get("max_duration_minutes")
    if max_duration is not None:
        started_at_raw: str | None = state.get("started_at")
        if started_at_raw:
            try:
                started_at = datetime.fromisoformat(started_at_raw)
                elapsed = minutes_since(started_at)
                if elapsed > max_duration:
                    return ContinuationDecision(
                        should_continue=False,
                        reason=(
                            f"Task has been running for {elapsed:.1f} minutes, "
                            f"exceeding the configured limit of {max_duration} minutes."
                        ),
                    )
            except (ValueError, TypeError):
                pass  # Unparseable started_at — ignore the budget check.

    return ContinuationDecision(
        should_continue=True,
        reason=(
            f"Task is active (status='{status}') with a valid goal "
            f"and work package — continue execution."
        ),
    )


def build_continuation_prompt(state: dict[str, Any]) -> str:
    """Build a continuation prompt string for the agent.

    Includes task_id, current goal, current work package, status, and last
    updated timestamp as a concise reminder for the agent to pick up where
    it left off.
    """
    task_id: str = state.get("task_id", "(unknown)")
    goal: str = state.get("goal", "(no goal set)")
    work_package: str = state.get("current_work_package", "(none)")
    status: str = state.get("status", "(unknown)")
    updated_at: str = state.get("updated_at", "(never)")

    return (
        f"[TASK RESUME]\n"
        f"Task ID       : {task_id}\n"
        f"Status        : {status}\n"
        f"Last Updated  : {updated_at}\n"
        f"Goal          : {goal}\n"
        f"Current Work  : {work_package}\n"
        f"\n"
        f"Pick up where the task left off. Focus on the current work package above."
    )
