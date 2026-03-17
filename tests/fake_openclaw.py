"""Fake openclaw binary builder for contract and E2E testing.

Usage::

    fake = FakeOpenClaw(tmp_path / "openclaw")
    fake.register("health --json", {"ok": True, "version": "1.0.0"})
    fake.register("doctor --json", "error", exit_code=1)
    fake.build()

    # Now use str(fake.path) as the binary path for CronClient/OpenClawClient.

Extending for new commands
--------------------------

Call ``fake.register(command_key, response, exit_code=0)`` before ``build()``.

- *command_key*: space-joined args **without** the binary name, e.g.
  ``"cron list --json"`` or ``"gateway status --json"``.
- *response*: a ``dict``/``list`` (serialised as JSON) or a ``str``
  (written as-is to stdout).
- *exit_code*: process exit code (default 0).
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

# Default responses for common commands.
_DEFAULTS: dict[str, tuple[Any, int]] = {
    "health --json": ({"ok": True, "version": "0.0.0-fake"}, 0),
    "gateway status --json": (
        {"service": {"scope": "system", "linger_enabled": True, "installed": True}},
        0,
    ),
    "doctor --json": ({"ok": True, "checks": ["gateway", "runtime"]}, 0),
    "cron list --json": ([], 0),
    "cron add --json": ({"id": "fake-job-1", "status": "created"}, 0),
    "cron remove": (None, 0),
    "cron disable": (None, 0),
}


class FakeOpenClaw:
    """Builder for a fake ``openclaw`` shell script."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._routes: dict[str, tuple[Any, int]] = dict(_DEFAULTS)

    def register(
        self,
        command_key: str,
        response: Any,
        *,
        exit_code: int = 0,
    ) -> None:
        """Register a custom response for *command_key*.

        Parameters
        ----------
        command_key:
            Space-joined args without binary, e.g. ``"health --json"``.
        response:
            ``dict``/``list`` → JSON, ``str`` → raw stdout, ``None`` → empty.
        exit_code:
            Exit code for the process.
        """
        self._routes[command_key] = (response, exit_code)

    def build(self) -> Path:
        """Write the fake binary script and make it executable.

        Returns the path to the script.
        """
        cases: list[str] = []
        # Sort routes: longer (more specific) keys first so they match
        # before shorter wildcard patterns in the bash case statement.
        sorted_routes = sorted(
            self._routes.items(), key=lambda kv: len(kv[0]), reverse=True
        )
        for key, (response, rc) in sorted_routes:
            if response is None:
                stdout_line = ""
            elif isinstance(response, str):
                stdout_line = f"echo {json.dumps(response)}"
            else:
                # Use heredoc to avoid single-quote escaping issues
                # (e.g. JSON containing apostrophes).
                encoded = json.dumps(response)
                stdout_line = f"cat <<'FAKEJSON'\n{encoded}\nFAKEJSON"
            pattern = self._key_to_pattern(key)
            cases.append(f"  {pattern})\n    {stdout_line}\n    exit {rc}\n    ;;")

        cases_block = "\n".join(cases)
        script = (
            "#!/usr/bin/env bash\n"
            "# Auto-generated fake openclaw binary for testing.\n"
            'ARGS="$*"\n'
            'case "$ARGS" in\n'
            f"{cases_block}\n"
            "  *)\n"
            '    echo "fake-openclaw: unknown command: $ARGS" >&2\n'
            "    exit 1\n"
            "    ;;\n"
            "esac\n"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(script, encoding="utf-8")
        mode = self.path.stat().st_mode
        self.path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return self.path

    @staticmethod
    def _key_to_pattern(key: str) -> str:
        """Convert a command key to a bash case pattern.

        Keys like ``"cron remove"`` match any args starting with that prefix
        (e.g. ``"cron remove job-id --json"``).
        """
        # For keys that end with known flags, match exactly.
        # For others, use a glob pattern to match additional trailing args.
        return json.dumps(key) if key.endswith("--json") else f'"{key}"*'
