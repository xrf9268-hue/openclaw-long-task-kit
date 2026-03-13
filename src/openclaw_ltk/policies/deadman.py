"""Deadman switch policy — detects stalled or silent tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from openclaw_ltk.clock import minutes_since


@dataclass
class DeadmanStatus:
    status: Literal["alive", "stale", "dead"]
    message: str
    minutes_silent: float


def check_deadman(
    state: dict[str, Any],
    silence_budget_minutes: int = 10,
    dead_threshold_minutes: int = 30,
) -> DeadmanStatus:
    """Check if the task appears to be stalled.

    Uses the 'updated_at' field from state to determine how long the task has
    been silent.

    Thresholds:
    - alive  : updated within silence_budget_minutes
    - stale  : updated between silence_budget_minutes and dead_threshold_minutes
    - dead   : no update for dead_threshold_minutes or more

    If updated_at is missing or unparseable, returns 'dead' with an
    appropriate message.
    """
    updated_at_raw: str | None = state.get("updated_at")

    # --- Missing timestamp ---
    if not updated_at_raw:
        return DeadmanStatus(
            status="dead",
            message="updated_at is missing — task has never reported progress.",
            minutes_silent=float("inf"),
        )

    # --- Unparseable timestamp ---
    try:
        updated_at: datetime = datetime.fromisoformat(updated_at_raw)
    except (ValueError, TypeError):
        return DeadmanStatus(
            status="dead",
            message=(
                f"updated_at unparseable: {updated_at_raw!r} — treating task as dead."
            ),
            minutes_silent=float("inf"),
        )

    elapsed = minutes_since(updated_at)

    if elapsed >= dead_threshold_minutes:
        return DeadmanStatus(
            status="dead",
            message=(
                f"No update for {elapsed:.1f} minutes "
                f"(dead threshold: {dead_threshold_minutes} min) — task is dead."
            ),
            minutes_silent=elapsed,
        )

    if elapsed >= silence_budget_minutes:
        return DeadmanStatus(
            status="stale",
            message=(
                f"No update for {elapsed:.1f} minutes "
                f"(silence budget: {silence_budget_minutes} min) — task is stale."
            ),
            minutes_silent=elapsed,
        )

    return DeadmanStatus(
        status="alive",
        message=(
            f"Last update {elapsed:.1f} minutes ago "
            f"(within silence budget of {silence_budget_minutes} min) — task is alive."
        ),
        minutes_silent=elapsed,
    )
