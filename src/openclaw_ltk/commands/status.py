"""Display the current status of a long-running task."""

from __future__ import annotations

from pathlib import Path

import click

from openclaw_ltk.clock import minutes_since
from openclaw_ltk.errors import LtkError
from openclaw_ltk.policies.deadman import check_deadman
from openclaw_ltk.schema import validate_state
from openclaw_ltk.state import StateFile


@click.command("status")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--brief", is_flag=True, help="Show brief one-line status")
def status_cmd(state_path: str, brief: bool) -> None:
    """Display the current status of a long-running task."""
    try:
        sf = StateFile(Path(state_path).expanduser().resolve())
        data = sf.load()
    except LtkError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(2) from exc

    task_id = data.get("task_id", "unknown")
    status = data.get("status", "unknown")
    phase = data.get("phase", "unknown")
    updated_at = data.get("updated_at", "")

    # Compute minutes since last update.
    mins_ago = "?"
    if updated_at:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(updated_at)
            mins_ago = f"{minutes_since(dt):.0f}"
        except (ValueError, TypeError):
            pass

    if brief:
        click.echo(f"{task_id} | {status} | {phase} | updated {mins_ago}m ago")
        return

    # Full mode.
    title = data.get("title", "untitled")
    goal = data.get("goal", "")
    cwp = data.get("current_work_package") or {}
    cwp_id = cwp.get("id", "-")
    cwp_goal = cwp.get("goal", "-")

    deadman = check_deadman(data)
    validation = validate_state(data)
    val_label = "valid" if validation.valid else "INVALID"

    click.echo(f"Task: {title} ({task_id})")
    click.echo(f"Status: {status}")
    click.echo(f"Phase: {phase}")
    click.echo(f"Goal: {goal}")
    click.echo(f"Work Package: {cwp_id} - {cwp_goal}")
    click.echo(f"Updated: {updated_at} ({mins_ago}m ago)")
    click.echo(f"Deadman: {deadman.status} — {deadman.message}")
    n_err = len(validation.errors)
    n_warn = len(validation.warnings)
    click.echo(f"Validation: {val_label} ({n_err} errors, {n_warn} warnings)")
