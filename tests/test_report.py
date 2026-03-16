"""Tests for ltk report issue command and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from openclaw_ltk.cli import main
from openclaw_ltk.report import render_issue_report


class TestRenderIssueReport:
    def test_contains_task_metadata(self, sample_state_data: dict[str, Any]) -> None:
        md = render_issue_report(sample_state_data)
        assert sample_state_data["task_id"] in md
        assert sample_state_data["title"] in md
        assert sample_state_data["status"] in md
        assert sample_state_data["phase"] in md
        assert sample_state_data["goal"] in md

    def test_contains_work_package(self, sample_state_data: dict[str, Any]) -> None:
        md = render_issue_report(sample_state_data)
        wp = sample_state_data["current_work_package"]
        assert wp["id"] in md
        assert wp["goal"] in md

    def test_contains_policy_diagnostics(
        self, sample_state_data: dict[str, Any]
    ) -> None:
        md = render_issue_report(sample_state_data)
        assert "Continuation" in md or "continuation" in md.lower()
        assert "Exhaustion" in md or "exhaustion" in md.lower()

    def test_sanitizes_paths_by_default(
        self, sample_state_data: dict[str, Any]
    ) -> None:
        sample_state_data["notes"] = ["/home/yvan/secret/file.py"]
        md = render_issue_report(sample_state_data)
        assert "/home/yvan" not in md

    def test_no_sanitize_preserves_paths(
        self, sample_state_data: dict[str, Any]
    ) -> None:
        sample_state_data["notes"] = ["/home/yvan/secret/file.py"]
        md = render_issue_report(sample_state_data, sanitize_output=False)
        assert "/home/yvan" in md

    def test_includes_error_count(self, sample_state_data: dict[str, Any]) -> None:
        sample_state_data["error_count"] = 3
        md = render_issue_report(sample_state_data)
        assert "3" in md

    def test_output_is_markdown(self, sample_state_data: dict[str, Any]) -> None:
        md = render_issue_report(sample_state_data)
        assert md.startswith("# ")


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    sf = state_dir / "test.json"
    sf.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return sf


class TestReportIssueCmd:
    def test_stdout_output(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        state_file = _write_state(tmp_path, sample_state_data)
        runner = CliRunner()
        result = runner.invoke(main, ["report", "issue", "--state", str(state_file)])
        assert result.exit_code == 0
        assert sample_state_data["task_id"] in result.output
        assert result.output.startswith("# ")

    def test_file_output(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        state_file = _write_state(tmp_path, sample_state_data)
        out_file = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["report", "issue", "--state", str(state_file), "--output", str(out_file)],
        )
        assert result.exit_code == 0
        content = out_file.read_text(encoding="utf-8")
        assert sample_state_data["task_id"] in content

    def test_no_sanitize_flag(
        self, tmp_path: Path, sample_state_data: dict[str, Any]
    ) -> None:
        sample_state_data["notes"] = ["/home/yvan/secret/file.py"]
        state_file = _write_state(tmp_path, sample_state_data)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["report", "issue", "--state", str(state_file), "--no-sanitize"],
        )
        assert result.exit_code == 0
        assert "/home/yvan" in result.output

    def test_missing_state_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["report", "issue", "--state", str(tmp_path / "nope.json")]
        )
        assert result.exit_code == 2
