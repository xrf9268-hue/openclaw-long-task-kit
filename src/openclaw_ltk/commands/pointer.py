"""Active task pointer commands — set, get, and clear the pointer file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.config import LtkConfig


@click.group("pointer")
def pointer_cmd() -> None:
    """Manage the active task pointer."""


# ---------------------------------------------------------------------------
# set subcommand
# ---------------------------------------------------------------------------


@pointer_cmd.command("set")
@click.option("--task-id", required=True, help="Task identifier to set as active")
@click.option(
    "--state-path", required=True, help="Absolute path to the task state file"
)
def set_cmd(task_id: str, state_path: str) -> None:
    """Write the active task pointer file."""
    config = LtkConfig.from_env()
    pointer_path: Path = config.pointer_path

    payload = {
        "task_id": task_id,
        "state_path": state_path,
        "set_at": now_utc_iso(),
    }

    try:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        click.echo(f"ERROR: could not write pointer file: {exc}", err=True)
        sys.exit(1)

    click.echo(f"SET: active task pointer -> '{task_id}' ({pointer_path})")
    sys.exit(0)


# ---------------------------------------------------------------------------
# get subcommand
# ---------------------------------------------------------------------------


@pointer_cmd.command("get")
def get_cmd() -> None:
    """Read and display the active task pointer."""
    config = LtkConfig.from_env()
    pointer_path: Path = config.pointer_path

    if not pointer_path.exists():
        click.echo(f"NOT_SET: no active task pointer at {pointer_path}", err=True)
        sys.exit(1)

    try:
        raw = pointer_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        click.echo(f"ERROR: pointer file contains invalid JSON: {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"ERROR: could not read pointer file: {exc}", err=True)
        sys.exit(1)

    click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(0)


# ---------------------------------------------------------------------------
# clear subcommand
# ---------------------------------------------------------------------------


@pointer_cmd.command("clear")
def clear_cmd() -> None:
    """Remove the active task pointer file."""
    config = LtkConfig.from_env()
    pointer_path: Path = config.pointer_path

    if not pointer_path.exists():
        click.echo("CLEARED: pointer file was not present (no-op)")
        sys.exit(0)

    try:
        pointer_path.unlink()
    except OSError as exc:
        click.echo(f"ERROR: could not remove pointer file: {exc}", err=True)
        sys.exit(1)

    click.echo(f"CLEARED: active task pointer removed ({pointer_path})")
    sys.exit(0)
