"""State file operations — single source of truth for all state read/write access.

Guarantees:
- Atomic writes via tmp file + os.rename (no partial-write corruption).
- Kernel-level exclusive locking via fcntl.flock (no TOCTOU races).
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


class StateFile:
    """Manages read/write access to a single JSON state file."""

    def __init__(self, path: Path) -> None:
        self.path = path

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
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.rename(tmp_path, self.path)
        except OSError as exc:
            # Best-effort cleanup of the temp file.
            import contextlib

            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
            raise StateFileError(
                "Failed to write state file.",
                detail=str(exc),
                path=self.path,
            ) from exc

    @contextmanager
    def locked_update(self) -> Generator[dict[str, Any], None, None]:
        """Acquire an exclusive lock, yield the current state dict, then save.

        Usage::

            with state_file.locked_update() as data:
                data["status"] = "running"

        The ``updated_at`` key is automatically set to the current UTC ISO
        timestamp on every successful exit.

        Raises:
            StateFileError: if the file cannot be opened, locked, parsed,
                            or saved.
        """
        try:
            fd = self.path.open("r+", encoding="utf-8")
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
            # Blocking exclusive lock — waits until no other process holds it.
            fcntl.flock(fd, fcntl.LOCK_EX)

            raw = fd.read()
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise StateFileError(
                    "State file contains invalid JSON (read inside lock).",
                    detail=f"Line {exc.lineno}, col {exc.colno}: {exc.msg}",
                    path=self.path,
                ) from exc

            yield data

            # Stamp the update time and persist atomically.
            data["updated_at"] = now_utc_iso()
            self.save(data)

        finally:
            # Always release the lock and close the file descriptor.
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

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
