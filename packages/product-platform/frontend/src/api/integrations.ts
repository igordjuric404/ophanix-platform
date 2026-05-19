import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

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
  environment_id: string;
  name: string;
  provider_type: string;
  subject_type: string;
  subject_id?: string | null;
  subject_id_redacted?: boolean;
  provider_account_id?: string | null;
  provider_account_id_redacted?: boolean;
  credential_type: string;
  scopes: string[];
  expires_at?: string | null;
  rotation_status: string;
  revoked_at?: string | null;
  revoked_by?: string | null;
  revoked_reason?: string | null;
  allowed_tool_ids: string[];
  secret_ref: string | null;
  secret_ref_redacted?: boolean;
  masked_secret: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
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

export function listIntegrationFrameworks(
  params: IntegrationParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<FrameworkIntegration[]>(
    `/integrations/frameworks${queryString(params)}`,
    { tenantContext }
  );
}

export function createFrameworkInstance(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<FrameworkInstance>("/integrations/framework-instances", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listFrameworkInstances(
  params: IntegrationParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<FrameworkInstance[]>(
    `/integrations/framework-instances${queryString(params)}`,
    { tenantContext }
  );
}

export function patchFrameworkInstance(
  instanceId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<FrameworkInstance>(
    `/integrations/framework-instances/${encodeURIComponent(instanceId)}`,
    { method: "PATCH", body, tenantContext }
  );
}

export function linkFrameworkAgent(
  instanceId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<FrameworkAgentLink>(
    `/integrations/framework-instances/${encodeURIComponent(instanceId)}/link-agent`,
    { method: "POST", body, tenantContext }
  );
}

export function listFrameworkAgentLinks(
  params: IntegrationParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<FrameworkAgentLink[]>(
    `/integrations/framework-agents${queryString(params)}`,
    { tenantContext }
  );
}

export function unlinkFrameworkAgent(linkId: string, tenantContext?: TenantContext) {
  return apiClient.request<FrameworkAgentLink>(
    `/integrations/framework-agents/${encodeURIComponent(linkId)}`,
    { method: "DELETE", tenantContext }
  );
}

export function createProviderCredential(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ProviderCredential>("/integrations/provider-credentials", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listProviderCredentials(
  params: IntegrationParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<ProviderCredential[]>(
    `/integrations/provider-credentials${queryString(params)}`,
    { tenantContext }
  );
}

export function testProviderCredential(credentialId: string, tenantContext?: TenantContext) {
  return apiClient.request<IntegrationHealthCheck>(
    `/integrations/provider-credentials/${encodeURIComponent(credentialId)}/test`,
    { method: "POST", tenantContext }
  );
}

export function createIntegrationHealthCheck(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<IntegrationHealthCheck>("/integrations/health-checks", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listIntegrationHealthChecks(
  params: IntegrationParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<IntegrationHealthCheck[]>(
    `/integrations/health-checks${queryString(params)}`,
    { tenantContext }
  );
}

export function listLatestIntegrationHealthChecks(tenantContext?: TenantContext) {
  return apiClient.request<IntegrationHealthCheck[]>("/integrations/health-checks/latest", {
    tenantContext
  });
}

export function useIntegrationFrameworks(params: IntegrationParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["integrations", "frameworks", params], scope),
    queryFn: () => listIntegrationFrameworks(params, scope.context)
  });
}

export function useFrameworkInstances(params: IntegrationParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["integrations", "framework-instances", params], scope),
    queryFn: () => listFrameworkInstances(params, scope.context)
  });
}

export function useFrameworkAgentLinks(params: IntegrationParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["integrations", "framework-agents", params], scope),
    queryFn: () => listFrameworkAgentLinks(params, scope.context)
  });
}

export function useProviderCredentials(params: IntegrationParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["integrations", "provider-credentials", params], scope),
    queryFn: () => listProviderCredentials(params, scope.context)
  });
}

export function useIntegrationHealthChecks(params: IntegrationParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["integrations", "health-checks", params], scope),
    queryFn: () => listIntegrationHealthChecks(params, scope.context)
  });
}

export function useIntegrationMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["integrations"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["agents"], scope) });
    }
  });
}
