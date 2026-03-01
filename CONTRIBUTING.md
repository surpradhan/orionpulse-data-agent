# Contributing to OrionPulse Data Agent

Thanks for your interest in contributing.

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

## Quality checks

Before opening a PR, run:

```bash
python scripts/preflight.py
pytest
```

## Branching and PRs

- Create a feature branch from `main`.
- Keep PRs focused and small.
- Include a clear summary, testing notes, and any security implications.

## Security-sensitive changes

If your change touches auth, SQL policy, exports, or secrets handling, call that out explicitly in the PR description.
