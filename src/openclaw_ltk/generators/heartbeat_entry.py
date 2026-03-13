"""Generator and injector for structured HEARTBEAT.md entries."""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Entry template
# ---------------------------------------------------------------------------

_ENTRY_TEMPLATE = """\
## LTK: {task_id}
<!-- ltk:meta task_id={task_id} status={status} -->
- **Task**: {title}
- **Status**: {status}
- **Updated**: {updated_at}
- **Goal**: {goal}
<!-- ltk:end -->"""


def generate_entry(
    task_id: str,
    title: str,
    status: str,
    goal: str,
    updated_at: str,
) -> str:
    """Return a fully-rendered heartbeat entry block as a string.

    The block is delimited by ``## LTK: {task_id}`` and ``<!-- ltk:end -->``.
    """
    return _ENTRY_TEMPLATE.format(
        task_id=task_id,
        title=title,
        status=status,
        goal=goal,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# Block regex helper
# ---------------------------------------------------------------------------


def _block_pattern(task_id: str) -> re.Pattern[str]:
    """Return a compiled regex that matches the full entry block for *task_id*.

    The pattern is non-greedy and DOTALL so it captures multi-line content
    between the opening heading and the closing comment (inclusive).
    """
    escaped = re.escape(task_id)
    return re.compile(
        rf"^## LTK: {escaped}\n.*?<!-- ltk:end -->",
        re.MULTILINE | re.DOTALL,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inject_heartbeat_entry(
    heartbeat_path: Path,
    task_id: str,
    title: str,
    status: str,
    goal: str,
    updated_at: str,
) -> None:
    """Insert or update the entry for *task_id* in *heartbeat_path*.

    Behaviour:
    - If the file does not exist it is created with the new entry.
    - If the file exists but contains no block for *task_id*, the entry is
      appended (preceded by a blank line when the file is non-empty).
    - If a block for *task_id* already exists it is replaced in-place,
      preserving all surrounding content.

    The operation is idempotent: calling it twice with identical arguments
    produces the same file.
    """
    entry = generate_entry(task_id, title, status, goal, updated_at)
    pattern = _block_pattern(task_id)

    if not heartbeat_path.exists():
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_path.write_text(entry + "\n", encoding="utf-8")
        return

    original = heartbeat_path.read_text(encoding="utf-8")

    if pattern.search(original):
        # Replace existing block in-place.
        updated = pattern.sub(entry, original)
    else:
        # Append, ensuring there is exactly one blank line separator.
        separator = "\n" if original.endswith("\n") else "\n\n"
        updated = original + separator + entry + "\n"

    heartbeat_path.write_text(updated, encoding="utf-8")


def remove_heartbeat_entry(heartbeat_path: Path, task_id: str) -> None:
    """Remove the entry block for *task_id* from *heartbeat_path*.

    If the file does not exist, or if no block for *task_id* is found,
    the function returns silently (idempotent).

    Trailing blank lines that result from the removal are collapsed to a
    single trailing newline so the file stays tidy.
    """
    if not heartbeat_path.exists():
        return

    original = heartbeat_path.read_text(encoding="utf-8")
    pattern = _block_pattern(task_id)

    if not pattern.search(original):
        return

    # Remove the block and any immediately preceding blank line so we do not
    # leave orphaned whitespace between adjacent sections.
    cleaned = pattern.sub("", original)

    # Collapse runs of more than two consecutive newlines down to two.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Ensure file ends with a single newline (or is truly empty).
    cleaned = cleaned.rstrip("\n")
    if cleaned:
        cleaned += "\n"

    heartbeat_path.write_text(cleaned, encoding="utf-8")
