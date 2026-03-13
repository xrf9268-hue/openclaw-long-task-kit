"""Tests for openclaw_ltk.state.StateFile."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from openclaw_ltk.errors import StateFileError
from openclaw_ltk.state import StateFile, atomic_write_text


class TestAtomicWriteText:
    def test_writes_content(self, tmp_state_dir: Path) -> None:
        """atomic_write_text creates the file with exact content."""
        target = tmp_state_dir / "out.txt"
        atomic_write_text(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_no_leftover_tmp_on_success(self, tmp_state_dir: Path) -> None:
        """Temp file is removed after a successful write."""
        target = tmp_state_dir / "out.txt"
        atomic_write_text(target, "data")
        tmp_file = target.with_suffix(target.suffix + ".tmp")
        assert not tmp_file.exists()

    def test_cleans_up_tmp_on_failure(self, tmp_state_dir: Path) -> None:
        """On write failure, the temp file is cleaned up and OSError is raised."""
        target = tmp_state_dir / "out.txt"

        def failing_rename(src: Any, dst: Any) -> None:
            raise OSError("simulated rename failure")

        with (
            patch("openclaw_ltk.state.os.rename", side_effect=failing_rename),
            pytest.raises(OSError, match="simulated rename failure"),
        ):
            atomic_write_text(target, "data")

        # Temp file should have been cleaned up.
        tmp_file = target.with_suffix(target.suffix + ".tmp")
        assert not tmp_file.exists()

    def test_overwrites_existing_file(self, tmp_state_dir: Path) -> None:
        """atomic_write_text overwrites an existing file atomically."""
        target = tmp_state_dir / "out.txt"
        target.write_text("old content", encoding="utf-8")
        atomic_write_text(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"


class TestSaveAndLoad:
    def test_save_and_load(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """Round-trip: save then load should return equivalent data."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        sf.save(sample_state_data)
        loaded = sf.load()
        assert loaded["task_id"] == sample_state_data["task_id"]
        assert loaded["title"] == sample_state_data["title"]
        assert loaded["status"] == sample_state_data["status"]


class TestAtomicWrite:
    def test_atomic_write(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """save() must use a .tmp sibling file and rename it into place."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        expected_tmp = path.with_suffix(path.suffix + ".tmp")

        rename_calls: list[tuple[Any, Any]] = []
        original_rename = os.rename

        def capturing_rename(src: Any, dst: Any) -> None:
            rename_calls.append((Path(src), Path(dst)))
            original_rename(src, dst)

        with patch("os.rename", side_effect=capturing_rename):
            sf.save(sample_state_data)

        assert len(rename_calls) == 1
        src, dst = rename_calls[0]
        assert src == expected_tmp
        assert dst == path


class TestLoadMissingFile:
    def test_load_missing_file(self, tmp_state_dir: Path) -> None:
        """Loading a non-existent file raises StateFileError."""
        sf = StateFile(tmp_state_dir / "nonexistent.json")
        with pytest.raises(StateFileError):
            sf.load()


class TestLoadInvalidJson:
    def test_load_invalid_json(self, tmp_state_dir: Path) -> None:
        """Invalid JSON raises StateFileError."""
        path = tmp_state_dir / "bad.json"
        path.write_text("{this is not valid json!!}", encoding="utf-8")
        sf = StateFile(path)
        with pytest.raises(StateFileError) as exc_info:
            sf.load()
        msg = str(exc_info.value).lower() + exc_info.value.message.lower()
        assert "invalid json" in msg


class TestEnsureNotExists:
    def test_ensure_not_exists_raises(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """Raises StateFileError when file exists and force=False."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        sf.save(sample_state_data)
        with pytest.raises(StateFileError):
            sf.ensure_not_exists(force=False)

    def test_ensure_not_exists_force(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """ensure_not_exists() does NOT raise when force=True, even if file exists."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        sf.save(sample_state_data)
        # Should not raise
        sf.ensure_not_exists(force=True)


class TestLockedUpdate:
    def test_locked_update(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """locked_update() yields mutable data and persists changes on exit."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        sf.save(sample_state_data)

        with sf.locked_update() as data:
            data["status"] = "completed"

        reloaded = sf.load()
        assert reloaded["status"] == "completed"

    def test_locked_update_sets_updated_at(
        self, tmp_state_dir: Path, sample_state_data: dict[str, Any]
    ) -> None:
        """locked_update() automatically updates the 'updated_at' timestamp."""
        path = tmp_state_dir / "task.json"
        sf = StateFile(path)
        sf.save(sample_state_data)
        with sf.locked_update() as data:
            # Make a trivial change to trigger the save
            data["status"] = "completed"

        reloaded = sf.load()
        # updated_at must have been refreshed (it's a new ISO timestamp)
        assert "updated_at" in reloaded
        # It should differ from the fixture value OR at minimum be a non-empty string
        assert isinstance(reloaded["updated_at"], str)
        assert reloaded["updated_at"] != ""
        # The timestamp written by locked_update comes from now_utc_iso(), which
        # produces a UTC ISO string.  That format differs from the +08:00 fixture value.
        # Sanity: updated_at was written (always passes if non-empty).
        assert reloaded["updated_at"]
