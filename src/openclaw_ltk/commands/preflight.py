"""Preflight verification command — runs a suite of checks before task execution."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from openclaw_ltk.config import LtkConfig
from openclaw_ltk.cron import CronClient
from openclaw_ltk.errors import StateFileError
from openclaw_ltk.openclaw_cli import OpenClawClient
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
        return True, "no cron jobs declared in control_plane (expected for --skip-cron)"

    try:
        live_jobs = cron_client.list_jobs()
    except Exception as exc:  # noqa: BLE001 — external process; keep broad catch
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
    """Verify the host-level exec-approvals file exists."""
    path = config.exec_approvals_path
    if path.exists():
        return True, f"host-level exec approvals file present: {path}"
    return False, f"host-level exec approvals file not found at {path}"


def check_active_pointer(config: LtkConfig) -> tuple[bool, str]:
    """Verify the active task pointer file exists."""
    path: Path = config.pointer_path
    if not path.exists():
        return False, f"active task pointer not found at {path}"
    return True, "active task pointer file present"


def check_gateway_health(
    config: LtkConfig, openclaw: OpenClawClient
) -> tuple[bool, str]:
    """Verify the local OpenClaw gateway responds to a health probe."""
    _ = config  # kept for future config-based overrides
    try:
        payload = openclaw.health()
    except Exception as exc:  # noqa: BLE001 - external command surface
        return False, f"gateway health probe failed: {exc}"

    if isinstance(payload, dict):
        if "ok" in payload and not bool(payload["ok"]):
            return False, f"gateway reported unhealthy payload: {payload}"
        if "healthy" in payload and not bool(payload["healthy"]):
            return False, f"gateway reported unhealthy payload: {payload}"
        status = payload.get("status")
        if isinstance(status, str) and status.lower() not in {"ok", "healthy", "pass"}:
            return False, f"gateway reported status={status!r}"

    return True, "gateway healthy"


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

_CheckFn = Callable[
    [dict[str, Any], LtkConfig, CronClient, OpenClawClient], tuple[bool, str]
]
_CheckSource = Callable[[LtkConfig], str] | str

_CHECKS: list[tuple[str, _CheckSource, _CheckFn]] = [
    (
        "required-fields",
        "state file",
        lambda state, config, cron, openclaw: check_required_fields(state),
    ),
    (
        "control-plane",
        "state file",
        lambda state, config, cron, openclaw: check_control_plane(state),
    ),
    (
        "cron-coverage",
        "openclaw cron list --json",
        lambda state, config, cron, openclaw: check_cron_coverage(state, cron),
    ),
    (
        "heartbeat",
        "workspace HEARTBEAT.md",
        lambda state, config, cron, openclaw: check_heartbeat(config),
    ),
    (
        "gateway-health",
        "openclaw health --json",
        lambda state, config, cron, openclaw: check_gateway_health(
            config, openclaw
        ),
    ),
    (
        "child-checkpoint",
        "state file",
        lambda state, config, cron, openclaw: check_child_checkpoint(state),
    ),
    (
        "post-restart-probe",
        "state file",
        lambda state, config, cron, openclaw: check_post_restart_probe(state),
    ),
    (
        "exec-approvals",
        lambda config: str(config.exec_approvals_path),
        lambda state, config, cron, openclaw: check_exec_approvals(config),
    ),
    (
        "active-pointer",
        lambda config: str(config.pointer_path),
        lambda state, config, cron, openclaw: check_active_pointer(config),
    ),
]


def run_preflight_checks(
    state: dict[str, Any],
    config: LtkConfig,
    *,
    cron_client: CronClient | None = None,
    openclaw: OpenClawClient | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run all preflight checks and return overall status plus structured results."""
    cron = cron_client or CronClient()
    openclaw_client = openclaw or OpenClawClient()

    results: list[dict[str, Any]] = []
    all_passed = True

    for name, source, fn in _CHECKS:
        try:
            passed, detail = fn(state, config, cron, openclaw_client)
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all for arbitrary check functions
            passed = False
            detail = f"exception: {exc}"

        resolved_source = source(config) if callable(source) else source
        results.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
                "source": resolved_source,
            }
        )
        if not passed:
            all_passed = False

    return ("PASS" if all_passed else "FAIL"), results


def print_preflight_results(overall: str, results: list[dict[str, Any]]) -> None:
    """Render structured preflight results to stdout."""
    click.echo(overall)
    for item in results:
        name = str(item["name"])
        passed = bool(item["passed"])
        detail = str(item["detail"])
        mark = "\u2713" if passed else "\u2717"
        line = f"  [{mark}] {name}"
        if not passed:
            line += f": {detail}"
        click.echo(line)


@click.command("preflight")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--write-back", is_flag=True, help="Write results into state.preflight")
def preflight_cmd(state_path: str, write_back: bool) -> None:
    """Run preflight checks before starting a long task."""
    config = LtkConfig.from_env()

    # Load state file.
    sf = StateFile(Path(state_path))
    try:
        state = sf.load()
    except (StateFileError, OSError) as exc:
        click.echo(f"FATAL: could not load state file: {exc}", err=True)
        sys.exit(2)

    overall, results = run_preflight_checks(state, config)
    print_preflight_results(overall, results)

    # Optional write-back.
    if write_back:
        try:
            with sf.locked_update() as data:
                data["preflight"] = {
                    "overall": overall,
                    "checks": {
                        str(item["name"]): {
                            "passed": bool(item["passed"]),
                            "detail": str(item["detail"]),
                            "source": str(item["source"]),
                        }
                        for item in results
                    },
                }
        except (StateFileError, OSError) as exc:
            click.echo(f"WARNING: write-back failed: {exc}", err=True)

    sys.exit(0 if overall == "PASS" else 1)
