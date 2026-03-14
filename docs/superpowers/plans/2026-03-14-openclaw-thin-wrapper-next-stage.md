# OpenClaw Thin Wrapper Next Stage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-value remaining gaps by adding small, verifiable helper commands around OpenClaw host config, webhook triggering, notification summaries, and workspace memory notes without reimplementing the upstream runtime.

**Architecture:** Keep `ltk` as a thin wrapper around the official `openclaw` CLI and host config file. Add focused helper commands that read, validate, render, and minimally update `~/.openclaw/openclaw.json`, reuse shared JSON helpers across commands, and keep all runtime execution, heartbeat scheduling, webhook serving, and daemon supervision delegated to upstream OpenClaw.

**Tech Stack:** Python 3.11+, Click, stdlib `json` / `pathlib`, pytest, mypy, ruff, upstream `openclaw` CLI

---

## Status Snapshot

- Baseline branch for this phase is `main` at merge commit `f7549b4`, which already contains the merged `codex/phase2-runtime-hardening-diagnostics` work.
- Completed already and out of scope for reimplementation:
  - diagnostics JSONL output
  - runtime service and heartbeat diagnostics in `ltk doctor`
  - `MEMORY.md` / `memory/YYYY-MM-DD.md` bootstrap
  - continuation / exhaustion summaries in `status` and `resume`
  - `ltk webhooks` minimal config helper
  - README refresh and close / lock / pointer edge-case hardening
- Hard constraints for this plan:
  - keep `ltk` as a thin wrapper around official OpenClaw
  - do not build a Python webhook server
  - do not rewrite heartbeat scheduling or gateway/runtime behavior
  - do not start multi-task lanes, external worker bridge, compaction-aware memory flush, or a full internal hook system in this phase

## Chunk 1: Heartbeat Host Config Helper

### Task 1: Add shared OpenClaw host-config JSON helpers

**Files:**
- Create: `src/openclaw_ltk/openclaw_config.py`
- Modify: `src/openclaw_ltk/commands/doctor.py`
- Test: `tests/test_openclaw_config.py`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: Write failing tests for loading, validating, and minimally updating `openclaw.json`**

```python
def test_load_openclaw_config_requires_object_payload(tmp_path: Path) -> None:
    ...

def test_upsert_object_path_preserves_unrelated_keys() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_openclaw_config.py tests/test_doctor.py`
Expected: FAIL because there is no shared helper module for host config parsing/upsert yet.

- [ ] **Step 3: Implement the smallest shared helper API**

```python
def load_openclaw_config(path: Path) -> dict[str, Any]:
    ...

def upsert_object_path(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    ...
```

- [ ] **Step 4: Re-run targeted tests**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_openclaw_config.py tests/test_doctor.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/openclaw_config.py src/openclaw_ltk/commands/doctor.py tests/test_openclaw_config.py tests/test_doctor.py
git commit -m "feat: add shared openclaw config helpers"
```

### Task 2: Add `ltk heartbeat` helper for render, validate, and minimal upsert

**Files:**
- Create: `src/openclaw_ltk/commands/heartbeat.py`
- Modify: `src/openclaw_ltk/cli.py`
- Modify: `README.md`
- Test: `tests/test_heartbeat_cmd.py`

- [ ] **Step 1: Write failing tests for example rendering, validation, and non-destructive apply**

```python
def test_heartbeat_command_prints_minimal_config() -> None:
    ...

def test_heartbeat_apply_upserts_config_without_clobbering_other_settings(tmp_path: Path) -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_heartbeat_cmd.py`
Expected: FAIL because the heartbeat helper command group does not exist yet.

- [ ] **Step 3: Implement the minimal command surface**

```python
@click.group("heartbeat", invoke_without_command=True)
def heartbeat_cmd() -> None:
    ...

@heartbeat_cmd.command("apply")
@click.option("--every", required=True)
@click.option("--target", required=True)
def apply_heartbeat_cmd(every: str, target: str) -> None:
    ...
```

- [ ] **Step 4: Re-run targeted tests**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_heartbeat_cmd.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/commands/heartbeat.py src/openclaw_ltk/cli.py README.md tests/test_heartbeat_cmd.py
git commit -m "feat: add heartbeat config helper"
```

## Chunk 2: Webhook Trigger Helper

### Task 3: Expand `ltk webhooks` into a trigger-oriented helper

**Files:**
- Modify: `src/openclaw_ltk/commands/webhooks.py`
- Modify: `src/openclaw_ltk/openclaw_config.py`
- Modify: `README.md`
- Test: `tests/test_webhooks_cmd.py`

- [ ] **Step 1: Write failing tests for payload rendering and curl preview**

```python
def test_webhooks_payload_renders_agent_event_json() -> None:
    ...

def test_webhooks_curl_uses_existing_config_values(tmp_path: Path) -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_webhooks_cmd.py`
Expected: FAIL because `webhooks` only prints a minimal config snippet today.

- [ ] **Step 3: Implement config-only trigger helpers**

```python
@webhooks_cmd.command("payload")
def payload_webhooks_cmd() -> None:
    ...

@webhooks_cmd.command("curl")
def curl_webhooks_cmd() -> None:
    ...
```

- [ ] **Step 4: Re-run targeted tests**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_webhooks_cmd.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/commands/webhooks.py src/openclaw_ltk/openclaw_config.py README.md tests/test_webhooks_cmd.py
git commit -m "feat: add webhook trigger helpers"
```

## Chunk 3: Notification Summary Bridge

### Task 4: Add wrapper-level notification summary rendering

**Files:**
- Create: `src/openclaw_ltk/notifications.py`
- Create: `src/openclaw_ltk/commands/notify.py`
- Modify: `src/openclaw_ltk/cli.py`
- Modify: `README.md`
- Test: `tests/test_notify_cmd.py`

- [ ] **Step 1: Write failing tests for summary rendering and Telegram preview output**

```python
def test_notify_summary_formats_exhaustion_alert(tmp_path: Path) -> None:
    ...

def test_notify_telegram_preview_uses_config_chat_id(tmp_path: Path) -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_notify_cmd.py`
Expected: FAIL because there is no notification bridge command yet.

- [ ] **Step 3: Implement output-only bridge helpers**

```python
def render_notification_summary(...) -> str:
    ...

@click.command("notify")
def notify_cmd(...) -> None:
    ...
```

- [ ] **Step 4: Re-run targeted tests**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_notify_cmd.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/notifications.py src/openclaw_ltk/commands/notify.py src/openclaw_ltk/cli.py README.md tests/test_notify_cmd.py
git commit -m "feat: add notification summary bridge"
```

## Chunk 4: Memory Tooling Minimal Next Step

### Task 5: Add memory note and list helpers

**Files:**
- Modify: `src/openclaw_ltk/memory.py`
- Create: `src/openclaw_ltk/commands/memory.py`
- Modify: `src/openclaw_ltk/cli.py`
- Modify: `README.md`
- Test: `tests/test_memory.py`
- Test: `tests/test_memory_cmd.py`

- [ ] **Step 1: Write failing tests for manual note append and daily note listing**

```python
def test_memory_note_appends_custom_entry(tmp_path: Path) -> None:
    ...

def test_memory_list_shows_daily_files_in_descending_order(tmp_path: Path) -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_memory.py tests/test_memory_cmd.py`
Expected: FAIL because memory tooling only supports bootstrap and resume/init appends today.

- [ ] **Step 3: Implement the smallest operator-facing memory commands**

```python
@click.group("memory")
def memory_cmd() -> None:
    ...

@memory_cmd.command("note")
@memory_cmd.command("list")
```

- [ ] **Step 4: Re-run targeted tests**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q tests/test_memory.py tests/test_memory_cmd.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openclaw_ltk/memory.py src/openclaw_ltk/commands/memory.py src/openclaw_ltk/cli.py README.md tests/test_memory.py tests/test_memory_cmd.py
git commit -m "feat: add memory note helpers"
```

## Chunk 5: Final Verification

### Task 6: Run the required full project checks

**Files:**
- Modify: `README.md` (only if command surface changed during prior tasks)

- [ ] **Step 1: Run the full test suite**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/pytest -q`
Expected: PASS

- [ ] **Step 2: Run lint**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/ruff check .`
Expected: PASS

- [ ] **Step 3: Run type checking**

Run: `/home/yvan/projects/openclaw-long-task-kit/.venv/bin/mypy --strict src tests`
Expected: PASS

- [ ] **Step 4: Inspect git status before reporting**

Run: `git status --short`
Expected: only intended plan/code/doc changes remain.

## Deferred Explicitly

- multi-task lanes
- external worker bridge
- compaction-aware memory flush
- full hook system
- Python webhook server
- heartbeat scheduler reimplementation
