"""Subprocess wrapper for `openclaw cron` commands.

Always uses the ``--json`` flag for structured output (fixes P1-8).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from openclaw_ltk.errors import CronError


@dataclass
class CronJob:
    """Represents a single openclaw cron job."""

    id: str
    name: str
    enabled: bool
    schedule: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class CronClient:
    """Client for interacting with the ``openclaw cron`` subsystem."""

    def __init__(self, binary: str = "openclaw") -> None:
        self.binary = binary

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the openclaw binary exists on PATH."""
        return shutil.which(self.binary) is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        args: list[str],
        *,
        input: str | None = None,  # noqa: A002
    ) -> subprocess.CompletedProcess[str]:
        """Run *self.binary* with *args*, capturing output.

        Raises :class:`~openclaw_ltk.errors.CronError` on non-zero exit.
        """
        cmd = [self.binary, *args]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            input=input,
        )
        if result.returncode != 0:
            raise CronError(
                f"Command failed: {' '.join(cmd)}",
                detail=(f"rc={result.returncode} | stderr={result.stderr.strip()!r}"),
            )
        return result

    def _parse_json(self, text: str, context: str) -> Any:
        """Parse JSON output, raising :class:`CronError` on failure."""
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise CronError(
                f"Failed to parse JSON output from {context}: {exc}",
                detail=text[:200],
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_jobs(self) -> list[CronJob]:
        """List all cron jobs.

        Runs ``openclaw cron list --json`` and returns a list of
        :class:`CronJob` objects.  Raises :class:`CronError` on failure.
        """
        result = self._run(["cron", "list", "--json"])
        payload = self._parse_json(result.stdout, "cron list")

        # Accept either a top-level list or {"jobs": [...]} envelope.
        if isinstance(payload, list):
            raw_jobs: list[dict[str, Any]] = payload
        elif isinstance(payload, dict):
            raw_jobs = payload.get("jobs", [])
        else:
            raise CronError(
                "Unexpected JSON shape from 'cron list --json'",
                detail=result.stdout[:200],
            )

        jobs: list[CronJob] = []
        for item in raw_jobs:
            jobs.append(
                CronJob(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    enabled=bool(item.get("enabled", True)),
                    schedule=(
                        item.get("schedule")
                        if isinstance(item.get("schedule"), dict)
                        else None
                    ),
                    raw=item,
                )
            )
        return jobs

    def add_job(self, spec: dict[str, Any]) -> str:
        """Add a cron job from *spec* and return the new job ID.

        Runs ``openclaw cron add --json`` with the spec JSON piped to stdin.
        Raises :class:`CronError` on failure.
        """
        spec_json = json.dumps(spec)
        result = self._run(["cron", "add", "--json"], input=spec_json)
        payload = self._parse_json(result.stdout, "cron add")

        if isinstance(payload, dict):
            job_id = payload.get("id") or payload.get("job_id")
            if job_id is not None:
                return str(job_id)

        raise CronError(
            "Could not extract job ID from 'cron add --json' response",
            detail=result.stdout[:200],
        )

    def remove_job(self, job_id: str) -> bool:
        """Remove cron job *job_id*.

        Returns ``True`` on success.  Raises :class:`CronError` on failure.
        """
        self._run(["cron", "remove", job_id, "--json"])
        return True

    def disable_job(self, job_id: str) -> bool:
        """Disable cron job *job_id*.

        Returns ``True`` on success.  Raises :class:`CronError` on failure.
        """
        self._run(["cron", "disable", job_id, "--json"])
        return True
