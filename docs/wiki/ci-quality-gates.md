# CI & Quality Gates

Verification commands, hooks, and code review workflow used by the
automated loop.

## Verification Commands

### Local (used by loop job)

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src/ tests/
.venv/bin/mypy --strict src tests
```

### CI (`.github/workflows/ci.yml`)

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/openclaw_ltk/ --strict
uv run pytest --cov=openclaw_ltk tests/ -v
```

### Differences

| Check | Local | CI | Impact |
|-------|-------|----|--------|
| ruff check | `.` (all files) | `src/ tests/` | Local is stricter (catches root-level files) |
| mypy scope | `src tests` | `src/openclaw_ltk/` only | Local is stricter (also checks tests/) |
| pytest | `-q` (quiet) | `--cov -v` (coverage + verbose) | Output format only |

Local being stricter than CI is **by design**.  If local passes, CI will
never fail on scope differences.

## Pre-commit Hook

File: `.claude/hooks/ruff-format.sh`

A Claude Code `PreToolUse` hook that auto-formats staged Python files
before `git commit`:

1. Detects `git commit` in the Bash command.
2. Finds staged `.py` files via `git diff --cached`.
3. Runs `ruff format` on each file.
4. Re-stages files that changed.

Configuration in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/ruff-format.sh",
            "timeout": 300
          }
        ]
      }
    ]
  }
}
```

### Why this hook exists

Early in the project, all 5 initial PRs failed CI because
`ruff format --check` caught pre-existing unformatted files.  The hook
prevents this class of failure by auto-formatting before every commit.

### Robustness

- `jq` calls use `2>/dev/null || true` to prevent hook failures from
  blocking non-git Bash commands.
- `set -e` is used for early exit on unexpected errors, but all critical
  paths have fallback guards.
- If `ruff` is not found, the hook silently exits (no-op).

## Code Review Workflow

The loop handles code review comments with priority-based triage:

| Priority | Type | Action |
|----------|------|--------|
| P0 | Critical bugs, security vulnerabilities | Must fix before merge |
| P1 | Logic errors, incorrect behavior | Must fix before merge |
| P2 | Code quality, naming, suggestions | Fix if clear and safe; report to user if uncertain |
| P3 | Style preferences | Note but do not block merge |
| P4 | Optional suggestions | Note but do not block merge |

### Review sources

- `gh api repos/.../pulls/N/reviews`: Formal review decisions (APPROVED,
  CHANGES_REQUESTED, COMMENTED).
- `gh api repos/.../pulls/N/comments`: Line-level review comments with
  priority badges.

### Merge criteria

A PR is merge-ready when:

1. All CI checks report SUCCESS.
2. `reviewDecision` is not `CHANGES_REQUESTED`.
3. `mergeable` is not `CONFLICTING`.
4. No unresolved P0-P2 comments remain.

Merge command: `gh pr merge <N> --squash --delete-branch`

## TDD Standards

The loop enforces "rocket-grade" TDD discipline:

1. **Red**: Write a failing test that captures the expected behavior.
2. **Verify red**: Run `pytest` to confirm the test fails for the right
   reason.
3. **Green**: Write the minimal implementation to make the test pass.
4. **Verify green**: Run `pytest` to confirm the test passes.
5. **Full suite**: Run all 4 verification commands before committing.

Additional rules:

- Every behavior change must have corresponding test coverage.
- CLI command/output changes require README.md updates in the same PR.
- One PR per issue.  Keep changes small and reviewable.
- Follow AGENTS.md constraints: thin wrapper, stdlib-first, no speculative
  abstractions.
