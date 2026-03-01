# MCP Response Contract Decision

## Decision
- Keep **MCP tool outputs as raw tool contracts** (no API envelope wrapper).

## Rationale
- MCP consumers currently depend on direct tool-shaped payloads (lists/dicts specific to each tool).
- Wrapping MCP responses in HTTP-style envelope fields (`status`, `trace_id`, `timestamp`) would be a breaking change for existing MCP integrations.
- The web API and MCP serve different interface goals:
  - Web API: stable HTTP contract with provenance metadata and standard envelope.
  - MCP tools: low-friction programmatic primitives with explicit, tool-specific schemas.

## Guardrails
- Keep tool docstrings/contracts explicit and test-backed in `tests/test_mcp_integration.py`.
- If envelope parity is needed later, add it via **new versioned tools** (e.g., `*_v2`) rather than mutating existing tool outputs.
- Continue surfacing execution provenance in web/CLI channels where envelope standardization is already established.

## Follow-up
- Revisit only if a downstream MCP client requests standardized envelope semantics across all tools.
