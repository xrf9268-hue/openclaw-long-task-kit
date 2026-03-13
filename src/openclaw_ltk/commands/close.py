"""Control plane close command — removes cron jobs and heartbeat entry for a task."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient, CronJob
from openclaw_ltk.errors import CronError
from openclaw_ltk.generators.heartbeat_entry import remove_heartbeat_entry
from openclaw_ltk.schema import nested_get
from openclaw_ltk.state import StateFile


def _find_matching_jobs(
    live_jobs: list[CronJob],
    declared: list[Any],
) -> list[CronJob]:
    """Return live jobs whose names match declared cron job entries.

    Declared entries are expected to be dicts with a 'name' key, or plain strings.
    """
    declared_names: set[str] = set()
    for entry in declared:
        name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
        if name:
            declared_names.add(name)

    return [job for job in live_jobs if job.name in declared_names]


@click.command("close")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--write-back", is_flag=True, help="Update state status to 'closed'")
def close_cmd(state_path: str, write_back: bool) -> None:
    """Close the control plane: remove cron jobs and heartbeat entry."""
    config = LtkConfig.from_env()
    cron_client = CronClient()

    # Step 1 — verify cron is available.
    if not cron_client.is_available():
        click.echo(
            "ERROR: openclaw not on PATH; cannot close control plane.",
            err=True,
        )
        sys.exit(3)

    # Step 2 — load state file.
    sf = StateFile(Path(state_path))
    try:
        state = sf.load()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"FATAL: could not load state file: {exc}", err=True)
        sys.exit(2)

    task_id: str = state.get("task_id", "")

    # Step 3 — find live cron jobs that match declared jobs in state.
    declared: list[Any] = nested_get(state, "control_plane.cron_jobs") or []
    removed: list[str] = []
    disabled: list[str] = []
    failed: list[str] = []

    if declared:
        try:
            live_jobs = cron_client.list_jobs()
        except CronError as exc:
            click.echo(f"ERROR: could not list cron jobs: {exc}", err=True)
            sys.exit(3)

        matching = _find_matching_jobs(live_jobs, declared)

        # Step 4 — remove or disable each matching job.
        for job in matching:
            try:
                cron_client.remove_job(job.id)
                removed.append(job.name)
            except CronError:
                # Fallback: try to disable instead.
                try:
                    cron_client.disable_job(job.id)
                    disabled.append(job.name)
                except CronError as exc2:
                    failed.append(f"{job.name}: {exc2}")

    # Step 5 — remove heartbeat entry.
    heartbeat_ok = True
    if task_id:
        try:
            remove_heartbeat_entry(config.heartbeat_path, task_id)
        except Exception as exc:  # noqa: BLE001
            heartbeat_ok = False
            click.echo(f"WARNING: could not remove heartbeat entry: {exc}", err=True)

    # Step 6 — optional write-back.
    if write_back:
        try:
            with sf.locked_update() as data:
                data["status"] = "closed"
        except Exception as exc:  # noqa: BLE001
            click.echo(f"WARNING: write-back failed: {exc}", err=True)

    # Step 7 — print result.
    partial = bool(failed) or not heartbeat_ok
    overall = "PARTIAL" if partial else "CLOSED"
    click.echo(overall)
    if removed:
        click.echo(f"  removed: {', '.join(removed)}")
    if disabled:
        click.echo(f"  disabled (remove failed): {', '.join(disabled)}")
    if failed:
        click.echo(f"  failed: {'; '.join(failed)}")
    if not declared:
        click.echo("  no cron jobs declared in control_plane")
    if heartbeat_ok and task_id:
        click.echo("  heartbeat entry removed")

    sys.exit(0)
