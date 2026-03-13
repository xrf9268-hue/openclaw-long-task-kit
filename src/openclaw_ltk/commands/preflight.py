"""Preflight verification command — runs a suite of checks before task execution."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient
from openclaw_ltk.schema import (
    nested_get,
    validate_control_plane,
    validate_required_fields,
)
from openclaw_ltk.state import StateFile

# ---------------------------------------------------------------------------
# Individual check functions — each returns (passed: bool, detail: str)
# ---------------------------------------------------------------------------


def check_required_fields(state: dict[str, Any]) -> tuple[bool, str]:
    """Verify all required top-level fields are present and non-empty."""
    missing = validate_required_fields(state)
    if missing:
        return False, f"missing fields: {', '.join(missing)}"
    return True, "all required fields present"


def check_control_plane(state: dict[str, Any]) -> tuple[bool, str]:
    """Verify the control_plane block is structurally valid."""
    issues = validate_control_plane(state)
    if issues:
        return False, "; ".join(issues)
    return True, "control_plane valid"


def check_cron_coverage(
    state: dict[str, Any], cron_client: CronClient
) -> tuple[bool, str]:
    """Verify declared cron jobs are present and enabled."""
    declared: list[Any] = nested_get(state, "control_plane.cron_jobs") or []
    if not declared:
        return True, "no cron jobs declared in control_plane"

    try:
        live_jobs = cron_client.list_jobs()
    except Exception as exc:  # noqa: BLE001
        return False, f"could not list cron jobs: {exc}"

    live_by_name = {job.name: job for job in live_jobs}

    problems: list[str] = []
    for entry in declared:
        name = entry.get("name", "") if isinstance(entry, dict) else str(entry)

        if not name:
            continue

        job = live_by_name.get(name)
        if job is None:
            problems.append(f"'{name}' not found")
        elif not job.enabled:
            problems.append(f"'{name}' is disabled")

    if problems:
        return False, "; ".join(problems)
    return True, f"{len(declared)} job(s) present and enabled"


def check_heartbeat(config: LtkConfig) -> tuple[bool, str]:
    """Verify HEARTBEAT.md exists and contains a structured '## LTK:' marker."""
    path: Path = config.heartbeat_path
    if not path.exists():
        return False, f"HEARTBEAT.md not found at {path}"

    content = path.read_text(encoding="utf-8")
    # Require the structured marker used by inject_heartbeat_entry().
    if "## LTK:" not in content:
        return False, "HEARTBEAT.md exists but contains no '## LTK:' section marker"
    return True, "HEARTBEAT.md present and contains LTK marker"


def check_child_checkpoint(state: dict[str, Any]) -> tuple[bool, str]:
    """Verify child_execution.checkpoint if the block is present."""
    child = state.get("child_execution")
    if child is None:
        return True, "no child_execution block (skipped)"

    if not isinstance(child, dict):
        return False, "child_execution is not a dict"

    checkpoint = child.get("checkpoint")
    if checkpoint is None:
        return False, "child_execution.checkpoint is missing"
    return True, "child_execution.checkpoint present"


def check_post_restart_probe(state: dict[str, Any]) -> tuple[bool, str]:
    """Verify post_restart_probe.required_checks if the block is present."""
    probe = state.get("post_restart_probe")
    if probe is None:
        return True, "no post_restart_probe block (skipped)"

    if not isinstance(probe, dict):
        return False, "post_restart_probe is not a dict"

    required_checks = probe.get("required_checks")
    if not required_checks:
        return False, "post_restart_probe.required_checks is missing or empty"
    return True, f"{len(required_checks)} required check(s) declared"


def check_exec_approvals(config: LtkConfig) -> tuple[bool, str]:
    """Verify the exec-approvals file exists in the workspace."""
    # Convention: exec-approvals lives at workspace/exec-approvals.json or .md
    ws = config.workspace
    candidates = [
        ws / "exec-approvals.json",
        ws / "exec-approvals.md",
        ws / "exec-approvals.txt",
        ws / "exec-approvals",
    ]
    for candidate in candidates:
        if candidate.exists():
            return True, f"exec-approvals file found: {candidate.name}"
    return False, f"no exec-approvals file found in {ws}"


def check_active_pointer(config: LtkConfig) -> tuple[bool, str]:
    """Verify the active task pointer file exists."""
    path: Path = config.pointer_path
    if not path.exists():
        return False, f"active task pointer not found at {path}"
    return True, "active task pointer file present"


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

_CheckFn = Callable[[dict[str, Any], LtkConfig, CronClient], tuple[bool, str]]

_CHECKS: list[tuple[str, _CheckFn]] = [
    ("required-fields", lambda state, config, cron: check_required_fields(state)),
    ("control-plane", lambda state, config, cron: check_control_plane(state)),
    ("cron-coverage", lambda state, config, cron: check_cron_coverage(state, cron)),
    ("heartbeat", lambda state, config, cron: check_heartbeat(config)),
    ("child-checkpoint", lambda state, config, cron: check_child_checkpoint(state)),
    ("post-restart-probe", lambda state, config, cron: check_post_restart_probe(state)),
    ("exec-approvals", lambda state, config, cron: check_exec_approvals(config)),
    ("active-pointer", lambda state, config, cron: check_active_pointer(config)),
]


@click.command("preflight")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--write-back", is_flag=True, help="Write results into state.preflight")
def preflight_cmd(state_path: str, write_back: bool) -> None:
    """Run preflight checks before starting a long task."""
    config = LtkConfig.from_env()
    cron_client = CronClient()

    # Load state file.
    sf = StateFile(Path(state_path))
    try:
        state = sf.load()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"FATAL: could not load state file: {exc}", err=True)
        sys.exit(2)

    # Run all checks.
    results: list[tuple[str, bool, str]] = []
    all_passed = True
    for name, fn in _CHECKS:
        try:
            passed, detail = fn(state, config, cron_client)
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"exception: {exc}"
        results.append((name, passed, detail))
        if not passed:
            all_passed = False

    # Print summary.
    overall = "PASS" if all_passed else "FAIL"
    click.echo(overall)
    for name, passed, detail in results:
        mark = "\u2713" if passed else "\u2717"
        line = f"  [{mark}] {name}"
        if not passed:
            line += f": {detail}"
        click.echo(line)

    # Optional write-back.
    if write_back:
        try:
            with sf.locked_update() as data:
                data["preflight"] = {
                    "overall": overall,
                    "checks": {
                        name: {"passed": passed, "detail": detail}
                        for name, passed, detail in results
                    },
                }
        except Exception as exc:  # noqa: BLE001
            click.echo(f"WARNING: write-back failed: {exc}", err=True)

    sys.exit(0 if all_passed else 1)
