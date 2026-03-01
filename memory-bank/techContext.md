# Technical Context

- Language/runtime: Python 3.13
- Core libs:
  - FastAPI, Uvicorn
  - pandas, numpy, statsmodels
  - matplotlib, seaborn
  - mcp
- Data store: SQLite (`data/orion_sales_agent.db`)
- Key modules:
  - `src/orion_sales_agent/agent.py`
  - `src/orion_sales_agent/webapp.py`
  - `src/orion_sales_agent/analytics.py`
  - `src/orion_sales_agent/sql_policy.py`
  - `mcp_server/server.py`
- Testing:
  - `pytest`
  - critical-path tests in `tests/test_critical_paths.py`