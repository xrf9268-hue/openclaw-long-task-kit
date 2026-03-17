# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `ltk github issue create` / `ltk github comment create` — GitHub API client with `--dry-run` mode
- `ltk report issue` — generate Markdown issue reports from task state
- Fake openclaw binary builder for contract testing
- CronClient/OpenClawClient JSON shape contract tests
- Version tags in HEARTBEAT/BOOT/AGENTS injection blocks
- Unified diagnostics event model (DiagnosticEvent, CheckResult)
- Configurable text sanitization for paths, tokens, URLs
- CI security hardening (SHA-pinned actions, CodeQL, pip-audit)
- Automated release workflow (tag-triggered GitHub Releases)

### Fixed
- Terminal status false alarm in progression stall detection

### Changed
- `ltk init` — bootstrap task state and workspace control files
- `ltk preflight` — pre-execution validation suite
- `ltk status` — task status with deadman, continuation, and exhaustion policies
- `ltk resume` — refresh bootstrap files and surface policy results
- `ltk doctor` — upstream doctor plus local runtime checks
- `ltk close` — remove cron jobs and heartbeat entries
- `ltk lock` — acquire, renew, or release task control lock
- `ltk logs` — tail gateway logs and record wrapper diagnostics
- `ltk memory` — append notes or list daily memory files
- `ltk notify` — render task summaries or Telegram preview payloads
- `ltk pointer` — manage active task pointer JSON file
- `ltk heartbeat` — print, validate, or upsert heartbeat config helpers
- `ltk watchdog` — manage watchdog cron jobs
- `ltk webhooks` — print config, validate hooks, render payload/curl previews
- Continuation, deadman, and exhaustion policy engines
- Cron matrix generators (watchdog, continuation, deadman, closure-check)
- Workspace bootstrap generators (HEARTBEAT.md, BOOT.md, AGENTS.md, MEMORY.md)
- Local JSONL diagnostics logging

## [0.1.0] - 2026-03-13

### Added
- Initial release with core CLI commands and state management.
