"""ltk init — one-stop bootstrapper for a new long-running task.

Steps performed:
  1. Check state file not exists (unless --force).
  2. Generate full state data dict.
  3. Create watchdog cron job.
  4. Create continuation cron job.
  5. Create deadman cron job.
  6. Create closure-check cron job.
  7. Update HEARTBEAT.md.
  8. Run preflight validation.
  9. Output timeoutSeconds recommendation.
 10. Write cron job IDs back into state and save.
"""

from __future__ import annotations

import re
import sys
from datetime import timedelta
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
from openclaw_ltk.schema import validate_state
from openclaw_ltk.state import StateFile

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert *text* to a URL-safe slug (ASCII + CJK characters preserved)."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] or "task"


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
    data: dict[str, Any] = {
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
            "silence_budget_minutes": config.silence_budget_minutes,
        },
        "runtime": {
            "mode": "main_session",
            "session_or_worker_id": "agent:main",
            "alive_expectation": "active",
            "continuation_source": "task_state_file",
        },
        "control_plane": {
            "lock": {},
            "cron_jobs": {},  # filled in step 10
        },
        "control_plane_hooks": {},
        "notes": [f"task_type={task_type}"],
    }

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
            # Step 3 — Watchdog
            click.echo("[3/10] Creating watchdog cron job.")
            try:
                watchdog_spec = build_watchdog_spec(
                    task_id,
                    watchdog_at_iso,
                    telegram_chat_id=config.telegram_chat_id,
                )
                watchdog_id = cron_client.add_job(watchdog_spec)
                cron_jobs["watchdog"] = watchdog_id
                click.echo(f"       watchdog job id: {watchdog_id}")
            except CronError as exc:
                click.echo(f"ERROR: Failed to create watchdog cron job: {exc.message}")
                if exc.detail:
                    click.echo(f"       {exc.detail}")
                sys.exit(2)

            # Step 4 — Continuation
            click.echo("[4/10] Creating continuation cron job.")
            try:
                continuation_spec = build_continuation_spec(
                    task_id,
                    interval_minutes=config.continuation_interval_minutes,
                )
                continuation_id = cron_client.add_job(continuation_spec)
                cron_jobs["continuation"] = continuation_id
                click.echo(f"       continuation job id: {continuation_id}")
            except CronError as exc:
                click.echo(
                    f"ERROR: Failed to create continuation cron job: {exc.message}"
                )
                if exc.detail:
                    click.echo(f"       {exc.detail}")
                sys.exit(2)

            # Step 5 — Deadman
            click.echo("[5/10] Creating deadman cron job.")
            try:
                deadman_spec = build_deadman_spec(
                    task_id,
                    interval_minutes=config.deadman_interval_minutes,
                )
                deadman_id = cron_client.add_job(deadman_spec)
                cron_jobs["deadman"] = deadman_id
                click.echo(f"       deadman job id: {deadman_id}")
            except CronError as exc:
                click.echo(f"ERROR: Failed to create deadman cron job: {exc.message}")
                if exc.detail:
                    click.echo(f"       {exc.detail}")
                sys.exit(2)

            # Step 6 — Closure check
            click.echo("[6/10] Creating closure-check cron job.")
            try:
                closure_spec = build_closure_check_spec(
                    task_id,
                    duration_minutes=duration,
                    at_iso=watchdog_at_iso,
                )
                closure_id = cron_client.add_job(closure_spec)
                cron_jobs["closure_check"] = closure_id
                click.echo(f"       closure-check job id: {closure_id}")
            except CronError as exc:
                click.echo(
                    f"ERROR: Failed to create closure-check cron job: {exc.message}"
                )
                if exc.detail:
                    click.echo(f"       {exc.detail}")
                sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 7 — Update HEARTBEAT.md                                         #
    # ------------------------------------------------------------------ #
    click.echo(f"[7/10] Updating HEARTBEAT.md at {config.heartbeat_path}.")
    try:
        inject_heartbeat_entry(
            heartbeat_path=config.heartbeat_path,
            task_id=task_id,
            title=title,
            status="launching",
            goal=goal,
            updated_at=now_str,
        )
    except OSError as exc:
        click.echo(f"ERROR: Failed to update HEARTBEAT.md: {exc}")
        sys.exit(2)

    # ------------------------------------------------------------------ #
    # Step 8 — Preflight validation                                        #
    # ------------------------------------------------------------------ #
    click.echo("[8/10] Running preflight validation.")
    result = validate_state(data)

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
    # Step 9 — Output timeoutSeconds recommendation                        #
    # ------------------------------------------------------------------ #
    click.echo("[9/10] Timeout recommendation.")
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

    # ------------------------------------------------------------------ #
    # Step 10 — Write cron job IDs back into state and save               #
    # ------------------------------------------------------------------ #
    click.echo("[10/10] Writing state file.")
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

    click.echo(f"\nTask '{task_id}' initialised successfully.")
    click.echo(f"  State file : {state_path}")
    click.echo(f"  Heartbeat  : {config.heartbeat_path}")
    if cron_jobs:
        for name, job_id in cron_jobs.items():
            click.echo(f"  Cron [{name}] : {job_id}")
    else:
        click.echo("  Cron jobs  : skipped")
