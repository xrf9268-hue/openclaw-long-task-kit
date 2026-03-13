"""Structured local diagnostics helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_diagnostic_event(path: Path, event: dict[str, Any]) -> None:
    """Append one JSON object per line to the diagnostics log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
