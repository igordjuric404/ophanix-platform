import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AuditEvent, AuditVerification } from "./audit";
import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export interface AuditExport {
  id?: string;
  format?: string;
  artifact_uri?: string | null;
  status?: string | null;
  event_count?: number | null;
  complete?: boolean | null;
  completeness_reason?: string | null;
  chain_proof?: Record<string, unknown> | null;
  filters?: Record<string, unknown> | null;
}

export interface ComplianceFramework {
  id: string;
  organization_id?: string | null;
  name: string;
  version: string;
  description?: string | null;
  status: string;
  created_at?: string | null;
}

export interface ComplianceControl {
  id: string;
  framework_id: string;
  framework_name?: string | null;
  control_code: string;
  title: string;
  description?: string | null;
  required_evidence_types?: string[];
  owner_user_id?: string | null;
}

export interface ComplianceEvidence {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  control_id: string;
  control_code?: string | null;
  source_type: string;
  source_id: string;
  title: string;
  summary?: string | null;
  source_event_hash?: string | null;
  control_mapping_version?: string | null;
  source_manifest?: Record<string, unknown> | null;
  chain_proof?: Record<string, unknown> | null;
  trace_id?: string | null;
  run_id?: string | null;
  tool_id?: string | null;
  policy_id?: string | null;
  policy_version_id?: string | null;
  freshness_at?: string | null;
  status: string;
  created_at?: string | null;
}

export interface ComplianceEvidenceRecompute {
  scanned_event_count?: number;
  evidence_count?: number;
  refreshed_count?: number;
  violation_count?: number;
  runtime_action_count?: number;
  complete?: boolean;
  completeness_reason?: string | null;
}

export interface ComplianceViolation {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  control_id: string;
  control_code?: string | null;
  agent_id?: string | null;
  severity: string;
  status: string;
  reason: string;
  source_type?: string | null;
  source_id?: string | null;
  source_event_id?: string | null;
  resolution_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ArtifactLink {
  id?: string;
  artifact_id?: string;
  target_type: string;
  target_id: string;
  link_type?: string | null;
  created_at?: string | null;
}

export interface Artifact {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  artifact_type: string;
  name: string;
  content_type?: string | null;
  storage_uri?: string | null;
  checksum?: string | null;
  size_bytes?: number | null;
  created_by?: string | null;
  created_at?: string | null;
  links?: ArtifactLink[];
}

export interface ComplianceReport {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  framework_id: string;
  framework_name?: string | null;
  name: string;
  status: string;
  date_from: string;
  date_to: string;
  generated_by?: string | null;
  artifact_uri?: string | null;
  summary?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
  generated_at?: string | null;
  evidence_item_ids?: string[];
  attestation_count?: number | null;
  rendered_markdown?: string | null;
}

export interface ComplianceAttestation {
  id: string;
  report_id?: string | null;
  statement?: string | null;
  signature_ref?: string | null;
  created_at?: string | null;
}

export type ComplianceParams = Record<string, string | number | boolean | null | undefined>;

export function exportAuditEvents(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<AuditExport>("/audit/export", {
    method: "POST",
    body,
    tenantContext
  });
}

export function verifyAuditRange(tenantContext?: TenantContext) {
  return apiClient.request<AuditVerification>("/audit/verify-range", {
    method: "POST",
    tenantContext
  });
}

export function listComplianceFrameworks(tenantContext?: TenantContext) {
  return apiClient.request<ComplianceFramework[]>("/compliance/frameworks", { tenantContext });
}

export function createComplianceFramework(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ComplianceFramework>("/compliance/frameworks", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listComplianceControls(params: ComplianceParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<ComplianceControl[]>(`/compliance/controls${queryString(params)}`, {
    tenantContext
  });
}

export function createComplianceControlMapping(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>("/compliance/control-mappings", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listComplianceEvidence(params: ComplianceParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<ComplianceEvidence[]>(`/compliance/evidence${queryString(params)}`, {
    tenantContext
  });
}

export function recomputeComplianceEvidence(tenantContext?: TenantContext) {
  return apiClient.request<ComplianceEvidenceRecompute>("/compliance/evidence/recompute", {
    method: "POST",
    tenantContext
  });
}

export function listComplianceViolations(
  params: ComplianceParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<ComplianceViolation[]>(
    `/compliance/violations${queryString(params)}`,
    { tenantContext }
  );
}

export function patchComplianceViolation(
  violationId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ComplianceViolation>(
    `/compliance/violations/${encodeURIComponent(violationId)}`,
    { method: "PATCH", body, tenantContext }
  );
}

export function createComplianceReport(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ComplianceReport>("/compliance/reports", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listComplianceReports(params: ComplianceParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<ComplianceReport[]>(`/compliance/reports${queryString(params)}`, {
    tenantContext
  });
}

export function getComplianceReport(reportId: string, tenantContext?: TenantContext) {
  return apiClient.request<ComplianceReport>(
    `/compliance/reports/${encodeURIComponent(reportId)}`,
    { tenantContext }
  );
}

export function generateComplianceReport(reportId: string, tenantContext?: TenantContext) {
  return apiClient.request<ComplianceReport>(
    `/compliance/reports/${encodeURIComponent(reportId)}/generate`,
    { method: "POST", tenantContext }
  );
}

export function downloadComplianceReport(reportId: string, tenantContext?: TenantContext) {
  return apiClient.request<Record<string, unknown> | string>(
    `/compliance/reports/${encodeURIComponent(reportId)}/download`,
    { tenantContext }
  );
}

export function attestComplianceReport(
  reportId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ComplianceAttestation>(
    `/compliance/reports/${encodeURIComponent(reportId)}/attest`,
    { method: "POST", body, tenantContext }
  );
}

export function listArtifacts(params: ComplianceParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<Artifact[]>(`/artifacts${queryString(params)}`, { tenantContext });
}

export function useComplianceAuditEvents(
  listAuditEvents: (
    params?: ComplianceParams,
    tenantContext?: TenantContext
  ) => Promise<AuditEvent[]>,
  params: ComplianceParams = {}
) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["audit", "events", params], scope),
    queryFn: () => listAuditEvents(params, scope.context)
  });
}

export function useComplianceFrameworks() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["compliance", "frameworks"], scope),
    queryFn: () => listComplianceFrameworks(scope.context)
  });
}

export function useComplianceControls(params: ComplianceParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["compliance", "controls", params], scope),
    queryFn: () => listComplianceControls(params, scope.context)
  });
}

export function useComplianceEvidence(params: ComplianceParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["compliance", "evidence", params], scope),
    queryFn: () => listComplianceEvidence(params, scope.context)
  });
}

export function useComplianceViolations(params: ComplianceParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["compliance", "violations", params], scope),
    queryFn: () => listComplianceViolations(params, scope.context)
  });
}

export function useComplianceReports(params: ComplianceParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["compliance", "reports", params], scope),
    queryFn: () => listComplianceReports(params, scope.context)
  });
}

export function useComplianceArtifacts(params: ComplianceParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["artifacts", params], scope),
    queryFn: () => listArtifacts(params, scope.context)
  });
}

export function useComplianceMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["compliance"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["audit"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["artifacts"], scope) });
    }
  });
}
