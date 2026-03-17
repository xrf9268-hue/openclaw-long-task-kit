# openclaw-long-task-kit

Thin Python control-plane companion for long-running OpenClaw tasks.

`ltk` manages task state files, workspace bootstrap files, local diagnostics,
and operator-facing checks. It deliberately stays a thin wrapper around the
official `openclaw` CLI instead of reimplementing the gateway/runtime.

## What LTK Does

- bootstraps long-running task state with `ltk init`
- maintains workspace control files such as `HEARTBEAT.md`, `BOOT.md`,
  `AGENTS.md`, `MEMORY.md`, and `memory/YYYY-MM-DD.md`
- runs control-plane health and runtime checks through `ltk preflight`,
  `ltk doctor`, `ltk status`, and `ltk resume`
- records local diagnostics JSONL under the OpenClaw state directory
- exposes config-only helpers such as `ltk heartbeat` and `ltk webhooks`

## What Still Belongs to OpenClaw

- gateway lifecycle, daemon supervision, and upstream health checks
- gateway log streaming via `openclaw logs`
- actual cron execution, heartbeat scheduling, and webhook endpoints
- host-level exec approvals and runtime enforcement
- memory search/index backends and other advanced memory tooling

## Commands

The current CLI surface matches `ltk --help`:

- `advance`: check phase transition guards and advance to the next stage (`--dry-run` to preview, `--record-evidence` to log artifacts)
- `close`: remove cron jobs and heartbeat entries for a task
- `doctor`: run upstream doctor plus local runtime checks
- `github issue create`: create a GitHub issue (`--dry-run` to preview)
- `github comment create`: post a comment on a GitHub issue (`--dry-run` to preview)
- `heartbeat`: print, validate, or minimally upsert heartbeat config helpers
- `init`: create a task state file and bootstrap workspace control files
- `lock`: acquire, renew, or release the task control lock
- `logs`: tail upstream gateway logs and record wrapper diagnostics
- `memory`: append manual notes or list daily memory files
- `migrate`: upgrade a state file to the current schema version (`--dry-run` to preview)
- `notify`: render wrapper-level task summaries or Telegram preview payloads
- `pointer`: manage the active task pointer JSON file
- `preflight`: validate state, files, approvals, cron coverage, and gateway health
- `report issue`: generate a Markdown issue report from task state (sanitized by default)
- `resume`: rerun preflight, refresh bootstrap files, append a memory note, and
  surface continuation/exhaustion policy results
- `status`: print task status plus deadman, continuation, exhaustion, and validation
- `watchdog`: manage watchdog cron jobs
- `webhooks`: print config, validate hooks, and render payload/curl previews

## Workspace Files

- `tasks/state/*.json`: long-running task state files, treated as the local source
  of truth for task progress
- `tasks/.active-task-pointer.json`: pointer to the active task state file
- `HEARTBEAT.md`: operator/agent heartbeat checklist
- `BOOT.md`: restart and recovery checklist
- `AGENTS.md`: task-specific operating guidance for the agent
- `MEMORY.md`: memory index that points at daily notes
- `memory/YYYY-MM-DD.md`: appended daily memory notes for init/resume activity

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | Supported | Primary development target |
| macOS | Supported | Full functionality |
| WSL 2 | Supported | Use native Linux paths, not `\\wsl$\...` |
| WSL 1 | Limited | `fcntl` locking may not work on Windows-mounted paths (e.g. `/mnt/c/`) |
| Native Windows | Not supported | `fcntl` module is unavailable; use WSL instead |
| NFS mounts | Not recommended | `fcntl.flock` is not reliable over NFS; use a local filesystem for the workspace |

### `fcntl` Lock Limitations

LTK uses `fcntl.flock()` for sidecar lock files that serialize concurrent
state file updates.  This mechanism has known limitations:

- **NFS**: `flock` locks are local to the client machine and are not enforced
  across NFS clients.  Running multiple LTK instances against a shared NFS
  workspace can cause data corruption.
- **WSL 1 + `/mnt/` paths**: Filesystem operations on Windows-mounted paths
  may not honour POSIX locking semantics.  Keep the workspace on the native
  Linux filesystem (e.g. `~/`).
- **Windows (native)**: The `fcntl` module does not exist on Windows.  Use
  WSL 2 or a Linux/macOS environment.

**Workaround**: If you must use a network filesystem, set `LTK_WORKSPACE` to a
local directory so that state files and lock files reside on a local disk.

## Incident and Pitfall Reporting

When a long-running task encounters issues, use the following workflow to
diagnose and report the problem.

### Diagnosing an Issue

1. **Check task status** — run `ltk status --state <path>` to see the current
   phase, deadman/continuation/exhaustion policy results, and validation
   errors or warnings.
2. **Run preflight** — `ltk preflight --state <path>` verifies required
   fields, control plane structure, cron coverage, heartbeat presence,
   gateway health, and exec approvals.  Any failing check points to the
   root cause.
3. **Review diagnostics** — local diagnostics are appended to
   `~/.openclaw/ltk-diagnostics.jsonl`.  Use `ltk logs` to tail gateway
   logs alongside wrapper events.
4. **Check doctor** — `ltk doctor` runs upstream health probes and records
   failures in the diagnostics log.

### Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Running `ltk init` without `ltk preflight` | State file exists but preflight never passed | Run `ltk preflight --state <path> --write-back` |
| Stale heartbeat | Deadman policy reports "dead" | Update `updated_at` in the state JSON to the current time, then run `ltk resume --state <path>` |
| Missing exec-approvals file | Preflight fails on `exec-approvals` check | Create `~/.openclaw/exec-approvals.json` |
| Exhausted task keeps retrying | Error count or retry count exceeds threshold | Check `ltk status` exhaustion output, then `ltk resume --state <path>` |
| Invalid state JSON after manual edit | Preflight reports missing required fields | Fix the JSON and re-run `ltk preflight --state <path>` |

### Reporting a Bug

1. Gather the output of `ltk status --state <path>` and
   `ltk preflight --state <path>`.
2. Include relevant lines from `~/.openclaw/ltk-diagnostics.jsonl`.
3. Open an issue on the
   [GitHub issue tracker](https://github.com/xrf9268-hue/openclaw-long-task-kit/issues)
   with the gathered details and steps to reproduce.

## Reference Documentation

- [Cron Configuration Reference](docs/cron-reference.md) — job types, specs, environment variables, and CLI commands
- [Heartbeat Reference](docs/heartbeat-reference.md) — config helpers, HEARTBEAT.md entries, liveness tracking, and deadman policies
- [Security Reference](docs/security-reference.md) — state file locking, credential sanitization, control plane locks, and platform limitations

## Runtime Defaults

- workspace root defaults to `~/.openclaw/workspace`
- host-level OpenClaw state defaults to `~/.openclaw`
- local diagnostics default to `~/.openclaw/ltk-diagnostics.jsonl`
- host-level OpenClaw config defaults to `~/.openclaw/openclaw.json`

## Releasing

Releases are automated via GitHub Actions. To cut a new release:

1. Update `__version__` in `src/openclaw_ltk/__init__.py` and `version` in `pyproject.toml`
2. Update `CHANGELOG.md` — move items from `[Unreleased]` to a new version section
3. Commit, then tag: `git tag v<version>`
4. Push the tag: `git push origin v<version>`

The release workflow verifies the tag matches the package version, runs
tests, and creates a GitHub Release with auto-generated release notes.

## Verification

From the repository root in a Unix-like shell (WSL/macOS/Linux), after
setting up the local virtual environment:

```bash
PYTHONPATH=src .venv/bin/ltk --help
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy --strict src tests
```
