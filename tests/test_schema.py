"""Tests for openclaw_ltk.schema validation functions."""

from __future__ import annotations

import copy
from typing import Any

from openclaw_ltk.schema import (
    nested_get,
    validate_required_fields,
    validate_state,
)


class TestValidState:
    def test_valid_state(self, sample_state_data: dict[str, Any]) -> None:
        """A complete valid state dict should pass validation with no errors."""
        result = validate_state(sample_state_data)
        assert result.valid is True
        assert result.errors == []


class TestMissingRequiredField:
    def test_missing_required_field(self, sample_state_data: dict[str, Any]) -> None:
        """Removing task_id should produce a hard error."""
        data = copy.deepcopy(sample_state_data)
        del data["task_id"]
        result = validate_state(data)
        assert result.valid is False
        assert any("task_id" in e for e in result.errors)


class TestMissingWorkPackage:
    def test_missing_work_package(self, sample_state_data: dict[str, Any]) -> None:
        """Removing current_work_package should produce a hard error."""
        data = copy.deepcopy(sample_state_data)
        del data["current_work_package"]
        result = validate_state(data)
        assert result.valid is False
        assert any("current_work_package" in e for e in result.errors)


class TestInvalidWorkPackage:
    def test_invalid_work_package(self, sample_state_data: dict[str, Any]) -> None:
        """A current_work_package dict missing 'id' should produce a hard error."""
        data = copy.deepcopy(sample_state_data)
        # Remove the required 'id' sub-key
        del data["current_work_package"]["id"]
        result = validate_state(data)
        assert result.valid is False
        assert any("current_work_package.id" in e for e in result.errors)


class TestOptionalFieldsWarn:
    def test_optional_fields_warn(self, sample_state_data: dict[str, Any]) -> None:
        """Missing control_plane produces warning, still valid."""
        data = copy.deepcopy(sample_state_data)
        # Ensure control_plane is absent
        data.pop("control_plane", None)
        result = validate_state(data)
        assert result.valid is True
        assert any("control_plane" in w for w in result.warnings)


class TestControlPlaneValid:
    def test_control_plane_valid(self, sample_state_data: dict[str, Any]) -> None:
        """A properly structured control_plane dict should produce no errors."""
        data = copy.deepcopy(sample_state_data)
        data["control_plane"] = {
            "lock": {"holder": "session-1"},
            "hooks": [],
            "last_heartbeat": "2026-03-13T00:00:00+00:00",
        }
        result = validate_state(data)
        assert result.valid is True
        # No control_plane errors
        assert not any("control_plane validation error" in e for e in result.errors)


class TestControlPlaneInvalidType:
    def test_control_plane_invalid_type(
        self, sample_state_data: dict[str, Any]
    ) -> None:
        """control_plane set to a string (non-dict) should produce a hard error."""
        data = copy.deepcopy(sample_state_data)
        data["control_plane"] = "this-is-wrong"
        result = validate_state(data)
        assert result.valid is False
        assert any("control_plane" in e for e in result.errors)


class TestStatusWhitelist:
    def test_valid_status_no_warning(self, sample_state_data: dict[str, Any]) -> None:
        """A recognised status produces no status warning."""
        result = validate_state(sample_state_data)
        assert not any("Unrecognised status" in w for w in result.warnings)

    def test_unknown_status_warns(self, sample_state_data: dict[str, Any]) -> None:
        """An unknown status produces a soft warning (not an error)."""
        data = copy.deepcopy(sample_state_data)
        data["status"] = "banana"
        result = validate_state(data)
        assert result.valid is True  # soft warning only
        assert any("Unrecognised status" in w for w in result.warnings)


class TestTimestampValidation:
    def test_valid_iso_no_warning(self, sample_state_data: dict[str, Any]) -> None:
        """Valid ISO-8601 timestamps produce no warnings."""
        result = validate_state(sample_state_data)
        assert not any("not valid ISO-8601" in w for w in result.warnings)

    def test_bad_timestamp_warns(self, sample_state_data: dict[str, Any]) -> None:
        """A non-ISO-8601 timestamp produces a soft warning."""
        data = copy.deepcopy(sample_state_data)
        data["created_at"] = "not-a-timestamp"
        result = validate_state(data)
        assert any(
            "created_at" in w and "not valid ISO-8601" in w for w in result.warnings
        )


class TestBlockersTypeCheck:
    def test_blockers_list_ok(self, sample_state_data: dict[str, Any]) -> None:
        """blockers as a list passes validation."""
        data = copy.deepcopy(sample_state_data)
        data["current_work_package"]["blockers"] = ["blocker-1"]
        errors = validate_required_fields(data)
        assert not any("blockers" in e for e in errors)

    def test_blockers_not_list_errors(self, sample_state_data: dict[str, Any]) -> None:
        """blockers as a string produces a hard error."""
        data = copy.deepcopy(sample_state_data)
        data["current_work_package"]["blockers"] = "not-a-list"
        errors = validate_required_fields(data)
        assert any("blockers must be a list" in e for e in errors)


class TestNestedGet:
    def test_nested_get_present(self) -> None:
        """nested_get returns the value at a dot-separated path when it exists."""
        data: dict[str, Any] = {"a": {"b": {"c": 42}}}
        assert nested_get(data, "a.b.c") == 42

    def test_nested_get_missing_intermediate(self) -> None:
        """nested_get returns None when an intermediate key is absent."""
        data: dict[str, Any] = {"a": {}}
        assert nested_get(data, "a.b.c") is None

    def test_nested_get_top_level(self) -> None:
        """nested_get works for single-level (no dot) paths."""
        data: dict[str, Any] = {"key": "value"}
        assert nested_get(data, "key") == "value"

    def test_nested_get_absent_key(self) -> None:
        """nested_get returns None for a key that does not exist at all."""
        data: dict[str, Any] = {}
        assert nested_get(data, "missing") is None
