from __future__ import annotations

import re
import sqlite3

ALLOWED_PREFIXES = ("select", "with")


def validate_single_statement(query: str) -> str:
    cleaned = query.strip().rstrip(";")
    if not cleaned:
        raise ValueError("Query cannot be empty")
    if ";" in cleaned:
        raise ValueError("Multi-statement SQL is not allowed")
    return cleaned


def extract_referenced_objects(query: str) -> set[str]:
    q = query.lower()
    return set(re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", q))


def validate_readonly_select(query: str, allowed_objects: set[str]) -> str:
    cleaned = validate_single_statement(query)
    q = cleaned.lower()
    if not q.startswith(ALLOWED_PREFIXES):
        raise ValueError("Only SELECT/CTE queries are allowed")

    forbidden_tokens = (
        " pragma ",
        " attach ",
        " detach ",
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " create ",
        " truncate ",
        " replace ",
    )
    padded = f" {q} "
    if any(tok in padded for tok in forbidden_tokens):
        raise ValueError("Disallowed SQL token detected")

    refs = extract_referenced_objects(cleaned)
    if not refs:
        raise ValueError("Query must reference at least one allowed table/view")
    bad = refs - allowed_objects
    if bad:
        raise ValueError(f"Query references disallowed objects: {sorted(bad)}")
    return cleaned


def validate_with_sqlite_parser(conn: sqlite3.Connection, query: str) -> None:
    """Parser-backed validation through SQLite compile step."""
    try:
        conn.execute(f"EXPLAIN QUERY PLAN {query}")
    except sqlite3.Error as exc:
        raise ValueError(f"SQL failed parser validation: {exc}") from exc
