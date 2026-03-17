# Security Reference

LTK's security model is minimal and deliberate: it protects local state
integrity through file locking and atomic writes, sanitizes credentials before
output, and delegates all authentication and runtime enforcement to the upstream
OpenClaw runtime.

## Threat Model

LTK is a local control-plane tool, not a networked service. The primary threats
it addresses are:

- **Concurrent state corruption** — multiple processes writing the same state file
- **Credential leakage** — secrets appearing in logs, reports, or diagnostic output
- **Partial-write corruption** — crashes during state file updates

LTK explicitly does **not** address:
- Authentication or authorization (delegated to OpenClaw)
- Encryption at rest (state files are plain-text JSON)
- Network security (no HTTP server or listener)
- Token rotation or credential lifecycle management

## State File Integrity

### Atomic Writes

All state file writes use `atomic_write_text()` (`src/openclaw_ltk/state.py:24-49`):

1. Write content to a temporary `.tmp` sibling file
2. `fsync` the file descriptor to flush to disk
3. `os.replace()` the temp file onto the target path (atomic on POSIX)
4. `fsync` the parent directory to ensure the rename is durable

If any step fails, the temp file is cleaned up and the original file is
untouched.

### Sidecar File Locking

Concurrent read-modify-write operations are serialized using `fcntl.flock()`
on a sidecar `.lock` file (`src/openclaw_ltk/state.py:62-85`):

```
state.json       ← the actual state
state.json.lock  ← sidecar lock file (created automatically)
```

`StateFile.locked_update()` acquires an exclusive lock, reads the current
state, yields it for modification, then writes and releases. This prevents
lost-update races between concurrent LTK processes.

### Platform Limitations

| Platform | fcntl Support | Notes |
|----------|---------------|-------|
| Linux | Full | Primary target |
| macOS | Full | Supported |
| WSL 2 | Full | Use native Linux paths |
| WSL 1 + `/mnt/` | Unreliable | POSIX locking may not work on Windows-mounted paths |
| NFS | Not enforced | `flock` locks are client-local only |
| Native Windows | Unavailable | `fcntl` module does not exist |

**Workaround**: Set `LTK_WORKSPACE` to a local filesystem directory so that
state files and lock files reside on a disk with reliable locking semantics.

## Control Plane Lock

The `ltk lock` command provides mutual exclusion for control-plane operations
at a higher level than file locking:

```bash
# Acquire (default TTL: 420 seconds / 7 minutes)
ltk lock acquire --state tasks/state/my-task.json --owner "session-A" --ttl 420

# Release
ltk lock release --state tasks/state/my-task.json --owner "session-A"
```

### Behaviour

| Scenario | Result | Exit Code |
|----------|--------|-----------|
| No existing lock | Lock granted | 0 |
| Same owner requests | Lock renewed | 0 |
| Different owner, lock not expired | Rejected | 10 |
| Different owner, lock expired | Lock granted (overwritten) | 0 |
| Unparseable expiry | Treated as expired, lock granted | 0 |
| Release by non-owner | Rejected | 10 |
| Release with no lock held | Idempotent success | 0 |
| Invalid state file | Error | 11 |
| Fatal OS error | Error | 2 |

The lock is stored in the state file under `control_plane.lock`:

```json
{
  "control_plane": {
    "lock": {
      "owner": "session-A",
      "acquired_at": "2025-01-15T10:00:00+00:00",
      "expires_at": "2025-01-15T10:07:00+00:00"
    }
  }
}
```

## Credential Sanitization

`src/openclaw_ltk/sanitize.py` redacts sensitive data before it appears in
reports, logs, or diagnostic output.

### Redaction Rules

| Pattern | Example Input | Redacted Output |
|---------|---------------|-----------------|
| Home paths | `/home/alice/project` | `~/project` |
| Bearer tokens | `Bearer sk-abc123` | `Bearer ***` |
| Key-value secrets | `ANTHROPIC_API_KEY=sk-123` | `ANTHROPIC_API_KEY=***` |
| URL credentials | `https://user:pass@host` | `https://***@host` |

### Recognized Secret Patterns

The key-value regex matches these patterns (case-insensitive):
- `api_key`, `api-key`, `apikey`
- `token`, `secret`, `password`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- Any `*_SECRET`, `*_TOKEN`, `*_KEY`, `*_PASSWORD` suffix

### Configuration

```python
from openclaw_ltk.sanitize import sanitize, SanitizeConfig

# All rules enabled (default)
sanitize(text)

# Selective rules
sanitize(text, SanitizeConfig(
    redact_home_paths=True,
    redact_tokens=True,
    redact_url_credentials=True,
))
```

## Diagnostics and Logging

Local diagnostics are appended to `~/.openclaw/ltk-diagnostics.jsonl`
(configurable via `LTK_DIAGNOSTICS_LOG_PATH`). This file contains:

- Wrapper-level invocation records (`ltk logs`)
- Error details when upstream `openclaw logs` fails

Currently, diagnostics events are emitted by `ltk logs` (wrapper invocation
and failure). Other commands such as `ltk lock` and `ltk preflight` do not
emit diagnostics events.

The file is plain-text JSONL. Protection depends on filesystem permissions of
the `~/.openclaw/` directory.

## Configuration Paths and Access

| Path | Purpose | LTK Access |
|------|---------|------------|
| `~/.openclaw/openclaw.json` | Host-level OpenClaw config | Read + minimal upsert (heartbeat only) |
| `~/.openclaw/exec-approvals.json` | Exec approval whitelist | Read only (checked by preflight) |
| `tasks/state/*.json` | Task state files | Read + atomic write |
| `HEARTBEAT.md` | Workspace heartbeat entries | Read + atomic write |
| `~/.openclaw/ltk-diagnostics.jsonl` | Local diagnostics | Append only |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LTK_WORKSPACE` | `~/.openclaw/workspace` | Workspace root (affects all derived paths) |
| `LTK_EXEC_APPROVALS_PATH` | `~/.openclaw/exec-approvals.json` | Exec approvals location |
| `LTK_OPENCLAW_CONFIG_PATH` | `~/.openclaw/openclaw.json` | OpenClaw config location |
| `LTK_DIAGNOSTICS_LOG_PATH` | `~/.openclaw/ltk-diagnostics.jsonl` | Diagnostics log location |

## Vulnerability Reporting

See [SECURITY.md](../SECURITY.md) for the vulnerability reporting policy:

- Report via GitHub's private vulnerability reporting feature
- Do not open public issues for security vulnerabilities
- 48-hour acknowledgement target, 7-day fix target

## See Also

- [Cron Reference](cron-reference.md) — cron job specs include task IDs and alert routing metadata
- [Heartbeat Reference](heartbeat-reference.md) — liveness tracking relies on state file atomic writes
