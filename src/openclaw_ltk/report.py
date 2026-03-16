"""Issue report rendering — generates Markdown from task state."""

from __future__ import annotations

from typing import Any

from openclaw_ltk.policies.continuation import (
    format_continuation_summary,
    should_continue,
)
from openclaw_ltk.policies.deadman import check_deadman
from openclaw_ltk.policies.exhaustion import (
    evaluate_exhaustion,
    format_exhaustion_summary,
)
from openclaw_ltk.policies.progression import (
    check_progression_stall,
    format_progression_summary,
)
from openclaw_ltk.sanitize import sanitize
from openclaw_ltk.schema import validate_state


def render_issue_report(
    state: dict[str, Any],
    *,
    sanitize_output: bool = True,
) -> str:
    """Render a Markdown issue report from task state data."""
    task_id = str(state.get("task_id", "unknown"))
    title = str(state.get("title", "untitled"))
    status = str(state.get("status", "unknown"))
    phase = str(state.get("phase", "unknown"))
    goal = str(state.get("goal", ""))
    updated_at = str(state.get("updated_at", ""))
    error_count = state.get("error_count", 0)

    cwp = state.get("current_work_package") or {}
    cwp_id = str(cwp.get("id", "-"))
    cwp_goal = str(cwp.get("goal", "-"))
    cwp_done_when = str(cwp.get("done_when", "-"))
    blockers = cwp.get("blockers", [])

    # Policy diagnostics.
    continuation = should_continue(state)
    exhaustion = evaluate_exhaustion(state)
    deadman = check_deadman(state)
    progression = check_progression_stall(state)
    validation = validate_state(state)

    # Notes.
    notes = state.get("notes", [])

    sections: list[str] = []

    # Header.
    sections.append(f"# Issue Report: {title}")
    sections.append("")

    # Task metadata table.
    sections.append("## Task Metadata")
    sections.append("")
    sections.append("| Field | Value |")
    sections.append("|-------|-------|")
    sections.append(f"| Task ID | `{task_id}` |")
    sections.append(f"| Status | {status} |")
    sections.append(f"| Phase | {phase} |")
    sections.append(f"| Goal | {goal} |")
    sections.append(f"| Updated | {updated_at} |")
    sections.append(f"| Error Count | {error_count} |")
    sections.append("")

    # Work package.
    sections.append("## Current Work Package")
    sections.append("")
    sections.append(f"- **ID:** {cwp_id}")
    sections.append(f"- **Goal:** {cwp_goal}")
    sections.append(f"- **Done when:** {cwp_done_when}")
    if blockers:
        sections.append(f"- **Blockers:** {', '.join(str(b) for b in blockers)}")
    sections.append("")

    # Diagnostics.
    sections.append("## Diagnostics")
    sections.append("")
    sections.append(f"- {format_continuation_summary(continuation)}")
    sections.append(f"- {format_exhaustion_summary(exhaustion)}")
    sections.append(f"- Deadman: {deadman.status} — {deadman.message}")
    sections.append(f"- {format_progression_summary(progression)}")
    sections.append("")

    # Validation.
    val_label = "valid" if validation.valid else "INVALID"
    sections.append("## Validation")
    sections.append("")
    sections.append(
        f"**{val_label}** ({len(validation.errors)} errors, "
        f"{len(validation.warnings)} warnings)"
    )
    if validation.errors:
        sections.append("")
        for err in validation.errors:
            sections.append(f"- {err}")
    sections.append("")

    # Notes.
    if notes:
        sections.append("## Notes")
        sections.append("")
        for note in notes:
            sections.append(f"- {note}")
        sections.append("")

    report = "\n".join(sections)

    if sanitize_output:
        report = sanitize(report)

    return report
