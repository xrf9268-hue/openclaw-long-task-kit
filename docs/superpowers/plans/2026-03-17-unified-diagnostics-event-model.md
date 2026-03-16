# Unified Diagnostics Event Model Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize scattered diagnostic event handling into a unified `diagnostics.py` module with typed dataclasses and a single emit function.

**Architecture:** Create two dataclasses — `DiagnosticEvent` (for JSONL log entries) and `CheckResult` (for health/runtime check results). Provide an `emit()` function to replace `write_diagnostic_event`. Migrate `doctor.py` and `logs.py` to use the new types. Remove `logging.py`.

**Tech Stack:** Python stdlib dataclasses, JSON serialization, pathlib

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/openclaw_ltk/diagnostics.py` | `DiagnosticEvent`, `CheckResult` dataclasses + `emit()` function |
| Create | `tests/test_diagnostics.py` | Unit tests for the new module |
| Modify | `src/openclaw_ltk/commands/doctor.py` | Replace `_runtime_check` dict with `CheckResult`, replace ad-hoc event dicts with `DiagnosticEvent` |
| Modify | `src/openclaw_ltk/commands/logs.py` | Replace ad-hoc event dicts with `DiagnosticEvent` |
| Delete | `src/openclaw_ltk/logging.py` | Remove — functionality moved to `diagnostics.py` |

**Not in scope:** Policy dataclasses (`ContinuationDecision`, `DeadmanStatus`, etc.) stay in their policy modules. Preflight `tuple[bool, str]` pattern stays as-is (different field names: `passed` vs `ok`).

---

## Chunk 1: Core Module + Migration

### Task 1: Create `DiagnosticEvent` dataclass with tests

**Files:**
- Create: `tests/test_diagnostics.py`
- Create: `src/openclaw_ltk/diagnostics.py`

- [ ] **Step 1: Write failing tests for `DiagnosticEvent`**

```python
"""Tests for the unified diagnostics event model."""

from __future__ import annotations

from openclaw_ltk.diagnostics import DiagnosticEvent


class TestDiagnosticEvent:
    def test_to_dict_basic(self) -> None:
        ev = DiagnosticEvent(ts="2026-01-01T00:00:00Z", event="test_event")
        d = ev.to_dict()
        assert d["ts"] == "2026-01-01T00:00:00Z"
        assert d["event"] == "test_event"

    def test_to_dict_with_data(self) -> None:
        ev = DiagnosticEvent(
            ts="2026-01-01T00:00:00Z",
            event="test_event",
            data={"command": "doctor", "repair": True},
        )
        d = ev.to_dict()
        assert d["command"] == "doctor"
        assert d["repair"] is True
        assert d["ts"] == "2026-01-01T00:00:00Z"

    def test_data_keys_merged_flat(self) -> None:
        """Extra data keys appear at top level, not nested under 'data'."""
        ev = DiagnosticEvent(
            ts="t", event="e", data={"foo": "bar"}
        )
        d = ev.to_dict()
        assert "data" not in d
        assert d["foo"] == "bar"
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'openclaw_ltk.diagnostics'`

- [ ] **Step 3: Implement `DiagnosticEvent`**

```python
"""Unified diagnostics event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DiagnosticEvent:
    """A structured event written to the JSONL diagnostics log."""

    ts: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ts": self.ts, "event": self.event}
        result.update(self.data)
        return result
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_diagnostics.py src/openclaw_ltk/diagnostics.py
git commit -m "feat(diagnostics): add DiagnosticEvent dataclass with tests"
```

---

### Task 2: Add `CheckResult` dataclass with tests

**Files:**
- Modify: `tests/test_diagnostics.py`
- Modify: `src/openclaw_ltk/diagnostics.py`

- [ ] **Step 1: Write failing tests for `CheckResult`**

Append to `tests/test_diagnostics.py`:

```python
from openclaw_ltk.diagnostics import CheckResult


class TestCheckResult:
    def test_to_dict_minimal(self) -> None:
        cr = CheckResult(name="heartbeat", ok=True, detail="ok")
        d = cr.to_dict()
        assert d == {"name": "heartbeat", "ok": True, "detail": "ok"}

    def test_to_dict_with_hint_and_source(self) -> None:
        cr = CheckResult(
            name="linux-linger",
            ok=False,
            detail="no lingering",
            hint="enable linger",
            source="gateway status",
        )
        d = cr.to_dict()
        assert d["hint"] == "enable linger"
        assert d["source"] == "gateway status"

    def test_to_dict_omits_none_hint_and_source(self) -> None:
        cr = CheckResult(name="test", ok=True, detail="fine")
        d = cr.to_dict()
        assert "hint" not in d
        assert "source" not in d
```

- [ ] **Step 2: Run tests — expect ImportError for `CheckResult`**

Run: `python3 -m pytest tests/test_diagnostics.py::TestCheckResult -v`
Expected: FAIL — `ImportError: cannot import name 'CheckResult'`

- [ ] **Step 3: Implement `CheckResult`**

Add to `src/openclaw_ltk/diagnostics.py`:

```python
@dataclass(frozen=True)
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    ok: bool
    detail: str
    hint: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "ok": self.ok, "detail": self.detail}
        if self.hint is not None:
            d["hint"] = self.hint
        if self.source is not None:
            d["source"] = self.source
        return d
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_diagnostics.py src/openclaw_ltk/diagnostics.py
git commit -m "feat(diagnostics): add CheckResult dataclass"
```

---

### Task 3: Add `emit()` function with tests

**Files:**
- Modify: `tests/test_diagnostics.py`
- Modify: `src/openclaw_ltk/diagnostics.py`

- [ ] **Step 1: Write failing test for `emit()`**

Append to `tests/test_diagnostics.py`:

```python
import json
from pathlib import Path

from openclaw_ltk.diagnostics import emit


class TestEmit:
    def test_creates_parent_dirs_and_appends(self, tmp_path: Path) -> None:
        log_path = tmp_path / "sub" / "diagnostics.jsonl"
        ev = DiagnosticEvent(ts="t1", event="e1", data={"k": "v"})
        emit(log_path, ev)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event"] == "e1"
        assert parsed["k"] == "v"

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        log_path = tmp_path / "diagnostics.jsonl"
        emit(log_path, DiagnosticEvent(ts="t1", event="first"))
        emit(log_path, DiagnosticEvent(ts="t2", event="second"))
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "first"
        assert json.loads(lines[1])["event"] == "second"
```

- [ ] **Step 2: Run tests — expect ImportError for `emit`**

Run: `python3 -m pytest tests/test_diagnostics.py::TestEmit -v`
Expected: FAIL — `ImportError: cannot import name 'emit'`

- [ ] **Step 3: Implement `emit()`**

Add to `src/openclaw_ltk/diagnostics.py`:

```python
import json
from pathlib import Path


def emit(path: Path, event: DiagnosticEvent) -> None:
    """Append one diagnostic event to the JSONL log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run all diagnostics tests — expect PASS**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_diagnostics.py src/openclaw_ltk/diagnostics.py
git commit -m "feat(diagnostics): add emit() function for JSONL logging"
```

---

### Task 4: Migrate `doctor.py` to use `CheckResult` and `DiagnosticEvent`

**Files:**
- Modify: `src/openclaw_ltk/commands/doctor.py`

**Changes:**
1. Replace `from openclaw_ltk.logging import write_diagnostic_event` → `from openclaw_ltk.diagnostics import CheckResult, DiagnosticEvent, emit`
2. Replace `_runtime_check()` helper → `CheckResult(...).to_dict()`
3. Replace ad-hoc event dict in the `except` block → `DiagnosticEvent(...)`

- [ ] **Step 1: Update imports and replace `_runtime_check` with `CheckResult`**

In `doctor.py`, remove the `_runtime_check` function. Replace all calls:

```python
# Before:
return _runtime_check("heartbeat-config", False, "...", hint=hint, source=source)

# After:
return CheckResult(name="heartbeat-config", ok=False, detail="...", hint=hint, source=source).to_dict()
```

Replace the `write_diagnostic_event` call in the except block:

```python
# Before:
write_diagnostic_event(config.diagnostics_log_path, {...})

# After:
emit(config.diagnostics_log_path, DiagnosticEvent(
    ts=now_utc_iso(),
    event="doctor_probe_failed",
    data={
        "command": "doctor",
        "repair": repair,
        "deep": deep,
        "error": exc.message,
        "detail": exc.detail,
    },
))
```

- [ ] **Step 2: Run doctor tests — expect PASS (unchanged behavior)**

Run: `python3 -m pytest tests/test_doctor.py -v`
Expected: All 5 tests pass — serialization output is identical.

- [ ] **Step 3: Commit**

```bash
git add src/openclaw_ltk/commands/doctor.py
git commit -m "refactor(doctor): migrate to diagnostics.CheckResult and emit()"
```

---

### Task 5: Migrate `logs.py` to use `DiagnosticEvent` and `emit()`

**Files:**
- Modify: `src/openclaw_ltk/commands/logs.py`

**Changes:**
1. Replace `from openclaw_ltk.logging import write_diagnostic_event` → `from openclaw_ltk.diagnostics import DiagnosticEvent, emit`
2. Replace both ad-hoc event dicts with `DiagnosticEvent(...)`

- [ ] **Step 1: Update imports and replace event dicts**

```python
# Before:
write_diagnostic_event(config.diagnostics_log_path, {"ts": now_utc_iso(), "event": "logs_wrapper_invoked", ...})

# After:
emit(config.diagnostics_log_path, DiagnosticEvent(
    ts=now_utc_iso(),
    event="logs_wrapper_invoked",
    data={"command": "logs", "follow": follow, "json_output": json_output, "limit": limit, "local_time": local_time},
))
```

Same for the `logs_wrapper_failed` event in the except block.

- [ ] **Step 2: Run logs tests — expect PASS**

Run: `python3 -m pytest tests/test_logs_cmd.py -v`
Expected: All 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/openclaw_ltk/commands/logs.py
git commit -m "refactor(logs): migrate to diagnostics.DiagnosticEvent and emit()"
```

---

### Task 6: Remove `logging.py`

**Files:**
- Delete: `src/openclaw_ltk/logging.py`

- [ ] **Step 1: Verify no remaining imports of `openclaw_ltk.logging`**

Run: `grep -r "from openclaw_ltk.logging" src/ tests/`
Expected: No matches (doctor.py and logs.py already migrated).

- [ ] **Step 2: Delete `logging.py`**

```bash
git rm src/openclaw_ltk/logging.py
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/`
Expected: All 183+ tests pass. No lint errors. No new mypy errors.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: remove logging.py — functionality moved to diagnostics.py"
```

---

### Task 7: Final verification and PR

- [ ] **Step 1: Run full CI-equivalent checks**

```bash
python3 -m pytest -q
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```

- [ ] **Step 2: Push and create PR**

```bash
git push -u origin codex/issue-18
gh pr create --title "refactor: unify diagnostics event model (new diagnostics.py)" \
  --body "$(cat <<'EOF'
## Summary
- Creates `src/openclaw_ltk/diagnostics.py` with `DiagnosticEvent` and `CheckResult` dataclasses plus `emit()` function
- Migrates `doctor.py` and `logs.py` from ad-hoc dicts to typed events
- Removes `logging.py` (functionality consolidated into `diagnostics.py`)
- Adds unit tests for the new module

## Test plan
- [ ] All existing tests pass unchanged (backward-compatible serialization)
- [ ] New `test_diagnostics.py` covers DiagnosticEvent, CheckResult, and emit()
- [ ] `ruff check` + `ruff format --check` + `mypy` clean

Closes #18
EOF
)"
```
