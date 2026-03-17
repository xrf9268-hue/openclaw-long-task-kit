"""State file schema migration — upgrades old state files to the current schema.

Each migration step is a function that transforms state from version N to N+1.
Migrations are applied sequentially until the state reaches CURRENT_SCHEMA_VERSION.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# The current schema version. Bump this when the state format changes.
CURRENT_SCHEMA_VERSION: int = 1

# Type alias for a single migration step: takes state dict, returns state dict.
MigrationStep = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class MigrationResult:
    """Result of running migrate_state()."""

    state: dict[str, Any]
    migrated: bool
    from_version: int
    to_version: int
    messages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Migration steps: v0 → v1, v1 → v2, etc.
# ---------------------------------------------------------------------------


def _migrate_v0_to_v1(state: dict[str, Any]) -> dict[str, Any]:
    """Add schema_version field to a legacy (v0) state file."""
    state["schema_version"] = 1
    return state


# Registry: maps source version to the migration step.
_MIGRATIONS: dict[int, MigrationStep] = {
    0: _migrate_v0_to_v1,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def needs_migration(state: dict[str, Any]) -> bool:
    """Return True if *state* needs to be migrated to the current schema."""
    version = state.get("schema_version", 0)
    return isinstance(version, int) and version < CURRENT_SCHEMA_VERSION


def migrate_state(state: dict[str, Any]) -> MigrationResult:
    """Migrate *state* to the current schema version.

    Returns a MigrationResult. If no migration is needed, returns the
    original state dict unchanged (not copied).
    """
    from_version: int = state.get("schema_version", 0)
    if not isinstance(from_version, int):
        from_version = 0

    if from_version >= CURRENT_SCHEMA_VERSION:
        return MigrationResult(
            state=state,
            migrated=False,
            from_version=from_version,
            to_version=from_version,
        )

    # Copy before mutating.
    migrated = copy.deepcopy(state)
    messages: list[str] = []
    current_version = from_version

    while current_version < CURRENT_SCHEMA_VERSION:
        step = _MIGRATIONS.get(current_version)
        if step is None:
            messages.append(
                f"No migration defined for v{current_version} "
                f"→ v{current_version + 1}; "
                f"stopping at v{current_version}."
            )
            break
        migrated = step(migrated)
        target = current_version + 1
        messages.append(f"Migrated v{current_version} → v{target}.")
        current_version = target

    return MigrationResult(
        state=migrated,
        migrated=True,
        from_version=from_version,
        to_version=current_version,
        messages=messages,
    )
