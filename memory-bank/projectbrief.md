# Project Brief

- Project: OrionPulse Data Agent (MCP + SQLite + FastAPI UI)
- Purpose: Answer business analytics questions over sales data, generate charts, export BI packs, and support deeper reasoning/prediction.
- Core capabilities:
  - Query + KPI + anomaly + forecast analytics
  - Agent orchestration (rule-based + optional LLM planner/tool/critique loop)
  - Dashboard/storyboard specs
  - Visualization generation (Seaborn/Matplotlib)
  - BI exports (Power BI/Tableau/OAC-oriented semantic packs)
  - Voice-enabled web chat UI (browser STT/TTS)
- Security baseline now includes token-based role controls for web endpoints (analyst/admin) when tokens are configured.