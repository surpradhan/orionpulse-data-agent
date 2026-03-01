from __future__ import annotations

from pathlib import Path


def main() -> None:
    required = [
        "requirements.txt",
        "sql/schema.sql",
        "sql/views.sql",
        "mcp_server/server.py",
        "skills/business_context.md",
    ]
    missing = [p for p in required if not Path(p).exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")
    print("Preflight OK: core files present.")


if __name__ == "__main__":
    main()
