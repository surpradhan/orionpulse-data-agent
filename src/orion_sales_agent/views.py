from __future__ import annotations

from pathlib import Path

from .db import execute_script


def apply_views(db_path: str, views_sql_path: str = "sql/views.sql") -> None:
    sql = Path(views_sql_path).read_text(encoding="utf-8")
    execute_script(db_path, sql)
