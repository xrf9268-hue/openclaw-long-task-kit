# Contributing

Thanks for your interest in contributing to openclaw-long-task-kit!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/xrf9268-hue/openclaw-long-task-kit.git
cd openclaw-long-task-kit

# Create a virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Verify everything works
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy --strict src tests
```

## Workflow

1. Create a feature branch from `main` (e.g. `codex/issue-42`).
2. Write a failing test first (TDD), then implement the minimal fix.
3. Run the full check suite before committing:
   ```bash
   .venv/bin/pytest -q
   .venv/bin/ruff check .
   .venv/bin/mypy --strict src tests
   ```
4. Keep commits small and reviewable.
5. Open a pull request against `main`.

## Code Style

- Python stdlib-first, explicit types, focused modules.
- Strict mypy compatibility (`--strict`).
- Ruff for linting and formatting.
- No broad refactors unless directly supporting the task at hand.

## Testing

- Use TDD: write the failing test, verify the failure, then implement.
- Add or update tests for any changed behaviour.
- Tests live in `tests/` and use pytest.

## What Makes a Good Change

- Small helper commands around `~/.openclaw/openclaw.json`
- Improved wrapper diagnostics or validation
- Extended memory/bootstrap helpers without inventing a backend
- Better tests around state, locks, pointers, and command output

See `AGENTS.md` for the full list of guidelines and explicit non-goals.
