from __future__ import annotations

import pytest

from src.orion_sales_agent.sql_policy import (
    extract_referenced_objects,
    validate_readonly_select,
    validate_single_statement,
)

ALLOWED = {
    "fact_sales",
    "dim_product",
    "dim_region",
    "vw_region_performance",
    "vw_product_margin_rank",
}


# ---------------------------------------------------------------------------
# existing tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# validate_single_statement
# ---------------------------------------------------------------------------


def test_single_statement_strips_trailing_semicolon() -> None:
    assert validate_single_statement("SELECT 1;") == "SELECT 1"


def test_single_statement_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_single_statement("   ")


def test_single_statement_rejects_multi_statement() -> None:
    with pytest.raises(ValueError, match="Multi-statement"):
        validate_single_statement("SELECT 1; SELECT 2")


# ---------------------------------------------------------------------------
# nested subqueries
# ---------------------------------------------------------------------------


def test_nested_subquery_in_where_allowed_objects() -> None:
    query = (
        "SELECT * FROM fact_sales "
        "WHERE product_id IN (SELECT product_id FROM dim_product WHERE active = 1)"
    )
    refs = extract_referenced_objects(query)
    assert "fact_sales" in refs
    assert "dim_product" in refs


def test_nested_subquery_in_from_clause() -> None:
    query = (
        "SELECT sub.total FROM "
        "(SELECT product_id, SUM(net_revenue) AS total FROM fact_sales GROUP BY product_id) sub"
    )
    refs = extract_referenced_objects(query)
    assert "fact_sales" in refs


def test_nested_subquery_blocked_when_inner_object_disallowed() -> None:
    query = (
        "SELECT * FROM fact_sales WHERE region_id = "
        "(SELECT id FROM hidden_table WHERE name = 'APAC')"
    )
    with pytest.raises(ValueError):
        validate_readonly_select(query, ALLOWED)


def test_deeply_nested_subquery_all_allowed() -> None:
    query = (
        "SELECT * FROM fact_sales WHERE product_id IN "
        "(SELECT product_id FROM dim_product WHERE category IN "
        "(SELECT category FROM dim_product WHERE active = 1))"
    )
    result = validate_readonly_select(query, ALLOWED)
    assert result is not None


# ---------------------------------------------------------------------------
# multi-level CTEs
# ---------------------------------------------------------------------------


def test_multi_cte_names_excluded_from_refs() -> None:
    query = """
    WITH base AS (
        SELECT * FROM fact_sales
    ),
    enriched AS (
        SELECT b.*, p.product_name FROM base b JOIN dim_product p ON b.product_id = p.product_id
    )
    SELECT * FROM enriched
    """
    refs = extract_referenced_objects(query)
    assert "fact_sales" in refs
    assert "dim_product" in refs
    assert "base" not in refs
    assert "enriched" not in refs


def test_multi_cte_validate_passes_with_allowed_objects() -> None:
    query = """
    WITH regional AS (
        SELECT region_id, SUM(net_revenue) AS rev FROM fact_sales GROUP BY region_id
    ),
    ranked AS (
        SELECT r.region_id, r.rev, dr.region_name
        FROM regional r JOIN dim_region dr ON r.region_id = dr.region_id
    )
    SELECT * FROM ranked ORDER BY rev DESC
    """
    result = validate_readonly_select(query, ALLOWED)
    assert result is not None


def test_cte_referencing_disallowed_base_table_blocked() -> None:
    query = """
    WITH leaky AS (
        SELECT * FROM private_data
    )
    SELECT * FROM leaky JOIN fact_sales ON leaky.id = fact_sales.product_id
    """
    with pytest.raises(ValueError):
        validate_readonly_select(query, ALLOWED)


# ---------------------------------------------------------------------------
# complex JOINs
# ---------------------------------------------------------------------------


def test_multiple_join_types_extract_correctly() -> None:
    query = """
    SELECT f.*, p.product_name, r.region_name
    FROM fact_sales f
    LEFT JOIN dim_product p ON f.product_id = p.product_id
    INNER JOIN dim_region r ON f.region_id = r.region_id
    """
    refs = extract_referenced_objects(query)
    assert refs == {"fact_sales", "dim_product", "dim_region"}


def test_self_join_same_table_counts_once() -> None:
    query = (
        "SELECT a.period, b.period FROM fact_sales a "
        "JOIN fact_sales b ON a.product_id = b.product_id AND a.period < b.period"
    )
    refs = extract_referenced_objects(query)
    assert refs == {"fact_sales"}


def test_cross_join_objects_extracted() -> None:
    query = "SELECT * FROM dim_product CROSS JOIN dim_region"
    refs = extract_referenced_objects(query)
    assert refs == {"dim_product", "dim_region"}


def test_four_way_join_all_allowed_passes() -> None:
    query = """
    SELECT f.net_revenue, p.product_name, r.region_name
    FROM fact_sales f
    JOIN dim_product p ON f.product_id = p.product_id
    JOIN dim_region r ON f.region_id = r.region_id
    JOIN vw_region_performance vp ON vp.region_id = r.region_id
    """
    result = validate_readonly_select(query, ALLOWED)
    assert result is not None


def test_join_with_one_disallowed_table_blocked() -> None:
    query = (
        "SELECT * FROM fact_sales f "
        "JOIN dim_product p ON f.product_id = p.product_id "
        "JOIN user_credentials uc ON uc.id = f.user_id"
    )
    with pytest.raises(ValueError, match="disallowed"):
        validate_readonly_select(query, ALLOWED)


# ---------------------------------------------------------------------------
# forbidden token checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "INSERT INTO fact_sales VALUES (1,2,3)",
        "UPDATE fact_sales SET net_revenue = 0",
        "DELETE FROM fact_sales",
        "DROP TABLE fact_sales",
        "ALTER TABLE fact_sales ADD COLUMN x INT",
        "CREATE TABLE evil AS SELECT * FROM fact_sales",
        "TRUNCATE fact_sales",
        "REPLACE INTO fact_sales VALUES (1,2,3)",
        "SELECT * FROM fact_sales; ATTACH DATABASE '/tmp/x' AS x",
    ],
)
def test_forbidden_tokens_rejected(token: str) -> None:
    with pytest.raises(ValueError):
        validate_readonly_select(token, ALLOWED)


def test_pragma_blocked() -> None:
    with pytest.raises(ValueError):
        validate_readonly_select("SELECT * FROM fact_sales WHERE 1=1 PRAGMA journal_mode", ALLOWED)


# ---------------------------------------------------------------------------
# allowlist boundary cases
# ---------------------------------------------------------------------------


def test_query_with_no_from_clause_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        validate_readonly_select("SELECT 1 + 1", ALLOWED)


def test_view_name_in_allowlist_passes() -> None:
    query = "SELECT * FROM vw_region_performance"
    result = validate_readonly_select(query, ALLOWED)
    assert "vw_region_performance" in result


def test_case_insensitive_table_matching() -> None:
    query = (
        "SELECT * FROM FACT_SALES JOIN DIM_PRODUCT "
        "ON FACT_SALES.product_id = DIM_PRODUCT.product_id"
    )
    refs = extract_referenced_objects(query)
    assert "fact_sales" in refs
    assert "dim_product" in refs
