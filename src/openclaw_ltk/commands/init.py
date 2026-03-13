"""ltk init — one-stop bootstrapper for a new long-running task.

Steps performed:
  1. Check state file not exists (unless --force).
  2. Generate full state data dict.
  3. Create watchdog cron job.
  4. Create continuation cron job.
  5. Create deadman cron job.
  6. Create closure-check cron job.
  7. Run preflight validation.
  8. Write cron job IDs back into state and save.
  9. Update bootstrap files (HEARTBEAT / BOOT / AGENTS / pointer).
 10. Output timeoutSeconds recommendation.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.clock import now, now_iso
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient
from openclaw_ltk.errors import CronError, LtkError, StateFileError
from openclaw_ltk.generators.cron_matrix import (
    build_closure_check_spec,
    build_continuation_spec,
    build_deadman_spec,
    build_watchdog_spec,
)
from openclaw_ltk.generators.heartbeat_entry import inject_heartbeat_entry
from openclaw_ltk.generators.workspace_bootstrap import (
    inject_agents_directive,
    inject_boot_entry,
)
from openclaw_ltk.memory import append_daily_memory_note
from openclaw_ltk.schema import ValidationResult, validate_state
from openclaw_ltk.state import StateFile, atomic_write_text

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert *text* to a URL-safe slug (ASCII + CJK characters preserved)."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] or "task"


def _build_state_data(
    *,
    task_id: str,
    title: str,
    goal: str,
    first_wp_goal: str,
    first_wp_done_when: str,
    task_type: str,
    now_str: str,
    next_report_due_str: str,
    silence_budget_minutes: int,
) -> dict[str, Any]:
    """Construct the initial state data dict (pure function, no I/O)."""
    return {
        "task_id": task_id,
        "title": title,
        "created_at": now_str,
        "updated_at": now_str,
        "status": "launching",
        "phase": "launch",
        "goal": goal,
        "current_work_package": {
            "id": "WP-1",
            "goal": first_wp_goal,
            "done_when": first_wp_done_when,
            "blockers": [],
        },
        "reporting": {
            "first_ack_sent_at": now_str,
            "next_report_due_at": next_report_due_str,
            "silence_budget_minutes": silence_budget_minutes,
        },
        "runtime": {
            "mode": "main_session",
            "session_or_worker_id": "agent:main",
            "alive_expectation": "active",
            "continuation_source": "task_state_file",
        },
        "control_plane": {
            "lock": {},
            "cron_jobs": {},  # filled later
        },
        "control_plane_hooks": {},
        "notes": [f"task_type={task_type}"],
    }


def _create_cron_jobs(
    cron_client: CronClient,
    task_id: str,
    config: LtkConfig,
    duration: int,
    watchdog_at_iso: str,
) -> dict[str, str]:
    """Create all four cron jobs and return a mapping of name -> job ID.

    Raises CronError on failure.
    """
    cron_jobs: dict[str, str] = {}

    # Watchdog
    click.echo("[3/10] Creating watchdog cron job.")
    watchdog_spec = build_watchdog_spec(
        task_id,
        watchdog_at_iso,
        telegram_chat_id=config.telegram_chat_id,
    )
    watchdog_id = cron_client.add_job(watchdog_spec)
    cron_jobs["watchdog"] = watchdog_id
    click.echo(f"       watchdog job id: {watchdog_id}")

    # Continuation
    click.echo("[4/10] Creating continuation cron job.")
    continuation_spec = build_continuation_spec(
        task_id,
        interval_minutes=config.continuation_interval_minutes,
    )
    continuation_id = cron_client.add_job(continuation_spec)
    cron_jobs["continuation"] = continuation_id
    click.echo(f"       continuation job id: {continuation_id}")

    # Deadman
    click.echo("[5/10] Creating deadman cron job.")
    deadman_spec = build_deadman_spec(
        task_id,
        interval_minutes=config.deadman_interval_minutes,
    )
    deadman_id = cron_client.add_job(deadman_spec)
    cron_jobs["deadman"] = deadman_id
    click.echo(f"       deadman job id: {deadman_id}")

    # Closure check
    click.echo("[6/10] Creating closure-check cron job.")
    closure_spec = build_closure_check_spec(
        task_id,
        duration_minutes=duration,
        at_iso=watchdog_at_iso,
    )
    closure_id = cron_client.add_job(closure_spec)
    cron_jobs["closure_check"] = closure_id
    click.echo(f"       closure-check job id: {closure_id}")

    return cron_jobs


def _run_init_preflight(data: dict[str, Any]) -> ValidationResult:
    """Run schema validation on the state data and return the result."""
    return validate_state(data)


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


# ---------------------------------------------------------------------------
# Command definition
# ---------------------------------------------------------------------------


@click.command("init")
@click.option("--title", required=True, help="Task title")
@click.option("--goal", required=True, help="Task goal")
@click.option(
    "--duration", required=True, type=int, help="Expected duration in minutes"
)
@click.option("--task-type", required=True, help="Task type (research, coding, etc.)")
@click.option("--first-wp-goal", required=True, help="First work package goal")
@click.option(
    "--first-wp-done-when", required=True, help="First work package completion criteria"
)
@click.option("--force", is_flag=True, help="Overwrite existing state file")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without executing"
)
@click.option(
    "--skip-cron", is_flag=True, help="Skip cron job creation (for offline/debug)"
)
def init_cmd(
    title: str,
    goal: str,
    duration: int,
    task_type: str,
    first_wp_goal: str,
    first_wp_done_when: str,
    force: bool,
    dry_run: bool,
    skip_cron: bool,
) -> None:
    """Bootstrap a new long-running task.

    Creates state file, cron jobs, and heartbeat entry.
    """

    # ------------------------------------------------------------------ #
    # Bootstrap config and derived values                                  #
    # ------------------------------------------------------------------ #
    config = LtkConfig.from_env()

    current_time = now(config.timezone)
    now_str = now_iso(config.timezone)
    task_id = f"{current_time.strftime('%Y-%m-%d')}-{_slugify(title)}"

    state_path = config.state_dir / f"{task_id}.json"
    state_file = StateFile(state_path)

    next_report_due = current_time + timedelta(minutes=10)
    next_report_due_str = next_report_due.isoformat()

    watchdog_at_iso = current_time.isoformat()

    if dry_run:
        click.echo("[dry-run] ltk init — no changes will be written.\n")
        click.echo(f"  task_id      : {task_id}")
        click.echo(f"  state_file   : {state_path}")
        click.echo(f"  heartbeat    : {config.heartbeat_path}")
        click.echo(f"  workspace    : {config.workspace}")
        click.echo(f"  skip_cron    : {skip_cron}")
        if not skip_cron:
            click.echo(
                "  cron jobs    : watchdog, continuation, deadman, closure-check"
            )
        click.echo("\n[dry-run] No files written, no cron jobs created.")
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Step 1 — Check state file not exists                                 #
    # ------------------------------------------------------------------ #
    click.echo(f"[1/10] Checking state file does not exist: {state_path}")
    try:
        state_file.ensure_not_exists(force=force)
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}")
        if exc.detail:
            click.echo(f"       {exc.detail}")
        sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 2 — Generate state data dict                                    #
    # ------------------------------------------------------------------ #
    click.echo("[2/10] Generating state data.")
    data = _build_state_data(
        task_id=task_id,
        title=title,
        goal=goal,
        first_wp_goal=first_wp_goal,
        first_wp_done_when=first_wp_done_when,
        task_type=task_type,
        now_str=now_str,
        next_report_due_str=next_report_due_str,
        silence_budget_minutes=config.silence_budget_minutes,
    )

    # ------------------------------------------------------------------ #
    # Steps 3–6 — Create cron jobs                                         #
    # ------------------------------------------------------------------ #
    cron_jobs: dict[str, str] = {}

    if skip_cron:
        click.echo("[3/10] Skipping watchdog cron (--skip-cron).")
        click.echo("[4/10] Skipping continuation cron (--skip-cron).")
        click.echo("[5/10] Skipping deadman cron (--skip-cron).")
        click.echo("[6/10] Skipping closure-check cron (--skip-cron).")
    else:
        cron_client = CronClient()

        if not cron_client.is_available():
            click.echo(
                "WARNING: 'openclaw' binary not found on PATH. "
                "Cron jobs will be skipped. Use --skip-cron to suppress this warning."
            )
            skip_cron = True

        if not skip_cron:
            try:
                cron_jobs = _create_cron_jobs(
                    cron_client, task_id, config, duration, watchdog_at_iso
                )
            except CronError as exc:
                click.echo(f"ERROR: Failed to create cron job: {exc.message}")
                if exc.detail:
                    click.echo(f"       {exc.detail}")
                sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 7 — Preflight validation                                        #
    # ------------------------------------------------------------------ #
    click.echo("[7/10] Running preflight validation.")
    result = _run_init_preflight(data)

    if result.warnings:
        for warn in result.warnings:
            click.echo(f"  WARN: {warn}")

    if not result.valid:
        click.echo("PREFLIGHT FAILED — state data has validation errors:")
        for err in result.errors:
            click.echo(f"  ERROR: {err}")
        sys.exit(1)

    click.echo("       Preflight passed.")

    # ------------------------------------------------------------------ #
    # Step 8 — Write cron job IDs back into state and save                #
    # ------------------------------------------------------------------ #
    click.echo("[8/10] Writing state file.")
    data["control_plane"]["cron_jobs"] = cron_jobs

    try:
        config.state_dir.mkdir(parents=True, exist_ok=True)
        state_file.save(data)
    except (StateFileError, LtkError) as exc:
        click.echo(f"ERROR: Failed to write state file: {exc.message}")
        if exc.detail:
            click.echo(f"       {exc.detail}")
        sys.exit(2)
    except OSError as exc:
        click.echo(f"ERROR: Failed to write state file: {exc}")
        sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 9 — Update bootstrap files                                     #
    # ------------------------------------------------------------------ #
    click.echo("[9/10] Updating bootstrap files.")
    try:
        inject_heartbeat_entry(
            heartbeat_path=config.heartbeat_path,
            task_id=task_id,
            title=title,
            status="launching",
            goal=goal,
            updated_at=now_str,
        )
        inject_boot_entry(
            config.boot_path,
            task_id=task_id,
            title=title,
            goal=goal,
            state_path=str(state_path),
        )
        inject_agents_directive(
            config.agents_path,
            task_id=task_id,
            state_path=str(state_path),
            config_hints={"timeout_seconds": config.timeout_seconds},
        )
        _write_active_pointer(config.pointer_path, task_id, state_path)
        append_daily_memory_note(
            config,
            current_time,
            f"Task initialised: {title} ({task_id})",
        )
    except OSError as exc:
        click.echo(f"ERROR: Failed to update bootstrap files: {exc}")
        sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 10 — Output timeoutSeconds recommendation                      #
    # ------------------------------------------------------------------ #
    click.echo("[10/10] Timeout recommendation.")
    recommended_timeout = duration * 60
    click.echo(
        f"       Recommended timeoutSeconds: {recommended_timeout} "
        f"({duration} min * 60). "
        f"Current config: {config.timeout_seconds}s."
    )
    if config.timeout_seconds < recommended_timeout:
        click.echo(
            f"       NOTE: LTK_TIMEOUT_SECONDS ({config.timeout_seconds}) is less than "
            f"the recommended value ({recommended_timeout}). "
            "Consider increasing it via the LTK_TIMEOUT_SECONDS env var."
        )

    click.echo(f"\nTask '{task_id}' initialised successfully.")
    click.echo(f"  State file : {state_path}")
    click.echo(f"  Heartbeat  : {config.heartbeat_path}")
    click.echo(f"  BOOT file  : {config.boot_path}")
    click.echo(f"  AGENTS file: {config.agents_path}")
    click.echo(f"  Pointer    : {config.pointer_path}")
    if cron_jobs:
        for name, job_id in cron_jobs.items():
            click.echo(f"  Cron [{name}] : {job_id}")
    else:
        click.echo("  Cron jobs  : skipped")
