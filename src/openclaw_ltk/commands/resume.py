"""Resume a long-running task from its persisted state."""

from __future__ import annotations

import json
from pathlib import Path

import click

from openclaw_ltk.clock import now, now_iso
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient
from openclaw_ltk.errors import LtkError
from openclaw_ltk.generators.heartbeat_entry import inject_heartbeat_entry
from openclaw_ltk.generators.workspace_bootstrap import (
    inject_agents_directive,
    inject_boot_entry,
)
from openclaw_ltk.memory import append_daily_memory_note
from openclaw_ltk.openclaw_cli import OpenClawClient
from openclaw_ltk.policies.continuation import (
    build_continuation_prompt,
    should_continue,
)
from openclaw_ltk.policies.exhaustion import evaluate_exhaustion
from openclaw_ltk.state import StateFile, atomic_write_text

from .preflight import print_preflight_results, run_preflight_checks


def _write_active_pointer(pointer_path: Path, task_id: str, state_path: Path) -> None:
    payload = {
        "task_id": task_id,
        "state_path": str(state_path),
        "set_at": now_iso("UTC"),
    }
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        pointer_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
    )


@click.command("resume")
@click.option("--state", "state_path", required=True, help="Path to state file")
def resume_cmd(state_path: str) -> None:
    """Run preflight, refresh bootstrap files, and print a continuation prompt."""
    config = LtkConfig.from_env()
    state_file = StateFile(Path(state_path).expanduser().resolve())

    try:
        state = state_file.load()
    except LtkError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        if exc.detail:
            click.echo(exc.detail, err=True)
        raise SystemExit(2) from exc

    overall, results = run_preflight_checks(
        state,
        config,
        cron_client=CronClient(),
        openclaw=OpenClawClient(),
    )
    if overall != "PASS":
        click.echo("Preflight failed.")
        print_preflight_results(overall, results)
        raise SystemExit(1)

    resolved_state_path = state_file.path
    task_id = str(state.get("task_id", resolved_state_path.stem))
    title = str(state.get("title", "untitled"))
    goal = str(state.get("goal", ""))
    status = str(state.get("status", "active"))
    updated_at = str(state.get("updated_at", now_iso(config.timezone)))

    inject_heartbeat_entry(
        config.heartbeat_path,
        task_id=task_id,
        title=title,
        status=status,
        goal=goal,
        updated_at=updated_at,
    )
    inject_boot_entry(
        config.boot_path,
        task_id=task_id,
        title=title,
        goal=goal,
        state_path=str(resolved_state_path),
    )
    inject_agents_directive(
        config.agents_path,
        task_id=task_id,
        state_path=str(resolved_state_path),
        config_hints={"timeout_seconds": config.timeout_seconds},
    )
    _write_active_pointer(config.pointer_path, task_id, resolved_state_path)
    append_daily_memory_note(
        config,
        now(config.timezone),
        f"Resume checkpoint for {task_id} from {resolved_state_path}",
    )

    decision = should_continue(state)
    exhaustion = evaluate_exhaustion(state)

    click.echo(build_continuation_prompt(state))
    if not decision.should_continue:
        click.echo(f"\nResume note: {decision.reason}")
    if exhaustion.action != "continue":
        click.echo(
            f"\nExhaustion: action={exhaustion.action} | reason={exhaustion.reason}"
        )
