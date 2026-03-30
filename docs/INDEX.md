# Documentation Index

This index defines **ownership**, **purpose**, and **update cadence** for every retained document in `docs/`.

> Owner labels are role-based to keep this practical across contributors.

## Ownership roles

- **Product/Engineering Lead**: roadmap, strategy, execution-policy decisions
- **Backend/API Engineer**: contracts, endpoints, auth/policy behavior
- **Data/Analytics Engineer**: KPI definitions, exports, forecasting/anomaly semantics
- **QA/Release Engineer**: test plans, runbooks, validation procedures

## Document registry

| Document | Primary owner | Purpose | Update cadence |
|---|---|---|---|
| `docs/ANALYTICS_EXPORT_GUIDE.md` | Data/Analytics Engineer | How to generate and consume analytics export artifacts and semantic packs | On export schema/format/tooling changes |
| `docs/API_REFERENCE.md` | Backend/API Engineer | Endpoint-by-endpoint contract: auth, parameters, request/response shapes, MCP tool list | On any endpoint, auth, or contract changes |
| `docs/CHANNEL_ERROR_CONTRACTS.md` | Backend/API Engineer | Defines web-vs-MCP error semantics and client mapping guidance | On any contract/error handling changes |
| `docs/DATA_MODEL_AND_KPIS.md` | Data/Analytics Engineer | Canonical table model, joins, and KPI formula references | On schema/KPI formula changes |
| `docs/ENGINEERING_EXECUTION_MODE_POLICY.md` | Product/Engineering Lead | Channel-specific orchestration mode policy and guardrails | On mode defaults/policy or endpoint behavior changes |
| `docs/FORECAST_METHODOLOGY.md` | Data/Analytics Engineer | Model selection logic, candidate methods, diagnostics interpretation, known limitations | On changes to forecast candidates, selection strategy, or CI construction |
| `docs/IMPLEMENTATION_ROADMAP.md` | Product/Engineering Lead | Phase-oriented implementation roadmap with shipped/planned/idea items | Milestone-level updates or when superseded by master planning |
| `docs/INTERACTION_MODES.md` | Backend/API Engineer | Practical usage guidance across MCP, CLI, and Web/API channels | On channel UX/workflow changes |
| `docs/MASTER_PLAN.md` | Product/Engineering Lead | Canonical high-level architecture + consolidated roadmap | At major release planning boundaries |
| `docs/MCP_RESPONSE_CONTRACT_DECISION.md` | Backend/API Engineer | Decision record for MCP response contract strategy and versioning path | Only when contract strategy is reconsidered |
| `docs/OPERATIONS_RUNBOOK.md` | QA/Release Engineer | Environment setup, startup, diagnostics, and operational troubleshooting | On operational workflow/env var changes |
| `docs/prompt_templates.md` | Product/Engineering Lead | Reusable structured prompt patterns for consistent outputs | On prompt strategy updates |
| `docs/TECHNICAL_REVIEW_2026-03-01.md` | Product/Engineering Lead | Point-in-time technical review findings and recommendations | Immutable historical snapshot; add new dated file for future reviews |
| `docs/UI_REALTIME_TEST_CASES.md` | QA/Release Engineer | Real-time UI/API validation scenarios and evidence expectations | On auth/contract/test-scope changes |
| `docs/VISUALIZATION_GUIDE.md` | Backend/API Engineer | Chart types, output formats, artifact layout, and programmatic usage | On changes to chart types, output paths, or visualization API |
| `docs/INDEX.md` | Product/Engineering Lead | This governance index for ownership + purpose + cadence | Review monthly or when docs are added/removed |

## Governance rules

1. **No orphan docs**: any new `docs/*.md` must be added to this index.
2. **No silent contract drift**: if endpoints/contracts/auth change, update relevant docs in the same PR.
3. **Keep strategy singular**: avoid duplicate roadmap docs; prefer `MASTER_PLAN.md` as canonical unless a new ADR/review requires a separate artifact.
4. **Preserve history intentionally**: keep dated review/decision docs immutable; add new dated docs instead of overwriting historical context.
