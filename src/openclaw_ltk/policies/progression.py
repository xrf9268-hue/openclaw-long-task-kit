"""Progression stall detection — identifies tasks stuck in a phase after
prerequisites have already been satisfied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openclaw_ltk.phases import check_transition, is_known_phase, next_phase

_TERMINAL_STATUSES = frozenset({"closed", "done", "failed", "cancelled"})


@dataclass
class ProgressionResult:
    """Result of checking for a progression stall."""

    stalled: bool
    reason: str
    suggested_action: str


def check_progression_stall(state: dict[str, Any]) -> ProgressionResult:
    """Detect progression stalls at any known phase boundary.

    A stall is detected when:
    - The task is at a known phase.
    - The transition guard for the next phase would PASS.
    - But the task hasn't advanced.

    This generalises the original preflight-only detection to cover
    research→spec, spec→execute, and other transitions.
    """
    phase = state.get("phase", "")
    status = str(state.get("status", "")).lower()

    # Terminal tasks cannot be stalled.
    if status in _TERMINAL_STATUSES:
        return ProgressionResult(
            stalled=False,
            reason="Task has terminal status; no stall applicable.",
            suggested_action="No action needed.",
        )

    # Unknown phases — we can't evaluate stalls.
    if not is_known_phase(phase):
        return ProgressionResult(
            stalled=False,
            reason=f"Phase '{phase}' is not a known phase; skipping stall check.",
            suggested_action="Continue normal execution.",
        )

    # If there's no next phase (e.g., "done"), no stall possible.
    target = next_phase(phase)
    if target is None:
        return ProgressionResult(
            stalled=False,
            reason=f"Phase '{phase}' is the final phase.",
            suggested_action="No action needed.",
        )

    # Check if the transition guard would allow advancing.
    guard_result = check_transition(state, target)

    if not guard_result.allowed:
        # Guard blocks transition — task is actively working, not stalled.
        return ProgressionResult(
            stalled=False,
            reason=(
                f"Phase '{phase}' prerequisites for '{target}' "
                f"not yet met: {guard_result.reason}"
            ),
            suggested_action=f"Complete '{phase}' phase requirements.",
        )

    # Guard passes but phase hasn't advanced — stall detected.
    return ProgressionResult(
        stalled=True,
        reason=(
            f"Phase '{phase}' exit criteria are met but task has not "
            f"advanced to '{target}'. "
            f"Guard check: {guard_result.reason}"
        ),
        suggested_action=(
            f"Run 'ltk advance --state <path> --to {target}' "
            f"to advance to the next phase."
        ),
    )


def format_progression_summary(result: ProgressionResult) -> str:
    """Return a human-readable summary of the progression check."""
    if result.stalled:
        return (
            f"Progression: STALLED — {result.reason}\n"
            f"  Suggested: {result.suggested_action}"
        )
    return f"Progression: ok — {result.reason}"
