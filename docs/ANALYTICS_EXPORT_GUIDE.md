# Analytics Export Guide

Phase 2 adds canonical dataset exports and semantic packs.

## Generate Analytics Exports via CLI

```bash
python scripts/ask_agent.py --question "prepare analytics exports" --with-analytics-exports --format json
```

Outputs are saved under:

- `artifacts/analytics_exports/`
  - `sales_monthly.csv`
  - `region_performance.csv`
  - `product_margin.csv`
  - `forecast_output.csv`
  - `manifest.json`

- `specs/analytics_exports/`
  - `kpi_dictionary.json`
  - `relationship_map.json`
  - `visual_mapping.json`
  - `powerbi_model_notes.json`
  - `tableau_workbook_template.json`
  - `oac_semantic_mapping.json`

## API endpoint

```text
/ask_with_analytics_exports?q=prepare%20analytics%20exports&fmt=csv
```

## Tool consumption notes

- Use generated CSV/Parquet datasets with your target analytics platform.
- Use semantic-pack JSON files as mapping stubs for downstream model configuration.
