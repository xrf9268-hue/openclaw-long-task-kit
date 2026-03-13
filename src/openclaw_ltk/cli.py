"""CLI entry point for openclaw-long-task-kit.

Registers all command groups under the `ltk` binary defined in pyproject.toml.
"""

from __future__ import annotations

import click


@click.group()
@click.version_option(package_name="openclaw-long-task-kit")
def main() -> None:
    """OpenClaw Long Task Kit — control-plane toolkit."""


# Import and register command groups.
from openclaw_ltk.commands.close import close_cmd  # noqa: E402
from openclaw_ltk.commands.doctor import doctor_cmd  # noqa: E402
from openclaw_ltk.commands.init import init_cmd  # noqa: E402
from openclaw_ltk.commands.lock import lock_cmd  # noqa: E402
from openclaw_ltk.commands.logs import logs_cmd  # noqa: E402
from openclaw_ltk.commands.pointer import pointer_cmd  # noqa: E402
from openclaw_ltk.commands.preflight import preflight_cmd  # noqa: E402
from openclaw_ltk.commands.resume import resume_cmd  # noqa: E402
from openclaw_ltk.commands.status import status_cmd  # noqa: E402
from openclaw_ltk.commands.watchdog import watchdog_cmd  # noqa: E402
from openclaw_ltk.commands.webhooks import webhooks_cmd  # noqa: E402

main.add_command(init_cmd, "init")
main.add_command(preflight_cmd, "preflight")
main.add_command(close_cmd, "close")
main.add_command(doctor_cmd, "doctor")
main.add_command(lock_cmd, "lock")
main.add_command(logs_cmd, "logs")
main.add_command(pointer_cmd, "pointer")
main.add_command(resume_cmd, "resume")
main.add_command(status_cmd, "status")
main.add_command(watchdog_cmd, "watchdog")
main.add_command(webhooks_cmd, "webhooks")
