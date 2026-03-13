# OpenClaw Control Plane Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining post-Phase-1 work so `openclaw-long-task-kit` can guide 24/7 OpenClaw operations, long-task recovery, and memory-aware automation without reimplementing the upstream gateway.

**Architecture:** Keep `ltk` as a thin Python control-plane companion around the official `openclaw` CLI. Extend the current command surface, host diagnostics, and workspace bootstrap files while reusing upstream health, logs, memory, and webhook capabilities through `src/openclaw_ltk/openclaw_cli.py`. Treat state JSON plus workspace markdown files as the local source of truth, and treat OpenClaw gateway/runtime features as delegated infrastructure.

**Tech Stack:** Python 3.11+, Click, stdlib `subprocess` / `json` / `pathlib`, pytest, mypy, ruff, upstream `openclaw` CLI

---

## Status Snapshot

- Phase 1 is complete on `main` as of commit `64d8034`.
- Implemented already:
  - sidecar-lock state writes
  - host-level preflight gateway/approval checks
  - idempotent `HEARTBEAT.md` / `BOOT.md` / `AGENTS.md` bootstrap updates
  - `ltk doctor`, `ltk logs`, `ltk resume`
- Remaining work in this plan:
  - Phase 2: 24/7 runtime and observability hardening
  - Phase 3: memory, continuation, and webhook-oriented task progression
  - Phase 4: documentation and edge-case test hardening

## Chunk 1: Phase 2 Runtime Hardening

### Task 1: Add structured local diagnostics output

**Files:**
- Modify: `src/openclaw_ltk/config.py`
- Create: `src/openclaw_ltk/logging.py`
- Modify: `src/openclaw_ltk/commands/doctor.py`
- Modify: `src/openclaw_ltk/commands/logs.py`
- Test: `tests/test_doctor.py`
- Test: `tests/test_logs_cmd.py`

- [ ] **Step 1: Write the failing tests for local log path resolution and JSONL writes**

```python
def test_log_path_defaults_under_openclaw_state_dir() -> None:
    ...

def test_doctor_emits_jsonl_event_when_probe_fails() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor.py tests/test_logs_cmd.py -v`
Expected: FAIL because no local logging helper or log-path config exists yet.

- [ ] **Step 3: Implement minimal diagnostics logger**

```python
def write_diagnostic_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Extend commands to log probe failures and wrapper activity**

Run:
`pytest tests/test_doctor.py tests/test_logs_cmd.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/config.py src/openclaw_ltk/logging.py src/openclaw_ltk/commands/doctor.py src/openclaw_ltk/commands/logs.py tests/test_doctor.py tests/test_logs_cmd.py
git commit -m "feat: add local diagnostics logging"
```

### Task 2: Add service and heartbeat config diagnostics

**Files:**
- Modify: `src/openclaw_ltk/openclaw_cli.py`
- Modify: `src/openclaw_ltk/commands/doctor.py`
- Modify: `src/openclaw_ltk/config.py`
- Create: `templates/systemd-user/openclaw-ltk.service.example`
- Create: `templates/launchd/ai.openclaw.ltk.plist.example`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: Write failing tests for heartbeat config validation and linger/service hints**

```python
def test_doctor_reports_missing_heartbeat_block() -> None:
    ...

def test_doctor_reports_linux_linger_hint() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor.py -v`
Expected: FAIL because doctor does not inspect config/service state yet.

- [ ] **Step 3: Add OpenClaw wrapper methods for gateway status and config-oriented doctor probes**

```python
def gateway_status(self) -> Any:
    return self._run_json(["gateway", "status", "--json"])
```

- [ ] **Step 4: Implement doctor checks and add service templates**

Run: `pytest tests/test_doctor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/openclaw_cli.py src/openclaw_ltk/commands/doctor.py src/openclaw_ltk/config.py templates/systemd-user/openclaw-ltk.service.example templates/launchd/ai.openclaw.ltk.plist.example tests/test_doctor.py
git commit -m "feat: add runtime service diagnostics"
```

## Chunk 2: Phase 3 Task Progression and Memory

### Task 3: Introduce workspace memory file helpers

**Files:**
- Modify: `src/openclaw_ltk/config.py`
- Create: `src/openclaw_ltk/memory.py`
- Modify: `src/openclaw_ltk/commands/init.py`
- Modify: `src/openclaw_ltk/commands/resume.py`
- Test: `tests/test_init.py`
- Test: `tests/test_resume.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write failing tests for `MEMORY.md` and `memory/YYYY-MM-DD.md` bootstrap creation**

```python
def test_init_creates_memory_files() -> None:
    ...

def test_resume_appends_daily_memory_note() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_init.py tests/test_resume.py tests/test_memory.py -v`
Expected: FAIL because memory helpers do not exist.

- [ ] **Step 3: Implement minimal memory bootstrap helpers**

```python
def ensure_memory_files(config: LtkConfig, now_local: datetime) -> tuple[Path, Path]:
    ...
```

- [ ] **Step 4: Update `init` and `resume` to create memory files without inventing search/index logic**

Run: `pytest tests/test_init.py tests/test_resume.py tests/test_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/config.py src/openclaw_ltk/memory.py src/openclaw_ltk/commands/init.py src/openclaw_ltk/commands/resume.py tests/test_init.py tests/test_resume.py tests/test_memory.py
git commit -m "feat: bootstrap workspace memory files"
```

### Task 4: Wire continuation and exhaustion into status/resume output

**Files:**
- Modify: `src/openclaw_ltk/commands/status.py`
- Modify: `src/openclaw_ltk/commands/resume.py`
- Modify: `src/openclaw_ltk/policies/continuation.py`
- Modify: `src/openclaw_ltk/policies/exhaustion.py`
- Test: `tests/test_status_cmd.py`
- Test: `tests/test_resume.py`

- [ ] **Step 1: Write failing tests for continuation/exhaustion summaries**

```python
def test_status_reports_exhaustion_action() -> None:
    ...

def test_resume_stops_when_task_should_not_continue() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_status_cmd.py tests/test_resume.py -v`
Expected: FAIL because command output does not surface these policy decisions consistently.

- [ ] **Step 3: Implement the smallest output-layer changes**

```python
decision = should_continue(state)
exhaustion = evaluate_exhaustion(state)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `pytest tests/test_status_cmd.py tests/test_resume.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/commands/status.py src/openclaw_ltk/commands/resume.py src/openclaw_ltk/policies/continuation.py src/openclaw_ltk/policies/exhaustion.py tests/test_status_cmd.py tests/test_resume.py
git commit -m "feat: surface continuation and exhaustion policy results"
```

### Task 5: Add webhook config inspection helpers

**Files:**
- Modify: `src/openclaw_ltk/openclaw_cli.py`
- Create: `src/openclaw_ltk/commands/webhooks.py`
- Modify: `src/openclaw_ltk/cli.py`
- Test: `tests/test_webhooks_cmd.py`

- [ ] **Step 1: Write failing tests for webhook config generation/validation**

```python
def test_webhooks_command_prints_minimal_hook_config() -> None:
    ...

def test_webhooks_validate_reports_missing_token() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webhooks_cmd.py -v`
Expected: FAIL because no webhook helper command exists.

- [ ] **Step 3: Implement a config-only helper, not a Python webhook server**

```python
@click.group("webhooks")
def webhooks_cmd() -> None:
    ...
```

- [ ] **Step 4: Re-run targeted tests**

Run: `pytest tests/test_webhooks_cmd.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/openclaw_cli.py src/openclaw_ltk/commands/webhooks.py src/openclaw_ltk/cli.py tests/test_webhooks_cmd.py
git commit -m "feat: add webhook configuration helpers"
```

## Chunk 3: Phase 4 Productization and Quality

### Task 6: Add README and usage documentation

**Files:**
- Create: `README.md`
- Modify: `gap-analysis-report.md`
- Modify: `docs/superpowers/plans/2026-03-13-openclaw-control-plane-followups.md`

- [ ] **Step 1: Write README sections for current commands and delegated upstream responsibilities**

```markdown
## What LTK Does
## What Still Belongs to OpenClaw
## Commands
## Workspace Files
```

- [ ] **Step 2: Verify docs are accurate against the current CLI**

Run: `ltk --help`
Expected: command list matches README exactly.

- [ ] **Step 3: Commit**

```bash
git add README.md gap-analysis-report.md docs/superpowers/plans/2026-03-13-openclaw-control-plane-followups.md
git commit -m "docs: add user-facing control plane guide"
```

### Task 7: Harden remaining edge-case tests

**Files:**
- Modify: `tests/test_close.py`
- Modify: `tests/test_lock.py`
- Modify: `tests/test_pointer.py`

- [ ] **Step 1: Add failing regression tests for the gaps called out in `gap-analysis-report.md`**

```python
def test_close_handles_heartbeat_remove_failure() -> None:
    ...

def test_lock_renews_same_owner_after_ttl_expiry() -> None:
    ...

def test_pointer_get_handles_permission_error() -> None:
    ...
```

- [ ] **Step 2: Run targeted tests to verify failures**

Run: `pytest tests/test_close.py tests/test_lock.py tests/test_pointer.py -v`
Expected: FAIL on the newly-added scenarios.

- [ ] **Step 3: Implement only the minimum fixes required by the tests**

- [ ] **Step 4: Re-run the targeted tests**

Run: `pytest tests/test_close.py tests/test_lock.py tests/test_pointer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_close.py tests/test_lock.py tests/test_pointer.py src/openclaw_ltk/commands/close.py src/openclaw_ltk/commands/lock.py src/openclaw_ltk/commands/pointer.py
git commit -m "test: cover remaining task control edge cases"
```

## Final Verification Gate

- [ ] Run the full suite after every chunk:

```bash
/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q
/home/yvan/projects/openclaw-long-task-kit/.venv/bin/ruff check .
/home/yvan/projects/openclaw-long-task-kit/.venv/bin/mypy --strict src tests
```

- [ ] Do not start multi-task lanes, external worker bridges, or compaction-aware memory flush in the same execution stream as this plan. Those are explicitly deferred until Phases 2-4 above are complete and stable.
