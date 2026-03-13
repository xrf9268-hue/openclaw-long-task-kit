"""Generator for BOOT.md recovery checklist entries."""

from __future__ import annotations


def generate_boot_entry(
    task_id: str,
    title: str,
    goal: str,
    state_path: str,
    recovery_steps: list[str] | None = None,
) -> str:
    """Generate a BOOT.md recovery checklist entry.

    Format:

        ## Recovery: {task_id}
        - **Task**: {title}
        - **Goal**: {goal}
        - **State File**: `{state_path}`

        ### Recovery Steps
        1. Load state file: `ltk status --state {state_path}`
        2. Run preflight: `ltk preflight --state {state_path}`
        3. Resume work on current work package
        {additional recovery_steps if provided}
    """
    lines: list[str] = [
        f"## Recovery: {task_id}",
        f"- **Task**: {title}",
        f"- **Goal**: {goal}",
        f"- **State File**: `{state_path}`",
        "",
        "### Recovery Steps",
        f"1. Load state file: `ltk status --state {state_path}`",
        f"2. Run preflight: `ltk preflight --state {state_path}`",
        "3. Resume work on current work package",
    ]

    if recovery_steps:
        start_index = 4  # Continue numbering after the three built-in steps.
        for i, step in enumerate(recovery_steps, start=start_index):
            lines.append(f"{i}. {step}")

    return "\n".join(lines)
