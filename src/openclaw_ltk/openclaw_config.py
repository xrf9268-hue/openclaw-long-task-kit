"""Helpers for reading and minimally updating host-level OpenClaw config."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openclaw_ltk.state import atomic_write_text


def load_openclaw_config(path: Path) -> dict[str, Any]:
    """Load a host-level OpenClaw config and require a JSON object root."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("OpenClaw config must be a JSON object.")
    return raw


def write_openclaw_config(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a host-level OpenClaw config with stable indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
    )


def upsert_object_path(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copy of *payload* with object keys created/updated at *keys*."""
    updated = copy.deepcopy(payload)
    current: dict[str, Any] = updated

    for key in keys:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value

    current.update(dict(values))
    return updated


def validate_heartbeat_config(payload: Mapping[str, Any]) -> list[str]:
    """Return validation errors for `agents.defaults.heartbeat`."""
    current: object = payload
    for key in ("agents", "defaults", "heartbeat"):
        if not isinstance(current, dict):
            return ["agents.defaults.heartbeat block is missing"]
        current = current.get(key)

    if not isinstance(current, dict):
        return ["agents.defaults.heartbeat block is missing"]

    errors: list[str] = []
    every = current.get("every")
    target = current.get("target")

    if not isinstance(every, str) or not every.strip():
        errors.append("agents.defaults.heartbeat.every must be a non-empty string")
    if not isinstance(target, str) or not target.strip():
        errors.append("agents.defaults.heartbeat.target must be a non-empty string")
    return errors
