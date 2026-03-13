"""Recoverable exhaustion strategy for long-running tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class ExhaustionResult:
    """Result of evaluating task resource exhaustion."""

    action: Literal["continue", "pause", "escalate", "abort"]
    reason: str
    suggested_next_step: str


def evaluate_exhaustion(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> ExhaustionResult:
    """Evaluate whether a task is approaching resource exhaustion.

    Checks status markers, error counts, and retry counts to determine
    the recommended recovery action.
    """
    cfg = config or {}
    max_errors = cfg.get("max_errors", 5)
    max_retries = cfg.get("max_retries", 3)

    status = state.get("status", "")
    error_count = state.get("error_count", 0)
    retry_count = state.get("retry_count", 0)

    # Explicit exhaustion marker in status.
    if status in ("exhausted", "resource_exhausted"):
        return ExhaustionResult(
            action="pause",
            reason=f"Task status is '{status}'",
            suggested_next_step=(
                "Wait for resources, then resume with 'ltk init --force'"
            ),
        )

    # Too many retries — give up.
    if isinstance(retry_count, int) and retry_count >= max_retries:
        return ExhaustionResult(
            action="abort",
            reason=f"Retry count ({retry_count}) >= max retries ({max_retries})",
            suggested_next_step="Investigate root cause before restarting",
        )

    # Error threshold breached — escalate to human.
    if isinstance(error_count, int) and error_count >= max_errors:
        return ExhaustionResult(
            action="escalate",
            reason=f"Error count ({error_count}) >= max errors ({max_errors})",
            suggested_next_step="Review errors and decide whether to continue or abort",
        )

    return ExhaustionResult(
        action="continue",
        reason="No exhaustion signals detected",
        suggested_next_step="Continue normal execution",
    )


def format_exhaustion_summary(result: ExhaustionResult) -> str:
    """Return a human-readable summary of the exhaustion decision."""
    return f"Exhaustion: action={result.action} | reason={result.reason}"
