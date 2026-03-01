# System Patterns

- Agent orchestration pattern:
  - Rule-based routing fallback is always available.
  - Optional LLM planner/tool/critique/synthesis loop for dynamic reasoning.
  - Trace artifacts capture execution phases and fallback reasons.

- Security pattern:
  - Role-based token gate at API edge (`x-orion-token`).
  - Analyst vs admin separation for read/compute vs export-sensitive routes.

- Data access pattern:
  - SQL policy module centralizes statement validation, allowlisting, and parser-backed checks.
  - MCP tools call vetted query paths with readonly constraints.
  - MCP response contract remains raw tool-shaped payloads (no HTTP-style envelope), with compatibility preserved via versioned-tool strategy for future contract evolution.

- Analytics pattern:
  - Forecast API returns both point estimates and interval bounds.
  - Visual layer consumes analytics contracts directly for chart confidence bands.