"""Configuration center for openclaw-long-task-kit.

All paths and runtime parameters are resolved here.
Callers are responsible for creating any directories they need.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

# Default workspace when no environment variable is set.
_DEFAULT_WORKSPACE = Path.home() / ".openclaw" / "workspace"


def _env(primary: str, fallback: str | None = None) -> str | None:
    """Return the first non-empty value found across env var names."""
    value = os.environ.get(primary, "").strip()
    if value:
        return value
    if fallback:
        value = os.environ.get(fallback, "").strip()
        if value:
            return value
    return None


@dataclasses.dataclass(frozen=True)
class LtkConfig:
    """Immutable configuration for the Long Task Kit runtime.

    All path fields are guaranteed to be Path objects after construction.
    No directories are created here; that is the caller's responsibility.
    """

    # Root workspace directory — all other paths derive from this by default.
    workspace: Path

    # Directory that holds per-task state files.
    state_dir: Path = dataclasses.field(default=Path())

    # Path to the HEARTBEAT.md liveness file.
    heartbeat_path: Path = dataclasses.field(default=Path())

    # Path to the BOOT.md startup record.
    boot_path: Path = dataclasses.field(default=Path())

    # Path to the active-task pointer JSON file.
    pointer_path: Path = dataclasses.field(default=Path())

    # IANA timezone name used for timestamps.
    timezone: str = "Asia/Shanghai"

    # Telegram chat ID for notifications; empty string means disabled.
    telegram_chat_id: str = ""

    # Maximum seconds a session may run before it is considered timed out.
    timeout_seconds: int = 1800

    # Minutes of silence allowed before a continuation prompt is required.
    silence_budget_minutes: int = 10

    # How often (minutes) the continuation cron job runs.
    continuation_interval_minutes: int = 5

    # How often (minutes) the deadman-switch cron job runs.
    deadman_interval_minutes: int = 20

    # Minutes without update before a task is considered dead.
    dead_threshold_minutes: int = 30

    def __post_init__(self) -> None:
        """Coerce string inputs to Path and backfill derived path defaults."""

        # Helper: resolve a field that may have been passed as a string.
        def _as_path(value: object) -> Path:
            return Path(value) if not isinstance(value, Path) else value  # type: ignore[arg-type]

        # Coerce workspace first so derived defaults are computed correctly.
        ws = _as_path(self.workspace)
        object.__setattr__(self, "workspace", ws)

        # Sentinel: an empty Path() signals "use the derived default".
        _sentinel = Path()

        derived: dict[str, Path] = {
            "state_dir": ws / "tasks" / "state",
            "heartbeat_path": ws / "HEARTBEAT.md",
            "boot_path": ws / "BOOT.md",
            "pointer_path": ws / "tasks" / ".active-task-pointer.json",
        }

        for field_name, default in derived.items():
            raw = getattr(self, field_name)
            coerced = _as_path(raw)
            # Use the derived default when the field still holds the sentinel.
            resolved = default if coerced == _sentinel else coerced
            object.__setattr__(self, field_name, resolved)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> LtkConfig:
        """Build an LtkConfig from environment variables.

        Primary prefix:  LTK_
        Fallback prefix: OPENCLAW_  (workspace only)

        Individual path overrides:
            LTK_WORKSPACE            — workspace root
            LTK_STATE_DIR            — state directory
            LTK_HEARTBEAT_PATH       — HEARTBEAT.md location
            LTK_BOOT_PATH            — BOOT.md location

        Scalar overrides:
            LTK_TIMEZONE                    — IANA timezone name
            LTK_TELEGRAM_CHAT_ID            — Telegram chat ID
            LTK_TIMEOUT_SECONDS             — session timeout (int)
            LTK_SILENCE_BUDGET_MINUTES      — silence budget (int)
            LTK_CONTINUATION_INTERVAL       — continuation cron interval (int)
            LTK_DEADMAN_INTERVAL            — deadman cron interval (int)
        """
        # Resolve workspace with LTK_ primary, OPENCLAW_ fallback.
        ws_raw = _env("LTK_WORKSPACE", "OPENCLAW_WORKSPACE")
        workspace = Path(ws_raw) if ws_raw else _DEFAULT_WORKSPACE

        # Optional individual path overrides (sentinel Path() = use default).
        def _opt_path(var: str) -> Path:
            raw = _env(var)
            return Path(raw) if raw else Path()

        # Optional integer overrides.
        def _opt_int(var: str, default: int) -> int:
            raw = _env(var)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError:
                import warnings

                warnings.warn(
                    f"Invalid integer for {var!r}: {raw!r}; using default {default}",
                    stacklevel=3,
                )
                return default

        return cls(
            workspace=workspace,
            state_dir=_opt_path("LTK_STATE_DIR"),
            heartbeat_path=_opt_path("LTK_HEARTBEAT_PATH"),
            boot_path=_opt_path("LTK_BOOT_PATH"),
            # pointer_path has no dedicated override; always derived.
            timezone=_env("LTK_TIMEZONE") or "Asia/Shanghai",
            telegram_chat_id=_env("LTK_TELEGRAM_CHAT_ID") or "",
            timeout_seconds=_opt_int("LTK_TIMEOUT_SECONDS", 1800),
            silence_budget_minutes=_opt_int("LTK_SILENCE_BUDGET_MINUTES", 10),
            continuation_interval_minutes=_opt_int("LTK_CONTINUATION_INTERVAL", 5),
            deadman_interval_minutes=_opt_int("LTK_DEADMAN_INTERVAL", 20),
            dead_threshold_minutes=_opt_int("LTK_DEAD_THRESHOLD_MINUTES", 30),
        )
