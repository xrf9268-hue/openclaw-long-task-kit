"""Tests for openclaw_ltk.cron.CronClient (subprocess mocked)."""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from openclaw_ltk.cron import CronClient
from openclaw_ltk.errors import CronError


def _make_completed_process(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Helper: build a CompletedProcess with the given fields."""
    result: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )
    return result


class TestIsAvailable:
    def test_is_available_true(self) -> None:
        """is_available() returns True when the binary is found on PATH."""
        client = CronClient(binary="openclaw")
        with patch("shutil.which", return_value="/usr/local/bin/openclaw"):
            assert client.is_available() is True

    def test_is_available_false(self) -> None:
        """is_available() returns False when the binary is NOT found on PATH."""
        client = CronClient(binary="openclaw")
        with patch("shutil.which", return_value=None):
            assert client.is_available() is False


class TestListJobs:
    def test_list_jobs_json_list(self) -> None:
        """list_jobs() handles a top-level JSON array response."""
        raw_jobs = [
            {"id": "1", "name": "heartbeat", "enabled": True},
            {"id": "2", "name": "deadman", "enabled": False},
        ]
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(stdout=json.dumps(raw_jobs)),
        ):
            jobs = client.list_jobs()

        assert len(jobs) == 2
        assert jobs[0].id == "1"
        assert jobs[0].name == "heartbeat"
        assert jobs[0].enabled is True
        assert jobs[1].id == "2"
        assert jobs[1].enabled is False

    def test_list_jobs_json_envelope(self) -> None:
        """list_jobs() handles a {"jobs": [...]} envelope response."""
        raw_jobs = [{"id": "42", "name": "continuation", "enabled": True}]
        payload = {"jobs": raw_jobs}
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(stdout=json.dumps(payload)),
        ):
            jobs = client.list_jobs()

        assert len(jobs) == 1
        assert jobs[0].id == "42"
        assert jobs[0].name == "continuation"

    def test_list_jobs_failure(self) -> None:
        """list_jobs() raises CronError when the subprocess exits non-zero."""
        client = CronClient()
        with (
            patch(
                "subprocess.run",
                return_value=_make_completed_process(
                    stdout="", stderr="permission denied", returncode=1
                ),
            ),
            pytest.raises(CronError),
        ):
            client.list_jobs()


class TestAddJob:
    def test_add_job(self) -> None:
        """add_job() returns the job ID parsed from the JSON response."""
        spec: dict[str, Any] = {
            "name": "heartbeat",
            "schedule": {"cron": "*/5 * * * *"},
        }
        response = {"id": "123", "status": "created"}
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(stdout=json.dumps(response)),
        ):
            job_id = client.add_job(spec)

        assert job_id == "123"


class TestRemoveJob:
    def test_remove_job(self) -> None:
        """remove_job() returns True on a successful (zero-exit) subprocess call."""
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(
                stdout=json.dumps({"status": "removed"})
            ),
        ):
            result = client.remove_job("123")

        assert result is True


class TestDisableJob:
    def test_disable_job(self) -> None:
        """disable_job() returns True on a successful (zero-exit) subprocess call."""
        client = CronClient()
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(
                stdout=json.dumps({"status": "disabled"})
            ),
        ):
            result = client.disable_job("123")

        assert result is True
