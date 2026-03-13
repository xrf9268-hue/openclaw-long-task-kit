"""Tests for openclaw_ltk.config.LtkConfig."""

from __future__ import annotations

import dataclasses
import warnings
from pathlib import Path

import pytest

from openclaw_ltk.config import LtkConfig


class TestDefaultValues:
    def test_default_values(self) -> None:
        """Default config constructed with a workspace should have correct defaults."""
        cfg = LtkConfig(workspace=Path("/tmp/ws"))
        assert cfg.workspace == Path("/tmp/ws")
        assert cfg.timezone == "Asia/Shanghai"
        assert cfg.telegram_chat_id == ""
        assert cfg.timeout_seconds == 1800
        assert cfg.silence_budget_minutes == 10
        assert cfg.continuation_interval_minutes == 5
        assert cfg.deadman_interval_minutes == 20


class TestFromEnv:
    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LTK_WORKSPACE env var is picked up by from_env()."""
        monkeypatch.setenv("LTK_WORKSPACE", "/custom/workspace")
        # Clear any fallback that might interfere
        monkeypatch.delenv("OPENCLAW_WORKSPACE", raising=False)
        cfg = LtkConfig.from_env()
        assert cfg.workspace == Path("/custom/workspace")

    def test_from_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENCLAW_WORKSPACE is used as fallback when LTK_WORKSPACE is absent."""
        monkeypatch.delenv("LTK_WORKSPACE", raising=False)
        monkeypatch.setenv("OPENCLAW_WORKSPACE", "/fallback/workspace")
        cfg = LtkConfig.from_env()
        assert cfg.workspace == Path("/fallback/workspace")


class TestDerivedPaths:
    def test_derived_paths(self) -> None:
        """state_dir, heartbeat_path, etc. are derived correctly from workspace."""
        ws = Path("/my/workspace")
        cfg = LtkConfig(workspace=ws)
        assert cfg.state_dir == ws / "tasks" / "state"
        assert cfg.heartbeat_path == ws / "HEARTBEAT.md"
        assert cfg.boot_path == ws / "BOOT.md"
        assert cfg.agents_path == ws / "AGENTS.md"
        assert cfg.pointer_path == ws / "tasks" / ".active-task-pointer.json"
        assert cfg.openclaw_state_dir == Path.home() / ".openclaw"
        assert cfg.exec_approvals_path == (
            Path.home() / ".openclaw" / "exec-approvals.json"
        )


class TestPathOverride:
    def test_path_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LTK_STATE_DIR env var overrides the derived state_dir default."""
        monkeypatch.setenv("LTK_WORKSPACE", "/base/ws")
        monkeypatch.setenv("LTK_STATE_DIR", "/override/state")
        monkeypatch.delenv("OPENCLAW_WORKSPACE", raising=False)
        cfg = LtkConfig.from_env()
        assert cfg.state_dir == Path("/override/state")
        # Other derived paths still use the workspace
        assert cfg.heartbeat_path == Path("/base/ws") / "HEARTBEAT.md"

    def test_openclaw_state_dir_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENCLAW_STATE_DIR should drive host-level OpenClaw paths."""
        monkeypatch.setenv("LTK_WORKSPACE", "/base/ws")
        monkeypatch.setenv("OPENCLAW_STATE_DIR", "/srv/openclaw-state")
        cfg = LtkConfig.from_env()
        assert cfg.openclaw_state_dir == Path("/srv/openclaw-state")
        assert cfg.exec_approvals_path == (
            Path("/srv/openclaw-state") / "exec-approvals.json"
        )


class TestInvalidIntWarns:
    def test_invalid_int_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An invalid integer env var emits a warning and uses the default."""
        monkeypatch.setenv("LTK_WORKSPACE", "/tmp/ws")
        monkeypatch.setenv("LTK_TIMEOUT_SECONDS", "not-a-number")
        monkeypatch.delenv("OPENCLAW_WORKSPACE", raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg = LtkConfig.from_env()
        assert cfg.timeout_seconds == 1800  # default
        assert len(caught) == 1
        assert "Invalid integer" in str(caught[0].message)
        assert "LTK_TIMEOUT_SECONDS" in str(caught[0].message)


class TestDeadThreshold:
    def test_default(self) -> None:
        """dead_threshold_minutes defaults to 30."""
        cfg = LtkConfig(workspace=Path("/tmp/ws"))
        assert cfg.dead_threshold_minutes == 30

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LTK_DEAD_THRESHOLD_MINUTES env var overrides the default."""
        monkeypatch.setenv("LTK_WORKSPACE", "/tmp/ws")
        monkeypatch.setenv("LTK_DEAD_THRESHOLD_MINUTES", "45")
        monkeypatch.delenv("OPENCLAW_WORKSPACE", raising=False)
        cfg = LtkConfig.from_env()
        assert cfg.dead_threshold_minutes == 45


class TestFrozen:
    def test_frozen(self) -> None:
        """LtkConfig is immutable; attempting mutation raises FrozenInstanceError."""
        cfg = LtkConfig(workspace=Path("/tmp/ws"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.timezone = "UTC"  # type: ignore[misc]
