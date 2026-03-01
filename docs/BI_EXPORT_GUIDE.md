# BI Export Guide (Power BI / Tableau / Oracle Analytics)

Phase 2 adds canonical dataset exports and semantic packs.

## Generate BI exports via CLI

```bash
python scripts/ask_agent.py --question "prepare bi export for power bi" --with-bi-exports --format json
```

Outputs are saved under:

- `artifacts/bi_exports/`
  - `sales_monthly.csv`
  - `region_performance.csv`
  - `product_margin.csv`
  - `forecast_output.csv`
  - `manifest.json`

- `specs/bi/`
  - `kpi_dictionary.json`
  - `relationship_map.json`
  - `visual_mapping.json`
  - `powerbi_model_notes.json`
  - `tableau_workbook_template.json`
  - `oac_semantic_mapping.json`

## API endpoint

```text
/ask_with_bi_exports?q=prepare%20bi%20exports&fmt=csv
```

## Tool consumption notes

- **Power BI**: import CSVs and apply `powerbi_model_notes.json` measures.
- **Tableau**: use CSVs as data sources and worksheet template mapping.
- **Oracle Analytics**: use dataset contracts and semantic mapping stub.
