"""State file operations — single source of truth for all state read/write access.

Guarantees:
- Atomic writes via tmp file + replace into place (no partial-write corruption).
- Sidecar lock file serialization for read-modify-write updates.
- Silent-overwrite prevention via ensure_not_exists.
- All I/O errors wrapped in StateFileError with actionable messages.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.errors import StateFileError


def atomic_write_text(path: Path, content: str) -> None:
    """Write *content* to *path* atomically and durably.

    On failure the temporary file is cleaned up and the original
    ``OSError`` is re-raised (never wrapped in ``StateFileError``).
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(tmp_path, path)

        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        import contextlib

        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


class StateFile:
    """Manages read/write access to a single JSON state file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _exclusive_lock(self) -> Generator[None, None, None]:
        lock_path = self._lock_path()
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_fd = lock_path.open("a+", encoding="utf-8")
        except OSError as exc:
            raise StateFileError(
                "Failed to open sidecar lock file.",
                detail=str(exc),
                path=lock_path,
            ) from exc

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        except OSError as exc:
            raise StateFileError(
                "Failed to acquire sidecar lock file.",
                detail=str(exc),
                path=lock_path,
            ) from exc
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def _save_unlocked(self, data: dict[str, Any]) -> None:
        try:
            atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=2))
        except OSError as exc:
            raise StateFileError(
                "Failed to write state file.",
                detail=str(exc),
                path=self.path,
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Read and parse the state file, returning its contents as a dict.

        Raises:
            StateFileError: if the file is missing, not valid JSON, or
                            any other OS-level error occurs.
        """
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise StateFileError(
                "State file not found.",
                detail="Run 'ltk init' to create it.",
                path=self.path,
            ) from None
        except OSError as exc:
            raise StateFileError(
                "Failed to read state file.",
                detail=str(exc),
                path=self.path,
            ) from exc

        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StateFileError(
                "State file contains invalid JSON.",
                detail=f"Line {exc.lineno}, col {exc.colno}: {exc.msg}",
                path=self.path,
            ) from exc

        return data

    def save(self, data: dict[str, Any]) -> None:
        """Write *data* to the state file atomically.

        Writes to a sibling `.tmp` file first, then renames it into place.
        On failure, the `.tmp` file is cleaned up.

        Raises:
            StateFileError: on any OS-level error.
        """
        with self._exclusive_lock():
            self._save_unlocked(data)

    @contextmanager
    def locked_update(self) -> Generator[dict[str, Any], None, None]:
        """Acquire the sidecar lock, yield the current state dict, then save.

        Usage::

            with state_file.locked_update() as data:
                data["status"] = "running"

        The ``updated_at`` key is automatically set to the current UTC ISO
        timestamp on every successful exit.

        Raises:
            StateFileError: if the file cannot be opened, locked, parsed,
                            or saved.
        """
        with self._exclusive_lock():
            try:
                raw = self.path.read_text(encoding="utf-8")
            except FileNotFoundError:
                raise StateFileError(
                    "State file not found; cannot lock for update.",
                    detail="Run 'ltk init' to create it.",
                    path=self.path,
                ) from None
            except OSError as exc:
                raise StateFileError(
                    "Failed to open state file for update.",
                    detail=str(exc),
                    path=self.path,
                ) from exc

            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise StateFileError(
                    "State file contains invalid JSON (read inside lock).",
                    detail=f"Line {exc.lineno}, col {exc.colno}: {exc.msg}",
                    path=self.path,
                ) from exc

            yield data

            data["updated_at"] = now_utc_iso()
            self._save_unlocked(data)

    def ensure_not_exists(self, force: bool = False) -> None:
        """Raise StateFileError if the state file already exists and *force* is False.

        Args:
            force: when True, skip the existence check (allow overwrite).

        Raises:
            StateFileError: if the file exists and *force* is False.
        """
        if not force and self.path.exists():
            raise StateFileError(
                "State file already exists.",
                detail="Pass force=True or use --force to overwrite.",
                path=self.path,
            )

    def exists(self) -> bool:
        """Return True if the state file exists on disk."""
        return self.path.exists()
