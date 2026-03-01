# Security Policy

## Reporting a vulnerability

Please do not open public issues for sensitive vulnerabilities.

- Preferred: report privately to the repository owner via GitHub Security Advisories.
- Include reproduction steps, impact, and affected components.

Please include, where possible:
- affected endpoint/tool name
- required auth role (`analyst`/`admin`) and whether bypass is possible
- data exposure or integrity impact
- suggested remediation or temporary mitigation

## Supported versions

At this stage, only the latest `main` branch is considered actively supported.

## Security expectations

- Never commit secrets (tokens, keys, credentials).
- Keep `.env` and local export artifacts out of version control.
- Follow SQL safety controls in `src/orion_sales_agent/sql_policy.py`.

## Runtime hardening baseline

- Prefer `ORION_AUTH_PROFILE=PROD_STRICT` for production-like deployments.
- Ensure `ORION_ANALYST_TOKEN` and `ORION_ADMIN_TOKEN` are set when auth is required.
- Startup should fail fast if required auth config is incomplete.
- Keep MCP SQL usage readonly and allowlist-constrained.

## Secure development checklist

- Validate role gates for changed endpoints/tools.
- Verify contract-safe error behavior (`docs/CHANNEL_ERROR_CONTRACTS.md`).
- Re-run security-sensitive tests before merge.
- Document any behavior change that could affect downstream clients.
