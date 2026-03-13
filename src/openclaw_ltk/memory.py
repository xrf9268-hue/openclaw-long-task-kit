"""Workspace memory bootstrap helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.state import atomic_write_text


def _daily_memory_path(config: LtkConfig, now_local: datetime) -> Path:
    return config.memory_dir / f"{now_local.date().isoformat()}.md"


def ensure_memory_files(config: LtkConfig, now_local: datetime) -> tuple[Path, Path]:
    """Ensure MEMORY.md and today's daily memory file exist."""
    memory_index = config.memory_index_path
    daily_path = _daily_memory_path(config, now_local)

    memory_index.parent.mkdir(parents=True, exist_ok=True)
    config.memory_dir.mkdir(parents=True, exist_ok=True)

    daily_reference = f"memory/{daily_path.name}"
    if memory_index.exists():
        index_text = memory_index.read_text(encoding="utf-8")
    else:
        index_text = "# MEMORY\n\n## Daily Logs\n"

    if daily_reference not in index_text:
        separator = "" if index_text.endswith("\n") else "\n"
        index_text = f"{index_text}{separator}- {daily_reference}\n"
        atomic_write_text(memory_index, index_text)

    if not daily_path.exists():
        atomic_write_text(
            daily_path,
            "\n".join(
                [
                    "# Memory Notes",
                    "",
                    f"Date: {now_local.date().isoformat()}",
                    "",
                ]
            ),
        )

    return memory_index, daily_path


def append_daily_memory_note(
    config: LtkConfig,
    now_local: datetime,
    note: str,
) -> Path:
    """Append a timestamped note to today's daily memory file."""
    _, daily_path = ensure_memory_files(config, now_local)
    existing = daily_path.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    updated = f"{existing}{separator}- {now_local.isoformat()} {note}\n"
    atomic_write_text(daily_path, updated)
    return daily_path
