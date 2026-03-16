"""Cron job spec generators for the 4 standard long-task lifecycle jobs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_iso(at_iso: str) -> datetime:
    """Parse an ISO-8601 string into an aware datetime (UTC if no tzinfo)."""
    dt = datetime.fromisoformat(at_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _to_iso(dt: datetime) -> str:
    """Serialise a datetime back to an ISO-8601 string."""
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Spec builders
# ---------------------------------------------------------------------------


def build_watchdog_spec(
    task_id: str,
    at_iso: str,
    telegram_chat_id: str = "",
) -> dict[str, Any]:
    """Build a watchdog cron spec that fires once at *at_iso* and self-deletes.

    The watchdog reminds the session to check on the task's current status.
    An optional *telegram_chat_id* is stored in meta for alert routing.
    """
    name = f"watchdog-{task_id}"
    text = (
        f"[LTK watchdog] Task '{task_id}' is due for a status check. "
        "Please verify progress, report current state, and remove this watchdog "
        "once the task has completed or is confirmed healthy."
    )
    spec: dict[str, Any] = {
        "name": name,
        "schedule": {"kind": "at", "at": at_iso},
        "payload": {"kind": "systemEvent", "text": text},
        "sessionTarget": "main",
        "enabled": True,
        "deleteAfterRun": True,
        "lightContext": True,
        "meta": {
            "taskId": task_id,
            "note": (
                "For sessionTarget=main, do not set delivery; "
                "OpenClaw forbids cron delivery config here."
            ),
        },
    }
    if telegram_chat_id:
        spec["meta"]["telegramChatId"] = telegram_chat_id
    return spec


def build_continuation_spec(
    task_id: str,
    interval_minutes: int = 5,
) -> dict[str, Any]:
    """Build a continuation cron spec that prompts the session every N minutes.

    *interval_minutes* controls the polling cadence (default: 5).
    A failure alert fires after 2 consecutive missed runs.
    """
    name = f"continuation-{task_id}"
    text = (
        f"[LTK continuation] Task '{task_id}' continuation prompt. "
        "If the task is still in progress, continue from where you left off. "
        "If it is complete, remove this continuation job."
    )
    return {
        "name": name,
        "schedule": {"kind": "every", "interval": f"{interval_minutes}m"},
        "payload": {"kind": "systemEvent", "text": text},
        "sessionTarget": "main",
        "enabled": True,
        "lightContext": True,
        "failureAlert": {"after": 2},
        "meta": {
            "taskId": task_id,
            "intervalMinutes": interval_minutes,
        },
    }


def build_deadman_spec(
    task_id: str,
    interval_minutes: int = 20,
) -> dict[str, Any]:
    """Build a deadman-switch cron spec that detects silence or stalls.

    Runs every *interval_minutes* (default: 20).  Uses announce delivery mode
    so that the alert surfaces even when the primary session is inactive.
    """
    name = f"deadman-{task_id}"
    text = (
        f"[LTK deadman] No recent activity detected for task '{task_id}'. "
        "Investigate whether the task has stalled, crashed, or silently failed, "
        "and take corrective action or close the task as appropriate."
    )
    return {
        "name": name,
        "schedule": {"kind": "every", "interval": f"{interval_minutes}m"},
        "payload": {"kind": "systemEvent", "text": text},
        "sessionTarget": "main",
        "enabled": True,
        "lightContext": True,
        "delivery": {"mode": "announce"},
        "meta": {
            "taskId": task_id,
            "intervalMinutes": interval_minutes,
        },
    }


def build_closure_check_spec(
    task_id: str,
    duration_minutes: int,
    at_iso: str | None = None,
) -> dict[str, Any]:
    """Build a closure-check cron spec that fires once after task completion.

    The fire time is *at_iso* + *duration_minutes* + 30-minute buffer.

    Raises
    ------
    ValueError
        If *at_iso* is ``None`` or not a valid absolute ISO 8601 timestamp.
    """
    if at_iso is None:
        raise ValueError(
            "at_iso must be an absolute ISO 8601 timestamp, got None"
        )

    try:
        start_dt = _parse_iso(at_iso)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"at_iso must be an absolute ISO 8601 timestamp, got {at_iso!r}"
        ) from exc

    name = f"closure-check-{task_id}"
    text = (
        f"[LTK closure-check] Task '{task_id}' should have completed by now. "
        "Verify that the task reached its goal, all artefacts are in place, "
        "cleanup has been performed, and the heartbeat entry is up to date."
    )

    fire_dt = start_dt + timedelta(minutes=duration_minutes + 30)
    schedule: dict[str, Any] = {"kind": "at", "at": _to_iso(fire_dt)}
    meta_note = f"Fires at start({at_iso}) + {duration_minutes}min + 30min buffer."

    return {
        "name": name,
        "schedule": schedule,
        "payload": {"kind": "systemEvent", "text": text},
        "sessionTarget": "main",
        "enabled": True,
        "deleteAfterRun": True,
        "lightContext": True,
        "meta": {
            "taskId": task_id,
            "durationMinutes": duration_minutes,
            "bufferMinutes": 30,
            "note": meta_note,
        },
    }


# ---------------------------------------------------------------------------
# Composite builder
# ---------------------------------------------------------------------------


def build_all_specs(
    task_id: str,
    duration_minutes: int,
    watchdog_at_iso: str | None = None,
    continuation_interval_minutes: int = 5,
    deadman_interval_minutes: int = 20,
    closure_at_iso: str | None = None,
    telegram_chat_id: str = "",
) -> list[dict[str, Any]]:
    """Build all 4 cron specs for a long-running task.

    Parameters
    ----------
    task_id:
        Unique identifier for the task.
    duration_minutes:
        Expected task duration, used to compute the closure-check fire time.
    watchdog_at_iso:
        ISO-8601 timestamp at which the watchdog should fire.  If omitted,
        defaults to *closure_at_iso* (or an empty placeholder string).
    continuation_interval_minutes:
        Polling cadence for the continuation job (default: 5).
    deadman_interval_minutes:
        Polling cadence for the deadman job (default: 20).
    closure_at_iso:
        ISO-8601 start timestamp used to compute the closure-check fire time.
        Must be an absolute ISO 8601 timestamp; raises ``ValueError`` if omitted.
    telegram_chat_id:
        Optional Telegram chat ID stored in the watchdog meta for alert routing.
    """
    watchdog_at = watchdog_at_iso or closure_at_iso or ""

    return [
        build_watchdog_spec(task_id, watchdog_at, telegram_chat_id),
        build_continuation_spec(task_id, continuation_interval_minutes),
        build_deadman_spec(task_id, deadman_interval_minutes),
        build_closure_check_spec(task_id, duration_minutes, closure_at_iso),
    ]
