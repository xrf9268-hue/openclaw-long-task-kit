"""Tests for workspace memory helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.memory import ensure_memory_files


def test_ensure_memory_files_creates_index_and_daily_file(tmp_path: Path) -> None:
    config = LtkConfig(workspace=tmp_path)
    now_local = datetime(2026, 3, 13, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    memory_index, daily_path = ensure_memory_files(config, now_local)

    assert memory_index == tmp_path / "MEMORY.md"
    assert daily_path == tmp_path / "memory" / "2026-03-13.md"
    assert memory_index.exists()
    assert daily_path.exists()
    assert "memory/2026-03-13.md" in memory_index.read_text(encoding="utf-8")
    assert "# Memory Notes" in daily_path.read_text(encoding="utf-8")
