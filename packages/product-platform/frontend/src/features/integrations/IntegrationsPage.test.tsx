import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import {
  IntegrationsPage,
  integrationInstancePayloadFromValues,
  providerCredentialPayloadFromValues
} from "./IntegrationsPage";

const framework = {
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

const instance = {
  id: "fwinst_1",
  organization_id: "org_default",
  environment_id: "env_default",
  integration_id: "openai_agents",
  integration_name: "OpenAI Agents",
  name: "OpenAI demo connector",
  config: { project: "demo-project", token: "hidden" },
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

const credential = {
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

const healthCheck = {
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

const agent = {
  id: "agent_demo",
  name: "Demo Support Agent",
  status: "active",
  framework: "openai_agents",
  runtime_type: "service",
  endpoint_url: "https://agent.local",
  owner_user_id: "user_1",
  sponsor_user_id: "user_1",
  trust_tier: "trusted",
  trust_score: 900,
  credential_status: "active",
  credential_expires_at: null,
  last_heartbeat_at: "2026-05-01T00:00:00Z",
  capability_count: 2
};

describe("IntegrationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders framework catalog, connector instances, linked agents, credentials, and health", async () => {
    mockIntegrationsFetch();

    renderWithQueryClient(<IntegrationsPage />);

    expect(await screen.findByRole("heading", { name: "Framework Catalog" })).toBeInTheDocument();
    expect((await screen.findAllByText("OpenAI Agents")).length).toBeGreaterThan(0);
    expect(await screen.findByText("OpenAI demo connector")).toBeInTheDocument();
    expect(await screen.findByText("Demo Support Agent")).toBeInTheDocument();
    expect(await screen.findByText("OpenAI demo key")).toBeInTheDocument();
    expect(screen.getByText("Check secret reference and provider configuration")).toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it("submits connector, link, credential, and health-check actions", async () => {
    const requests = mockIntegrationsFetch();

    renderWithQueryClient(<IntegrationsPage />);
    await screen.findByText("OpenAI demo connector");

    fireEvent.change(screen.getByLabelText("Connector Name"), {
      target: { value: "Release connector" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Connector" }));
    expect(await screen.findByText("Connector instance created")).toBeInTheDocument();

    const instanceRow = document.querySelector('[data-integration-instance-row="fwinst_1"]');
    expect(instanceRow).not.toBeNull();
    fireEvent.change(within(instanceRow as HTMLElement).getByLabelText("OpenAI demo connector name"), {
      target: { value: "OpenAI updated connector" }
    });
    fireEvent.click(within(instanceRow as HTMLElement).getByRole("button", { name: "Patch" }));
    expect(await screen.findByText("Connector instance updated")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Framework Agent Ref"), {
      target: { value: "assistant:new-support" }
    });
    fireEvent.click(screen.getByRole("button", { name: /Link Agent/ }));
    expect(await screen.findByText("Agent linked to connector")).toBeInTheDocument();

    const linkRow = document.querySelector('[data-integration-linked-agent-row="fwagent_1"]');
    expect(linkRow).not.toBeNull();
    fireEvent.click(within(linkRow as HTMLElement).getByRole("button", { name: "Unlink" }));
    expect(await screen.findByText("Agent unlinked from connector")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Credential Name"), { target: { value: "Release Key" } });
    fireEvent.change(screen.getByLabelText("Secret Value"), { target: { value: "sk-release" } });
    fireEvent.click(screen.getByRole("button", { name: /Add Credential/ }));
    expect(await screen.findByText("Provider credential created")).toBeInTheDocument();

    const credentialRow = document.querySelector('[data-provider-credential-row="provcred_1"]');
    expect(credentialRow).not.toBeNull();
    fireEvent.click(within(credentialRow as HTMLElement).getByRole("button", { name: "Test" }));
    expect(await screen.findByText("Provider credential tested")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/framework-instances"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/fwinst_1"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/link-agent"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/fwagent_1"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/provider-credentials"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/provcred_1/test"))).toBe(true);
  });

  it("normalizes connector and credential payloads", () => {
    expect(
      integrationInstancePayloadFromValues({
        integration_id: " openai_agents ",
        name: " Demo ",
        status: " active ",
        config_json: '{"project":"demo"}'
      })
    ).toEqual({
      integration_id: "openai_agents",
      name: "Demo",
      status: "active",
      config: { project: "demo" }
    });

    expect(() =>
      integrationInstancePayloadFromValues({
        integration_id: "openai_agents",
        name: "Demo",
        config_json: "{"
      })
    ).toThrow("Config JSON must be valid JSON.");

    expect(
      providerCredentialPayloadFromValues({
        name: " Demo key ",
        provider_type: " model_provider ",
        secret_value: " sk-secret "
      })
    ).toEqual({
      name: "Demo key",
      provider_type: "model_provider",
      secret_value: "sk-secret"
    });
  });
});

function mockIntegrationsFetch() {
  const requests: Array<{ url: string; method: string; body?: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ url: path, method, body });

      if (path === "/api/v1/integrations/frameworks" && method === "GET") {
        return json([framework]);
      }
      if (path === "/api/v1/integrations/framework-instances" && method === "GET") {
        return json([instance]);
      }
      if (path === "/api/v1/integrations/framework-agents" && method === "GET") {
        return json([linkedAgent]);
      }
      if (path === "/api/v1/integrations/provider-credentials" && method === "GET") {
        return json([credential]);
      }
      if (path === "/api/v1/integrations/health-checks" && method === "GET") {
        return json([healthCheck]);
      }
      if (path === "/api/v1/agents" && method === "GET") {
        return json([agent]);
      }
      if (path === "/api/v1/integrations/framework-instances" && method === "POST") {
        return json({ ...instance, id: "fwinst_2", name: "Release connector" }, 201);
      }
      if (path === "/api/v1/integrations/framework-instances/fwinst_1" && method === "PATCH") {
        return json({ ...instance, name: "OpenAI updated connector" });
      }
      if (path === "/api/v1/integrations/framework-instances/fwinst_1/link-agent" && method === "POST") {
        return json({ ...linkedAgent, id: "fwagent_2", framework_agent_ref: "assistant:new-support" }, 201);
      }
      if (path === "/api/v1/integrations/framework-agents/fwagent_1" && method === "DELETE") {
        return json(linkedAgent);
      }
      if (path === "/api/v1/integrations/provider-credentials" && method === "POST") {
        return json({ ...credential, id: "provcred_2", name: "Release Key" }, 201);
      }
      if (path === "/api/v1/integrations/provider-credentials/provcred_1/test" && method === "POST") {
        return json({ ...healthCheck, id: "inthealth_2", status: "healthy", message: "Provider reachable" }, 201);
      }

      return json({ detail: `Unhandled ${method} ${path}` }, 404);
    })
  );
  return requests;
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
