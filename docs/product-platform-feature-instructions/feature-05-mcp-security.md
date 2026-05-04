# Feature 05: MCP Security

## Feature Goal and Expected User Outcome

Validate that a security operator can register MCP servers, discover tools, run security scans, triage findings, evaluate proxy calls, approve or deny escalated tool use, and configure rate limits.

The expected outcome is a registered MCP server with tool and scan records, visible findings or clean scan state, proxy traffic decisions, approval queue behavior, and persisted rate-limit records.

## Implementation Surface

- Frontend route: `/mcp`.
- Frontend page: `frontend/src/features/mcp/McpPage.tsx`.
- API endpoints include:
  - `GET /api/v1/mcp/servers`
  - `POST /api/v1/mcp/servers`
  - `GET /api/v1/mcp/servers/{server_id}`
  - `PATCH /api/v1/mcp/servers/{server_id}`
  - `POST /api/v1/mcp/servers/{server_id}/discover-tools`
  - `GET /api/v1/mcp/tools`
  - `GET /api/v1/mcp/tools/{tool_id}`
  - `POST /api/v1/mcp/servers/{server_id}/scan`
  - `GET /api/v1/mcp/scans`
  - `GET /api/v1/mcp/scans/{scan_run_id}`
  - `GET /api/v1/mcp/findings`
  - `POST /api/v1/mcp/findings/{finding_id}/accept-risk`
  - `POST /api/v1/mcp/findings/{finding_id}/resolve`
  - `POST /api/v1/mcp/findings/{finding_id}/false-positive`
  - `POST /api/v1/mcp/proxy/call`
  - `GET /api/v1/mcp/traffic`
  - `GET /api/v1/mcp/approvals`
  - `POST /api/v1/mcp/approvals/{approval_id}/approve`
  - `POST /api/v1/mcp/approvals/{approval_id}/deny`
  - `GET /api/v1/mcp/rate-limits`
  - `POST /api/v1/mcp/rate-limits`
- Domain modules: `mcp/repository.py`, `mcp/discovery.py`, `mcp/scans.py`, `mcp/proxy.py`.
- Migrations: `0014_mcp_registry.up.sql`, `0015_mcp_tools.up.sql`, `0016_mcp_security_scans.up.sql`, `0017_mcp_proxy_traffic.up.sql`.
- Tests: `test_mcp_server_tool_registry_*.py`, `test_mcp_security_scans_*.py`, `test_mcp_proxy_traffic_*.py`, `frontend/src/features/mcp/McpPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin` or `Security Admin`.
- Use environment `Development`.
- Optional: start Docker local demo to use the demo MCP service at `http://localhost:8091/health`.
- Suggested server values:
  - `Name`: `Demo Refund MCP`
  - `Endpoint`: `https://demo.ophanix.local/mcp/refunds` for repository-only validation, or the Docker demo MCP endpoint if validating a live adapter.
  - `Owner`: `user_admin`
  - `Auth`: `none`
  - `Status`: `active`

## UI Validation Steps

1. Click `MCP Security` in the left navigation.
2. Expected URL change: current route changes to `/mcp`.
3. Confirm page title `MCP Security` and description `MCP server registry, tool discovery, security scans, proxy approvals, and rate limits.`
4. Confirm summary metrics:
   - `Servers`
   - `Tools`
   - `Open Findings`
   - `Pending Approvals`
5. In `Server Registry`, enter:
   - `Name`: `Demo Refund MCP`
   - `Endpoint`: `https://demo.ophanix.local/mcp/refunds`
   - `Owner`: `user_admin`
   - `Auth`: `none`
   - `Status`: `active`
6. Click `Register`.
7. Expected UI response: success message `MCP server registered`; the server appears in the table.
8. In the server row, click `Discover`.
9. Expected UI response:
   - Tool discovery completes.
   - `Tool Registry` table populates if the discovery adapter returns tools.
   - If no tools are returned, the tool registry remains empty but the server remains registered.
10. In the server row, click `Scan`.
11. Expected UI response:
   - `Scan History` shows a scan row with server, status, tool count, finding count, and finished time.
   - `Security Findings` shows findings if the scanner detected schema or risk issues.
12. In `Tool Registry`, click `Details` on a tool row if one exists.
13. Expected UI response: detail panel shows schema and version history. If no tool is selected, it shows `No tool selected`.
14. In `Security Findings`, set filters:
   - `Status`: `open`
   - `Severity`: leave blank or choose `critical`, `warning`, or `info`
   - `Server`: the server ID if known
   - `Tool`: leave blank unless known
   - Click `Filter`
15. Open a finding detail if present.
16. Expected UI response:
   - Detail shows finding, tool, server, tool version, description, recommendation, and evidence JSON.
17. Triage the finding:
   - To accept risk, enter `validation accepted risk` in `Risk Reason` and click `Accept Risk`.
   - To resolve, enter `validation resolved` in `Resolution Note` and click `Resolve`.
   - To mark false positive, enter `validation false positive` in `False Positive Reason` and click `False Positive`.
18. Expected UI response: finding status changes and the open finding count updates.
19. In `Proxy Traffic`, fill:
   - `Source Agent`: an agent ID from Feature 02
   - `Server ID`: the MCP server ID
   - `Tool ID`: a discovered tool ID, or a typed tool ID if validating denial behavior
   - `Correlation`: `validation-mcp-call`
   - `Params JSON`: `{"demo":true}`
20. Click `Evaluate`.
21. Expected UI response:
   - A traffic row appears.
   - Decision is `allowed`, `denied`, or `escalated`.
   - Columns include tool, agent, decision, reason, policy, sanitizer, and created time.
22. In `Approval Queue`, filter:
   - `Status`: `pending`
   - Click `Filter`
23. If an approval row exists, enter `validation approval` in `Approve Reason` and click `Approve`.
24. Expected UI response: approval status changes to approved.
25. If validating denial, enter `validation denial` in `Deny Reason` and click `Deny`.
26. Expected UI response: approval status changes to denied.
27. In `Rate Limits`, enter:
   - `Target Type`: `mcp-server`
   - `Target ID`: the MCP server ID
   - `Window Seconds`: `60`
   - `Max Calls`: `60`
   - Leave `Enabled` checked.
28. Click `Create`.
29. Expected UI response: rate limit row appears with target, window, max calls, and status.

## Expected Backend Effects

- Server registration creates an MCP server registry record.
- Tool discovery records tool schemas and version hashes when the discovery adapter returns tools.
- Security scans create scan run records and finding records.
- Finding triage updates status and reason fields.
- Proxy evaluation records a tool call decision, reason, policy references, sanitizer output, and correlation ID.
- Escalated proxy decisions can create approval queue records.
- Approval or denial updates approval status and affects subsequent proxy behavior where connected.
- Rate limit creation persists target, window, max calls, and enabled state.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Security Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

Register a server, discover tools, and scan:

```bash
SERVER_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "name":"Demo Refund MCP API",
    "endpoint_url":"https://demo.ophanix.local/mcp/refunds",
    "owner_user_id":"user_admin",
    "auth_type":"none",
    "status":"active"
  }' \
  "$API/api/v1/mcp/servers")

echo "$SERVER_JSON" | jq
SERVER_ID=$(echo "$SERVER_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' "$API/api/v1/mcp/servers/$SERVER_ID/discover-tools" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' "$API/api/v1/mcp/servers/$SERVER_ID/scan" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mcp/tools?server_id=$SERVER_ID" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mcp/findings?server_id=$SERVER_ID" | jq
```

Evaluate proxy traffic and create rate limit:

```bash
AGENT_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[0].id')
TOOL_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mcp/tools?server_id=$SERVER_ID" | jq -r '.[0].id // empty')

if [ -z "$TOOL_ID" ]; then
  echo "No MCP tools were discovered for $SERVER_ID; skip proxy-call verification until discovery returns a tool."
else
  curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
    -d "{
      \"source_agent_id\":\"$AGENT_ID\",
      \"server_id\":\"$SERVER_ID\",
      \"tool_id\":\"$TOOL_ID\",
      \"correlation_id\":\"validation-mcp-call\",
      \"params\":{\"demo\":true}
    }" \
    "$API/api/v1/mcp/proxy/call" | jq
fi

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"target_type\":\"mcp-server\",
    \"target_id\":\"$SERVER_ID\",
    \"window_seconds\":60,
    \"max_calls\":60,
    \"enabled\":true
  }" \
  "$API/api/v1/mcp/rate-limits" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mcp/traffic?server_id=$SERVER_ID" | jq
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/mcp/approvals" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_mcp_server_tool_registry_overall \
  tests.test_mcp_security_scans_overall \
  tests.test_mcp_proxy_traffic_overall \
  -v

cd frontend
npm test -- McpPage.test.tsx
```

## Edge Cases and Alternative Flows

- No tools discovered: the server remains valid, `Tool Registry` may show no rows, and scans may report zero tools.
- Invalid endpoint: registration may fail validation or later discovery/scan may fail.
- Open findings only: use the status filter to confirm accepted-risk, resolved, and false-positive findings disappear from the open queue.
- Proxy call with malformed JSON: `Params JSON` should reject invalid JSON before or during submission.
- Approval queue empty: allowed and denied decisions do not necessarily create approvals. Create a stricter policy or threshold if an escalated decision is required.
- Rate limit disabled: uncheck `Enabled` and create the row; it should appear disabled and should not enforce limits until enabled.

## Integration Setup Required: External MCP Server

Repository validation can register and scan records without a production MCP deployment. To validate a real MCP integration:

1. Start or provision an MCP server.
2. Confirm its health endpoint manually, for example `curl http://localhost:8091/health` for the Docker demo server.
3. Choose the matching auth type: `none`, `api_key`, `bearer`, `oauth`, `mtls`, or `custom`.
4. Store any required secret through the integrations or deployment secret system. Exact production secret wiring for every auth type needs verification in the deployment environment.
5. Register the MCP server in `/mcp`.
6. Click `Discover`.
7. Confirm tools appear in `Tool Registry`.
8. Click `Scan`.
9. Confirm scans and findings reference the discovered tool IDs.

Needs verification: live tool invocation behavior depends on the external MCP server and auth configuration.

## Troubleshooting

- `Discover` returns no tools: verify the endpoint is reachable from the API process and auth type matches the server.
- `Scan` fails or stays empty: inspect the scan run detail and API logs for schema parsing failures.
- Proxy evaluation denies unexpectedly: check policy bindings, trust thresholds, rate limits, and whether the tool has security findings.
- Approval action fails: confirm the approval is still `pending`; approved or denied approvals cannot be decided again.
- Rate limit row does not appear: clear filters and query `GET /api/v1/mcp/rate-limits`.
