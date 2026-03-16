#!/bin/bash
# Pre-commit hook: auto-format staged Python files with ruff before git commit
set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)

# Only trigger on git commit commands
if ! echo "$COMMAND" | grep -q 'git commit'; then
  exit 0
fi

# Get project directory
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || true)
if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR="$(pwd)"
fi
cd "$PROJECT_DIR" || exit 0

# Find Python files staged for commit
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep '\.py$' || true)

if [ -z "$STAGED_PY" ]; then
  exit 0
fi

# Locate ruff (prefer project venv)
RUFF=""
if [ -x ".venv/bin/ruff" ]; then
  RUFF=".venv/bin/ruff"
elif command -v ruff &>/dev/null; then
  RUFF="ruff"
else
  echo "ruff not found, skipping format" >&2
  exit 0
fi

# Auto-format staged files
FORMATTED=0
while IFS= read -r file; do
  if [ -f "$file" ]; then
    BEFORE=$(cat "$file")
    $RUFF format "$file" 2>/dev/null || true
    AFTER=$(cat "$file")
    if [ "$BEFORE" != "$AFTER" ]; then
      git add "$file"
      FORMATTED=$((FORMATTED + 1))
    fi
  fi
done <<< "$STAGED_PY"

if [ "$FORMATTED" -gt 0 ]; then
  echo "ruff format: auto-formatted $FORMATTED file(s) and re-staged" >&2
fi

exit 0
