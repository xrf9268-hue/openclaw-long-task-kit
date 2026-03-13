"""Tests for the pointer command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from openclaw_ltk.cli import main


class TestPointerSetAndGet:
    def test_set_then_get(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["pointer", "set", "--task-id", "t1", "--state-path", "/tmp/t1.json"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0

        result = runner.invoke(
            main,
            ["pointer", "get"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0
        assert "t1" in result.output


class TestPointerClear:
    def test_clear(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            main,
            ["pointer", "set", "--task-id", "t1", "--state-path", "/tmp/t1.json"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        result = runner.invoke(
            main,
            ["pointer", "clear"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        assert result.exit_code == 0


class TestPointerGetMissing:
    def test_get_missing(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["pointer", "get"],
            env={"LTK_WORKSPACE": str(tmp_path)},
        )
        # Should indicate no pointer is set — non-zero or message.
        out = result.output.lower()
        assert result.exit_code != 0 or "no" in out or "not" in out


class TestPointerErrors:
    def test_pointer_get_handles_permission_error(self, tmp_path: Path) -> None:
        pointer_path = tmp_path / "tasks" / ".active-task-pointer.json"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_path.write_text(json.dumps({"task_id": "t1"}), encoding="utf-8")

        original_exists = Path.exists

        def fake_exists(path_self: Path) -> bool:
            if path_self == pointer_path:
                raise PermissionError("permission denied")
            return original_exists(path_self)

        runner = CliRunner()
        with patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists):
            result = runner.invoke(
                main,
                ["pointer", "get"],
                env={"LTK_WORKSPACE": str(tmp_path)},
            )

        assert result.exit_code == 1
        assert "could not inspect pointer file" in result.output
