# Channel Error Contracts (Web vs MCP)

This document defines the intentional difference and mapping between web HTTP errors and MCP tool errors.

## Web channel (FastAPI)

- Transport: HTTP status + JSON body.
- Success shape: standardized envelope (`status`, `trace_id`, `timestamp`, `warnings`, `data`, optional provenance).
- Error shape:
  - AuthN failure: `401` with `detail` message.
  - AuthZ failure: `403` with `detail` message.
  - Validation failure: `422` (FastAPI/Pydantic contract errors).
  - Server error: `500`.

## MCP channel (tool invocation)

- Transport: tool return values for success, raised exceptions for failure.
- Success shape: tool-native payloads (no HTTP-like envelope).
- Error shape:
  - Invalid parameters / policy violations: `ValueError`.
  - Privilege violations: `PermissionError`.
  - Unexpected runtime failures: propagated exception.

## Cross-channel semantic mapping

| Semantic class | Web HTTP | MCP tool |
|---|---:|---|
| Unauthorized | 401 | `PermissionError` / policy `ValueError` |
| Forbidden | 403 | `PermissionError` |
| Invalid input | 422 | `ValueError` |
| Disallowed SQL/policy | 400/422/500 (depending on route handling) | `ValueError` |
| Internal failure | 500 | propagated exception |

## Client guidance

- Web clients should branch on HTTP status and parse `detail`.
- MCP clients should catch exception classes and normalize into client-side domain errors.
- For compatibility, MCP payloads remain raw tool outputs (see `docs/MCP_RESPONSE_CONTRACT_DECISION.md`).
