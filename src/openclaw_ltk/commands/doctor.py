"""Doctor command wrapper for upstream `openclaw doctor`."""

from __future__ import annotations

import json
import platform
from typing import Any

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.config import LtkConfig
from openclaw_ltk.errors import OpenClawError
from openclaw_ltk.logging import write_diagnostic_event
from openclaw_ltk.openclaw_cli import OpenClawClient
from openclaw_ltk.openclaw_config import (
    load_openclaw_config,
    validate_heartbeat_config,
)


def _nested_get(payload: object, *keys: str) -> object | None:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _runtime_check(
    name: str,
    ok: bool,
    detail: str,
    *,
    hint: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    check: dict[str, Any] = {
        "name": name,
        "ok": ok,
        "detail": detail,
    }
    if hint is not None:
        check["hint"] = hint
    if source is not None:
        check["source"] = source
    return check


def _heartbeat_config_check(config: LtkConfig) -> dict[str, Any]:
    path = config.openclaw_config_path
    source = str(path)
    hint = (
        "Add agents.defaults.heartbeat.every and target to the OpenClaw config "
        "so HEARTBEAT.md can drive unattended work."
    )
    if not path.exists():
        return _runtime_check(
            "heartbeat-config",
            False,
            f"OpenClaw config file not found at {path}",
            hint=hint,
            source=source,
        )

    try:
        raw = load_openclaw_config(path)
    except (OSError, ValueError) as exc:
        return _runtime_check(
            "heartbeat-config",
            False,
            f"Failed to read OpenClaw config at {path}: {exc}",
            hint=hint,
            source=source,
        )

    errors = validate_heartbeat_config(raw)
    if errors:
        return _runtime_check(
            "heartbeat-config",
            False,
            f"Heartbeat config in {path} is invalid: {'; '.join(errors)}",
            hint=hint,
            source=source,
        )

    return _runtime_check(
        "heartbeat-config",
        True,
        f"Heartbeat config present in {path}",
        source=source,
    )


def _linux_linger_check(openclaw: OpenClawClient) -> dict[str, Any]:
    hint = (
        'Run `loginctl enable-linger "$USER"` or move the gateway to a system '
        "service. Example template: templates/systemd-user/openclaw-ltk.service.example"
    )
    try:
        status = openclaw.gateway_status()
    except OpenClawError as exc:
        return _runtime_check(
            "linux-linger",
            False,
            f"Failed to inspect gateway service state: {exc.message}",
            hint=hint,
            source="openclaw gateway status --json",
        )

    scope = _nested_get(status, "service", "scope")
    linger_enabled = _nested_get(status, "service", "linger_enabled")

    if scope == "system" or linger_enabled is True:
        return _runtime_check(
            "linux-linger",
            True,
            "Gateway persistence looks compatible with Linux 24/7 operation",
            source="openclaw gateway status --json",
        )

    if scope == "user":
        detail = (
            "Gateway appears to rely on a user-scoped service without lingering enabled"
        )
    else:
        detail = "Gateway status did not confirm lingering or a system-level service"

    return _runtime_check(
        "linux-linger",
        False,
        detail,
        hint=hint,
        source="openclaw gateway status --json",
    )


def _collect_runtime_checks(
    config: LtkConfig,
    openclaw: OpenClawClient,
) -> list[dict[str, Any]]:
    checks = [_heartbeat_config_check(config)]
    if platform.system() == "Linux":
        checks.append(_linux_linger_check(openclaw))
    return checks


def _merge_doctor_payload(
    payload: Any,
    runtime_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = dict(payload) if isinstance(payload, dict) else {"upstream": payload}

    merged["ltk_runtime_checks"] = runtime_checks
    upstream_ok = merged.get("ok", True)
    merged["ok"] = bool(upstream_ok) and all(
        bool(check.get("ok")) for check in runtime_checks
    )
    return merged


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

    payload = _merge_doctor_payload(payload, _collect_runtime_checks(config, client))
    indent = None if json_output else 2
    click.echo(json.dumps(payload, ensure_ascii=False, indent=indent))
