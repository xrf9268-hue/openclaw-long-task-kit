"""JSON shape contract tests for CronClient and OpenClawClient.

These tests define the expected response shapes from the upstream
``openclaw`` CLI and verify that our clients handle conforming
and non-conforming payloads correctly.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from openclaw_ltk.cron import CronClient, CronJob
from openclaw_ltk.errors import CronError, OpenClawError
from openclaw_ltk.openclaw_cli import OpenClawClient


def _completed(stdout: str, rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr="")


# ---------------------------------------------------------------------------
# CronClient contracts
# ---------------------------------------------------------------------------

# Canonical response shapes the upstream binary may return.
CRON_LIST_FLAT: list[dict[str, Any]] = [
    {
        "id": "j1",
        "name": "watchdog",
        "enabled": True,
        "schedule": {"cron": "*/5 * * * *"},
    },
    {"id": "j2", "name": "deadman", "enabled": False},
]

CRON_LIST_ENVELOPE: dict[str, Any] = {"jobs": CRON_LIST_FLAT}

CRON_ADD_RESPONSE_ID: dict[str, Any] = {"id": "new-123", "status": "created"}
CRON_ADD_RESPONSE_JOB_ID: dict[str, Any] = {"job_id": "new-456", "status": "created"}


class TestCronListContract:
    """list_jobs() must accept both flat-list and envelope shapes."""

    def test_flat_list_shape(self) -> None:
        client = CronClient()
        with patch(
            "subprocess.run", return_value=_completed(json.dumps(CRON_LIST_FLAT))
        ):
            jobs = client.list_jobs()
        assert len(jobs) == 2
        assert all(isinstance(j, CronJob) for j in jobs)
        assert jobs[0].id == "j1"
        assert jobs[0].schedule == {"cron": "*/5 * * * *"}

    def test_envelope_shape(self) -> None:
        client = CronClient()
        with patch(
            "subprocess.run", return_value=_completed(json.dumps(CRON_LIST_ENVELOPE))
        ):
            jobs = client.list_jobs()
        assert len(jobs) == 2

    def test_empty_list(self) -> None:
        client = CronClient()
        with patch("subprocess.run", return_value=_completed("[]")):
            jobs = client.list_jobs()
        assert jobs == []

    def test_empty_envelope(self) -> None:
        client = CronClient()
        with patch("subprocess.run", return_value=_completed('{"jobs": []}')):
            jobs = client.list_jobs()
        assert jobs == []

    def test_missing_fields_uses_defaults(self) -> None:
        """Jobs with missing optional fields should still parse."""
        client = CronClient()
        minimal = [{"id": "x"}]
        with patch("subprocess.run", return_value=_completed(json.dumps(minimal))):
            jobs = client.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "x"
        assert jobs[0].name == ""
        assert jobs[0].enabled is True
        assert jobs[0].schedule is None

    def test_unexpected_scalar_raises(self) -> None:
        """A non-list, non-dict top-level value must raise CronError."""
        client = CronClient()
        with (
            patch("subprocess.run", return_value=_completed('"just-a-string"')),
            pytest.raises(CronError, match="Unexpected JSON shape"),
        ):
            client.list_jobs()

    def test_invalid_json_raises(self) -> None:
        client = CronClient()
        with (
            patch("subprocess.run", return_value=_completed("not json")),
            pytest.raises(CronError, match="Failed to parse JSON"),
        ):
            client.list_jobs()


class TestCronAddContract:
    """add_job() must extract job ID from either ``id`` or ``job_id``."""

    def test_id_field(self) -> None:
        client = CronClient()
        with patch(
            "subprocess.run", return_value=_completed(json.dumps(CRON_ADD_RESPONSE_ID))
        ):
            job_id = client.add_job({"name": "test"})
        assert job_id == "new-123"

    def test_job_id_field(self) -> None:
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_completed(json.dumps(CRON_ADD_RESPONSE_JOB_ID)),
        ):
            job_id = client.add_job({"name": "test"})
        assert job_id == "new-456"

    def test_missing_id_raises(self) -> None:
        """Response without id or job_id must raise CronError."""
        client = CronClient()
        with (
            patch("subprocess.run", return_value=_completed('{"status": "created"}')),
            pytest.raises(CronError, match="Could not extract job ID"),
        ):
            client.add_job({"name": "test"})


# ---------------------------------------------------------------------------
# OpenClawClient contracts
# ---------------------------------------------------------------------------

HEALTH_OK: dict[str, Any] = {"ok": True, "version": "1.2.3"}
HEALTH_UNHEALTHY: dict[str, Any] = {"ok": False, "error": "db down"}

GATEWAY_STATUS: dict[str, Any] = {
    "service": {"scope": "system", "linger_enabled": True, "installed": True},
}

DOCTOR_OK: dict[str, Any] = {
    "ok": True,
    "checks": ["gateway", "runtime"],
}


class TestOpenClawHealthContract:
    """health() must return parsed JSON from ``openclaw health --json``."""

    def test_healthy_response(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch("subprocess.run", return_value=_completed(json.dumps(HEALTH_OK))),
        ):
            result = client.health()
        assert result["ok"] is True
        assert "version" in result

    def test_unhealthy_response_still_parses(self) -> None:
        """Even unhealthy payloads must be returned as dicts (not raise)."""
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch(
                "subprocess.run", return_value=_completed(json.dumps(HEALTH_UNHEALTHY))
            ),
        ):
            result = client.health()
        assert result["ok"] is False

    def test_invalid_json_raises(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch("subprocess.run", return_value=_completed("not json")),
            pytest.raises(OpenClawError, match="Failed to parse JSON"),
        ):
            client.health()

    def test_binary_not_found_raises(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(OpenClawError, match="not available"),
        ):
            client.health()


class TestOpenClawGatewayStatusContract:
    """gateway_status() must return service info dict."""

    def test_service_shape(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch(
                "subprocess.run", return_value=_completed(json.dumps(GATEWAY_STATUS))
            ),
        ):
            result = client.gateway_status()
        assert isinstance(result["service"], dict)
        assert result["service"]["scope"] == "system"


class TestOpenClawDoctorContract:
    """doctor() must return ok/checks structure."""

    def test_ok_shape(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch("subprocess.run", return_value=_completed(json.dumps(DOCTOR_OK))),
        ):
            result = client.doctor()
        assert result["ok"] is True
        assert isinstance(result["checks"], list)

    def test_with_repair_and_deep_flags(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch(
                "subprocess.run", return_value=_completed(json.dumps(DOCTOR_OK))
            ) as mock_run,
        ):
            client.doctor(repair=True, deep=True)
        call_args = mock_run.call_args[0][0]
        assert "--repair" in call_args
        assert "--deep" in call_args

    def test_non_zero_exit_raises(self) -> None:
        client = OpenClawClient()
        with (
            patch("shutil.which", return_value="/usr/bin/openclaw"),
            patch("subprocess.run", return_value=_completed("error", rc=1)),
            pytest.raises(OpenClawError, match="Command failed"),
        ):
            client.doctor()
