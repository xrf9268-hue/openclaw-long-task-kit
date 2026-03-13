"""Thin wrapper around upstream `openclaw` CLI commands used by ltk."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from openclaw_ltk.errors import OpenClawError


class OpenClawClient:
    """Run OpenClaw CLI commands and normalize JSON responses."""

    def __init__(self, binary: str = "openclaw") -> None:
        self.binary = binary

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def _run(
        self,
        args: list[str],
        *,
        capture_output: bool = True,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if not self.is_available():
            raise OpenClawError(
                "openclaw binary not available on PATH.",
                detail=f"Missing executable: {self.binary}",
            )

        result = subprocess.run(
            [self.binary, *args],
            capture_output=capture_output,
            text=True,
            input=input_text,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise OpenClawError(
                f"Command failed: {self.binary} {' '.join(args)}",
                detail=detail,
            )
        return result

    def _run_json(self, args: list[str]) -> Any:
        result = self._run(args)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OpenClawError(
                f"Failed to parse JSON from: {self.binary} {' '.join(args)}",
                detail=result.stdout[:200],
            ) from exc

    def health(self) -> Any:
        return self._run_json(["health", "--json"])

    def gateway_status(self) -> Any:
        return self._run_json(["gateway", "status", "--json"])

    def doctor(self, *, repair: bool = False, deep: bool = False) -> Any:
        args = ["doctor", "--json"]
        if repair:
            args.append("--repair")
        if deep:
            args.append("--deep")
        return self._run_json(args)

    def logs(
        self,
        *,
        follow: bool = False,
        json_output: bool = False,
        limit: int | None = None,
        local_time: bool = False,
    ) -> int:
        if not self.is_available():
            raise OpenClawError(
                "openclaw binary not available on PATH.",
                detail=f"Missing executable: {self.binary}",
            )

        args = ["logs"]
        if follow:
            args.append("--follow")
        if json_output:
            args.append("--json")
        if local_time:
            args.append("--local-time")
        if limit is not None:
            args.extend(["--limit", str(limit)])

        completed = subprocess.run([self.binary, *args], check=False)
        if completed.returncode != 0:
            raise OpenClawError(
                f"Command failed: {self.binary} {' '.join(args)}",
                detail=f"rc={completed.returncode}",
            )
        return completed.returncode
