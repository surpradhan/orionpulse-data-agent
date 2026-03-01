# Security Policy

## Reporting a vulnerability

Please do not open public issues for sensitive vulnerabilities.

- Preferred: report privately to the repository owner via GitHub Security Advisories.
- Include reproduction steps, impact, and affected components.

## Supported versions

At this stage, only the latest `main` branch is considered actively supported.

## Security expectations

- Never commit secrets (tokens, keys, credentials).
- Keep `.env` and local export artifacts out of version control.
- Follow SQL safety controls in `src/orion_sales_agent/sql_policy.py`.
