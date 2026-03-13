"""Unified exception hierarchy for openclaw-long-task-kit."""

from __future__ import annotations

from pathlib import Path


class LtkError(Exception):
    """Base exception for all ltk errors."""

    def __init__(self, message: str = "", detail: str = "") -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class StateFileError(LtkError):
    """State file read/write/parse errors."""

    def __init__(
        self,
        message: str = "",
        detail: str = "",
        path: Path | None = None,
    ) -> None:
        self.path = path
        super().__init__(message=message, detail=detail)


class CronError(LtkError):
    """Openclaw cron subprocess errors."""


class OpenClawError(LtkError):
    """OpenClaw CLI subprocess / parse errors."""


class ValidationError(LtkError):
    """JSON schema / field validation errors."""

    def __init__(
        self,
        message: str = "",
        detail: str = "",
        field: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        self.field = field
        self.errors: list[str] = errors if errors is not None else []
        super().__init__(message=message, detail=detail)


class LockError(LtkError):
    """Lock acquisition/release errors."""
