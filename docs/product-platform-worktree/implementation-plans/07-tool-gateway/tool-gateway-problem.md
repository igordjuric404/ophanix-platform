## Top three relevant company patterns

I would model Ophanix from these three: **Microsoft Agent 365 / Entra Agent ID**, **Okta for AI Agents**, and **Salesforce Agentforce**. They are the closest matches because they focus on agent identity, ownership, access, governance, and audit rather than only agent orchestration.

---

## 1. Microsoft: Agent 365 + Entra Agent ID

Microsoft’s pattern is the closest conceptual match to Ophanix. **Agent 365 is the control plane**, while **Entra Agent ID is the identity and access layer**. Microsoft describes Agent 365 as a control plane for IT and security leaders to observe, secure, and govern agents across an organization, including agents built or acquired elsewhere. ([Microsoft Learn][1])

The key idea is that agents become visible assets in a central registry. Microsoft’s docs describe a centralized registry where admins can see agent adoption, activity, and health, then apply lifecycle management, access control, compliance, data protection, and threat detection around those agents. ([Microsoft Learn][2])

For identity, Microsoft treats agents as **first-class identities**. Entra Agent ID provides authentication, authorization, lifecycle management, ownership, permissions, policy enforcement, and monitoring for agents. It separates registry/visibility from identity enforcement: Agent 365 discovers and inventories agents, while Entra Agent ID gives them identities and permissions. ([Microsoft Learn][3])

Important design details from Microsoft:

| Concept              | Microsoft approach                            | What Ophanix should copy              |
| -------------------- | --------------------------------------------- | ------------------------------------- |
| Agent registry       | Central inventory of agents                   | Ophanix agent registry                |
| Agent identity       | Dedicated agent identity in Entra             | `agent_id` as a first-class principal |
| Human accountability | Owners and sponsors                           | Owning team plus responsible human    |
| Lifecycle            | Active, disabled, retired, reviewed           | Lifecycle states in Ophanix           |
| Access               | Conditional Access, permissions, risk signals | Policy decision before tool execution |
| Observability        | Activity, sign-in, audit logs                 | Runtime action feed and audit UI      |
| Kill switch          | Disable agent identity or blueprint           | Suspend agent to block token issuance |

Microsoft’s agent identity management page explicitly includes owners, sponsors, granted permissions, sign-in logs, audit logs, inheritable permissions, Conditional Access, risk detection, disabling agents, and lifecycle workflows. ([Microsoft Learn][4])

For Ophanix, the main takeaway is:

> Do not treat an agent as just metadata. Treat it as a security principal with lifecycle, owner, permissions, credentials, and runtime events.

---

## 2. Okta: AI agents as managed identities with resource connections

Okta’s approach is identity-first and vendor-neutral. Okta for AI Agents is designed to discover, manage, and secure the AI agent lifecycle, enforce least privilege and time-bound access, show connections/scopes/risks, and expose System Log events for compliance. ([Okta Docs][5])

Okta’s workflow is very relevant to Ophanix:

1. Discover and assess agents.
2. Add and register agents.
3. Connect agents to resources.
4. Govern access to agents and linked apps. ([Okta Docs][5])

Okta’s registration docs say custom agents can be manually registered, imported agents can be synced from third-party builder platforms, and registered agents can have owners, credentials, linked OIDC apps, and resource connections. ([Okta Docs][6])

The most important concept for Ophanix is Okta’s **resource connection** model. Okta lets an agent connect to an authorization server, secret, service account, application, custom resource server, or MCP server. For authorization servers, Okta supports allow-all scopes, allow-only scopes, and disallowed scopes. For secrets and service accounts, Okta uses a resource indicator that the agent uses when requesting access. ([Okta Docs][7])

Okta also has a strong answer to shadow agents. Its docs describe discovering unknown agents in managed and unmanaged apps, assessing ownership, permissions, resources, and the risk those agents pose. ([Okta Docs][8])

Important design details from Okta:

| Concept             | Okta approach                                           | What Ophanix should copy                        |
| ------------------- | ------------------------------------------------------- | ----------------------------------------------- |
| Agent discovery     | Find known and shadow agents                            | Later, import/sync agents from external systems |
| Registration        | Manual or imported                                      | Start with manual registration                  |
| Ownership           | Add owners                                              | Required owner/team fields                      |
| Credentials         | Credentials and linked OIDC app                         | Client credentials now, OAuth later             |
| Resource connection | Agent connected to app, secret, MCP server, auth server | Tool/resource registry                          |
| Scopes              | Allow, deny, disallow scopes                            | Per-tool allowed scopes                         |
| Governance          | Access requests and certifications                      | Later access review workflow                    |
| Kill switch         | Revoke/deactivate access                                | Suspend agent and revoke credentials            |

Okta’s product page also emphasizes short-lived credentials, least-privilege policies, vaulting and rotating secrets, full audit trail, and revoking access when an agent behaves unexpectedly. ([Okta][9])

For Ophanix, the main takeaway is:

> Model every callable thing as a resource connection with scopes, not as an unstructured webhook.

---

## 3. Salesforce: Agentforce actions, trust layer, and platform permissions

Salesforce is different because Agentforce is more vertically integrated. It does not only observe external agents. It hosts agents inside the Salesforce platform and connects them to Salesforce actions, data, permissions, and trust controls.

The useful part for Ophanix is how Salesforce structures **actions**. Agentforce actions are tasks a subagent can perform, such as calling a Flow, prompt template, or Apex class. Actions have names, descriptions, inputs, outputs, executable targets, and optional `require_user_confirmation`. Salesforce also lets action outputs be included in or filtered out of the agent context. ([Developer][10])

Salesforce’s Trust Layer includes CRM grounding, sensitive data masking, toxicity detection, audit trail and feedback, and zero data retention agreements with third-party LLM providers. ([Developer][11])

The key lesson is that the tool/action contract is explicit. A tool is not just a URL. It has a name, schema, target, input schema, output schema, visibility rules, and sometimes a confirmation requirement.

Important design details from Salesforce:

| Concept                | Salesforce approach                       | What Ophanix should copy                      |
| ---------------------- | ----------------------------------------- | --------------------------------------------- |
| Tool/action definition | Named action with inputs, outputs, target | Tool registry schema                          |
| Execution target       | Flow, Apex, prompt                        | Upstream API endpoint                         |
| Agent visibility       | Output can be hidden from agent context   | Redaction and response visibility flags       |
| User confirmation      | Action can require confirmation           | Later approval flow                           |
| Trust layer            | Masking, grounding, toxicity, audit       | Audit plus optional data filters              |
| Existing permissions   | Agents respect platform access controls   | Ophanix policy should sit before upstream API |

For Ophanix, the main takeaway is:

> A production tool call needs a registered contract: name, input schema, upstream target, required scope, policy, audit behavior, and response handling.

---

## Important MCP authorization finding

MCP authorization gives you a good future direction, but it does **not** fully solve your tool-level authorization problem by itself.

The MCP authorization spec says a protected MCP server acts as an OAuth 2.1 resource server, MCP clients use access tokens, and the authorization server issues tokens for use at the MCP server. It also requires MCP servers to expose protected resource metadata and validate that access tokens were issued specifically for the MCP server as the intended audience. ([Model Context Protocol][12])

The spec also says access tokens must be sent in the `Authorization: Bearer <token>` header on every HTTP request and must not be sent in the URI query string. MCP servers must reject invalid or expired tokens with `401`, and insufficient scopes should result in `403`. ([Model Context Protocol][12])

But Microsoft’s Azure MCP authorization docs make a very important point: MCP server authorization controls access to the server, but it does not provide granular control to individual MCP tools. ([Microsoft Learn][13])

That means Ophanix must implement its own **tool-level policy decision** even if it later becomes MCP/OAuth compliant.

---

# How Ophanix should do this simply

## The simplest correct architecture

```text
External Agent Runtime
        |
        | tool call request
        v
Ophanix Tool Gateway
        |
        | allow or deny decision
        v
Protected Business API
```

The agent lives outside Ophanix. The business API lives outside Ophanix. Ophanix owns the identity, policy decision, routing, and audit trail.

## Minimum Ophanix components

| Component          | Purpose                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| Agent Registry     | Stores agents, owners, lifecycle state                                  |
| Tool Registry      | Stores callable tools and upstream API routes                           |
| Credential Service | Issues agent credentials and short-lived access tokens                  |
| Tool Gateway       | Receives tool calls, validates token, checks policy, forwards or blocks |
| Policy Engine      | Decides allow or deny                                                   |
| Audit Store        | Stores every decision and runtime action                                |
| UI                 | Shows agents, tools, decisions, denied calls, allowed calls             |

## Do you need an SDK?

Yes, but it should be optional at first.

The real required piece is the **Ophanix Tool Gateway**. The SDK is just the easiest integration path.

Support both:

```text
1. SDK call
   ophanix.callTool("claims.lookup", payload)

2. Direct HTTP call
   POST /v1/tools/claims.lookup/invoke
```

This makes adoption easier. Teams that want convenience use your SDK. Teams that want full control use HTTP.

---

# Finished feature flow

1. Team has an agent running outside Ophanix.

2. Team registers the agent in Ophanix.

3. Team registers the tools the agent may call.

4. Ophanix shows the agent in the platform.

5. Ophanix shows the tool permissions for that agent.

6. The agent receives a user prompt outside Ophanix.

7. The agent decides it needs to call a tool.

8. The agent sends the tool call to Ophanix instead of calling the real API directly.

9. Ophanix identifies the agent.

10. Ophanix checks whether the agent is active.

11. Ophanix checks whether the requested tool exists.

12. Ophanix checks whether the agent is allowed to call that tool.

13. Ophanix creates a policy decision.

14. If the decision is deny:

    * Ophanix blocks the call.
    * Ophanix returns a denied response to the agent.
    * Ophanix stores the denied action.
    * Ophanix shows the denied decision in the UI.

15. If the decision is allow:

    * Ophanix forwards the call to the real tool/API.
    * The real API executes.
    * Ophanix receives the API response.
    * Ophanix returns the response to the agent.
    * Ophanix stores the allowed action.
    * Ophanix shows the allowed decision in the UI.

---

# What to build now vs later

## Build now

| Build now          | Reason                              |
| ------------------ | ----------------------------------- |
| Agent registration | Required to know who is acting      |
| Tool registration  | Required to know what can be called |
| Client credentials | Simple machine-to-machine auth      |
| Short-lived JWT    | Simple access token                 |
| Tool gateway       | Required for live routing           |
| Allow/deny policy  | Core feature                        |
| Audit event table  | Core UI data                        |
| Decisions UI       | Makes the platform useful           |
| SDK wrapper        | Makes integration easier            |

## Do not build now

| Avoid for now                              | Reason                             |
| ------------------------------------------ | ---------------------------------- |
| Full OAuth 2.1 dynamic client registration | Too much complexity for MVP        |
| Full MCP protected resource metadata       | Add after basic HTTP gateway works |
| Service mesh                               | Too heavy for first version        |
| mTLS everywhere                            | Useful later, not needed first     |
| Full model gateway                         | Separate problem                   |
| Human approval workflow                    | Add after allow/deny works         |
| External IdP federation                    | Add after local credentials work   |
| Complex policy language                    | Start with simple DB rules         |

---

# Recommended MVP behavior

For now, implement this policy model:

```text
agent_id + tool_name + environment -> allow or deny
```

Then add conditions:

```text
refund.issue allowed only if amount <= 100
refund.issue denied if claim.status = fraud_review
```

That is enough to prove the feature.

---

# Technical implementation summary for an AI coding agent

```text
FEATURE: Ophanix Live Tool Gateway for External AI Agents

GOAL
Build the minimal production version of Ophanix where:
1. AI agents run outside Ophanix.
2. Agents call tools through Ophanix.
3. Ophanix identifies the agent.
4. Ophanix decides allow or deny.
5. If allowed, Ophanix forwards the request to the real upstream API.
6. If denied, Ophanix blocks the request.
7. Every decision is stored and visible in the Ophanix UI.

CORE CONCEPTS
Ophanix is not the agent runtime.
Ophanix is the control plane plus tool gateway.
Teams own agent prompts, agent logic, model calls, and business APIs.
Ophanix owns agent identity, credentials, policy decisions, routing, and audit visibility.

MAIN OBJECTS

1. Agent
Represents one external AI agent.

Fields:
- id: UUID
- agent_key: string, unique, example "claims-assistant-prod"
- display_name: string
- description: string nullable
- owning_team: string
- owner_email: string
- environment: enum "dev" | "stage" | "prod"
- status: enum "draft" | "active" | "suspended" | "retired"
- created_at: timestamp
- updated_at: timestamp
- last_seen_at: timestamp nullable

Behavior:
- Only agents with status "active" can receive access tokens.
- Suspended or retired agents must be blocked from token issuance and tool invocation.
- The UI must show agent status and last seen time.

2. AgentCredential
Represents machine credentials used by an external agent to authenticate to Ophanix.

Fields:
- id: UUID
- agent_id: UUID
- client_id: string, unique
- client_secret_hash: string
- status: enum "active" | "revoked"
- created_at: timestamp
- expires_at: timestamp nullable
- last_used_at: timestamp nullable

Behavior:
- Client secret is shown only once at creation time.
- Store only a hash of the client secret.
- Revoked credentials cannot be used to obtain tokens.
- Token issuance should update last_used_at.

3. Tool
Represents a callable business tool.

Fields:
- id: UUID
- name: string, unique, example "claims.lookup"
- display_name: string
- description: string nullable
- environment: enum "dev" | "stage" | "prod"
- upstream_url: string
- upstream_method: enum "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
- required_scope: string, example "tool:claims.lookup"
- timeout_ms: integer default 10000
- status: enum "active" | "disabled"
- request_schema_json: JSON nullable
- response_schema_json: JSON nullable
- created_at: timestamp
- updated_at: timestamp

Behavior:
- Disabled tools cannot be invoked.
- Each tool has exactly one upstream target for MVP.
- Tool name is the public stable contract agents call.
- Upstream URL is internal implementation detail.

4. AgentToolPermission
Represents whether an agent can call a tool.

Fields:
- id: UUID
- agent_id: UUID
- tool_id: UUID
- effect: enum "allow" | "deny"
- conditions_json: JSON nullable
- created_at: timestamp
- updated_at: timestamp

MVP condition examples:
{
  "max_amount": 100
}

{
  "deny_if_payload_equals": {
    "claim_status": "fraud_review"
  }
}

Behavior:
- Explicit deny always wins over allow.
- If no permission exists, default decision is deny.
- Conditions are optional in the first version.
- Implement simple condition evaluation, not a full policy language.

5. AccessToken
Use signed JWTs for MVP.
Do not store every token unless needed.
Store token issuance events as audit events.

JWT claims:
- iss: "https://ophanix.example.com"
- sub: agent.id
- aud: "ophanix-tool-gateway"
- exp: now + 15 minutes
- iat: now
- jti: UUID
- agent_key: agent.agent_key
- environment: agent.environment
- scopes: list of strings, example ["tool:claims.lookup", "tool:refund.issue"]

Behavior:
- Token lifetime should be short, recommended 15 minutes.
- Gateway validates signature, issuer, audience, expiry, agent status, and scopes.
- Do not accept tokens from unknown issuers.
- Do not accept expired tokens.
- Do not accept tokens with the wrong audience.

6. PolicyDecision
Represents the authorization result for one attempted tool call.

Fields:
- id: UUID
- event_id: UUID
- agent_id: UUID
- tool_id: UUID nullable
- decision: enum "allow" | "deny"
- reason_code: string
- reason_message: string
- matched_permission_id: UUID nullable
- created_at: timestamp

Reason code examples:
- AGENT_NOT_FOUND
- AGENT_INACTIVE
- TOKEN_INVALID
- TOKEN_EXPIRED
- TOOL_NOT_FOUND
- TOOL_DISABLED
- SCOPE_MISSING
- PERMISSION_NOT_FOUND
- EXPLICIT_DENY
- CONDITION_FAILED
- ALLOW

7. RuntimeActionEvent
Represents one tool invocation attempt.

Fields:
- id: UUID
- timestamp: timestamp
- trace_id: string
- request_id: string
- agent_id: UUID nullable
- agent_key: string nullable
- tool_id: UUID nullable
- tool_name: string
- environment: string nullable
- action_type: enum "tool.invoke"
- decision: enum "allow" | "deny"
- decision_reason_code: string
- decision_reason_message: string
- request_payload_hash: string nullable
- request_payload_redacted: JSON nullable
- response_payload_hash: string nullable
- response_payload_redacted: JSON nullable
- upstream_url: string nullable
- upstream_status_code: integer nullable
- gateway_status_code: integer
- latency_ms: integer
- error_message: string nullable
- created_at: timestamp

Behavior:
- Always write one RuntimeActionEvent for every tool invocation attempt.
- Store redacted payloads only. Never store secrets or raw authorization headers.
- Store request and response hashes for forensic comparison without storing sensitive data.
- The UI uses this table to show live activity.

API ENDPOINTS

1. Create agent
POST /v1/agents

Request:
{
  "agent_key": "claims-assistant-prod",
  "display_name": "Claims Assistant",
  "owning_team": "Claims",
  "owner_email": "owner@example.com",
  "environment": "prod"
}

Response:
{
  "id": "...",
  "agent_key": "claims-assistant-prod",
  "status": "draft"
}

2. Activate agent
POST /v1/agents/{agent_id}/activate

Behavior:
- Set status to "active".
- Agent can now receive tokens.

3. Create agent credential
POST /v1/agents/{agent_id}/credentials

Response:
{
  "client_id": "...",
  "client_secret": "shown-once"
}

Behavior:
- Store hash of client_secret only.
- Never return the secret again.

4. Register tool
POST /v1/tools

Request:
{
  "name": "claims.lookup",
  "display_name": "Lookup Claim",
  "environment": "prod",
  "upstream_url": "https://claims-api.example.com/claims/lookup",
  "upstream_method": "POST",
  "required_scope": "tool:claims.lookup",
  "timeout_ms": 10000
}

5. Grant permission
POST /v1/agents/{agent_id}/tools/{tool_id}/permissions

Request:
{
  "effect": "allow",
  "conditions_json": null
}

6. Issue token
POST /v1/auth/token

Request:
{
  "grant_type": "client_credentials",
  "client_id": "...",
  "client_secret": "..."
}

Behavior:
- Validate client_id and client_secret.
- Find credential.
- Find agent.
- Require credential.status = "active".
- Require agent.status = "active".
- Load all allowed tools for this agent.
- Create scopes from allowed tools.
- Return signed JWT.

Response:
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 900
}

7. Invoke tool
POST /v1/tools/{tool_name}/invoke

Headers:
Authorization: Bearer <access_token>
Content-Type: application/json
X-Ophanix-Trace-Id: optional client trace id

Request:
{
  "input": {
    "...": "..."
  },
  "metadata": {
    "session_id": "optional",
    "user_id": "optional",
    "runtime": "langgraph|openai-agents-sdk|custom"
  }
}

Gateway behavior:
Step 1: Create request_id and trace_id.
Step 2: Validate Authorization header exists.
Step 3: Validate JWT signature.
Step 4: Validate iss, aud, exp, iat.
Step 5: Extract agent_id from sub.
Step 6: Load agent.
Step 7: Deny if agent missing.
Step 8: Deny if agent.status is not "active".
Step 9: Load tool by tool_name.
Step 10: Deny if tool missing.
Step 11: Deny if tool.status is not "active".
Step 12: Check token scopes include tool.required_scope.
Step 13: Deny if required scope missing.
Step 14: Load AgentToolPermission records for agent and tool.
Step 15: Deny if explicit deny exists.
Step 16: Deny if no allow exists.
Step 17: Evaluate conditions_json if present.
Step 18: Deny if condition fails.
Step 19: Create PolicyDecision allow.
Step 20: Forward request to tool.upstream_url.
Step 21: Include sanitized headers only.
Step 22: Do not forward the Ophanix client credential.
Step 23: Add Ophanix headers to upstream request:
  - X-Ophanix-Agent-Id
  - X-Ophanix-Agent-Key
  - X-Ophanix-Trace-Id
  - X-Ophanix-Request-Id
  - X-Ophanix-Tool-Name
Step 24: Wait for upstream response.
Step 25: Store RuntimeActionEvent with decision, latency, upstream status, hashes, and redacted payloads.
Step 26: Return upstream response to agent.

Deny behavior:
- Do not call upstream API.
- Store PolicyDecision deny.
- Store RuntimeActionEvent deny.
- Return JSON error.

Deny response example:
{
  "error": {
    "code": "TOOL_CALL_DENIED",
    "reason_code": "PERMISSION_NOT_FOUND",
    "message": "Agent is not allowed to call tool refund.issue",
    "trace_id": "..."
  }
}

HTTP status mapping:
- 401 for missing, invalid, or expired token.
- 403 for valid token but denied tool permission.
- 404 for unknown tool if you do not want to reveal tool existence.
- 502 for upstream failure.
- 504 for upstream timeout.

CLAIMS ASSISTANT MVP

Create one external agent:
- agent_key: "claims-assistant-prod"
- display_name: "Claims Assistant"
- environment: "prod"
- status: "active"

Create two tools:
1. claims.lookup
- required_scope: "tool:claims.lookup"
- upstream_url: "https://claims-api.example.com/claims/lookup"
- upstream_method: "POST"

2. refund.issue
- required_scope: "tool:refund.issue"
- upstream_url: "https://refund-api.example.com/refunds/issue"
- upstream_method: "POST"

Create permissions:
1. Claims Assistant can call claims.lookup.
2. Claims Assistant can call refund.issue only if input.amount <= 100.
3. Default deny all other tools.

Example agent-side direct HTTP call:
POST /v1/tools/claims.lookup/invoke
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "input": {
    "claim_id": "CLM-123"
  },
  "metadata": {
    "session_id": "sess-123",
    "runtime": "custom-node-agent"
  }
}

Example allowed flow:
1. Agent calls claims.lookup through Ophanix.
2. Gateway validates token.
3. Gateway checks agent status.
4. Gateway checks tool status.
5. Gateway checks scope.
6. Gateway checks permission.
7. Decision is allow.
8. Gateway forwards request to claims API.
9. Gateway stores RuntimeActionEvent.
10. UI shows allowed decision.

Example denied flow:
1. Agent calls refund.issue with amount 250.
2. Gateway validates token.
3. Gateway checks permission condition.
4. Condition fails because amount > 100.
5. Decision is deny.
6. Gateway does not call refund API.
7. Gateway stores RuntimeActionEvent.
8. UI shows denied decision with reason CONDITION_FAILED.

UI REQUIREMENTS

Agents page:
- List agents.
- Show display name, agent key, owner, team, environment, status, last seen.
- Agent detail page shows credentials, allowed tools, recent runtime actions.

Tools page:
- List registered tools.
- Show tool name, upstream URL, status, required scope.
- Tool detail page shows which agents can call it.

Runtime actions page:
- Table of RuntimeActionEvent.
- Columns:
  - timestamp
  - agent
  - tool
  - decision
  - reason
  - gateway status
  - upstream status
  - latency
  - trace id
- Filters:
  - agent
  - tool
  - decision
  - environment
  - time range

Decision detail page:
- Show request metadata.
- Show agent.
- Show tool.
- Show token validation result.
- Show matched permission.
- Show policy decision.
- Show upstream status if allowed.
- Show denial reason if denied.
- Show redacted payload if available.

SDK REQUIREMENTS

Build minimal TypeScript SDK after HTTP API works.

SDK usage:
const ophanix = new OphanixClient({
  baseUrl: process.env.OPHANIX_BASE_URL,
  clientId: process.env.OPHANIX_CLIENT_ID,
  clientSecret: process.env.OPHANIX_CLIENT_SECRET
});

const result = await ophanix.callTool("claims.lookup", {
  claim_id: "CLM-123"
});

SDK behavior:
- Fetch access token using client credentials.
- Cache token until near expiry.
- Attach Authorization header.
- Send tool call to /v1/tools/{tool_name}/invoke.
- Include metadata like runtime, session_id, trace_id when provided.
- Throw typed error for denied calls.
- Expose trace_id on errors and responses.

SECURITY REQUIREMENTS

- Never log client_secret.
- Never log Authorization header.
- Hash payloads before storage.
- Redact sensitive fields from stored payloads.
- Token lifetime should be short, 15 minutes.
- All gateway endpoints require HTTPS in production.
- Default decision is deny.
- Suspended agent cannot get token.
- Suspended agent token should also fail at gateway even if token is not expired.
- Disabled tool cannot be invoked.
- Explicit deny beats allow.
- Store every allowed and denied attempt.

FUTURE COMPATIBILITY

Design the gateway so it can later become MCP-compatible:
- Keep tool names stable.
- Keep scopes stable.
- Keep token audience specific to the gateway.
- Later expose protected resource metadata.
- Later support OAuth 2.1 authorization server metadata.
- Later support resource indicators.
- Later support token exchange for downstream resources.
- Later support MCP transport, but keep the same internal policy decision flow.

NON-GOALS FOR MVP

- Do not host agent runtime.
- Do not build model gateway.
- Do not build full OAuth 2.1 dynamic client registration.
- Do not build service mesh.
- Do not require mTLS.
- Do not build human approval workflow yet.
- Do not build full policy language.
- Do not build external IdP federation yet.

SUCCESS CRITERIA

1. A Claims Assistant running outside Ophanix can get an access token.
2. The agent can call claims.lookup through Ophanix.
3. Ophanix allows claims.lookup and forwards it to the real API.
4. The agent can call refund.issue through Ophanix.
5. Ophanix allows refund.issue when amount <= 100.
6. Ophanix denies refund.issue when amount > 100.
7. Denied calls never reach the upstream refund API.
8. All allow and deny decisions appear in the Ophanix UI.
9. Each UI event has agent, tool, decision, reason, timestamp, latency, and trace id.
```

[1]: https://learn.microsoft.com/en-us/microsoft-agent-365/ "Microsoft Agent 365 documentation | Microsoft Learn"
[2]: https://learn.microsoft.com/en-us/microsoft-agent-365/overview "Microsoft Agent 365 overview | Microsoft Learn"
[3]: https://learn.microsoft.com/en-us/microsoft-agent-365/admin/capabilities-entra "Protect agent identities with Microsoft Entra | Microsoft Learn"
[4]: https://learn.microsoft.com/en-us/entra/agent-id/manage-agent-identities-admin "Manage agent identities in your organization - Microsoft Entra Agent ID | Microsoft Learn"
[5]: https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agents-home.htm "Okta for AI Agents | Okta Identity Engine"
[6]: https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-register.htm "Add and register AI agents | Okta Identity Engine"
[7]: https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-connected-resource.htm "Connect AI agents to resources | Okta Identity Engine"
[8]: https://help.okta.com/oie/en-us/content/topics/ai-agents/ai-agent-discover.htm "Discover and assess AI agents | Okta Identity Engine"
[9]: https://www.okta.com/products/govern-ai-agent-identity/ "Okta for AI Agents | Govern Agentic Identity | Okta"
[10]: https://developer.salesforce.com/docs/ai/agentforce/guide/ascript-ref-actions.html "Actions | Agent Script | Agentforce Developer Guide | Salesforce Developers"
[11]: https://developer.salesforce.com/docs/ai/agentforce/guide/trust.html "Trust Layer | Get Started | Agentforce Developer Guide | Salesforce Developers"
[12]: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization "Authorization - Model Context Protocol"
[13]: https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-mcp "Configure MCP server authorization - Azure App Service | Microsoft Learn"
