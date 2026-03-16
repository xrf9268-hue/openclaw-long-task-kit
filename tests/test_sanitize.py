"""Tests for the sanitization utility module."""

from __future__ import annotations

from openclaw_ltk.sanitize import SanitizeConfig, sanitize


class TestRedactHomePaths:
    def test_linux_home_path(self) -> None:
        text = "Error at /home/yvan/projects/ltk/state.json"
        result = sanitize(text)
        assert "/home/yvan" not in result
        assert "~/projects/ltk/state.json" in result

    def test_macos_users_path(self) -> None:
        text = "Config: /Users/alice/developer/openclaw/config.json"
        result = sanitize(text)
        assert "/Users/alice" not in result
        assert "~/developer/openclaw/config.json" in result

    def test_multiple_paths(self) -> None:
        text = "src: /home/bob/a.py dest: /home/bob/b.py"
        result = sanitize(text)
        assert "/home/bob" not in result
        assert "~/a.py" in result
        assert "~/b.py" in result

    def test_preserves_non_home_paths(self) -> None:
        text = "Binary at /usr/local/bin/openclaw"
        result = sanitize(text)
        assert text == result

    def test_disabled(self) -> None:
        cfg = SanitizeConfig(redact_home_paths=False)
        text = "/home/yvan/secret"
        result = sanitize(text, cfg)
        assert result == text


class TestRedactTokens:
    def test_bearer_token(self) -> None:
        text = "Authorization: Bearer sk-ant-api03-abc123xyz"
        result = sanitize(text)
        assert "sk-ant-api03-abc123xyz" not in result
        assert "Bearer" in result

    def test_github_pat(self) -> None:
        text = "token: ghp_1234567890abcdef"
        result = sanitize(text)
        assert "ghp_1234567890abcdef" not in result

    def test_env_var_assignment(self) -> None:
        text = "ANTHROPIC_API_KEY=sk-ant-secret123"
        result = sanitize(text)
        assert "sk-ant-secret123" not in result
        assert "ANTHROPIC_API_KEY=" in result

    def test_key_value_with_colon(self) -> None:
        text = 'api_key: "my-super-secret-key"'
        result = sanitize(text)
        assert "my-super-secret-key" not in result

    def test_preserves_normal_text(self) -> None:
        text = "Task status is active, phase is research"
        result = sanitize(text)
        assert result == text

    def test_disabled(self) -> None:
        cfg = SanitizeConfig(redact_tokens=False)
        text = "Bearer sk-secret"
        result = sanitize(text, cfg)
        assert result == text


class TestRedactUrlCredentials:
    def test_http_basic_auth(self) -> None:
        text = "endpoint: https://admin:p4ssw0rd@api.example.com/v1"
        result = sanitize(text)
        assert "admin:p4ssw0rd" not in result
        assert "api.example.com/v1" in result

    def test_preserves_url_without_credentials(self) -> None:
        text = "endpoint: https://api.example.com/v1"
        result = sanitize(text)
        assert result == text

    def test_disabled(self) -> None:
        cfg = SanitizeConfig(redact_url_credentials=False)
        text = "https://user:pass@host.com"
        result = sanitize(text, cfg)
        assert result == text


class TestSanitizeComposite:
    def test_all_rules_applied(self) -> None:
        text = (
            "Error at /home/yvan/ltk/state.json\n"
            "Authorization: Bearer sk-ant-secret\n"
            "Proxy: https://user:pass@proxy.internal:8080/path"
        )
        result = sanitize(text)
        assert "/home/yvan" not in result
        assert "sk-ant-secret" not in result
        assert "user:pass" not in result

    def test_all_disabled(self) -> None:
        cfg = SanitizeConfig(
            redact_home_paths=False,
            redact_tokens=False,
            redact_url_credentials=False,
        )
        text = "/home/yvan Bearer sk-secret https://u:p@h.com"
        result = sanitize(text, cfg)
        assert result == text

    def test_sanitize_dict_values(self) -> None:
        """sanitize() works on any string, callers handle dict traversal."""
        data = {"error": "/home/yvan/secret/file.py", "status": "ok"}
        sanitized = {k: sanitize(v) for k, v in data.items()}
        assert "/home/yvan" not in sanitized["error"]
        assert sanitized["status"] == "ok"
