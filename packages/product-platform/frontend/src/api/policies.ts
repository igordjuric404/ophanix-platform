import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, resolveUrl } from "./client";

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

export function listPolicies(params: PolicyParams = {}) {
  return apiClient.request<PolicySummary[]>(`/policies${queryString(params)}`);
}

export function getPolicy(policyId: string) {
  return apiClient.request<PolicyDetail>(`/policies/${encodeURIComponent(policyId)}`);
}

export function createPolicyVersion(policyId: string, body: Record<string, unknown>) {
  return apiClient.request<PolicyVersion>(`/policies/${encodeURIComponent(policyId)}/versions`, {
    method: "POST",
    body
  });
}

export function listPolicyVersions(policyId: string) {
  return apiClient.request<PolicyVersion[]>(
    `/policies/${encodeURIComponent(policyId)}/versions`
  );
}

export function importPolicy(body: Record<string, unknown>) {
  return apiClient.request<PolicyImportResult>("/policies/import", { method: "POST", body });
}

export function lintPolicy(body: Record<string, unknown>) {
  return apiClient.request<PolicyLintResult>("/policies/lint", { method: "POST", body });
}

export function savePolicyDraftVersion(policyId: string, body: Record<string, unknown>) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/draft`,
    { method: "POST", body }
  );
}

export function lintPolicyVersion(policyId: string, versionId: string) {
  return apiClient.request<PolicyLintResult>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(versionId)}/lint`,
    { method: "POST" }
  );
}

export function listPolicyLintResults(policyId: string, versionId: string) {
  return apiClient.request<PolicyLintIssue[]>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/lint-results`
  );
}

export function getPolicyAffectedResources(policyId: string) {
  return apiClient.request<PolicyAffectedResources>(
    `/policies/${encodeURIComponent(policyId)}/affected-resources`
  );
}

export function activatePolicyVersion(policyId: string, versionId: string) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/activate`,
    { method: "POST" }
  );
}

export function rollbackPolicyVersion(policyId: string, versionId: string) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/rollback`,
    { method: "POST" }
  );
}

export function archivePolicyVersion(policyId: string, versionId: string) {
  return apiClient.request<PolicyVersion>(
    `/policies/${encodeURIComponent(policyId)}/versions/${encodeURIComponent(
      versionId
    )}/archive`,
    { method: "POST" }
  );
}

export function exportPolicy(policyId: string, versionId?: string | null) {
  const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return apiClient.request<PolicyExport>(`/policies/${encodeURIComponent(policyId)}/export${query}`);
}

export function listPolicyBindings(params: PolicyParams = {}) {
  return apiClient.request<PolicyBinding[]>(`/policy-bindings${queryString(params)}`);
}

export function createPolicyBinding(body: Record<string, unknown>) {
  return apiClient.request<PolicyBinding>("/policy-bindings", { method: "POST", body });
}

export function patchPolicyBinding(bindingId: string, body: Record<string, unknown>) {
  return apiClient.request<PolicyBinding>(`/policy-bindings/${encodeURIComponent(bindingId)}`, {
    method: "PATCH",
    body
  });
}

export function deletePolicyBinding(bindingId: string) {
  return apiClient.request<null>(`/policy-bindings/${encodeURIComponent(bindingId)}`, {
    method: "DELETE"
  });
}

export function promotePolicyBinding(bindingId: string, body: Record<string, unknown>) {
  return apiClient.request<PolicyBinding>(
    `/policy-bindings/${encodeURIComponent(bindingId)}/promote`,
    { method: "POST", body }
  );
}

export function createPolicyException(bindingId: string, body: Record<string, unknown>) {
  return apiClient.request<PolicyException>(
    `/policy-bindings/${encodeURIComponent(bindingId)}/exceptions`,
    { method: "POST", body }
  );
}

export function listPolicyExceptions(params: PolicyParams = {}) {
  return apiClient.request<PolicyException[]>(`/policy-exceptions${queryString(params)}`);
}

export function simulatePolicyEvaluation(body: Record<string, unknown>) {
  return apiClient.request<PolicyEvaluation>("/policy-evaluations/simulate", {
    method: "POST",
    body
  });
}

export function evaluatePolicy(body: Record<string, unknown>) {
  return apiClient.request<PolicyEvaluation>("/policy-evaluations/evaluate", {
    method: "POST",
    body
  });
}

export function listPolicyEvaluations(params: PolicyParams = {}) {
  return apiClient.request<PolicyEvaluation[]>(`/policy-evaluations${queryString(params)}`);
}

export function getPolicyEvaluationSummary(params: PolicyParams = {}) {
  return apiClient.request<PolicyEvaluationSummary>(
    `/policy-evaluations/summary${queryString(params)}`
  );
}

export function getPolicyEvaluation(evaluationId: string) {
  return apiClient.request<PolicyEvaluation>(
    `/policy-evaluations/${encodeURIComponent(evaluationId)}`
  );
}

export function policyEvaluationStreamUrl(params: PolicyParams = {}, baseUrl = "/api/v1") {
  return resolveUrl(baseUrl, `/policy-evaluations/stream${queryString(params)}`);
}

export function usePolicies(params: PolicyParams = {}) {
  return useQuery({ queryKey: ["policies", params], queryFn: () => listPolicies(params) });
}

export function usePolicyDetail(policyId: string | null) {
  return useQuery({
    enabled: Boolean(policyId),
    queryKey: ["policies", policyId, "detail"],
    queryFn: () => getPolicy(policyId as string)
  });
}

export function usePolicyAffectedResources(policyId: string | null) {
  return useQuery({
    enabled: Boolean(policyId),
    queryKey: ["policies", policyId, "affected-resources"],
    queryFn: () => getPolicyAffectedResources(policyId as string)
  });
}

export function usePolicyBindings(params: PolicyParams = {}) {
  return useQuery({
    queryKey: ["policies", "bindings", params],
    queryFn: () => listPolicyBindings(params)
  });
}

export function usePolicyExceptions(params: PolicyParams = {}) {
  return useQuery({
    queryKey: ["policies", "exceptions", params],
    queryFn: () => listPolicyExceptions(params)
  });
}

export function usePolicyEvaluations(params: PolicyParams = {}) {
  return useQuery({
    queryKey: ["policies", "evaluations", params],
    queryFn: () => listPolicyEvaluations(params)
  });
}

export function usePolicyEvaluationSummary(params: PolicyParams = {}) {
  return useQuery({
    queryKey: ["policies", "evaluations", "summary", params],
    queryFn: () => getPolicyEvaluationSummary(params)
  });
}

export function usePolicyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
    }
  });
}
