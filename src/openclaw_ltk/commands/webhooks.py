"""Webhook configuration helper commands."""

from __future__ import annotations

import json
import shlex
from typing import Any

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.openclaw_config import load_openclaw_config


def _minimal_hooks_config() -> dict[str, Any]:
    return {
        "hooks": {
            "enabled": True,
            "token": "REPLACE_WITH_SHARED_SECRET",
            "path": "/hooks",
        }
    }


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


def _build_webhook_payload(event: str, task_id: str, status: str) -> dict[str, str]:
    return {
        "event": event,
        "task_id": task_id,
        "status": status,
    }


def _endpoint_url(base_url: str, hooks_path: str, event: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = hooks_path if hooks_path.startswith("/") else f"/{hooks_path}"
    return f"{normalized_base}{normalized_path}/{event}"


def _render_curl_command(
    *,
    url: str,
    token: str,
    payload: dict[str, str],
) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return " ".join(
        [
            "curl",
            "-X",
            "POST",
            shlex.quote(url),
            "-H",
            shlex.quote("Content-Type: application/json"),
            "-H",
            shlex.quote(f"Authorization: Bearer {token}"),
            "--data",
            shlex.quote(payload_json),
        ]
    )


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
        payload = load_openclaw_config(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        click.echo(f"Failed to read OpenClaw config: {exc}")
        raise SystemExit(1) from exc

    errors = _validate_hooks_config(payload)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)

    click.echo("Webhooks config OK.")


@webhooks_cmd.command("payload")
@click.option(
    "--event",
    "event_name",
    required=True,
    type=click.Choice(["agent", "wake"]),
    help="Webhook event name.",
)
@click.option("--task-id", required=True, help="Task identifier.")
@click.option("--status", required=True, help="Task status to include in the payload.")
def payload_webhooks_cmd(event_name: str, task_id: str, status: str) -> None:
    """Render a minimal webhook JSON payload."""
    click.echo(
        json.dumps(
            _build_webhook_payload(event_name, task_id, status),
            ensure_ascii=False,
            indent=2,
        )
    )


@webhooks_cmd.command("curl")
@click.option(
    "--event",
    "event_name",
    required=True,
    type=click.Choice(["agent", "wake"]),
    help="Webhook event name.",
)
@click.option("--task-id", required=True, help="Task identifier.")
@click.option("--status", required=True, help="Task status to include in the payload.")
@click.option(
    "--base-url",
    default="http://127.0.0.1:3456",
    show_default=True,
    help="Base URL for the OpenClaw gateway.",
)
def curl_webhooks_cmd(
    event_name: str,
    task_id: str,
    status: str,
    base_url: str,
) -> None:
    """Render a curl preview using the configured hooks path and token."""
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

    errors = _validate_hooks_config(payload)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)

    hooks = payload["hooks"]
    if not isinstance(hooks, dict):
        click.echo("hooks block is missing")
        raise SystemExit(1)

    token = hooks.get("token")
    hooks_path = hooks.get("path")
    if not isinstance(token, str) or not isinstance(hooks_path, str):
        click.echo("hooks config is incomplete")
        raise SystemExit(1)

    request_payload = _build_webhook_payload(event_name, task_id, status)
    click.echo(
        _render_curl_command(
            url=_endpoint_url(base_url, hooks_path, event_name),
            token=token,
            payload=request_payload,
        )
    )
