"""Memory helper commands."""

from __future__ import annotations

import click

from openclaw_ltk.clock import now
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.memory import append_daily_memory_note, list_daily_memory_files


@click.group("memory")
def memory_cmd() -> None:
    """Append or inspect minimal workspace memory notes."""


@memory_cmd.command("note")
@click.option("--message", required=True, help="Note text to append to today's memory.")
def note_memory_cmd(message: str) -> None:
    """Append a custom note to today's daily memory file."""
    config = LtkConfig.from_env()
    daily_path = append_daily_memory_note(config, now(config.timezone), message)
    click.echo(f"Appended memory note to {daily_path}")


@memory_cmd.command("list")
def list_memory_cmd() -> None:
    """List existing daily memory files, newest first."""
    config = LtkConfig.from_env()
    for path in list_daily_memory_files(config):
        click.echo(path)
