# Changelog

## 0.1.0 - 2026-05-12

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
- Adds `ToolGatewayClientConfig`, `check_compatibility()`, token length
  validation, denial-safe `tool_not_visible` lookup errors, elapsed telemetry,
  discovery retry telemetry, PII-aware diagnostic redaction, and an async worker
  example for MVP pilots.
- Adds `Idempotency-Key` support through `call_tool(..., idempotency_key=...)`
  and retries transient invocation failures only when an idempotency key is
  present.
- Release validation now writes a local CycloneDX SBOM with artifact hashes and
  records the publish-workflow provenance requirement in the release manifest.
- Compatibility probing now fails closed when gateway `min_sdk_version` is
  higher than the installed SDK version.
- Adds a payload nesting-depth cap, typed custom HTTP adapter Protocols, typed
  telemetry event aliases, and a default `list_all_tools()` total cap.
- Documents PyPI-first installation, local dev-login credential issuance,
  diagnostic `raw` field stability, idempotency stale outcomes, and release
  dependency-audit expectations.
