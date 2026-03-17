# Cron Configuration Reference

LTK manages cron jobs through a thin wrapper around `openclaw cron` commands.
All scheduling and execution is delegated to the upstream OpenClaw runtime —
LTK only builds job specs, registers them, and removes them when a task closes.

## Architecture

```
ltk init / ltk resume
  └─► cron_matrix.py   (builds 4 job specs)
        └─► CronClient  (subprocess: openclaw cron add --json)
              └─► OpenClaw runtime  (schedules & fires jobs)
```

LTK never runs a scheduler itself. The `CronClient` class
(`src/openclaw_ltk/cron.py`) shells out to `openclaw cron list|add|remove|disable`
with `--json` for structured I/O.

## Standard Job Types

Every long-running task declares up to four cron jobs, built by
`src/openclaw_ltk/generators/cron_matrix.py`:

### Watchdog

| Field | Value |
|-------|-------|
| Name | `watchdog-{task_id}` |
| Schedule | `kind: at` — fires once at a specified ISO-8601 time |
| Behaviour | Reminds the session to check task status; self-deletes after firing |
| CLI | `ltk watchdog arm --state <path> --at <iso>` |

Managed via `ltk watchdog arm`, `ltk watchdog disarm`, and `ltk watchdog renew`.
An optional Telegram chat ID (from `LTK_TELEGRAM_CHAT_ID`) is stored in meta
for alert routing.

### Continuation

| Field | Value |
|-------|-------|
| Name | `continuation-{task_id}` |
| Schedule | `kind: every` — fires every N minutes (default: 5) |
| Behaviour | Prompts the session to continue from where it left off |
| Failure alert | After 2 consecutive missed runs |

### Deadman Switch

| Field | Value |
|-------|-------|
| Name | `deadman-{task_id}` |
| Schedule | `kind: every` — fires every N minutes (default: 20) |
| Behaviour | Detects silence or stalls; uses `announce` delivery mode |
| Delivery | `{"mode": "announce"}` — surfaces even when primary session is inactive |

### Closure Check

| Field | Value |
|-------|-------|
| Name | `closure-check-{task_id}` |
| Schedule | `kind: at` — fires at `start_time + duration + 30min buffer` |
| Behaviour | Verifies task reached its goal; self-deletes after firing |

## Configuration

Cron intervals are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LTK_CONTINUATION_INTERVAL` | `5` | Minutes between continuation prompts |
| `LTK_DEADMAN_INTERVAL` | `20` | Minutes between deadman checks |

These map to `LtkConfig.continuation_interval_minutes` and
`LtkConfig.deadman_interval_minutes` in `src/openclaw_ltk/config.py`.

## Composite Builder

`build_all_specs()` creates all four job specs at once:

```python
from openclaw_ltk.generators.cron_matrix import build_all_specs

specs = build_all_specs(
    task_id="my-task",
    duration_minutes=120,
    closure_at_iso="2025-01-15T10:00:00+00:00",
    continuation_interval_minutes=5,
    deadman_interval_minutes=20,
    telegram_chat_id="123456",
)
```

## Job Spec Format

Each spec is a JSON dict with the following structure:

```json
{
  "name": "continuation-my-task",
  "schedule": {"kind": "every", "interval": "5m"},
  "payload": {"kind": "systemEvent", "text": "..."},
  "sessionTarget": "main",
  "enabled": true,
  "lightContext": true,
  "meta": {"taskId": "my-task", "intervalMinutes": 5}
}
```

Optional fields:
- `deleteAfterRun: true` — used by watchdog and closure-check for one-shot jobs
- `delivery: {"mode": "announce"}` — used by the deadman switch
- `failureAlert: {"after": 2}` — used by continuation

## CLI Commands

### `ltk watchdog arm`

```bash
ltk watchdog arm --state tasks/state/my-task.json --at 2025-01-15T12:00:00Z
```

### `ltk watchdog disarm`

```bash
ltk watchdog disarm --state tasks/state/my-task.json
```

### `ltk watchdog renew`

```bash
ltk watchdog renew --state tasks/state/my-task.json --at 2025-01-15T14:00:00Z
```

### `ltk close`

Removes all declared cron jobs and the heartbeat entry for a task:

```bash
ltk close --state tasks/state/my-task.json
```

## See Also

- [Heartbeat Reference](heartbeat-reference.md) — liveness tracking that complements cron monitoring
- [Security Reference](security-reference.md) — credential sanitization and state file locking
