"""Webhook configuration helper commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.config import LtkConfig


def _minimal_hooks_config() -> dict[str, Any]:
    return {
        "hooks": {
            "enabled": True,
            "token": "REPLACE_WITH_SHARED_SECRET",
            "path": "/hooks",
        }
    }


def _load_openclaw_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("OpenClaw config must be a JSON object.")
    return raw


def _validate_hooks_config(payload: dict[str, Any]) -> list[str]:
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return ["hooks block is missing"]

    enabled = hooks.get("enabled")
    token = hooks.get("token")
    path = hooks.get("path")

    errors: list[str] = []
    if enabled is True and not token:
        errors.append("hooks.token is required when hooks.enabled=true")
    if enabled is True and not path:
        errors.append("hooks.path is required when hooks.enabled=true")
    return errors


@click.group("webhooks", invoke_without_command=True)
@click.pass_context
def webhooks_cmd(ctx: click.Context) -> None:
    """Inspect or generate webhook configuration snippets."""
    if ctx.invoked_subcommand is None:
        click.echo(json.dumps(_minimal_hooks_config(), ensure_ascii=False, indent=2))


@webhooks_cmd.command("validate")
def validate_webhooks_cmd() -> None:
    """Validate webhook-related settings in the local OpenClaw config."""
    config = LtkConfig.from_env()
    path = config.openclaw_config_path
    if not path.exists():
        click.echo(f"OpenClaw config file not found at {path}")
        raise SystemExit(1)

    try:
        payload = _load_openclaw_config(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        click.echo(f"Failed to read OpenClaw config: {exc}")
        raise SystemExit(1) from exc

    errors = _validate_hooks_config(payload)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)

    click.echo("Webhooks config OK.")
