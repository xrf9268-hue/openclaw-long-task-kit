"""Watchdog management commands — arm, disarm, and renew task watchdog cron jobs."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient
from openclaw_ltk.errors import CronError, StateFileError
from openclaw_ltk.generators.cron_matrix import build_watchdog_spec
from openclaw_ltk.state import StateFile


def _get_task_id(state_path: str) -> str:
    """Load state and return task_id, exiting on error."""
    sf = StateFile(Path(state_path))
    try:
        state = sf.load()
    except (StateFileError, OSError) as exc:
        click.echo(f"FATAL: could not load state file: {exc}", err=True)
        sys.exit(2)
    task_id: str = state.get("task_id", "")
    if not task_id:
        click.echo("FATAL: state file is missing 'task_id'", err=True)
        sys.exit(2)
    return task_id


def _watchdog_job_name(task_id: str) -> str:
    return f"watchdog-{task_id}"


def _find_watchdog_job_id(cron_client: CronClient, task_id: str) -> str | None:
    """Return the job ID of an existing watchdog job for *task_id*, or None."""
    name = _watchdog_job_name(task_id)
    try:
        jobs = cron_client.list_jobs()
    except CronError as exc:
        click.echo(f"ERROR: could not list cron jobs: {exc}", err=True)
        sys.exit(3)
    for job in jobs:
        if job.name == name:
            return job.id
    return None


@click.group("watchdog")
def watchdog_cmd() -> None:
    """Manage task watchdog cron jobs."""


# ---------------------------------------------------------------------------
# arm subcommand
# ---------------------------------------------------------------------------


@watchdog_cmd.command("arm")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option(
    "--at", "at_iso", required=True, help="ISO-8601 time at which watchdog fires"
)
def arm_cmd(state_path: str, at_iso: str) -> None:
    """Create a watchdog cron job that fires at the given ISO time."""
    config = LtkConfig.from_env()
    cron_client = CronClient()

    if not cron_client.is_available():
        click.echo("ERROR: openclaw binary not available on PATH", err=True)
        sys.exit(3)

    task_id = _get_task_id(state_path)
    spec = build_watchdog_spec(
        task_id=task_id,
        at_iso=at_iso,
        telegram_chat_id=config.telegram_chat_id,
    )

    try:
        job_id = cron_client.add_job(spec)
    except CronError as exc:
        click.echo(f"ERROR: could not create watchdog job: {exc}", err=True)
        sys.exit(3)

    wname = _watchdog_job_name(task_id)
    click.echo(f"ARMED: watchdog job '{wname}' created (id={job_id}, at={at_iso})")
    sys.exit(0)


# ---------------------------------------------------------------------------
# disarm subcommand
# ---------------------------------------------------------------------------


@watchdog_cmd.command("disarm")
@click.option("--state", "state_path", required=True, help="Path to state file")
def disarm_cmd(state_path: str) -> None:
    """Remove the watchdog cron job for the given task."""
    cron_client = CronClient()

    if not cron_client.is_available():
        click.echo("ERROR: openclaw binary not available on PATH", err=True)
        sys.exit(3)

    task_id = _get_task_id(state_path)
    job_id = _find_watchdog_job_id(cron_client, task_id)

    if job_id is None:
        click.echo(f"DISARMED: no watchdog job found for task '{task_id}' (no-op)")
        sys.exit(0)

    try:
        cron_client.remove_job(job_id)
    except CronError as exc:
        click.echo(f"ERROR: could not remove watchdog job: {exc}", err=True)
        sys.exit(3)

    click.echo(f"DISARMED: watchdog job '{_watchdog_job_name(task_id)}' removed")
    sys.exit(0)


# ---------------------------------------------------------------------------
# renew subcommand
# ---------------------------------------------------------------------------


@watchdog_cmd.command("renew")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option(
    "--at", "at_iso", required=True, help="New ISO-8601 fire time for the watchdog"
)
def renew_cmd(state_path: str, at_iso: str) -> None:
    """Remove the old watchdog job and create a new one at the given ISO time."""
    config = LtkConfig.from_env()
    cron_client = CronClient()

    if not cron_client.is_available():
        click.echo("ERROR: openclaw binary not available on PATH", err=True)
        sys.exit(3)

    task_id = _get_task_id(state_path)
    name = _watchdog_job_name(task_id)

    # Remove existing watchdog if present.
    old_job_id = _find_watchdog_job_id(cron_client, task_id)
    if old_job_id is not None:
        try:
            cron_client.remove_job(old_job_id)
        except CronError as exc:
            click.echo(f"WARNING: could not remove old watchdog job: {exc}", err=True)
            # Continue to attempt creating the new job.

    # Create new watchdog.
    spec = build_watchdog_spec(
        task_id=task_id,
        at_iso=at_iso,
        telegram_chat_id=config.telegram_chat_id,
    )

    try:
        new_job_id = cron_client.add_job(spec)
    except CronError as exc:
        click.echo(f"ERROR: could not create new watchdog job: {exc}", err=True)
        sys.exit(3)

    click.echo(
        f"RENEWED: watchdog job '{name}' rescheduled (id={new_job_id}, at={at_iso})"
    )
    sys.exit(0)
