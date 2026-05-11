# Changelog

## 0.1.0

- Initial beta package for the Ophanix Tool Gateway Python SDK.
- Provides synchronous and asynchronous clients, environment and static token
  providers, typed result objects, discovery pagination, bounded discovery
  retries, strict payload validation, and safe-by-default HTTPS handling.
- Adds SDK-specific validation errors, early rejection of `Bearer `-prefixed
  token values, deterministic closed-client errors, process-local HMAC cache
  partitioning, sanitized lookup errors, and optional strict telemetry-hook
  failure mode.
- Requires streaming support for custom injected HTTP clients by default so
  response-size caps apply before body materialization.
- Documents the beta compatibility matrix, `list_tools(status=...)`
  deprecation, and standalone `ophanix_tool_gateway` import path.
