"""Report generation commands."""

from __future__ import annotations

from pathlib import Path

import click

from openclaw_ltk.errors import LtkError
from openclaw_ltk.report import render_issue_report
from openclaw_ltk.state import StateFile


@click.group("report")
def report_cmd() -> None:
    """Generate reports from task data."""


@report_cmd.command("issue")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--output", "output_path", default=None, help="Write report to file")
@click.option("--no-sanitize", is_flag=True, help="Disable sensitive data redaction")
def report_issue_cmd(
    state_path: str, output_path: str | None, no_sanitize: bool
) -> None:
    """Generate a Markdown issue report from task state."""
    try:
        state = StateFile(Path(state_path).expanduser().resolve()).load()
    except LtkError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(2) from exc

    report = render_issue_report(state, sanitize_output=not no_sanitize)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        click.echo(f"Report written to {out}")
    else:
        click.echo(report)
