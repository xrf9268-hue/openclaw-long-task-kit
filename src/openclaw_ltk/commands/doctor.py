"""Doctor command wrapper for upstream `openclaw doctor`."""

from __future__ import annotations

import json

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.errors import OpenClawError
from openclaw_ltk.logging import write_diagnostic_event
from openclaw_ltk.openclaw_cli import OpenClawClient


@click.command("doctor")
@click.option("--repair", is_flag=True, help="Run guided repair actions when available")
@click.option("--deep", is_flag=True, help="Run deeper diagnostic probes")
@click.option("--json", "json_output", is_flag=True, help="Emit raw JSON output")
def doctor_cmd(repair: bool, deep: bool, json_output: bool) -> None:
    """Run OpenClaw health diagnostics."""
    config = LtkConfig.from_env()
    client = OpenClawClient()
    try:
        payload = client.doctor(repair=repair, deep=deep)
    except OpenClawError as exc:
        write_diagnostic_event(
            config.diagnostics_log_path,
            {
                "ts": now_utc_iso(),
                "event": "doctor_probe_failed",
                "command": "doctor",
                "repair": repair,
                "deep": deep,
                "error": exc.message,
                "detail": exc.detail,
            },
        )
        click.echo(f"ERROR: {exc.message}", err=True)
        if exc.detail:
            click.echo(exc.detail, err=True)
        raise SystemExit(2) from exc

    indent = None if json_output else 2
    click.echo(json.dumps(payload, ensure_ascii=False, indent=indent))
