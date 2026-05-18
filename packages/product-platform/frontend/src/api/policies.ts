import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, resolveUrl, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export interface PolicyVersion {
  id: string;
  policy_id?: string | null;
  version_number: number;
  body_format: string;
  body_text?: string | null;
  backend: string;
  checksum?: string | null;
  status: string;
  created_by?: string | null;
  created_at?: string | null;
  activated_at?: string | null;
  archived_at?: string | null;
}

export interface PolicySummary {
  id: string;
  organization_id?: string | null;
  name: string;
  slug?: string | null;
  description?: string | null;
  scope: string;
  owner_user_id?: string | null;
  status: string;
  tags?: string[];
  created_at?: string | null;
  updated_at?: string | null;
  active_version_id?: string | null;
  active_version_number?: number | null;
  version_count?: number | null;
  versions?: PolicyVersion[];
}

export type PolicyDetail = PolicySummary & { versions?: PolicyVersion[] };

export interface PolicyImportResult {
  policy: PolicyDetail;
  version?: PolicyVersion | null;
  warnings?: string[];
  summary?: Record<string, unknown> | null;
}

export interface PolicyExport {
  filename?: string | null;
  body_text: string;
  body_format?: string | null;
  checksum?: string | null;
}

export interface PolicyLintIssue {
  severity: string;
  code: string;
  message: string;
  path?: string | null;
  line?: number | null;
  fatal?: boolean | null;
}

export interface PolicyLintResult {
  passed?: boolean;
  error_count?: number;
  warning_count?: number;
  issues?: PolicyLintIssue[];
}

export interface PolicyAffectedResource {
  target_type: string;
  target_id: string;
  label?: string | null;
  status?: string | null;
  mode?: string | null;
  environment_id?: string | null;
}

export interface PolicyAffectedResources {
  policy_id?: string | null;
  active_binding_count?: number | null;
  resources?: PolicyAffectedResource[];
}

export interface PolicyBinding {
  id: string;
  policy_id: string;
  policy_version_id?: string | null;
  target_type: string;
  target_id: string;
  mode: string;
  rollout_percentage: number;
  priority?: number | null;
  status: string;
  created_at?: string | null;
}

export interface PolicyException {
  id: string;
  binding_id: string;
  target_type?: string | null;
  target_id?: string | null;
  reason: string;
  expires_at?: string | null;
  status?: string | null;
  created_at?: string | null;
}

export interface PolicyEvaluation {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  policy_id?: string | null;
  policy_version_id?: string | null;
  binding_id?: string | null;
  binding_mode?: string | null;
  agent_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  context?: Record<string, unknown> | null;
  decision: string;
  policy_action?: string | null;
  matched_rule?: string | null;
  reason?: string | null;
  latency_ms?: number | null;
  mode: string;
  correlation_id?: string | null;
  backend?: string | null;
  error?: boolean | null;
  audit_preview?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface PolicyEvaluationSummary {
  total_count?: number;
  decision_counts?: Record<string, number>;
  mode_counts?: Record<string, number>;
  action_counts?: Record<string, number>;
  time_buckets?: Array<{
    bucket: string;
    total_count?: number;
    decision_counts?: Record<string, number>;
  }>;
}

export type PolicyParams = Record<string, string | number | boolean | null | undefined>;

export function listPolicies(params: PolicyParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<PolicySummary[]>(`/policies${queryString(params)}`, {
    tenantContext
  });
}

export function getPolicy(policyId: string, tenantContext?: TenantContext) {
  return apiClient.request<PolicyDetail>(`/policies/${encodeURIComponent(policyId)}`, {
    tenantContext
  });
}

export function createPolicyVersion(
  policyId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyVersion>(`/policies/${encodeURIComponent(policyId)}/versions`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function listPolicyVersions(policyId: string, tenantContext?: TenantContext) {
  return apiClient.request<PolicyVersion[]>(
    `/policies/${encodeURIComponent(policyId)}/versions`,
    { tenantContext }
  );
}

export function importPolicy(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<PolicyImportResult>("/policies/import", {
    method: "POST",
    body,
    tenantContext
  });
}

export function lintPolicy(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<PolicyLintResult>("/policies/lint", {
    method: "POST",
    body,
    tenantContext
  });
}

export function savePolicyDraftVersion(
  policyId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/draft`,
    { method: "POST", body, tenantContext }
  );
}

export function lintPolicyVersion(
  policyId: string,
  versionId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyLintResult>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(versionId)}/lint`,
    { method: "POST", tenantContext }
  );
}

export function listPolicyLintResults(policyId: string, versionId: string) {
  return apiClient.request<PolicyLintIssue[]>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/lint-results`
  );
}

export function getPolicyAffectedResources(policyId: string, tenantContext?: TenantContext) {
  return apiClient.request<PolicyAffectedResources>(
    `/policies/${encodeURIComponent(policyId)}/affected-resources`,
    { tenantContext }
  );
}

export function activatePolicyVersion(
  policyId: string,
  versionId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/activate`,
    { method: "POST", tenantContext }
  );
}

export function rollbackPolicyVersion(
  policyId: string,
  versionId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/rollback`,
    { method: "POST", tenantContext }
  );
}

export function archivePolicyVersion(
  policyId: string,
  versionId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/archive`,
    { method: "POST", tenantContext }
  );
}

export function exportPolicy(
  policyId: string,
  versionId?: string | null,
  tenantContext?: TenantContext
) {
  const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return apiClient.request<PolicyExport>(`/policies/${encodeURIComponent(policyId)}/export${query}`, {
    tenantContext
  });
}

export function listPolicyBindings(params: PolicyParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<PolicyBinding[]>(`/policy-bindings${queryString(params)}`, {
    tenantContext
  });
}

export function createPolicyBinding(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<PolicyBinding>("/policy-bindings", {
    method: "POST",
    body,
    tenantContext
  });
}

export function patchPolicyBinding(
  bindingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyBinding>(`/policy-bindings/${encodeURIComponent(bindingId)}`, {
    method: "PATCH",
    body,
    tenantContext
  });
}

export function deletePolicyBinding(bindingId: string, tenantContext?: TenantContext) {
  return apiClient.request<null>(`/policy-bindings/${encodeURIComponent(bindingId)}`, {
    method: "DELETE",
    tenantContext
  });
}

export function promotePolicyBinding(
  bindingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyBinding>(
    `/policy-bindings/${encodeURIComponent(bindingId)}/promote`,
    { method: "POST", body, tenantContext }
  );
}

export function createPolicyException(
  bindingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyException>(
    `/policy-bindings/${encodeURIComponent(bindingId)}/exceptions`,
    { method: "POST", body, tenantContext }
  );
}

export function listPolicyExceptions(params: PolicyParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<PolicyException[]>(`/policy-exceptions${queryString(params)}`, {
    tenantContext
  });
}

export function simulatePolicyEvaluation(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyEvaluation>("/policy-evaluations/simulate", {
    method: "POST",
    body,
    tenantContext
  });
}

export function evaluatePolicy(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<PolicyEvaluation>("/policy-evaluations/evaluate", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listPolicyEvaluations(params: PolicyParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<PolicyEvaluation[]>(`/policy-evaluations${queryString(params)}`, {
    tenantContext
  });
}

export function getPolicyEvaluationSummary(
  params: PolicyParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<PolicyEvaluationSummary>(
    `/policy-evaluations/summary${queryString(params)}`,
    { tenantContext }
  );
}

export function getPolicyEvaluation(evaluationId: string, tenantContext?: TenantContext) {
  return apiClient.request<PolicyEvaluation>(
    `/policy-evaluations/${encodeURIComponent(evaluationId)}`,
    { tenantContext }
  );
}

export function policyEvaluationStreamUrl(params: PolicyParams = {}, baseUrl = "/api/v1") {
  return resolveUrl(baseUrl, `/policy-evaluations/stream${queryString(params)}`);
}

export function usePolicies(params: PolicyParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["policies", params], scope),
    queryFn: () => listPolicies(params, scope.context)
  });
}

export function usePolicyDetail(policyId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(policyId),
    queryKey: scopedQueryKey(["policies", policyId, "detail"], scope),
    queryFn: () => getPolicy(policyId as string, scope.context)
  });
}

export function usePolicyAffectedResources(policyId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(policyId),
    queryKey: scopedQueryKey(["policies", policyId, "affected-resources"], scope),
    queryFn: () => getPolicyAffectedResources(policyId as string, scope.context)
  });
}

export function usePolicyBindings(params: PolicyParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["policies", "bindings", params], scope),
    queryFn: () => listPolicyBindings(params, scope.context)
  });
}

export function usePolicyExceptions(params: PolicyParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["policies", "exceptions", params], scope),
    queryFn: () => listPolicyExceptions(params, scope.context)
  });
}

export function usePolicyEvaluations(params: PolicyParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["policies", "evaluations", params], scope),
    queryFn: () => listPolicyEvaluations(params, scope.context)
  });
}

export function usePolicyEvaluationSummary(params: PolicyParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["policies", "evaluations", "summary", params], scope),
    queryFn: () => getPolicyEvaluationSummary(params, scope.context)
  });
}

export function usePolicyMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["policies"], scope) });
    }
  });
}
