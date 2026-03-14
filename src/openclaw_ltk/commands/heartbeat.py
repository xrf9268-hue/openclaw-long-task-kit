"""Heartbeat configuration helper commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.openclaw_config import (
    load_openclaw_config,
    upsert_object_path,
    validate_heartbeat_config,
    write_openclaw_config,
)


def _minimal_heartbeat_config(*, every: str = "10m", target: str = "last") -> dict[str, Any]:
    return {
        "agents": {
            "defaults": {
                "heartbeat": {
                    "every": every,
                    "target": target,
                }
            }
        }
    }


def _load_existing_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_openclaw_config(path)


@click.group("heartbeat", invoke_without_command=True)
@click.pass_context
def heartbeat_cmd(ctx: click.Context) -> None:
    """Inspect or minimally update heartbeat-related OpenClaw config."""
    if ctx.invoked_subcommand is None:
        click.echo(json.dumps(_minimal_heartbeat_config(), ensure_ascii=False, indent=2))


@heartbeat_cmd.command("validate")
def validate_heartbeat_cmd() -> None:
    """Validate heartbeat settings in the local OpenClaw config."""
    config = LtkConfig.from_env()
    path = config.openclaw_config_path
    if not path.exists():
        click.echo(f"OpenClaw config file not found at {path}")
        raise SystemExit(1)

    try:
        payload = load_openclaw_config(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        click.echo(f"Failed to read OpenClaw config: {exc}")
        raise SystemExit(1) from exc

    errors = validate_heartbeat_config(payload)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)

    click.echo("Heartbeat config OK.")


@heartbeat_cmd.command("apply")
@click.option("--every", required=True, help="Heartbeat cadence, for example 10m")
@click.option("--target", required=True, help="Heartbeat target, for example last")
def apply_heartbeat_cmd(every: str, target: str) -> None:
    """Minimally upsert heartbeat settings in the local OpenClaw config."""
    config = LtkConfig.from_env()
    path = config.openclaw_config_path

    try:
        payload = _load_existing_config(path)
        updated = upsert_object_path(
            payload,
            ("agents", "defaults", "heartbeat"),
            {"every": every, "target": target},
        )
        write_openclaw_config(path, updated)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        click.echo(f"Failed to update OpenClaw config: {exc}")
        raise SystemExit(1) from exc

    click.echo(f"Updated heartbeat config in {path}")
    click.echo(
        json.dumps(
            _minimal_heartbeat_config(every=every, target=target)["agents"]["defaults"][
                "heartbeat"
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
