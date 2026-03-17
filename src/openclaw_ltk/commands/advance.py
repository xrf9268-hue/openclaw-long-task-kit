"""Advance the task to the next phase after checking transition guards."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from openclaw_ltk.clock import now_utc_iso
from openclaw_ltk.errors import StateFileError
from openclaw_ltk.phases import check_transition, next_phase
from openclaw_ltk.state import StateFile


@click.command("advance")
@click.option("--state", "state_path", required=True, help="Path to state file")
@click.option("--to", "target_phase", default=None, help="Target phase to advance to")
@click.option("--next", "use_next", is_flag=True, help="Advance to the next phase")
@click.option("--dry-run", is_flag=True, help="Check guards without writing")
@click.option(
    "--record-evidence",
    "evidence_phase",
    default=None,
    help="Record evidence for a phase (without advancing)",
)
@click.option(
    "--artifact",
    "artifacts",
    multiple=True,
    help="Artifact path/name to record as evidence (repeatable)",
)
def advance_cmd(
    state_path: str,
    target_phase: str | None,
    use_next: bool,
    dry_run: bool,
    evidence_phase: str | None,
    artifacts: tuple[str, ...],
) -> None:
    """Advance the task phase or record phase evidence."""
    sf = StateFile(Path(state_path).expanduser().resolve())

    # --- Record-evidence mode ---
    if evidence_phase is not None:
        if not artifacts:
            click.echo(
                "ERROR: --record-evidence requires at least one --artifact",
                err=True,
            )
            sys.exit(2)
        if dry_run:
            click.echo(
                f"DRY-RUN: would record evidence for '{evidence_phase}': "
                f"{', '.join(artifacts)}"
            )
            return
        try:
            with sf.locked_update() as data:
                evidence = data.setdefault("phase_evidence", {})
                evidence[evidence_phase] = {
                    "artifacts": list(artifacts),
                    "completed_at": now_utc_iso(),
                }
        except StateFileError as exc:
            click.echo(f"ERROR: {exc.message}", err=True)
            sys.exit(2)
        click.echo(f"Recorded evidence for '{evidence_phase}': {', '.join(artifacts)}")
        return

    # --- Advance mode ---
    if not target_phase and not use_next:
        click.echo("ERROR: specify --to <phase> or --next", err=True)
        sys.exit(2)

    try:
        state = sf.load()
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        sys.exit(2)

    current = str(state.get("phase", ""))

    if use_next and not target_phase:
        target_phase = next_phase(current)
        if target_phase is None:
            click.echo(
                f"No next phase after '{current}' (already at end or unknown phase).",
                err=True,
            )
            sys.exit(1)

    assert target_phase is not None  # guaranteed by checks above

    result = check_transition(state, target_phase)

    if not result.allowed:
        click.echo(f"BLOCKED: {current} → {target_phase}")
        click.echo(f"  Reason: {result.reason}")
        sys.exit(1)

    if dry_run:
        click.echo(f"DRY-RUN: {current} → {target_phase} — guard passed")
        return

    try:
        with sf.locked_update() as data:
            data["phase"] = target_phase
            transitions = data.setdefault("phase_transitions", [])
            transitions.append(
                {
                    "from": current,
                    "to": target_phase,
                    "at": now_utc_iso(),
                }
            )
    except StateFileError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        sys.exit(2)

    click.echo(f"Advanced: {current} → {target_phase}")
