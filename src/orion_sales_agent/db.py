from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(db_path: str, sql: str, params: tuple[Any, ...] = ()):
    import pandas as pd

    with get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute_script(db_path: str, script: str) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(script)
        conn.commit()
