# Contributing to OrionPulse Data Agent

Thanks for your interest in contributing.

This project values small, testable changes with clear documentation and explicit security posture notes.

## Development setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize local database if needed:

```bash
python data/init_db.py
```

4. Apply SQL views:

```bash
python -c "from src.orion_sales_agent.views import apply_views; from src.orion_sales_agent.config import settings; apply_views(settings.db_path)"
```

## Quality checks

Before opening a PR, run:

```bash
python scripts/preflight.py
pytest
```

If you touch typing/lint-sensitive areas, also run:

```bash
python -m mypy src
python -m ruff check src tests
```

## Branching and PRs

- Create a feature branch from `main`.
- Keep PRs focused and small.
- Include a clear summary, testing notes, and any security implications.
- Reference impacted docs when behavior/contracts change.
- Prefer additive, backward-compatible API/MCP contract updates.

## Security-sensitive changes

If your change touches auth, SQL policy, exports, or secrets handling, call that out explicitly in the PR description.

## Documentation expectations

- Update `README.md` if setup, mode policy, or endpoint behavior changes.
- Update relevant `docs/*.md` for contract/policy/operational changes.
- For significant implementation decisions, update `memory-bank/activeContext.md` and `memory-bank/progress.md`.

## Testing expectations by area

- Web/API contract changes: update/add tests in `tests/test_web_contracts_performance.py` and related suites.
- SQL policy or access control changes: update/add `tests/test_sql_policy_edge_cases.py` and auth/profile tests.
- Forecast/analytics changes: update/add forecast quality and critical-path tests.
