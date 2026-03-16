"""Sanitization utilities for redacting sensitive data from text."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches /home/<user> or /Users/<user>
_HOME_PATH_RE = re.compile(r"/(?:home|Users)/[\w.\-]+")

# Matches Bearer <token>
_BEARER_RE = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)

# Matches known secret-like key=value or key: value patterns
_KEY_VALUE_RE = re.compile(
    r"("
    r"(?:api[_-]?key|token|secret|password|"
    r"ANTHROPIC_API_KEY|OPENAI_API_KEY|"
    r"[A-Z_]*(?:SECRET|TOKEN|KEY|PASSWORD))"
    r"[\s]*[=:]\s*)"
    r'["\']?(\S+)["\']?',
    re.IGNORECASE,
)

# Matches user:pass@ in URLs
_URL_CREDS_RE = re.compile(r"(https?://)([^@\s]+)@")


@dataclass(frozen=True)
class SanitizeConfig:
    """Configuration for which sanitization rules to apply."""

    redact_home_paths: bool = True
    redact_tokens: bool = True
    redact_url_credentials: bool = True


def sanitize(text: str, config: SanitizeConfig | None = None) -> str:
    """Apply configured sanitization rules to *text*."""
    cfg = config or SanitizeConfig()
    result = text
    if cfg.redact_tokens:
        result = _redact_tokens(result)
    if cfg.redact_url_credentials:
        result = _redact_url_credentials(result)
    if cfg.redact_home_paths:
        result = _redact_home_paths(result)
    return result


def _redact_home_paths(text: str) -> str:
    return _HOME_PATH_RE.sub("~", text)


def _redact_tokens(text: str) -> str:
    text = _BEARER_RE.sub(r"\g<1>***", text)
    text = _KEY_VALUE_RE.sub(r"\g<1>***", text)
    return text


def _redact_url_credentials(text: str) -> str:
    return _URL_CREDS_RE.sub(r"\g<1>***@", text)
