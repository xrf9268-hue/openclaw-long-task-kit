"""Tests for shared OpenClaw host-config helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw_ltk.openclaw_config import (
    load_openclaw_config,
    upsert_object_path,
    validate_heartbeat_config,
)


def test_load_openclaw_config_requires_object_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_openclaw_config(config_path)


def test_validate_heartbeat_config_reports_missing_fields() -> None:
    payload = {
        "agents": {
            "defaults": {
                "heartbeat": {
                    "every": "10m",
                }
            }
        }
    }

    errors = validate_heartbeat_config(payload)

    assert errors == ["agents.defaults.heartbeat.target must be a non-empty string"]


def test_upsert_object_path_preserves_unrelated_keys() -> None:
    payload = {
        "gateway": {"port": 3456},
        "agents": {
            "defaults": {
                "model": "gpt-5",
            }
        },
    }

    updated = upsert_object_path(
        payload,
        ("agents", "defaults", "heartbeat"),
        {
            "every": "15m",
            "target": "last",
        },
    )

    assert payload == {
        "gateway": {"port": 3456},
        "agents": {
            "defaults": {
                "model": "gpt-5",
            }
        },
    }
    assert updated["gateway"] == {"port": 3456}
    assert updated["agents"]["defaults"]["model"] == "gpt-5"
    assert updated["agents"]["defaults"]["heartbeat"] == {
        "every": "15m",
        "target": "last",
    }


def test_load_openclaw_config_round_trips_object_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    expected = {
        "agents": {
            "defaults": {
                "heartbeat": {"every": "10m", "target": "last"},
            }
        }
    }
    config_path.write_text(json.dumps(expected), encoding="utf-8")

    assert load_openclaw_config(config_path) == expected
