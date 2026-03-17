# Heartbeat Reference

LTK provides heartbeat as a two-part system: a **config helper** that sets up
the upstream OpenClaw heartbeat schedule, and **state-based liveness tracking**
via `updated_at` timestamps and deadman-switch policies.

## Architecture

```
ltk heartbeat apply         ─► ~/.openclaw/openclaw.json  (schedule config)
                                   └─► OpenClaw runtime   (fires heartbeat on cadence)

ltk init / ltk resume       ─► HEARTBEAT.md               (workspace entry)
every state file write       ─► state.json: updated_at     (liveness timestamp)
ltk status / ltk doctor     ─► deadman policy check        (alive / stale / dead)
```

LTK does **not** implement a heartbeat scheduler. It configures the upstream
OpenClaw heartbeat, maintains liveness data in the state file, and evaluates
deadman thresholds locally.

## Heartbeat Config Helper

The `ltk heartbeat` command group manages the `agents.defaults.heartbeat`
section of the host-level OpenClaw config (`~/.openclaw/openclaw.json`).

### Print Template

Running `ltk heartbeat` with no subcommand prints the minimal config template:

```bash
ltk heartbeat
```

Output:

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "10m",
        "target": "last"
      }
    }
  }
}
```

### Validate

Check that heartbeat settings exist and are well-formed:

```bash
ltk heartbeat validate
```

Validates:
- `agents.defaults.heartbeat` block exists
- `every` is a non-empty string (e.g. `"10m"`)
- `target` is a non-empty string (e.g. `"last"`)

### Apply

Non-destructively upsert heartbeat settings:

```bash
ltk heartbeat apply --every 10m --target last
```

This uses `upsert_object_path()` from `src/openclaw_ltk/openclaw_config.py`
to merge the heartbeat block into the existing config without clobbering
unrelated keys.

## HEARTBEAT.md Entries

`ltk init` and `ltk resume` inject structured entries into workspace
`HEARTBEAT.md` via `src/openclaw_ltk/generators/heartbeat_entry.py`.

### Entry Format

```markdown
## LTK: my-task-001
<!-- ltk:meta task_id=my-task-001 status=running version=0.1.0 -->
- **Task**: Implement feature X
- **Status**: running
- **Updated**: 2025-01-15T10:30:00+00:00
- **Goal**: Complete implementation with tests
<!-- ltk:end -->
```

### Entry Lifecycle

| Operation | Behaviour |
|-----------|-----------|
| `inject_heartbeat_entry()` — file missing | Creates HEARTBEAT.md with the entry |
| `inject_heartbeat_entry()` — entry missing | Appends entry with blank-line separator |
| `inject_heartbeat_entry()` — entry exists | Replaces existing block in-place |
| `remove_heartbeat_entry()` — entry exists | Removes block, collapses trailing newlines |
| `remove_heartbeat_entry()` — entry/file missing | No-op (idempotent) |

All writes use `atomic_write_text()` for crash safety.

## Liveness Tracking

### updated_at Timestamp

Every call to `StateFile.locked_update()` automatically sets `updated_at` to
the current UTC ISO-8601 timestamp (`src/openclaw_ltk/state.py:189`). This
serves as the heartbeat signal for deadman-switch evaluation.

### Deadman Switch Policy

`src/openclaw_ltk/policies/deadman.py` evaluates task liveness based on the
elapsed time since `updated_at`:

| Status | Condition | Default Threshold |
|--------|-----------|-------------------|
| `alive` | Updated within silence budget | < 10 minutes |
| `stale` | Between silence budget and dead threshold | 10–30 minutes |
| `dead` | No update for dead threshold or longer | >= 30 minutes |

If `updated_at` is missing or unparseable, the task is treated as `dead`.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LTK_SILENCE_BUDGET_MINUTES` | `10` | Minutes of silence before task is "stale" |
| `LTK_DEAD_THRESHOLD_MINUTES` | `30` | Minutes of silence before task is "dead" |
| `LTK_DEADMAN_INTERVAL` | `20` | How often the deadman cron job fires |

### Checking Liveness

```bash
ltk status --state tasks/state/my-task.json
```

The status output includes the deadman evaluation result alongside
continuation and exhaustion policy results.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Deadman reports "dead" | `updated_at` is stale or missing | Update `updated_at` in state JSON, then `ltk resume --state <path>` |
| Heartbeat validate fails | Config missing or malformed | Run `ltk heartbeat apply --every 10m --target last` |
| HEARTBEAT.md entry stale | `ltk resume` not run recently | Run `ltk resume --state <path>` to refresh |

## See Also

- [Cron Reference](cron-reference.md) — the deadman and continuation cron jobs that complement heartbeat tracking
- [Security Reference](security-reference.md) — state file locking that protects `updated_at` from concurrent writes
