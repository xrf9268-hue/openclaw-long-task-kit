# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in openclaw-long-task-kit, please
report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email the maintainer at the address listed in `pyproject.toml`, or use
   GitHub's private vulnerability reporting feature on this repository.
3. Include a clear description of the vulnerability, steps to reproduce, and
   any potential impact.

We aim to acknowledge reports within 48 hours and to provide a fix or
mitigation within 7 days for confirmed issues.

## Scope

This policy covers the `openclaw-long-task-kit` Python package and its
direct dependencies.  Issues in the upstream OpenClaw runtime or gateway
should be reported to the OpenClaw project directly.

## Known Limitations

- **`fcntl` file locking** is not enforced across NFS clients.  See the
  platform support section in `README.md` for details.
- State files and diagnostics logs are stored as plain-text JSON on disk.
  Protect the workspace directory with appropriate filesystem permissions.
