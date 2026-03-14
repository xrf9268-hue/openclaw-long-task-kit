"""Notification summary bridge command."""

from __future__ import annotations

import json
from pathlib import Path

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.errors import LtkError
from openclaw_ltk.notifications import (
    render_notification_summary,
    render_telegram_preview,
)
from openclaw_ltk.state import StateFile


@click.command("notify")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "telegram-json"]),
    default="text",
    show_default=True,
    help="Notification output format.",
)
def notify_cmd(state_path: str, output_format: str) -> None:
    """Render wrapper-level task notification summaries."""
    try:
        state = StateFile(Path(state_path).expanduser().resolve()).load()
    except LtkError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        if exc.detail:
            click.echo(exc.detail, err=True)
        raise SystemExit(2) from exc

    summary = render_notification_summary(state)
    if output_format == "text":
        click.echo(summary)
        return

    config = LtkConfig.from_env()
    if not config.telegram_chat_id:
        click.echo("LTK_TELEGRAM_CHAT_ID is not configured")
        raise SystemExit(1)

    click.echo(
        json.dumps(
            render_telegram_preview(config.telegram_chat_id, summary),
            ensure_ascii=False,
            indent=2,
        )
    )
