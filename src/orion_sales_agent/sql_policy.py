"""Centralized SQL safety policy for read-only query validation."""

from __future__ import annotations

import re
import sqlite3

ALLOWED_PREFIXES = ("select", "with")
FROM_JOIN_OBJECT_RE = re.compile(
    r'\b(?:from|join)\s+((?:[a-z_][a-z0-9_]*\.)?[a-z_][a-z0-9_]*|"[^"]+")',
    flags=re.IGNORECASE,
)
CTE_NAME_RE = re.compile(r"(?:\bwith\s+|,\s*)([a-z_][a-z0-9_]*)\s+as\s*\(", flags=re.IGNORECASE)


def validate_single_statement(query: str) -> str:
    """Ensure SQL contains exactly one non-empty statement."""
    cleaned = query.strip().rstrip(";")
    if not cleaned:
        raise ValueError("Query cannot be empty")
    if ";" in cleaned:
        raise ValueError("Multi-statement SQL is not allowed")
    return cleaned


def extract_referenced_objects(query: str) -> set[str]:
    """Extract referenced table/view names from FROM/JOIN clauses.

    Notes:
        - Supports optional schema-qualified tokens (keeps object name segment).
        - Excludes CTE names defined in the same statement.
        - Handles quoted identifiers like "fact_sales".
    """

    cte_names = {m.group(1).lower() for m in CTE_NAME_RE.finditer(query)}
    refs: set[str] = set()
    for match in FROM_JOIN_OBJECT_RE.finditer(query):
        raw = match.group(1).strip().strip('"')
        name = raw.split(".")[-1].lower()
        if name and name not in cte_names:
            refs.add(name)
    return refs


def validate_readonly_select(query: str, allowed_objects: set[str]) -> str:
    """Validate query against read-only and allowlist constraints.

    Returns cleaned SQL when valid; raises ValueError otherwise.
    """
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
