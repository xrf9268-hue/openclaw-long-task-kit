"""Phase definitions, ordering, and transition guards.

Defines the standard phase progression for long-running tasks and the
guard functions that validate whether a phase transition is allowed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Ordered tuple of known phases.  Index position defines ordering.
KNOWN_PHASES: tuple[str, ...] = (
    "launch",
    "preflight",
    "research",
    "spec",
    "execute",
    "review",
    "done",
)

_PHASE_INDEX: dict[str, int] = {p: i for i, p in enumerate(KNOWN_PHASES)}


def phase_index(phase: str) -> int | None:
    """Return the zero-based index of *phase*, or None if unknown."""
    return _PHASE_INDEX.get(phase)


def is_known_phase(phase: str) -> bool:
    """Return True if *phase* is in the known phase list."""
    return phase in _PHASE_INDEX


def next_phase(current: str) -> str | None:
    """Return the phase after *current*, or None if at end or unknown."""
    idx = _PHASE_INDEX.get(current)
    if idx is None or idx >= len(KNOWN_PHASES) - 1:
        return None
    return KNOWN_PHASES[idx + 1]


@dataclass
class GuardResult:
    """Result of evaluating a transition guard."""

    allowed: bool
    reason: str


# Statuses that block all transitions.
_TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled", "closed"})

# Type alias for guard functions.
_GuardFn = Callable[[dict[str, Any]], GuardResult]


# ---------------------------------------------------------------------------
# Guard functions
# ---------------------------------------------------------------------------


def _guard_always_allow(state: dict[str, Any]) -> GuardResult:
    """No prerequisites — transition is always allowed."""
    return GuardResult(allowed=True, reason="No prerequisites required.")


def _guard_preflight_passed(state: dict[str, Any]) -> GuardResult:
    """Require preflight_status == 'passed' or preflight.overall == 'PASS'."""
    preflight_status = state.get("preflight_status", "")
    preflight_block = state.get("preflight")
    preflight_overall = ""
    if isinstance(preflight_block, dict):
        preflight_overall = str(preflight_block.get("overall", ""))

    if preflight_status == "passed" or preflight_overall == "PASS":
        return GuardResult(allowed=True, reason="Preflight passed.")
    return GuardResult(
        allowed=False,
        reason="Preflight has not passed. Run 'ltk preflight --write-back' first.",
    )


def _make_evidence_guard(phase_name: str) -> _GuardFn:
    """Return a guard that requires phase_evidence.<phase_name> to exist."""

    def _guard(state: dict[str, Any]) -> GuardResult:
        evidence = state.get("phase_evidence")
        if not isinstance(evidence, dict):
            return GuardResult(
                allowed=False,
                reason=(
                    f"No phase_evidence found. Record {phase_name} "
                    f"evidence before advancing."
                ),
            )
        phase_ev = evidence.get(phase_name)
        if not isinstance(phase_ev, dict) or not phase_ev.get("artifacts"):
            return GuardResult(
                allowed=False,
                reason=(
                    f"No evidence for '{phase_name}' phase. "
                    f"Record artifacts before advancing."
                ),
            )
        return GuardResult(
            allowed=True,
            reason=f"Phase '{phase_name}' evidence present.",
        )

    return _guard


def _guard_work_package_complete(state: dict[str, Any]) -> GuardResult:
    """Require the current work package to be complete or execute evidence."""
    cwp = state.get("current_work_package")
    if isinstance(cwp, dict) and (cwp.get("status") == "complete" or cwp.get("done")):
        return GuardResult(allowed=True, reason="Work package complete.")

    evidence = state.get("phase_evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("execute"), dict):
        return GuardResult(allowed=True, reason="Execute phase evidence present.")

    return GuardResult(
        allowed=False,
        reason=(
            "Work package not marked complete and no execute evidence. "
            "Mark work as done or record evidence before advancing."
        ),
    )


# Registry: maps target phase to its entry guard.
_GUARDS: dict[str, _GuardFn] = {
    "launch": _guard_always_allow,
    "preflight": _guard_always_allow,
    "research": _guard_preflight_passed,
    "spec": _make_evidence_guard("research"),
    "execute": _make_evidence_guard("spec"),
    "review": _guard_work_package_complete,
    "done": _guard_always_allow,
}


def check_transition(state: dict[str, Any], target: str) -> GuardResult:
    """Check whether transitioning to *target* phase is allowed.

    Validates:
    1. Status is not terminal.
    2. Current phase is known.
    3. Target phase is known.
    4. Target is the immediate next phase (no skipping, no backward).
    5. Phase-specific guard passes.
    """
    current = state.get("phase", "")
    status = str(state.get("status", ""))

    if status in _TERMINAL_STATUSES:
        return GuardResult(
            allowed=False,
            reason=f"Task has terminal status '{status}'; cannot transition.",
        )

    current_idx = phase_index(current)
    target_idx = phase_index(target)

    if current_idx is None:
        return GuardResult(
            allowed=False,
            reason=f"Current phase '{current}' is not a known phase.",
        )

    if target_idx is None:
        return GuardResult(
            allowed=False,
            reason=f"Target phase '{target}' is not a known phase.",
        )

    if target_idx <= current_idx:
        return GuardResult(
            allowed=False,
            reason=f"Cannot move backward from '{current}' to '{target}'.",
        )

    if target_idx != current_idx + 1:
        return GuardResult(
            allowed=False,
            reason=(
                f"Cannot skip from '{current}' to '{target}'; "
                f"must advance to adjacent phase "
                f"'{KNOWN_PHASES[current_idx + 1]}' first."
            ),
        )

    guard = _GUARDS.get(target, _guard_always_allow)
    return guard(state)
