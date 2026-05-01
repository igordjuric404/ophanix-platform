import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  integrationAgentLinkPayloadFromValues,
  integrationInstancePayloadFromValues,
  providerCredentialPayloadFromValues,
  renderConnectorInstanceForm,
  renderHealthChecksTable,
  renderIntegrationsPage,
  renderLinkedAgentsTable,
  renderProviderCredentialsTable,
  renderFrameworkCatalogTable,
  renderFrameworkSupportBadge
} from "../src/integrations.js";

const openaiFramework = {
  id: "openai_agents",
  integration_type: "framework",
  name: "OpenAI Agents",
  description: "Primary demo connector.",
  status: "primary_demo",
  supported_versions: ["0.2.x", "0.3.x"],
  setup_doc_url: "/docs/integrations/openai-agents",
  example_path: "packages/agent-os/examples/openai_agents",
  setup_snippet: "ophanix integrations init openai_agents",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z"
};

const connectorInstance = {
  id: "fwinst_1",
  organization_id: "org_default",
  environment_id: "env_default",
  integration_id: "openai_agents",
  integration_name: "OpenAI Agents",
  name: "OpenAI demo connector",
  config: { project: "demo-project" },
  status: "active",
  created_by: "user_admin",
  created_at: "2026-05-01T00:10:00Z",
  updated_at: "2026-05-01T00:10:00Z"
};

const linkedAgent = {
  id: "fwagent_1",
  integration_instance_id: "fwinst_1",
  integration_name: "OpenAI Agents",
  agent_id: "agent_demo",
  agent_name: "Demo Support Agent",
  framework_agent_ref: "assistant:demo-support",
  sdk_version: "0.3.0",
  telemetry_status: "unknown",
  policy_coverage_status: "unknown",
  linked_at: "2026-05-01T00:20:00Z",
  updated_at: "2026-05-01T00:20:00Z"
};

const providerCredential = {
  id: "provcred_1",
  organization_id: "org_default",
  name: "OpenAI demo key",
  provider_type: "model_provider",
  secret_ref: "secref_1",
  masked_secret: "••••••••",
  status: "active",
  created_by: "user_admin",
  created_at: "2026-05-01T00:30:00Z",
  last_used_at: null
};

const failedHealthCheck = {
  id: "inthealth_1",
  organization_id: "org_default",
  environment_id: "env_default",
  target_type: "provider_credential",
  target_id: "provcred_1",
  status: "failed",
  latency_ms: 12,
  message: "Provider secret is invalid or missing.",
  details: {},
  checked_at: "2026-05-01T00:31:00Z"
};

test("component support badge renders", () => {
  const html = renderFrameworkSupportBadge("primary_demo");

  assert.match(html, /integration-support-primary_demo/);
  assert.match(html, /Primary demo/);
});

test("component framework list renders", () => {
  const html = renderFrameworkCatalogTable({ frameworks: [openaiFramework] });

  assert.match(html, /data-integration-frameworks/);
  assert.match(html, /data-integration-framework-row="openai_agents"/);
  assert.match(html, /OpenAI Agents/);
  assert.match(html, /0.2.x, 0.3.x/);
});

test("component connector form validates required fields", () => {
  const html = renderConnectorInstanceForm({ frameworks: [openaiFramework] });

  assert.match(html, /data-integration-instance-form/);
  assert.match(html, /name="integration_id" required/);
  assert.match(html, /name="name" required/);
  assert.match(html, /name="config_json" required/);
});

test("component linked agent row displays coverage status", () => {
  const html = renderLinkedAgentsTable({ linkedAgents: [linkedAgent] });

  assert.match(html, /data-integration-linked-agent-row="fwagent_1"/);
  assert.match(html, /Demo Support Agent/);
  assert.match(html, /assistant:demo-support/);
  assert.match(html, /unknown/);
});

test("integrations route renders framework instances snippets and linked agents", () => {
  const html = renderIntegrationsPage({
    integrationFrameworks: [openaiFramework],
    integrationFrameworkInstances: [connectorInstance],
    integrationFrameworkAgents: [linkedAgent],
    providerCredentials: [providerCredential],
    integrationHealthChecks: [failedHealthCheck]
  });

  assert.match(html, /data-route-page="\/integrations"/);
  assert.match(html, /data-integration-framework-catalog/);
  assert.match(html, /data-integration-setup-snippet="openai_agents"/);
  assert.match(html, /data-integration-instance-row="fwinst_1"/);
  assert.match(html, /data-integration-linked-agent-row="fwagent_1"/);
  assert.match(html, /data-provider-credential-row="provcred_1"/);
  assert.match(html, /data-integration-health-row="inthealth_1"/);
});

test("component credential value is never displayed", () => {
  const html = renderProviderCredentialsTable({ credentials: [providerCredential] });

  assert.match(html, /data-provider-credential-row="provcred_1"/);
  assert.match(html, /••••••••/);
  assert.doesNotMatch(html, /sk-secret/);
});

test("component test-credential action renders result", () => {
  const html = renderProviderCredentialsTable({ credentials: [providerCredential] });

  assert.match(html, /data-provider-credential-test="provcred_1"/);
});

test("component failed health check shows remediation message", () => {
  const html = renderHealthChecksTable({ healthChecks: [failedHealthCheck] });

  assert.match(html, /data-health-remediation/);
  assert.match(html, /Check secret reference and provider configuration/);
});

test("payload helpers normalize connector forms", () => {
  assert.deepEqual(
    integrationInstancePayloadFromValues({
      integration_id: " openai_agents ",
      name: " Demo ",
      status: " active ",
      config_json: '{"project":"demo-project"}'
    }),
    {
      integration_id: "openai_agents",
      name: "Demo",
      status: "active",
      config: { project: "demo-project" }
    }
  );
  assert.deepEqual(
    integrationAgentLinkPayloadFromValues({
      agent_id: " agent_demo ",
      framework_agent_ref: " assistant:demo ",
      sdk_version: " 0.3.0 "
    }),
    {
      agent_id: "agent_demo",
      framework_agent_ref: "assistant:demo",
      sdk_version: "0.3.0"
    }
  );
  assert.deepEqual(
    providerCredentialPayloadFromValues({
      name: " Demo key ",
      provider_type: " model_provider ",
      secret_value: " sk-secret "
    }),
    {
      name: "Demo key",
      provider_type: "model_provider",
      secret_value: "sk-secret"
    }
  );
});

test("api client integration endpoints use expected paths", async () => {
  const calls = [];
  const api = createApiClient({
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET" });
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" }
      });
    }
  });

  await api.listIntegrationFrameworks({ status: "supported" });
  await api.createIntegrationFrameworkInstance({ name: "Demo" });
  await api.listIntegrationFrameworkInstances({ integration_id: "openai_agents" });
  await api.patchIntegrationFrameworkInstance("fwinst_1", { name: "Updated" });
  await api.linkIntegrationFrameworkAgent("fwinst_1", { agent_id: "agent_demo" });
  await api.listIntegrationFrameworkAgents({ agent_id: "agent_demo" });
  await api.unlinkIntegrationFrameworkAgent("fwagent_1");
  await api.createProviderCredential({ name: "Demo" });
  await api.listProviderCredentials({ provider_type: "model_provider" });
  await api.testProviderCredential("provcred_1");
  await api.createIntegrationHealthCheck({ target_id: "x" });
  await api.listIntegrationHealthChecks({ status: "failed" });
  await api.listLatestIntegrationHealthChecks();

  assert.deepEqual(calls, [
    { url: "/api/v1/integrations/frameworks?status=supported", method: "GET" },
    { url: "/api/v1/integrations/framework-instances", method: "POST" },
    { url: "/api/v1/integrations/framework-instances?integration_id=openai_agents", method: "GET" },
    { url: "/api/v1/integrations/framework-instances/fwinst_1", method: "PATCH" },
    { url: "/api/v1/integrations/framework-instances/fwinst_1/link-agent", method: "POST" },
    { url: "/api/v1/integrations/framework-agents?agent_id=agent_demo", method: "GET" },
    { url: "/api/v1/integrations/framework-agents/fwagent_1", method: "DELETE" },
    { url: "/api/v1/integrations/provider-credentials", method: "POST" },
    { url: "/api/v1/integrations/provider-credentials?provider_type=model_provider", method: "GET" },
    { url: "/api/v1/integrations/provider-credentials/provcred_1/test", method: "POST" },
    { url: "/api/v1/integrations/health-checks", method: "POST" },
    { url: "/api/v1/integrations/health-checks?status=failed", method: "GET" },
    { url: "/api/v1/integrations/health-checks/latest", method: "GET" }
  ]);
});
