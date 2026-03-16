"""GitHub API client with dry-run support.

Uses stdlib ``urllib.request`` to keep dependencies minimal.
Authentication is via ``GITHUB_TOKEN`` environment variable or explicit token.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from openclaw_ltk.errors import LtkError


class GitHubError(LtkError):
    """GitHub API errors (auth, rate-limit, not-found, etc.)."""


_DEFAULT_BASE_URL = "https://api.github.com"


class GitHubClient:
    """Thin wrapper around the GitHub REST API."""

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        dry_run: bool = False,
    ) -> None:
        resolved = token or os.environ.get("GITHUB_TOKEN")
        if not resolved:
            raise GitHubError(
                message="GITHUB_TOKEN environment variable is not set "
                "and no token was provided."
            )
        self.token: str = resolved
        self.base_url: str = base_url.rstrip("/")
        self.dry_run: bool = dry_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())  # type: ignore[no-any-return]
        except urllib.error.HTTPError as exc:
            try:
                err_body = json.loads(exc.read())
                msg = err_body.get("message", "")
            except (json.JSONDecodeError, OSError):
                msg = str(exc)
            if exc.code == 403 and "rate limit" in msg:
                raise GitHubError(
                    message=f"GitHub API rate limit exceeded (403): {msg}"
                ) from exc
            raise GitHubError(message=f"GitHub API error ({exc.code}): {msg}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a GitHub issue. Returns API response or dry-run preview."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if self.dry_run:
            return {"dry_run": True, "repo": repo, **payload}
        return self._request("POST", f"/repos/{repo}/issues", body=payload)

    def create_comment(
        self,
        repo: str,
        *,
        issue_number: int,
        body: str,
    ) -> dict[str, Any]:
        """Post a comment on a GitHub issue. Returns API response or dry-run preview."""
        if self.dry_run:
            return {
                "dry_run": True,
                "repo": repo,
                "issue_number": issue_number,
                "body": body,
            }
        return self._request(
            "POST",
            f"/repos/{repo}/issues/{issue_number}/comments",
            body={"body": body},
        )
