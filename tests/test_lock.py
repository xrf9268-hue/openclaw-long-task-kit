"""Tests for the lock command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from openclaw_ltk.cli import main


class TestLockAcquire:
    def test_acquire(self, state_file_on_disk: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["lock", "acquire", "--state", str(state_file_on_disk), "--owner", "test"],
        )
        assert result.exit_code == 0
        assert "ACQUIRED" in result.output


class TestLockRelease:
    def test_release(self, state_file_on_disk: Path) -> None:
        runner = CliRunner()
        # Acquire first.
        runner.invoke(
            main,
            ["lock", "acquire", "--state", str(state_file_on_disk), "--owner", "test"],
        )
        result = runner.invoke(
            main,
            ["lock", "release", "--state", str(state_file_on_disk), "--owner", "test"],
        )
        assert result.exit_code == 0
        assert "RELEASED" in result.output


class TestLockHeldByOther:
    def test_blocked(self, state_file_on_disk: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "lock",
                "acquire",
                "--state",
                str(state_file_on_disk),
                "--owner",
                "owner1",
                "--ttl",
                "3600",
            ],
        )
        result = runner.invoke(
            main,
            [
                "lock",
                "acquire",
                "--state",
                str(state_file_on_disk),
                "--owner",
                "owner2",
            ],
        )
        assert result.exit_code == 10


class TestLockRenewal:
    def test_lock_renews_same_owner_after_ttl_expiry(
        self,
        state_file_on_disk: Path,
    ) -> None:
        state = json.loads(state_file_on_disk.read_text(encoding="utf-8"))
        state["control_plane"] = {
            "lock": {
                "owner": "test",
                "acquired_at": "2026-03-13T00:00:00+00:00",
                "expires_at": "2026-03-13T00:00:01+00:00",
            }
        }
        state_file_on_disk.write_text(json.dumps(state, indent=2), encoding="utf-8")

        now_value = datetime(2026, 3, 13, 0, 2, tzinfo=UTC)
        runner = CliRunner()
        with (
            patch("openclaw_ltk.commands.lock._utc_now", return_value=now_value),
            patch(
                "openclaw_ltk.commands.lock.now_utc_iso",
                return_value="2026-03-13T00:02:00+00:00",
            ),
        ):
            result = runner.invoke(
                main,
                [
                    "lock",
                    "acquire",
                    "--state",
                    str(state_file_on_disk),
                    "--owner",
                    "test",
                    "--ttl",
                    "30",
                ],
            )

        updated = json.loads(state_file_on_disk.read_text(encoding="utf-8"))
        lock = updated["control_plane"]["lock"]
        assert result.exit_code == 0
        assert "RENEWED" in result.output
        assert lock["acquired_at"] == "2026-03-13T00:02:00+00:00"
        assert lock["expires_at"] == "2026-03-13T00:02:30+00:00"
