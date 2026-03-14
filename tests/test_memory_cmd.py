"""Tests for the ltk memory helper command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from openclaw_ltk.cli import main


def test_memory_note_appends_custom_entry(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["memory", "note", "--message", "Captured a follow-up action"],
        env={"LTK_WORKSPACE": str(tmp_path)},
    )

    assert result.exit_code == 0
    daily_files = list((tmp_path / "memory").glob("*.md"))
    assert len(daily_files) == 1
    assert "Captured a follow-up action" in daily_files[0].read_text(encoding="utf-8")


def test_memory_list_shows_daily_files_in_descending_order(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "2026-03-12.md").write_text("# a\n", encoding="utf-8")
    (memory_dir / "2026-03-14.md").write_text("# b\n", encoding="utf-8")
    (memory_dir / "2026-03-13.md").write_text("# c\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["memory", "list"],
        env={"LTK_WORKSPACE": str(tmp_path)},
    )

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        str(memory_dir / "2026-03-14.md"),
        str(memory_dir / "2026-03-13.md"),
        str(memory_dir / "2026-03-12.md"),
    ]
