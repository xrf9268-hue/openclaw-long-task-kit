"""GitHub integration commands."""

from __future__ import annotations

import json

import click

from openclaw_ltk.github import GitHubClient, GitHubError


@click.group("github")
def github_cmd() -> None:
    """Interact with the GitHub API."""


# -- issue subgroup ----------------------------------------------------------


@github_cmd.group("issue")
def issue_group() -> None:
    """Issue operations."""


@issue_group.command("create")
@click.option("--repo", required=True, help="owner/repo")
@click.option("--title", required=True, help="Issue title")
@click.option("--body", default="", help="Issue body (Markdown)")
@click.option("--label", "labels", multiple=True, help="Labels (repeatable)")
@click.option("--dry-run", is_flag=True, help="Preview without submitting")
def issue_create_cmd(
    repo: str,
    title: str,
    body: str,
    labels: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Create a GitHub issue."""
    try:
        client = GitHubClient(dry_run=dry_run)
    except GitHubError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(2) from exc

    try:
        result = client.create_issue(
            repo, title=title, body=body, labels=list(labels) or None
        )
    except GitHubError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(1) from exc

    if dry_run:
        click.echo("DRY RUN — would create issue:")
    click.echo(json.dumps(result, indent=2))


# -- comment subgroup --------------------------------------------------------


@github_cmd.group("comment")
def comment_group() -> None:
    """Comment operations."""


@comment_group.command("create")
@click.option("--repo", required=True, help="owner/repo")
@click.option("--issue", "issue_number", required=True, type=int, help="Issue #")
@click.option("--body", required=True, help="Comment body")
@click.option("--dry-run", is_flag=True, help="Preview without submitting")
def comment_create_cmd(
    repo: str,
    issue_number: int,
    body: str,
    dry_run: bool,
) -> None:
    """Post a comment on a GitHub issue."""
    try:
        client = GitHubClient(dry_run=dry_run)
    except GitHubError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(2) from exc

    try:
        result = client.create_comment(repo, issue_number=issue_number, body=body)
    except GitHubError as exc:
        click.echo(f"ERROR: {exc.message}", err=True)
        raise SystemExit(1) from exc

    if dry_run:
        click.echo("DRY RUN — would create comment:")
    click.echo(json.dumps(result, indent=2))
