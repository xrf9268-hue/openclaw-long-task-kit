"""Control plane lock commands — acquire and release a named lock in the state file."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.errors import StateFileError
from openclaw_ltk.state import StateFile


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _add_seconds(iso: str, seconds: int) -> str:
    """Return an ISO-8601 UTC string *seconds* after the given *iso* timestamp."""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt + timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# Lock group
# ---------------------------------------------------------------------------


@click.group("lock")
def lock_cmd() -> None:
    """Acquire or release the control plane lock on a task state file."""


# ---------------------------------------------------------------------------
# acquire subcommand
# ---------------------------------------------------------------------------


@lock_cmd.command("acquire")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--owner", required=True, help="Lock owner identifier")
@click.option("--ttl", default=420, show_default=True, help="Lock TTL in seconds")
def acquire_cmd(state_path: str, owner: str, ttl: int) -> None:
    """Acquire the control plane lock.

    Exit codes: 0=acquired, 10=lock held by another, 11=invalid state, 2=fatal error.
    """
    sf = StateFile(Path(state_path))

    try:
        acquired = False
        renewed = False
        conflict_owner: str | None = None

        with sf.locked_update() as data:
            # Ensure control_plane namespace exists.
            cp: dict[str, Any] = data.setdefault("control_plane", {})
            existing_lock: dict[str, Any] | None = cp.get("lock")

            if existing_lock and isinstance(existing_lock, dict):
                # Check if the existing lock has expired.
                expires_at_raw: str | None = existing_lock.get("expires_at")
                if expires_at_raw:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at_raw)
                        if expires_dt.tzinfo is None:
                            expires_dt = expires_dt.replace(tzinfo=UTC)
                        if _utc_now() < expires_dt:
                            # Lock is still valid — check if same owner.
                            if existing_lock.get("owner") == owner:
                                renewed = True
                                pass  # Same owner — fall through to refresh below.
                            else:
                                conflict_owner = existing_lock.get("owner", "unknown")
                                # Abort — raise to exit ctx.
                                raise _LockConflict(conflict_owner)
                    except _LockConflict:
                        raise
                    except (ValueError, TypeError, OverflowError):
                        # Unparseable expiry — treat as expired, allow overwrite.
                        pass
                if existing_lock.get("owner") == owner:
                    renewed = True

            acquired_at = now_utc_iso()
            cp["lock"] = {
                "owner": owner,
                "acquired_at": acquired_at,
                "expires_at": _add_seconds(acquired_at, ttl),
            }
            acquired = True

    except _LockConflict as exc:
        click.echo(f"LOCK_HELD: lock is held by '{exc.owner}'", err=True)
        sys.exit(10)
    except StateFileError as exc:
        click.echo(f"INVALID_STATE: {exc}", err=True)
        sys.exit(11)
    except OSError as exc:
        click.echo(f"FATAL: {exc}", err=True)
        sys.exit(2)

    if acquired:
        verb = "RENEWED" if renewed else "ACQUIRED"
        click.echo(f"{verb}: lock held by '{owner}' (ttl={ttl}s)")
        sys.exit(0)


# ---------------------------------------------------------------------------
# release subcommand
# ---------------------------------------------------------------------------


@lock_cmd.command("release")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--owner", required=True, help="Lock owner identifier")
def release_cmd(state_path: str, owner: str) -> None:
    """Release the control plane lock.

    Exit codes: 0=released, 10=lock held by another, 11=invalid state, 2=fatal error.
    """
    sf = StateFile(Path(state_path))

    try:
        with sf.locked_update() as data:
            cp: dict[str, Any] | None = data.get("control_plane")
            if not isinstance(cp, dict):
                raise _InvalidState("control_plane block is missing or not a dict")

            existing_lock: dict[str, Any] | None = cp.get("lock")
            if not existing_lock:
                # Nothing to release — idempotent success.
                click.echo("RELEASED: no lock was held")
                return

            if not isinstance(existing_lock, dict):
                raise _InvalidState("control_plane.lock is not a dict")

            current_owner = existing_lock.get("owner")
            if current_owner != owner:
                raise _LockConflict(current_owner or "unknown")

            cp.pop("lock", None)

    except _LockConflict as exc:
        click.echo(
            f"LOCK_HELD: lock is held by '{exc.owner}', cannot release", err=True
        )
        sys.exit(10)
    except _InvalidState as exc:
        click.echo(f"INVALID_STATE: {exc}", err=True)
        sys.exit(11)
    except StateFileError as exc:
        click.echo(f"INVALID_STATE: {exc}", err=True)
        sys.exit(11)
    except OSError as exc:
        click.echo(f"FATAL: {exc}", err=True)
        sys.exit(2)

    click.echo(f"RELEASED: lock for '{owner}' removed")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Internal sentinel exceptions (not part of the public API)
# ---------------------------------------------------------------------------


class _LockConflict(Exception):
    def __init__(self, owner: str) -> None:
        self.owner = owner
        super().__init__(owner)


class _InvalidState(Exception):
    pass
