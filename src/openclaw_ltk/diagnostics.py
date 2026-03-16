"""Unified diagnostics event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DiagnosticEvent:
    """A structured event written to the JSONL diagnostics log."""

    ts: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ts": self.ts, "event": self.event}
        result.update(self.data)
        return result
