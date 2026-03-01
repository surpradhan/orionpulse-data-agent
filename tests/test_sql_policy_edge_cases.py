from __future__ import annotations

import pytest

from src.orion_sales_agent.sql_policy import extract_referenced_objects, validate_readonly_select


def test_extract_referenced_objects_handles_cte_and_aliases() -> None:
    query = """
    WITH recent AS (
        SELECT * FROM fact_sales
    )
    SELECT r.period, p.product_name
    FROM recent r
    JOIN dim_product p ON p.product_id = r.product_id
    """
    refs = extract_referenced_objects(query)
    assert "fact_sales" in refs
    assert "dim_product" in refs
    assert "recent" not in refs


def test_extract_referenced_objects_handles_quoted_and_schema_names() -> None:
    query = 'SELECT * FROM "fact_sales" fs JOIN main.dim_region dr ON fs.region_id = dr.region_id'
    refs = extract_referenced_objects(query)
    assert refs == {"fact_sales", "dim_region"}


def test_validate_readonly_select_rejects_unknown_nested_object() -> None:
    allowed = {"fact_sales", "dim_region"}
    query = "SELECT * FROM fact_sales WHERE region_id IN (SELECT region_id FROM secret_regions)"
    with pytest.raises(ValueError):
        validate_readonly_select(query, allowed)
