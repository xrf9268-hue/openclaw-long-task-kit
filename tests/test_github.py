"""Tests for GitHub API client module."""

from __future__ import annotations

import json
from http.client import HTTPResponse
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError as UrllibHTTPError

import pytest

from openclaw_ltk.errors import LtkError
from openclaw_ltk.github import GitHubClient, GitHubError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(body: dict[str, Any] | list[Any], status: int = 200) -> HTTPResponse:
    """Build a fake HTTPResponse with JSON body."""
    raw = json.dumps(body).encode()
    resp = MagicMock(spec=HTTPResponse)
    resp.status = status
    resp.read.return_value = raw
    resp.headers = {"Content-Type": "application/json"}
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# GitHubError hierarchy
# ---------------------------------------------------------------------------


class TestGitHubError:
    def test_is_ltk_error(self) -> None:
        assert issubclass(GitHubError, LtkError)


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_requires_token(self) -> None:
        """Client without token must raise GitHubError."""
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(GitHubError, match="GITHUB_TOKEN"),
        ):
            GitHubClient()

    def test_token_from_env(self) -> None:
        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"}):
            client = GitHubClient()
        assert client.token == "ghp_test123"

    def test_explicit_token(self) -> None:
        client = GitHubClient(token="ghp_explicit")
        assert client.token == "ghp_explicit"

    def test_custom_base_url(self) -> None:
        client = GitHubClient(token="t", base_url="https://api.github.example.com")
        assert client.base_url == "https://api.github.example.com"


# ---------------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------------


class TestCreateIssue:
    def test_creates_issue(self) -> None:
        client = GitHubClient(token="ghp_test")
        resp_body = {
            "number": 42,
            "html_url": "https://github.com/o/r/issues/42",
        }
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_body)):
            result = client.create_issue("o/r", title="Bug", body="desc")
        assert result["number"] == 42

    def test_dry_run_returns_preview(self) -> None:
        client = GitHubClient(token="ghp_test", dry_run=True)
        result = client.create_issue("o/r", title="Bug", body="desc", labels=["bug"])
        assert result["dry_run"] is True
        assert result["title"] == "Bug"
        assert result["labels"] == ["bug"]

    def test_auth_failure_raises(self) -> None:
        client = GitHubClient(token="ghp_bad")
        err = UrllibHTTPError(
            "https://api.github.com/repos/o/r/issues",
            401,
            "Unauthorized",
            {},  # type: ignore[arg-type]
            BytesIO(json.dumps({"message": "Bad credentials"}).encode()),
        )
        with (
            patch("urllib.request.urlopen", side_effect=err),
            pytest.raises(GitHubError, match="401"),
        ):
            client.create_issue("o/r", title="Bug")

    def test_rate_limit_raises(self) -> None:
        client = GitHubClient(token="ghp_test")
        err = UrllibHTTPError(
            "https://api.github.com/repos/o/r/issues",
            403,
            "Forbidden",
            {},  # type: ignore[arg-type]
            BytesIO(json.dumps({"message": "API rate limit exceeded"}).encode()),
        )
        with (
            patch("urllib.request.urlopen", side_effect=err),
            pytest.raises(GitHubError, match="rate limit"),
        ):
            client.create_issue("o/r", title="Bug")


# ---------------------------------------------------------------------------
# create_comment
# ---------------------------------------------------------------------------


class TestCreateComment:
    def test_creates_comment(self) -> None:
        client = GitHubClient(token="ghp_test")
        resp_body = {
            "id": 999,
            "html_url": "https://github.com/o/r/issues/1#issuecomment-999",
        }
        with patch("urllib.request.urlopen", return_value=_mock_response(resp_body)):
            result = client.create_comment("o/r", issue_number=1, body="hi")
        assert result["id"] == 999

    def test_dry_run_returns_preview(self) -> None:
        client = GitHubClient(token="ghp_test", dry_run=True)
        result = client.create_comment("o/r", issue_number=1, body="hi")
        assert result["dry_run"] is True
        assert result["issue_number"] == 1
        assert result["body"] == "hi"

    def test_not_found_raises(self) -> None:
        client = GitHubClient(token="ghp_test")
        err = UrllibHTTPError(
            "https://api.github.com/repos/o/r/issues/999/comments",
            404,
            "Not Found",
            {},  # type: ignore[arg-type]
            BytesIO(json.dumps({"message": "Not Found"}).encode()),
        )
        with (
            patch("urllib.request.urlopen", side_effect=err),
            pytest.raises(GitHubError, match="404"),
        ):
            client.create_comment("o/r", issue_number=999, body="hi")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestGitHubCli:
    def test_issue_create_dry_run(self) -> None:
        from click.testing import CliRunner

        from openclaw_ltk.commands.github import github_cmd

        runner = CliRunner()
        result = runner.invoke(
            github_cmd,
            [
                "issue",
                "create",
                "--repo",
                "o/r",
                "--title",
                "Bug",
                "--dry-run",
            ],
            env={"GITHUB_TOKEN": "ghp_test"},
        )
        assert result.exit_code == 0
        assert "dry_run" in result.output or "DRY RUN" in result.output

    def test_comment_create_dry_run(self) -> None:
        from click.testing import CliRunner

        from openclaw_ltk.commands.github import github_cmd

        runner = CliRunner()
        result = runner.invoke(
            github_cmd,
            [
                "comment",
                "create",
                "--repo",
                "o/r",
                "--issue",
                "1",
                "--body",
                "hello",
                "--dry-run",
            ],
            env={"GITHUB_TOKEN": "ghp_test"},
        )
        assert result.exit_code == 0
        assert "dry_run" in result.output or "DRY RUN" in result.output

    def test_missing_token_exits_error(self) -> None:
        from click.testing import CliRunner

        from openclaw_ltk.commands.github import github_cmd

        runner = CliRunner()
        result = runner.invoke(
            github_cmd,
            [
                "issue",
                "create",
                "--repo",
                "o/r",
                "--title",
                "Bug",
            ],
            env={},
        )
        assert result.exit_code != 0
