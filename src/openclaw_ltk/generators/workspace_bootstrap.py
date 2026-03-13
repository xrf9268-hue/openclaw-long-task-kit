"""Helpers for idempotent BOOT.md / AGENTS.md long-task bootstrap blocks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openclaw_ltk.generators.agents_directive import generate_agents_directive
from openclaw_ltk.generators.boot_entry import generate_boot_entry
from openclaw_ltk.state import atomic_write_text


def _block_pattern(kind: str, task_id: str) -> re.Pattern[str]:
    escaped = re.escape(task_id)
    return re.compile(
        rf"^<!-- ltk:{kind} task_id={escaped} -->\n.*?<!-- ltk:{kind}:end -->",
        re.MULTILINE | re.DOTALL,
    )


def _inject_block(path: Path, block: str, pattern: re.Pattern[str]) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, block + "\n")
        return

    original = path.read_text(encoding="utf-8")

    if pattern.search(original):
        updated = pattern.sub(block, original)
    else:
        separator = "\n" if original.endswith("\n") else "\n\n"
        updated = original + separator + block + "\n"

    atomic_write_text(path, updated)


def inject_boot_entry(
    path: Path,
    *,
    task_id: str,
    title: str,
    goal: str,
    state_path: str,
    recovery_steps: list[str] | None = None,
) -> None:
    body = generate_boot_entry(
        task_id=task_id,
        title=title,
        goal=goal,
        state_path=state_path,
        recovery_steps=recovery_steps,
    )
    block = "\n".join(
        [
            f"<!-- ltk:boot task_id={task_id} -->",
            body,
            "<!-- ltk:boot:end -->",
        ]
    )
    _inject_block(path, block, _block_pattern("boot", task_id))


def inject_agents_directive(
    path: Path,
    task_id: str,
    state_path: str,
    config_hints: dict[str, Any] | None = None,
) -> None:
    body = generate_agents_directive(
        task_id=task_id,
        state_path=state_path,
        config_hints=config_hints,
    )
    block = "\n".join(
        [
            f"<!-- ltk:agents task_id={task_id} -->",
            body.rstrip("\n"),
            "<!-- ltk:agents:end -->",
        ]
    )
    _inject_block(path, block, _block_pattern("agents", task_id))
