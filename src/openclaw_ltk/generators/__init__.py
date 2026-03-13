"""Generator modules for OpenClaw long-task-kit."""

from openclaw_ltk.generators.cron_matrix import (
    build_all_specs,
    build_closure_check_spec,
    build_continuation_spec,
    build_deadman_spec,
    build_watchdog_spec,
)
from openclaw_ltk.generators.heartbeat_entry import (
    generate_entry,
    inject_heartbeat_entry,
    remove_heartbeat_entry,
)

__all__ = [
    # cron_matrix
    "build_watchdog_spec",
    "build_continuation_spec",
    "build_deadman_spec",
    "build_closure_check_spec",
    "build_all_specs",
    # heartbeat_entry
    "generate_entry",
    "inject_heartbeat_entry",
    "remove_heartbeat_entry",
]
