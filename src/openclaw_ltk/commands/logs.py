"""Logs command wrapper for upstream `openclaw logs`."""

from __future__ import annotations

import click

from openclaw_ltk.errors import OpenClawError
from openclaw_ltk.openclaw_cli import OpenClawClient


@click.command("logs")
@click.option("--follow", is_flag=True, help="Follow log output")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON lines")
@click.option("--limit", type=int, default=None, help="Limit number of log lines")
@click.option("--local-time", is_flag=True, help="Render timestamps in local time")
def logs_cmd(
    follow: bool,
    json_output: bool,
    limit: int | None,
    local_time: bool,
) -> None:
    """Tail OpenClaw gateway logs."""
    client = OpenClawClient()
    try:
        client.logs(
            follow=follow,
            json_output=json_output,
            limit=limit,
            local_time=local_time,
        )
    except OpenClawError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        if exc.detail:
            click.echo(exc.detail, err=True)
        raise SystemExit(2) from exc
