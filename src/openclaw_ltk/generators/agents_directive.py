"""Generate AGENTS.md directive snippets for long-task awareness."""

from __future__ import annotations

from typing import Any


def generate_agents_directive(
    task_id: str,
    state_path: str,
    config_hints: dict[str, Any] | None = None,
) -> str:
    """Generate an AGENTS.md directive snippet for long-task awareness.

    The output is a Markdown fragment that can be appended to an existing
    AGENTS.md file to make agents aware of the active long-running task.
    """
    lines = [
        f"## Long Task Directive: {task_id}",
        "",
        "This workspace has an active long-running task. Follow these rules:",
        "",
        f"1. Before any action, check task state: `ltk status --state {state_path}`",
        f"2. After work: `ltk preflight --state {state_path} --write-back`",
        "3. Do NOT modify the state file directly — use `ltk` commands",
        f"4. If stalled: `ltk watchdog renew --state {state_path} --at <ISO_TIME>`",
        "5. On session start, check the active pointer: `ltk pointer get`",
    ]

    if config_hints:
        timeout = config_hints.get("timeout_seconds")
        if timeout:
            lines.append(f"6. Session timeout is {timeout}s — plan work accordingly")

    lines.append("")
    return "\n".join(lines)
