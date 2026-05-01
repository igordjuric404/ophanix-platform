# Framework Connector Registry

## Feature Scope

Create a registry for agent framework connectors. Users can see which frameworks are supported, configure connector instances, link agents to connectors, and validate telemetry/policy coverage.

## Existing Repo Assets To Reuse

- Agent OS integrations under `packages/agent-os/src/agent_os/integrations`.
- AgentMesh integrations under `packages/agentmesh-integrations`.
- Examples for OpenAI Agents, CrewAI, smolagents, and LangChain.

## Out Of Scope

- Model provider credential management.
- Building every connector implementation.

## Data Model

Tables:

- `integrations`: id, integration_type, name, description, status, supported_versions_json.
- `integration_instances`: id, organization_id, environment_id, integration_id, name, config_json, status, created_at.
- `framework_agents`: id, integration_instance_id, agent_id, framework_agent_ref, sdk_version, telemetry_status, policy_coverage_status.

## API Surface

Implement:

- `GET /api/v1/integrations/frameworks`
- `POST /api/v1/integrations/framework-instances`
- `GET /api/v1/integrations/framework-instances`
- `PATCH /api/v1/integrations/framework-instances/{id}`
- `POST /api/v1/integrations/framework-instances/{id}/link-agent`
- `GET /api/v1/integrations/framework-agents`

## UI Surface

Integrations -> Frameworks.

Agent Detail -> Integrations.

## Implementation Phases

### Phase 1: Supported Framework Catalog

Steps:

1. Seed framework catalog: OpenAI Agents, LangChain, CrewAI, smolagents, LlamaIndex, AutoGen, custom.
2. Store support status: primary demo, supported, experimental, scaffold.
3. Include setup doc links and example paths.

Tests:

- Integration test seed is idempotent.
- API test lists frameworks.
- Component test support badge renders.

### Phase 2: Connector Instances

Steps:

1. Add instance create/update API.
2. Validate config per framework.
3. Store non-secret config only.
4. Emit audit event on connector changes.

Tests:

- API test creates OpenAI Agents connector instance.
- API test secret-like values are rejected from config.
- Integration test update emits audit event.

### Phase 3: Link Agents To Connectors

Steps:

1. Add link endpoint for agent and connector instance.
2. Store SDK version and framework reference.
3. Show policy and telemetry coverage status.
4. Allow unlink with audit.

Tests:

- API test links agent to connector.
- API test cannot link agent from another environment.
- API test coverage status defaults to unknown until health check runs.

### Phase 4: UI

Steps:

1. Build framework catalog table.
2. Build connector instance form.
3. Build linked agents table.
4. Add setup snippet panel for each framework.

Tests:

- Component test framework list renders.
- Component test connector form validates required fields.
- Component test linked agent row displays coverage status.

## Overall Validation

- Configure OpenAI Agents connector.
- Link demo support agent.
- Show setup snippet and coverage status.
- Confirm changes are auditable.

## Dependencies

- Agent inventory.
- Event pipeline.
- Provider credentials for full health checks.

## Definition Of Done

- Framework integration state is visible and configurable from the product.
