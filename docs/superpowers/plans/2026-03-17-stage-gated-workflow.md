# Stage-Gated Workflow Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add formal phase definitions, transition guards, and stall detection so LTK can enforce stage-gated progression without becoming a workflow engine.

**Architecture:** Define an ordered phase enum with prerequisite guards per transition. A new `ltk advance` command checks guards and advances the phase. Existing policies (`progression`, `continuation`) are enhanced to detect stalls at any phase boundary, not just preflight. The system remains a thin validation/detection layer — it never auto-executes work, only validates readiness and records transitions.

**Tech Stack:** Python 3.10+, Click CLI, dataclasses, existing StateFile/migration infrastructure.

---

## Design Decisions

### The "Thin Wrapper" Constraint

Issues #8-#12 request a "stage-gated, state-machine-driven workflow model." However, AGENTS.md explicitly states LTK must not "expand into a general workflow engine." The resolution:

1. **LTK validates and records** — it checks guards and writes phase transitions.
2. **LTK never executes work** — it does not run research, generate specs, or start builds.
3. **LTK detects stalls** — it identifies when a phase's exit criteria are met but the task hasn't advanced.
4. **Operators/agents call `ltk advance`** — phase transitions are explicit CLI commands, not automatic.

### Phase Model

Ordered phases with defined predecessors:

```
launch → preflight → research → spec → execute → review → done
```

- `phase` remains a free-form string in the state file for forward compatibility.
- A known-phase registry defines guard functions for transitions between known phases.
- Unknown phases are allowed (warning only) — LTK doesn't block custom workflows.

### Guard Model

Each transition `A → B` has a guard function: `(state) -> (allowed: bool, reason: str)`.

Guards check **state prerequisites**, not external systems (that's preflight's job). Examples:
- `preflight → research`: requires `preflight_status == "passed"`
- `research → spec`: requires `phase_evidence.research` to exist (a list of artifact paths/notes)
- `spec → execute`: requires `phase_evidence.spec` to exist
- `execute → review`: requires work package marked complete

### Phase Evidence

A new optional `phase_evidence` dict in state records what each phase produced:

```json
{
  "phase_evidence": {
    "preflight": {"passed_at": "...", "overall": "PASS"},
    "research": {"artifacts": ["research-notes.md"], "completed_at": "..."},
    "spec": {"artifacts": ["spec.md"], "completed_at": "..."}
  }
}
```

This is what guards check — lightweight metadata, not the artifacts themselves.

### Schema Migration

This adds `phase_evidence` (optional, defaults to `{}`) — no migration needed since it's optional. `CURRENT_SCHEMA_VERSION` stays at 1.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/openclaw_ltk/phases.py` | Phase definitions, ordering, guard registry, transition logic |
| Create | `src/openclaw_ltk/commands/advance.py` | `ltk advance` CLI command |
| Create | `tests/test_phases.py` | Unit tests for phase logic and guards |
| Create | `tests/test_advance_cmd.py` | CLI integration tests for `ltk advance` |
| Modify | `src/openclaw_ltk/policies/progression.py` | Generalize stall detection to all phase boundaries |
| Modify | `tests/test_progression.py` | Tests for generalized stall detection |
| Modify | `src/openclaw_ltk/cli.py` | Register `advance` command |
| Modify | `src/openclaw_ltk/schema.py` | Add `phase_evidence` to optional fields |
| Modify | `src/openclaw_ltk/commands/status.py` | Show phase gate status in output |
| Modify | `src/openclaw_ltk/commands/resume.py` | Check phase guards on resume |

---

## Chunk 1: Phase Definitions and Guards

### Task 1: Phase ordering and guard infrastructure (`phases.py`)

**Files:**
- Create: `src/openclaw_ltk/phases.py`
- Create: `tests/test_phases.py`

- [ ] **Step 1: Write failing tests for phase ordering**

```python
# tests/test_phases.py
"""Tests for phase definitions and transition guards."""

from __future__ import annotations

from openclaw_ltk.phases import (
    KNOWN_PHASES,
    GuardResult,
    check_transition,
    is_known_phase,
    next_phase,
    phase_index,
)


class TestPhaseOrdering:
    def test_known_phases_ordered(self) -> None:
        assert KNOWN_PHASES == (
            "launch",
            "preflight",
            "research",
            "spec",
            "execute",
            "review",
            "done",
        )

    def test_phase_index(self) -> None:
        assert phase_index("launch") == 0
        assert phase_index("done") == 6

    def test_phase_index_unknown_returns_none(self) -> None:
        assert phase_index("custom-phase") is None

    def test_is_known_phase(self) -> None:
        assert is_known_phase("preflight") is True
        assert is_known_phase("banana") is False

    def test_next_phase(self) -> None:
        assert next_phase("launch") == "preflight"
        assert next_phase("execute") == "review"

    def test_next_phase_done_returns_none(self) -> None:
        assert next_phase("done") is None

    def test_next_phase_unknown_returns_none(self) -> None:
        assert next_phase("custom") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_phases.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'openclaw_ltk.phases'`

- [ ] **Step 3: Implement phase ordering**

```python
# src/openclaw_ltk/phases.py
"""Phase definitions, ordering, and transition guards.

Defines the standard phase progression for long-running tasks and the
guard functions that validate whether a phase transition is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Ordered tuple of known phases. Index position defines ordering.
KNOWN_PHASES: tuple[str, ...] = (
    "launch",
    "preflight",
    "research",
    "spec",
    "execute",
    "review",
    "done",
)

_PHASE_INDEX: dict[str, int] = {p: i for i, p in enumerate(KNOWN_PHASES)}


def phase_index(phase: str) -> int | None:
    """Return the zero-based index of *phase*, or None if unknown."""
    return _PHASE_INDEX.get(phase)


def is_known_phase(phase: str) -> bool:
    """Return True if *phase* is in the known phase list."""
    return phase in _PHASE_INDEX


def next_phase(current: str) -> str | None:
    """Return the phase after *current*, or None if at end or unknown."""
    idx = _PHASE_INDEX.get(current)
    if idx is None or idx >= len(KNOWN_PHASES) - 1:
        return None
    return KNOWN_PHASES[idx + 1]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_phases.py::TestPhaseOrdering -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for transition guards**

```python
# Append to tests/test_phases.py

class TestGuardResult:
    def test_allowed_result(self) -> None:
        r = GuardResult(allowed=True, reason="ok")
        assert r.allowed is True

    def test_blocked_result(self) -> None:
        r = GuardResult(allowed=False, reason="preflight not passed")
        assert r.allowed is False


class TestCheckTransition:
    def test_launch_to_preflight_always_allowed(self) -> None:
        state = {"phase": "launch", "status": "launching"}
        result = check_transition(state, "preflight")
        assert result.allowed is True

    def test_preflight_to_research_requires_preflight_passed(self) -> None:
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "failed",
        }
        result = check_transition(state, "research")
        assert result.allowed is False
        assert "preflight" in result.reason.lower()

    def test_preflight_to_research_allowed_when_passed(self) -> None:
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "passed",
        }
        result = check_transition(state, "research")
        assert result.allowed is True

    def test_research_to_spec_requires_evidence(self) -> None:
        state = {"phase": "research", "status": "active"}
        result = check_transition(state, "spec")
        assert result.allowed is False
        assert "evidence" in result.reason.lower()

    def test_research_to_spec_allowed_with_evidence(self) -> None:
        state = {
            "phase": "research",
            "status": "active",
            "phase_evidence": {
                "research": {
                    "artifacts": ["notes.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_transition(state, "spec")
        assert result.allowed is True

    def test_spec_to_execute_requires_evidence(self) -> None:
        state = {"phase": "spec", "status": "active"}
        result = check_transition(state, "spec")
        assert result.allowed is False

    def test_spec_to_execute_allowed_with_evidence(self) -> None:
        state = {
            "phase": "spec",
            "status": "active",
            "phase_evidence": {
                "spec": {
                    "artifacts": ["spec.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_transition(state, "execute")
        assert result.allowed is True

    def test_backward_transition_blocked(self) -> None:
        state = {"phase": "execute", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False
        assert "backward" in result.reason.lower()

    def test_skip_transition_blocked(self) -> None:
        state = {"phase": "launch", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False
        assert "skip" in result.reason.lower() or "adjacent" in result.reason.lower()

    def test_unknown_current_phase_blocked(self) -> None:
        state = {"phase": "custom", "status": "active"}
        result = check_transition(state, "research")
        assert result.allowed is False

    def test_unknown_target_phase_blocked(self) -> None:
        state = {"phase": "launch", "status": "active"}
        result = check_transition(state, "banana")
        assert result.allowed is False

    def test_terminal_status_blocks_transition(self) -> None:
        state = {"phase": "research", "status": "done"}
        result = check_transition(state, "spec")
        assert result.allowed is False
        assert "terminal" in result.reason.lower()
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_phases.py::TestCheckTransition -v`
Expected: FAIL — `GuardResult` and `check_transition` not yet implemented

- [ ] **Step 7: Implement guard infrastructure and check_transition**

```python
# Append to src/openclaw_ltk/phases.py

@dataclass
class GuardResult:
    """Result of evaluating a transition guard."""

    allowed: bool
    reason: str


# Statuses that block all transitions.
_TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled", "closed"})


# ---------------------------------------------------------------------------
# Guard functions: (state) -> GuardResult
# Each guard checks prerequisites for entering a specific target phase.
# ---------------------------------------------------------------------------

def _guard_always_allow(state: dict[str, Any]) -> GuardResult:
    """No prerequisites — transition is always allowed."""
    return GuardResult(allowed=True, reason="No prerequisites required.")


def _guard_preflight_passed(state: dict[str, Any]) -> GuardResult:
    """Require preflight_status == 'passed' or preflight.overall == 'PASS'."""
    preflight_status = state.get("preflight_status", "")
    preflight_block = state.get("preflight")
    preflight_overall = ""
    if isinstance(preflight_block, dict):
        preflight_overall = str(preflight_block.get("overall", ""))

    if preflight_status == "passed" or preflight_overall == "PASS":
        return GuardResult(allowed=True, reason="Preflight passed.")
    return GuardResult(
        allowed=False,
        reason="Preflight has not passed. Run 'ltk preflight --write-back' first.",
    )


def _guard_phase_evidence(phase_name: str) -> Any:
    """Return a guard that requires phase_evidence.<phase_name> to exist."""

    def _guard(state: dict[str, Any]) -> GuardResult:
        evidence = state.get("phase_evidence")
        if not isinstance(evidence, dict):
            return GuardResult(
                allowed=False,
                reason=(
                    f"No phase_evidence found. Record {phase_name} "
                    f"evidence before advancing."
                ),
            )
        phase_ev = evidence.get(phase_name)
        if not isinstance(phase_ev, dict) or not phase_ev.get("artifacts"):
            return GuardResult(
                allowed=False,
                reason=(
                    f"No evidence for '{phase_name}' phase. "
                    f"Record artifacts before advancing."
                ),
            )
        return GuardResult(
            allowed=True,
            reason=f"Phase '{phase_name}' evidence present.",
        )

    return _guard


def _guard_work_package_complete(state: dict[str, Any]) -> GuardResult:
    """Require the current work package to be marked complete."""
    cwp = state.get("current_work_package")
    if not isinstance(cwp, dict):
        return GuardResult(
            allowed=False,
            reason="No current_work_package found.",
        )
    if cwp.get("status") == "complete" or cwp.get("done"):
        return GuardResult(allowed=True, reason="Work package complete.")
    evidence = state.get("phase_evidence", {})
    if isinstance(evidence, dict) and isinstance(
        evidence.get("execute"), dict
    ):
        return GuardResult(allowed=True, reason="Execute phase evidence present.")
    return GuardResult(
        allowed=False,
        reason=(
            "Work package not marked complete and no execute evidence. "
            "Mark work as done or record evidence before advancing."
        ),
    )


# Registry: maps target phase to its entry guard.
_GUARDS: dict[str, Any] = {
    "launch": _guard_always_allow,
    "preflight": _guard_always_allow,
    "research": _guard_preflight_passed,
    "spec": _guard_phase_evidence("research"),
    "execute": _guard_phase_evidence("spec"),
    "review": _guard_work_package_complete,
    "done": _guard_always_allow,
}


def check_transition(
    state: dict[str, Any], target: str
) -> GuardResult:
    """Check whether transitioning to *target* phase is allowed.

    Validates:
    1. Current phase is known.
    2. Target phase is known.
    3. Target is the immediate next phase (no skipping, no backward).
    4. Status is not terminal.
    5. Phase-specific guard passes.
    """
    current = state.get("phase", "")
    status = str(state.get("status", ""))

    # Terminal status blocks all transitions.
    if status in _TERMINAL_STATUSES:
        return GuardResult(
            allowed=False,
            reason=f"Task has terminal status '{status}'; cannot transition.",
        )

    current_idx = phase_index(current)
    target_idx = phase_index(target)

    if current_idx is None:
        return GuardResult(
            allowed=False,
            reason=f"Current phase '{current}' is not a known phase.",
        )

    if target_idx is None:
        return GuardResult(
            allowed=False,
            reason=f"Target phase '{target}' is not a known phase.",
        )

    if target_idx <= current_idx:
        return GuardResult(
            allowed=False,
            reason=(
                f"Cannot move backward from '{current}' to '{target}'."
            ),
        )

    if target_idx != current_idx + 1:
        return GuardResult(
            allowed=False,
            reason=(
                f"Cannot skip from '{current}' to '{target}'; "
                f"must advance to adjacent phase "
                f"'{KNOWN_PHASES[current_idx + 1]}' first."
            ),
        )

    guard = _GUARDS.get(target, _guard_always_allow)
    return guard(state)
```

- [ ] **Step 8: Run all phase tests to verify they pass**

Run: `pytest tests/test_phases.py -v`
Expected: PASS

- [ ] **Step 9: Run linting**

Run: `ruff check src/openclaw_ltk/phases.py tests/test_phases.py && ruff format src/openclaw_ltk/phases.py tests/test_phases.py`

- [ ] **Step 10: Commit**

```bash
git add src/openclaw_ltk/phases.py tests/test_phases.py
git commit -m "feat: add phase definitions and transition guards (#8 #9 #10)"
```

---

### Task 2: `ltk advance` CLI command

**Files:**
- Create: `src/openclaw_ltk/commands/advance.py`
- Create: `tests/test_advance_cmd.py`
- Modify: `src/openclaw_ltk/cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_advance_cmd.py
"""Tests for the ltk advance command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from openclaw_ltk.cli import main


def _write_state(tmp_path: Path, data: dict[str, Any]) -> Path:
    state_dir = tmp_path / "tasks" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "test-task.json"
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return state_file


def _base_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "task_id": "test-task",
        "title": "Test",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T01:00:00+00:00",
        "status": "active",
        "phase": "launch",
        "goal": "Test goal",
        "schema_version": 1,
        "current_work_package": {
            "id": "WP-1",
            "goal": "g",
            "done_when": "d",
            "blockers": [],
        },
        "reporting": {"silence_budget_minutes": 10},
        "runtime": {"mode": "main_session"},
        "control_plane": {"lock": {}, "cron_jobs": {}},
    }
    base.update(overrides)
    return base


class TestAdvanceCmd:
    def test_advance_launch_to_preflight(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "preflight"]
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_records_transition_log(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "preflight"]
        )
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        log = reloaded.get("phase_transitions", [])
        assert len(log) == 1
        assert log[0]["from"] == "launch"
        assert log[0]["to"] == "preflight"

    def test_advance_blocked_by_guard(self, tmp_path: Path) -> None:
        # preflight → research requires preflight_status == "passed"
        state_file = _write_state(tmp_path, _base_state(phase="preflight"))
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "research"]
        )
        assert result.exit_code != 0
        assert "preflight" in result.output.lower()
        # Phase should NOT have changed.
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_dry_run(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["advance", "--state", str(state_file), "--to", "preflight", "--dry-run"],
        )
        assert result.exit_code == 0
        # Phase should NOT have changed on disk.
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "launch"

    def test_advance_next_infers_target(self, tmp_path: Path) -> None:
        state_file = _write_state(tmp_path, _base_state(phase="launch"))
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--next"]
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "preflight"

    def test_advance_backward_blocked(self, tmp_path: Path) -> None:
        state_file = _write_state(
            tmp_path, _base_state(phase="research", preflight_status="passed")
        )
        runner = CliRunner()
        result = runner.invoke(
            main, ["advance", "--state", str(state_file), "--to", "launch"]
        )
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_advance_cmd.py -v`
Expected: FAIL — command not registered

- [ ] **Step 3: Implement `advance` command**

```python
# src/openclaw_ltk/commands/advance.py
"""Advance the task to the next phase after checking transition guards."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.errors import StateFileError
from openclaw_ltk.phases import check_transition, next_phase
from openclaw_ltk.state import StateFile


@click.command("advance")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--to", "target_phase", default=None, help="Target phase to advance to")
@click.option("--next", "use_next", is_flag=True, help="Advance to the next phase")
@click.option("--dry-run", is_flag=True, help="Check guards without writing")
def advance_cmd(
    state_path: str,
    target_phase: str | None,
    use_next: bool,
    dry_run: bool,
) -> None:
    """Advance the task phase after checking transition guards."""
    if not target_phase and not use_next:
        click.echo("ERROR: specify --to <phase> or --next", err=True)
        sys.exit(2)

    sf = StateFile(Path(state_path).expanduser().resolve())
    try:
        state = sf.load()
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        sys.exit(2)

    current = str(state.get("phase", ""))

    if use_next and not target_phase:
        target_phase = next_phase(current)
        if target_phase is None:
            click.echo(
                f"No next phase after '{current}' "
                f"(already at end or unknown phase).",
                err=True,
            )
            sys.exit(1)

    assert target_phase is not None  # guaranteed by checks above

    result = check_transition(state, target_phase)

    if not result.allowed:
        click.echo(f"BLOCKED: {current} → {target_phase}")
        click.echo(f"  Reason: {result.reason}")
        sys.exit(1)

    if dry_run:
        click.echo(f"DRY-RUN: {current} → {target_phase} — guard passed")
        return

    try:
        with sf.locked_update() as data:
            data["phase"] = target_phase
            # Append to transition log.
            transitions = data.setdefault("phase_transitions", [])
            transitions.append(
                {
                    "from": current,
                    "to": target_phase,
                    "at": now_utc_iso(),
                }
            )
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        sys.exit(2)

    click.echo(f"Advanced: {current} → {target_phase}")
```

- [ ] **Step 4: Register command in cli.py**

Add to `src/openclaw_ltk/cli.py`:

```python
from openclaw_ltk.commands.advance import advance_cmd
# ... in the group setup:
main.add_command(advance_cmd)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_advance_cmd.py -v`
Expected: PASS

- [ ] **Step 6: Run linting**

Run: `ruff check src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py && ruff format src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py`

- [ ] **Step 7: Commit**

```bash
git add src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py src/openclaw_ltk/cli.py
git commit -m "feat: add ltk advance command with transition guards (#8 #9)"
```

---

## Chunk 2: Enhanced Stall Detection and Integration

### Task 3: Generalize progression stall detection

**Files:**
- Modify: `src/openclaw_ltk/policies/progression.py`
- Modify: `tests/test_progression.py` (or create if it doesn't exist)

- [ ] **Step 1: Write failing tests for generalized stall detection**

```python
# tests/test_progression.py (append or create)
"""Tests for generalized phase stall detection."""

from __future__ import annotations

from openclaw_ltk.policies.progression import (
    check_progression_stall,
)


class TestGeneralizedStallDetection:
    def test_preflight_passed_stall(self) -> None:
        """Original behavior: preflight passed but phase still 'preflight'."""
        state = {
            "phase": "preflight",
            "status": "active",
            "preflight_status": "passed",
        }
        result = check_progression_stall(state)
        assert result.stalled is True

    def test_research_done_but_phase_not_advanced(self) -> None:
        """Issue #12: research evidence exists but phase is still 'research'."""
        state = {
            "phase": "research",
            "status": "active",
            "phase_evidence": {
                "research": {
                    "artifacts": ["notes.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is True
        assert "research" in result.reason.lower()

    def test_spec_done_but_phase_not_advanced(self) -> None:
        """Issue #12: spec evidence exists but phase is still 'spec'."""
        state = {
            "phase": "spec",
            "status": "active",
            "phase_evidence": {
                "spec": {
                    "artifacts": ["spec.md"],
                    "completed_at": "2026-01-01T00:00:00",
                },
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is True

    def test_no_evidence_no_stall(self) -> None:
        """Phase without evidence is actively working, not stalled."""
        state = {"phase": "research", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_execute_phase_no_stall_without_evidence(self) -> None:
        state = {"phase": "execute", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_done_phase_no_stall(self) -> None:
        state = {"phase": "done", "status": "done"}
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_terminal_status_no_stall(self) -> None:
        state = {
            "phase": "research",
            "status": "cancelled",
            "phase_evidence": {
                "research": {"artifacts": ["x"], "completed_at": "2026-01-01"},
            },
        }
        result = check_progression_stall(state)
        assert result.stalled is False

    def test_unknown_phase_no_stall(self) -> None:
        state = {"phase": "custom-thing", "status": "active"}
        result = check_progression_stall(state)
        assert result.stalled is False
```

- [ ] **Step 2: Run tests to verify they fail (new stall cases)**

Run: `pytest tests/test_progression.py -v`
Expected: `test_research_done_but_phase_not_advanced` and `test_spec_done_but_phase_not_advanced` FAIL

- [ ] **Step 3: Update progression.py to detect stalls at any known phase**

Replace the body of `check_progression_stall` in `src/openclaw_ltk/policies/progression.py`:

```python
"""Progression stall detection — identifies tasks stuck in a phase after
prerequisites have already been satisfied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openclaw_ltk.phases import is_known_phase, next_phase, check_transition

_TERMINAL_STATUSES = frozenset({"closed", "done", "failed", "cancelled"})


@dataclass
class ProgressionResult:
    """Result of checking for a progression stall."""

    stalled: bool
    reason: str
    suggested_action: str


def check_progression_stall(state: dict[str, Any]) -> ProgressionResult:
    """Detect progression stalls at any known phase boundary.

    A stall is detected when:
    - The task is at a known phase.
    - The transition guard for the next phase would PASS.
    - But the task hasn't advanced.

    This generalizes the original preflight-only detection to cover
    research→spec, spec→execute, and other transitions.
    """
    phase = state.get("phase", "")
    status = str(state.get("status", "")).lower()

    # Terminal tasks cannot be stalled.
    if status in _TERMINAL_STATUSES:
        return ProgressionResult(
            stalled=False,
            reason="Task has terminal status; no stall applicable.",
            suggested_action="No action needed.",
        )

    # Unknown phases — we can't evaluate stalls.
    if not is_known_phase(phase):
        return ProgressionResult(
            stalled=False,
            reason=f"Phase '{phase}' is not a known phase; skipping stall check.",
            suggested_action="Continue normal execution.",
        )

    # If there's no next phase (e.g., "done"), no stall possible.
    target = next_phase(phase)
    if target is None:
        return ProgressionResult(
            stalled=False,
            reason=f"Phase '{phase}' is the final phase.",
            suggested_action="No action needed.",
        )

    # Check if the transition guard would allow advancing.
    guard_result = check_transition(state, target)

    if not guard_result.allowed:
        # Guard blocks transition — task is actively working, not stalled.
        return ProgressionResult(
            stalled=False,
            reason=(
                f"Phase '{phase}' prerequisites for '{target}' "
                f"not yet met: {guard_result.reason}"
            ),
            suggested_action=f"Complete '{phase}' phase requirements.",
        )

    # Guard passes but phase hasn't advanced — stall detected.
    return ProgressionResult(
        stalled=True,
        reason=(
            f"Phase '{phase}' exit criteria are met but task has not "
            f"advanced to '{target}'. "
            f"Guard check: {guard_result.reason}"
        ),
        suggested_action=(
            f"Run 'ltk advance --state <path> --to {target}' "
            f"to advance to the next phase."
        ),
    )


def format_progression_summary(result: ProgressionResult) -> str:
    """Return a human-readable summary of the progression check."""
    if result.stalled:
        return (
            f"Progression: STALLED — {result.reason}\n"
            f"  Suggested: {result.suggested_action}"
        )
    return f"Progression: ok — {result.reason}"
```

- [ ] **Step 4: Run all progression tests**

Run: `pytest tests/test_progression.py -v`
Expected: PASS

- [ ] **Step 5: Run existing test suite to verify no regressions**

Run: `pytest tests/ -v`
Expected: PASS (existing preflight stall tests should still pass because the new code handles the same cases)

- [ ] **Step 6: Run linting**

Run: `ruff check src/openclaw_ltk/policies/progression.py tests/test_progression.py && ruff format src/openclaw_ltk/policies/progression.py tests/test_progression.py`

- [ ] **Step 7: Commit**

```bash
git add src/openclaw_ltk/policies/progression.py tests/test_progression.py
git commit -m "feat: generalize stall detection to all phase boundaries (#11 #12)"
```

---

### Task 4: Add `phase_evidence` to schema and integrate with status/resume

**Files:**
- Modify: `src/openclaw_ltk/schema.py`
- Modify: `src/openclaw_ltk/commands/status.py`
- Modify: `src/openclaw_ltk/commands/resume.py`

- [ ] **Step 1: Add `phase_evidence` and `phase_transitions` to optional fields in schema.py**

```python
# In src/openclaw_ltk/schema.py, update _OPTIONAL_FIELDS:
_OPTIONAL_FIELDS: list[str] = [
    "control_plane",
    "control_plane_hooks",
    "active_task_pointer",
    "preflight",
    "child_execution",
    "phase_evidence",
    "phase_transitions",
]
```

- [ ] **Step 2: Write test for schema change**

```python
# Add to tests/test_init.py or a dedicated test — verify phase_evidence is optional
# Actually, existing validation tests already cover this implicitly since
# phase_evidence is optional (warning only). Verify by running existing tests.
```

Run: `pytest tests/ -k "test_valid_data_passes" -v`
Expected: PASS

- [ ] **Step 3: Add phase gate status to `ltk status` output**

In `src/openclaw_ltk/commands/status.py`, after the progression stall line, add phase gate info:

```python
# After: click.echo(format_progression_summary(progression))
# Add:
from openclaw_ltk.phases import is_known_phase, next_phase, check_transition

if is_known_phase(phase):
    target = next_phase(phase)
    if target is not None:
        gate = check_transition(data, target)
        gate_label = "OPEN" if gate.allowed else "CLOSED"
        click.echo(f"Phase Gate ({phase} → {target}): {gate_label} — {gate.reason}")
```

- [ ] **Step 4: Add stall warning to `ltk resume`**

In `src/openclaw_ltk/commands/resume.py`, after continuation/exhaustion checks, add:

```python
from openclaw_ltk.policies.progression import check_progression_stall, format_progression_summary

progression = check_progression_stall(state)
if progression.stalled:
    click.echo(f"\nWARNING: {format_progression_summary(progression)}")
```

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Run linting**

Run: `ruff check src/openclaw_ltk/ && ruff format src/openclaw_ltk/`

- [ ] **Step 7: Commit**

```bash
git add src/openclaw_ltk/schema.py src/openclaw_ltk/commands/status.py src/openclaw_ltk/commands/resume.py
git commit -m "feat: integrate phase gates into status and resume commands (#10 #11)"
```

---

### Task 5: Add `ltk advance --record-evidence` for phase evidence recording

**Files:**
- Modify: `src/openclaw_ltk/commands/advance.py`
- Modify: `tests/test_advance_cmd.py`

- [ ] **Step 1: Write failing test for evidence recording**

```python
# Append to tests/test_advance_cmd.py

class TestRecordEvidence:
    def test_record_evidence_stores_artifacts(self, tmp_path: Path) -> None:
        state_file = _write_state(
            tmp_path,
            _base_state(phase="research", preflight_status="passed"),
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "advance", "--state", str(state_file),
                "--record-evidence", "research",
                "--artifact", "notes.md",
                "--artifact", "findings.md",
            ],
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        ev = reloaded["phase_evidence"]["research"]
        assert ev["artifacts"] == ["notes.md", "findings.md"]
        assert "completed_at" in ev

    def test_record_evidence_then_advance(self, tmp_path: Path) -> None:
        """Record evidence and advance in one step."""
        state_file = _write_state(
            tmp_path,
            _base_state(phase="research", preflight_status="passed"),
        )
        runner = CliRunner()
        # First record evidence
        runner.invoke(
            main,
            [
                "advance", "--state", str(state_file),
                "--record-evidence", "research",
                "--artifact", "notes.md",
            ],
        )
        # Then advance (guard should now pass)
        result = runner.invoke(
            main,
            ["advance", "--state", str(state_file), "--to", "spec"],
        )
        assert result.exit_code == 0
        reloaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert reloaded["phase"] == "spec"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_advance_cmd.py::TestRecordEvidence -v`
Expected: FAIL

- [ ] **Step 3: Add `--record-evidence` and `--artifact` options to advance command**

Update `src/openclaw_ltk/commands/advance.py`:

```python
@click.command("advance")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--to", "target_phase", default=None, help="Target phase to advance to")
@click.option("--next", "use_next", is_flag=True, help="Advance to the next phase")
@click.option("--dry-run", is_flag=True, help="Check guards without writing")
@click.option(
    "--record-evidence",
    "evidence_phase",
    default=None,
    help="Record evidence for a phase (without advancing)",
)
@click.option(
    "--artifact",
    "artifacts",
    multiple=True,
    help="Artifact path/name to record as evidence (repeatable)",
)
def advance_cmd(
    state_path: str,
    target_phase: str | None,
    use_next: bool,
    dry_run: bool,
    evidence_phase: str | None,
    artifacts: tuple[str, ...],
) -> None:
    """Advance the task phase or record phase evidence."""
    sf = StateFile(Path(state_path).expanduser().resolve())

    # Record-evidence mode: write evidence and exit.
    if evidence_phase is not None:
        if not artifacts:
            click.echo("ERROR: --record-evidence requires at least one --artifact", err=True)
            sys.exit(2)
        try:
            with sf.locked_update() as data:
                evidence = data.setdefault("phase_evidence", {})
                evidence[evidence_phase] = {
                    "artifacts": list(artifacts),
                    "completed_at": now_utc_iso(),
                }
        except StateFileError as exc:
            click.echo(f"ERROR: {exc.message}", err=True)
            sys.exit(2)
        click.echo(
            f"Recorded evidence for '{evidence_phase}': "
            f"{', '.join(artifacts)}"
        )
        return

    # ... rest of existing advance logic ...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_advance_cmd.py -v`
Expected: PASS

- [ ] **Step 5: Run linting**

Run: `ruff check src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py && ruff format src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py`

- [ ] **Step 6: Commit**

```bash
git add src/openclaw_ltk/commands/advance.py tests/test_advance_cmd.py
git commit -m "feat: add --record-evidence to ltk advance for phase evidence (#12)"
```

---

### Task 6: Update README and run full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `advance` command to README Commands section**

```markdown
- `advance`: check phase transition guards and advance to the next stage (`--dry-run` to preview, `--record-evidence` to log artifacts)
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Run all linters**

Run: `ruff check . && ruff format --check . && mypy --strict src tests`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add advance command to README"
```

- [ ] **Step 5: Create PR**

```bash
gh pr create --title "feat: stage-gated workflow with phase guards" --body "..."
```
