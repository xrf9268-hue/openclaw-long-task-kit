"""Tests for the lock command."""

from __future__ import annotations

from pathlib import Path

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
