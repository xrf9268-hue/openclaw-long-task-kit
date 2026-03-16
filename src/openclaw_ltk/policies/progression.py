"""Progression stall detection — identifies tasks stuck in a phase after
prerequisites have already been satisfied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PREFLIGHT_KEYWORDS = ("preflight", "pre-flight", "pre flight")
_TERMINAL_STATUSES = frozenset({"closed", "done", "failed", "cancelled"})


@dataclass
class ProgressionResult:
    """Result of checking for a progression stall."""

    stalled: bool
    reason: str
    suggested_action: str


def check_progression_stall(state: dict[str, Any]) -> ProgressionResult:
    """Detect post-preflight progression stalls.

    A stall is detected when:
    - ``phase`` is ``"preflight"``
    - ``preflight_status`` is ``"passed"`` (or ``preflight.overall`` is ``"PASS"``)

    This means preflight succeeded but the task was never advanced to the
    next phase, causing patrol/watchdog to repeat stale preflight reminders.
    """
    phase = state.get("phase", "")
    if phase != "preflight":
        return ProgressionResult(
            stalled=False,
            reason="Phase is not 'preflight'; no stall detected.",
            suggested_action="Continue normal execution.",
        )

    # Determine whether preflight has passed.
    preflight_status = state.get("preflight_status", "")
    preflight_block = state.get("preflight")
    preflight_overall = ""
    if isinstance(preflight_block, dict):
        preflight_overall = str(preflight_block.get("overall", ""))

    preflight_passed = preflight_status == "passed" or preflight_overall == "PASS"

    # Terminal tasks cannot be stalled.
    if str(state.get("status", "")).lower() in _TERMINAL_STATUSES:
        return ProgressionResult(
            stalled=False,
            reason="Task has terminal status; no stall applicable.",
            suggested_action="No action needed.",
        )

    if not preflight_passed:
        return ProgressionResult(
            stalled=False,
            reason="Preflight has not passed yet; phase='preflight' is expected.",
            suggested_action="Complete preflight checks.",
        )

    # Stall detected.  Build a detailed reason.
    next_step = str(state.get("next_step", ""))
    next_step_stale = any(kw in next_step.lower() for kw in _PREFLIGHT_KEYWORDS)

    reason_parts = ["Preflight already PASS but phase is still 'preflight'."]
    if next_step_stale:
        reason_parts.append(f"next_step still references preflight: {next_step!r}")

    return ProgressionResult(
        stalled=True,
        reason=" ".join(reason_parts),
        suggested_action=(
            "Update phase to the next stage (e.g. 'research' or 'spec'), "
            "create a new work package, attach fresh evidence, "
            "and refresh reporting timestamps."
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
