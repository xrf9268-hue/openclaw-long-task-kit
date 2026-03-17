"""Migrate command — upgrade state files to the current schema version."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from openclaw_ltk.errors import StateFileError
from openclaw_ltk.migration import (
    migrate_state,
    needs_migration,
)
from openclaw_ltk.state import StateFile


@click.command("migrate")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
def migrate_cmd(state_path: str, dry_run: bool) -> None:
    """Upgrade a state file to the current schema version."""
    sf = StateFile(Path(state_path))

    try:
        data = sf.load()
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        if exc.detail:
            click.echo(exc.detail, err=True)
        sys.exit(2)

    if not needs_migration(data):
        version = data.get("schema_version", 0)
        click.echo(
            f"State file already at current schema version (v{version}). "
            "No migration needed."
        )
        sys.exit(0)

    result = migrate_state(data)

    for msg in result.messages:
        click.echo(msg)

    if dry_run:
        click.echo(
            f"[dry-run] Would migrate v{result.from_version} → v{result.to_version}. "
            "No changes written."
        )
        sys.exit(0)

    try:
        sf.save(result.state)
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        sys.exit(2)

    click.echo(
        f"Migrated state file from v{result.from_version} to v{result.to_version}."
    )
