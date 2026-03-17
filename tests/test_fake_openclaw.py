"""Tests for the fake openclaw binary test helper."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.fake_openclaw import FakeOpenClaw


class TestFakeOpenClawBuild:
    """The helper should produce a runnable script."""

    def test_creates_executable(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.build()
        assert fake.path.exists()
        assert os.access(fake.path, os.X_OK)

    def test_default_health_response(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.build()
        result = subprocess.run(
            [str(fake.path), "health", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

    def test_custom_response(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.register("health --json", {"ok": False, "error": "db down"})
        fake.build()
        result = subprocess.run(
            [str(fake.path), "health", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert data["error"] == "db down"

    def test_custom_exit_code(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.register("doctor --json", "error output", exit_code=1)
        fake.build()
        result = subprocess.run(
            [str(fake.path), "doctor", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "error output" in result.stdout

    def test_cron_list_response(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        jobs = [{"id": "j1", "name": "watchdog", "enabled": True}]
        fake.register("cron list --json", jobs)
        fake.build()
        result = subprocess.run(
            [str(fake.path), "cron", "list", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["id"] == "j1"

    def test_unknown_command_returns_error(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.build()
        result = subprocess.run(
            [str(fake.path), "unknown", "subcommand"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "unknown" in result.stderr.lower() or "unknown" in result.stdout.lower()

    def test_gateway_status_default(self, tmp_path: Path) -> None:
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.build()
        result = subprocess.run(
            [str(fake.path), "gateway", "status", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "service" in data

    def test_json_with_apostrophe(self, tmp_path: Path) -> None:
        """P1: JSON containing apostrophes must not break bash quoting."""
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.register("health --json", {"msg": "it's down", "ok": False})
        fake.build()
        result = subprocess.run(
            [str(fake.path), "health", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["msg"] == "it's down"

    def test_custom_route_overrides_wildcard_default(self, tmp_path: Path) -> None:
        """P2: Specific custom route must take priority over default wildcard."""
        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.register(
            "cron remove job-1 --json",
            {"error": "not found"},
            exit_code=1,
        )
        fake.build()
        result = subprocess.run(
            [str(fake.path), "cron", "remove", "job-1", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["error"] == "not found"


class TestFakeOpenClawIntegration:
    """Use the fake binary with real CronClient/OpenClawClient."""

    def test_with_openclaw_client(self, tmp_path: Path) -> None:
        from openclaw_ltk.openclaw_cli import OpenClawClient

        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.build()
        client = OpenClawClient(binary=str(fake.path))
        result = client.health()
        assert result["ok"] is True

    def test_with_cron_client(self, tmp_path: Path) -> None:
        from openclaw_ltk.cron import CronClient

        fake = FakeOpenClaw(tmp_path / "openclaw")
        jobs = [{"id": "j1", "name": "test", "enabled": True}]
        fake.register("cron list --json", jobs)
        fake.build()
        client = CronClient(binary=str(fake.path))
        result = client.list_jobs()
        assert len(result) == 1
        assert result[0].id == "j1"

    def test_error_scenario_with_client(self, tmp_path: Path) -> None:
        from openclaw_ltk.errors import OpenClawError
        from openclaw_ltk.openclaw_cli import OpenClawClient

        fake = FakeOpenClaw(tmp_path / "openclaw")
        fake.register("doctor --json", "internal error", exit_code=1)
        fake.build()
        client = OpenClawClient(binary=str(fake.path))
        with pytest.raises(OpenClawError, match="Command failed"):
            client.doctor()
