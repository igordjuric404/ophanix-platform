import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type IntegrationParams = Record<string, string | number | boolean | null | undefined>;

export interface FrameworkIntegration {
  id: string;
  integration_type: string;
  name: string;
  description: string;
  status: string;
  supported_versions: string[];
  setup_doc_url?: string | null;
  example_path?: string | null;
  setup_snippet?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FrameworkInstance {
  id: string;
  organization_id: string;
  environment_id: string;
  integration_id: string;
  integration_name: string;
  name: string;
  config: Record<string, unknown>;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface FrameworkAgentLink {
  id: string;
  integration_instance_id: string;
  integration_name: string;
  agent_id: string;
  agent_name: string;
  framework_agent_ref: string;
  sdk_version: string;
  telemetry_status: string;
  policy_coverage_status: string;
  linked_at: string;
  updated_at: string;
}

export interface ProviderCredential {
  id: string;
  organization_id: string;
  name: string;
  provider_type: string;
  secret_ref: string;
  masked_secret: string;
  status: string;
  created_by: string;
  created_at: string;
  last_used_at?: string | null;
}

export interface IntegrationHealthCheck {
  id: string;
  organization_id: string;
  environment_id: string;
  target_type: string;
  target_id: string;
  status: string;
  latency_ms: number;
  message: string;
  details: Record<string, unknown>;
  checked_at: string;
}

export function listIntegrationFrameworks(params: IntegrationParams = {}) {
  return apiClient.request<FrameworkIntegration[]>(
    `/integrations/frameworks${queryString(params)}`
  );
}

export function createFrameworkInstance(body: Record<string, unknown>) {
  return apiClient.request<FrameworkInstance>("/integrations/framework-instances", {
    method: "POST",
    body
  });
}

export function listFrameworkInstances(params: IntegrationParams = {}) {
  return apiClient.request<FrameworkInstance[]>(
    `/integrations/framework-instances${queryString(params)}`
  );
}

export function patchFrameworkInstance(instanceId: string, body: Record<string, unknown>) {
  return apiClient.request<FrameworkInstance>(
    `/integrations/framework-instances/${encodeURIComponent(instanceId)}`,
    { method: "PATCH", body }
  );
}

export function linkFrameworkAgent(instanceId: string, body: Record<string, unknown>) {
  return apiClient.request<FrameworkAgentLink>(
    `/integrations/framework-instances/${encodeURIComponent(instanceId)}/link-agent`,
    { method: "POST", body }
  );
}

export function listFrameworkAgentLinks(params: IntegrationParams = {}) {
  return apiClient.request<FrameworkAgentLink[]>(
    `/integrations/framework-agents${queryString(params)}`
  );
}

export function unlinkFrameworkAgent(linkId: string) {
  return apiClient.request<FrameworkAgentLink>(
    `/integrations/framework-agents/${encodeURIComponent(linkId)}`,
    { method: "DELETE" }
  );
}

export function createProviderCredential(body: Record<string, unknown>) {
  return apiClient.request<ProviderCredential>("/integrations/provider-credentials", {
    method: "POST",
    body
  });
}

export function listProviderCredentials(params: IntegrationParams = {}) {
  return apiClient.request<ProviderCredential[]>(
    `/integrations/provider-credentials${queryString(params)}`
  );
}

export function testProviderCredential(credentialId: string) {
  return apiClient.request<IntegrationHealthCheck>(
    `/integrations/provider-credentials/${encodeURIComponent(credentialId)}/test`,
    { method: "POST" }
  );
}

export function createIntegrationHealthCheck(body: Record<string, unknown>) {
  return apiClient.request<IntegrationHealthCheck>("/integrations/health-checks", {
    method: "POST",
    body
  });
}

export function listIntegrationHealthChecks(params: IntegrationParams = {}) {
  return apiClient.request<IntegrationHealthCheck[]>(
    `/integrations/health-checks${queryString(params)}`
  );
}

export function listLatestIntegrationHealthChecks() {
  return apiClient.request<IntegrationHealthCheck[]>("/integrations/health-checks/latest");
}

export function useIntegrationFrameworks(params: IntegrationParams = {}) {
  return useQuery({
    queryKey: ["integrations", "frameworks", params],
    queryFn: () => listIntegrationFrameworks(params)
  });
}

export function useFrameworkInstances(params: IntegrationParams = {}) {
  return useQuery({
    queryKey: ["integrations", "framework-instances", params],
    queryFn: () => listFrameworkInstances(params)
  });
}

export function useFrameworkAgentLinks(params: IntegrationParams = {}) {
  return useQuery({
    queryKey: ["integrations", "framework-agents", params],
    queryFn: () => listFrameworkAgentLinks(params)
  });
}

export function useProviderCredentials(params: IntegrationParams = {}) {
  return useQuery({
    queryKey: ["integrations", "provider-credentials", params],
    queryFn: () => listProviderCredentials(params)
  });
}

export function useIntegrationHealthChecks(params: IntegrationParams = {}) {
  return useQuery({
    queryKey: ["integrations", "health-checks", params],
    queryFn: () => listIntegrationHealthChecks(params)
  });
}

export function useIntegrationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["integrations"] });
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
    }
  });
}
