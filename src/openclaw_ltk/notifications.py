"""Wrapper-level notification rendering helpers."""

from __future__ import annotations

from typing import Any

from openclaw_ltk.policies.continuation import (
    format_continuation_summary,
    should_continue,
)
from openclaw_ltk.policies.exhaustion import (
    evaluate_exhaustion,
    format_exhaustion_summary,
)


def render_notification_summary(state: dict[str, Any]) -> str:
    """Render a concise task summary suitable for operators or bridges."""
    task_id = str(state.get("task_id", "unknown"))
    title = str(state.get("title", "untitled"))
    status = str(state.get("status", "unknown"))
    phase = str(state.get("phase", "unknown"))

    continuation = should_continue(state)
    exhaustion = evaluate_exhaustion(state)

    return "\n".join(
        [
            f"Task: {title} ({task_id})",
            f"Status: {status}",
            f"Phase: {phase}",
            format_continuation_summary(continuation),
            format_exhaustion_summary(exhaustion),
        ]
    )


def render_telegram_preview(chat_id: str, text: str) -> dict[str, str]:
    """Return a Telegram-compatible preview payload."""
    return {
        "chat_id": chat_id,
        "text": text,
    }
