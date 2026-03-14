# AGENTS.md

This file applies to the entire repository.

Closest-file wins: if a deeper `AGENTS.md` exists for a subdirectory, follow that file for work in that subtree. Direct user instructions override this file.

## Project Overview

`openclaw-long-task-kit` is a thin Python control-plane companion for long-running OpenClaw tasks.

The core design constraint is non-negotiable:

- `ltk` wraps the official `openclaw` CLI and host config.
- Do not reimplement the OpenClaw gateway, runtime, daemon supervision, webhook server, or heartbeat scheduler.
- Prefer small helper commands that validate, render, or minimally update state and config.

## Environment

- Treat this project as developed in WSL Ubuntu 24.04.
- Use Linux paths such as `/home/yvan/projects/openclaw-long-task-kit`.
- Do not use Windows paths such as `\\wsl$\\...`, `C:\\...`, or backslash-separated paths.
- Use bash-compatible commands and tooling.
- Do not use PowerShell, `cmd.exe`, `.bat`, or other Windows-specific commands.
- If the current shell is not WSL/Linux, stop and switch to WSL before making changes.

## Repository Layout

- `src/openclaw_ltk/`: CLI commands, policies, config helpers, state handling, generators
- `tests/`: pytest coverage for CLI behavior and core helpers
- `templates/`: example service templates and related operator assets
- `docs/`: plans and supporting project docs
- `schemas/`: JSON schema and related structured artifacts

## Working Rules

- Keep the wrapper thin. Reuse the existing command structure and shared helpers instead of adding parallel systems.
- Follow the existing Python style: stdlib-first, explicit types, focused modules, strict mypy compatibility.
- Avoid broad refactors unless they directly support the task at hand.
- When changing user-facing CLI behavior, update `README.md` and any relevant docs in the same change.
- When changing config or state semantics, prefer additive, minimal updates over destructive rewrites.

## Explicit Non-Goals

Do not introduce these unless the user explicitly asks for them and the work is split into small verified slices:

- multi-task lanes
- external worker bridge
- compaction-aware memory flush
- full internal hook system
- Python webhook server
- rewritten heartbeat/runtime scheduling

## Setup Commands

From the repository root:

```bash
pwd
python3 --version
```

Preferred local environment:

```bash
test -x .venv/bin/python || uv sync
```

Use the checked-in virtualenv when it already exists:

```bash
.venv/bin/python --version
PYTHONPATH=src .venv/bin/ltk --help
```

CI uses `uv sync` plus:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/openclaw_ltk/ --strict
uv run pytest --cov=openclaw_ltk tests/ -v
```

## Development Workflow

- Do not develop directly on `main` or on an already-pushed shared branch.
- Create a fresh `codex/...` branch, preferably in `.worktrees/`.
- Keep commits small and reviewable.
- Do not rewrite published history unless the user explicitly asks for it.
- Prefer `rg` for search and `apply_patch` for manual file edits.

## Testing Expectations

- For behavior changes or bug fixes, use TDD: write the failing test first, verify the failure, then implement the minimal fix.
- Add or update tests for any changed behavior, even if not explicitly requested.
- Start with the most targeted tests for the affected area.
- Before claiming completion, run the full repository checks from the repo root:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy --strict src tests
```

- If a check cannot be run, say so clearly and explain why.

## Documentation Expectations

- Keep `README.md` aligned with the current CLI surface.
- If you add a command, change command output, or alter the operator workflow, update docs in the same change.
- Save multi-step implementation plans under `docs/superpowers/plans/`.

## Change Boundaries

Good changes in this repository usually look like:

- adding a small helper command around `~/.openclaw/openclaw.json`
- improving wrapper diagnostics or validation
- extending memory/bootstrap helpers without inventing a backend
- adding payload/curl/config helpers for existing webhook behavior
- improving tests around state, locks, pointers, and command output

Bad changes in this repository usually look like:

- replacing upstream OpenClaw behavior with local Python services
- expanding the toolkit into a general workflow engine
- introducing large speculative abstractions before tests justify them
