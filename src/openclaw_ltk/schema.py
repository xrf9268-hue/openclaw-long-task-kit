"""Hand-written validation for task state files.

No external dependencies — intentionally YAGNI. The formal JSON Schema in
schemas/task-state-v2.schema.json exists for documentation and external tooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of validating a task state dict."""

    valid: bool
    errors: list[str] = field(default_factory=list)  # hard errors (required missing)
    warnings: list[str] = field(default_factory=list)  # soft warnings (optional absent)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def nested_get(data: dict[str, Any], path: str) -> Any:
    """Traverse a dot-separated *path*, return value or None."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _is_nonempty(value: Any) -> bool:
    """True when *value* is present and non-empty."""
    if value is None:
        return False
    if isinstance(value, (str, dict, list)):
        return len(value) > 0  # type: ignore[arg-type]
    return True


# ---------------------------------------------------------------------------
# Public validation functions
# ---------------------------------------------------------------------------

# Top-level scalar fields that must be present and non-empty strings.
_REQUIRED_SCALAR_FIELDS: list[str] = [
    "task_id",
    "title",
    "created_at",
    "updated_at",
    "status",
    "phase",
    "goal",
]

# Top-level dict fields that must be present and non-empty dicts.
_REQUIRED_DICT_FIELDS: list[str] = [
    "reporting",
    "runtime",
]

# Sub-keys that current_work_package must contain.
_CWP_REQUIRED_KEYS: list[str] = ["id", "goal", "done_when"]

# Optional top-level fields — warn if absent but do not fail.
_OPTIONAL_FIELDS: list[str] = [
    "control_plane",
    "control_plane_hooks",
    "active_task_pointer",
    "preflight",
    "child_execution",
]


def validate_required_fields(data: dict[str, Any]) -> list[str]:
    """Return a list of missing-or-empty required field paths.

    An empty return value means all required fields are present.
    """
    errors: list[str] = []

    # Scalar top-level fields
    for field_name in _REQUIRED_SCALAR_FIELDS:
        value = data.get(field_name)
        if not _is_nonempty(value):
            errors.append(field_name)

    # Required dict fields
    for field_name in _REQUIRED_DICT_FIELDS:
        value = data.get(field_name)
        if not isinstance(value, dict) or not value:
            errors.append(field_name)

    # current_work_package: must be a dict with specific sub-keys
    cwp = data.get("current_work_package")
    if not isinstance(cwp, dict) or not cwp:
        errors.append("current_work_package")
    else:
        for key in _CWP_REQUIRED_KEYS:
            if not _is_nonempty(cwp.get(key)):
                errors.append(f"current_work_package.{key}")

    return errors


def validate_control_plane(data: dict[str, Any]) -> list[str]:
    """Return a list of issue descriptions for the ``control_plane`` block.

    Returns an empty list when the block is absent (it is optional) or valid.
    """
    issues: list[str] = []
    cp = data.get("control_plane")

    if cp is None:
        # Optional — absence is not an issue here; validate_state will warn.
        return issues

    if not isinstance(cp, dict):
        issues.append("control_plane must be a dict")
        return issues

    # Validate known sub-fields when present
    lock = cp.get("lock")
    if lock is not None and not isinstance(lock, dict):
        issues.append("control_plane.lock must be a dict")

    hooks = cp.get("hooks")
    if hooks is not None and not isinstance(hooks, list):
        issues.append("control_plane.hooks must be a list")

    last_heartbeat = cp.get("last_heartbeat")
    if last_heartbeat is not None and not isinstance(last_heartbeat, str):
        issues.append(
            "control_plane.last_heartbeat must be a string (ISO-8601 timestamp)"
        )

    return issues


def validate_state(data: dict[str, Any]) -> ValidationResult:
    """Validate a task state dict fully.

    Returns a :class:`ValidationResult` whose ``valid`` flag is ``True`` only
    when there are zero hard errors.  Warnings are always collected regardless.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Hard errors ---
    missing = validate_required_fields(data)
    for path in missing:
        errors.append(f"Required field missing or empty: '{path}'")

    cp_issues = validate_control_plane(data)
    for issue in cp_issues:
        errors.append(f"control_plane validation error: {issue}")

    # --- Soft warnings ---
    for field_name in _OPTIONAL_FIELDS:
        if data.get(field_name) is None:
            warnings.append(f"Optional field not present: '{field_name}'")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
