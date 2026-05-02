import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AuditEvent, AuditVerification } from "./audit";
import { apiClient, queryString } from "./client";

export interface AuditExport {
  id?: string;
  format?: string;
  artifact_uri?: string | null;
  status?: string | null;
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
  freshness_at?: string | null;
  status: string;
  created_at?: string | null;
}

export interface ComplianceEvidenceRecompute {
  scanned_event_count?: number;
  evidence_count?: number;
  refreshed_count?: number;
  violation_count?: number;
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

export function exportAuditEvents(body: Record<string, unknown>) {
  return apiClient.request<AuditExport>("/audit/export", { method: "POST", body });
}

export function verifyAuditRange() {
  return apiClient.request<AuditVerification>("/audit/verify-range", { method: "POST" });
}

export function listComplianceFrameworks() {
  return apiClient.request<ComplianceFramework[]>("/compliance/frameworks");
}

export function createComplianceFramework(body: Record<string, unknown>) {
  return apiClient.request<ComplianceFramework>("/compliance/frameworks", {
    method: "POST",
    body
  });
}

export function listComplianceControls(params: ComplianceParams = {}) {
  return apiClient.request<ComplianceControl[]>(`/compliance/controls${queryString(params)}`);
}

export function createComplianceControlMapping(body: Record<string, unknown>) {
  return apiClient.request<Record<string, unknown>>("/compliance/control-mappings", {
    method: "POST",
    body
  });
}

export function listComplianceEvidence(params: ComplianceParams = {}) {
  return apiClient.request<ComplianceEvidence[]>(`/compliance/evidence${queryString(params)}`);
}

export function recomputeComplianceEvidence() {
  return apiClient.request<ComplianceEvidenceRecompute>("/compliance/evidence/recompute", {
    method: "POST"
  });
}

export function listComplianceViolations(params: ComplianceParams = {}) {
  return apiClient.request<ComplianceViolation[]>(
    `/compliance/violations${queryString(params)}`
  );
}

export function patchComplianceViolation(violationId: string, body: Record<string, unknown>) {
  return apiClient.request<ComplianceViolation>(
    `/compliance/violations/${encodeURIComponent(violationId)}`,
    { method: "PATCH", body }
  );
}

export function createComplianceReport(body: Record<string, unknown>) {
  return apiClient.request<ComplianceReport>("/compliance/reports", { method: "POST", body });
}

export function listComplianceReports(params: ComplianceParams = {}) {
  return apiClient.request<ComplianceReport[]>(`/compliance/reports${queryString(params)}`);
}

export function getComplianceReport(reportId: string) {
  return apiClient.request<ComplianceReport>(
    `/compliance/reports/${encodeURIComponent(reportId)}`
  );
}

export function generateComplianceReport(reportId: string) {
  return apiClient.request<ComplianceReport>(
    `/compliance/reports/${encodeURIComponent(reportId)}/generate`,
    { method: "POST" }
  );
}

export function downloadComplianceReport(reportId: string) {
  return apiClient.request<Record<string, unknown> | string>(
    `/compliance/reports/${encodeURIComponent(reportId)}/download`
  );
}

export function attestComplianceReport(reportId: string, body: Record<string, unknown>) {
  return apiClient.request<ComplianceAttestation>(
    `/compliance/reports/${encodeURIComponent(reportId)}/attest`,
    { method: "POST", body }
  );
}

export function listArtifacts(params: ComplianceParams = {}) {
  return apiClient.request<Artifact[]>(`/artifacts${queryString(params)}`);
}

export function useComplianceAuditEvents(
  listAuditEvents: (params?: ComplianceParams) => Promise<AuditEvent[]>,
  params: ComplianceParams = {}
) {
  return useQuery({
    queryKey: ["audit", "events", params],
    queryFn: () => listAuditEvents(params)
  });
}

export function useComplianceFrameworks() {
  return useQuery({
    queryKey: ["compliance", "frameworks"],
    queryFn: listComplianceFrameworks
  });
}

export function useComplianceControls(params: ComplianceParams = {}) {
  return useQuery({
    queryKey: ["compliance", "controls", params],
    queryFn: () => listComplianceControls(params)
  });
}

export function useComplianceEvidence(params: ComplianceParams = {}) {
  return useQuery({
    queryKey: ["compliance", "evidence", params],
    queryFn: () => listComplianceEvidence(params)
  });
}

export function useComplianceViolations(params: ComplianceParams = {}) {
  return useQuery({
    queryKey: ["compliance", "violations", params],
    queryFn: () => listComplianceViolations(params)
  });
}

export function useComplianceReports(params: ComplianceParams = {}) {
  return useQuery({
    queryKey: ["compliance", "reports", params],
    queryFn: () => listComplianceReports(params)
  });
}

export function useComplianceArtifacts(params: ComplianceParams = {}) {
  return useQuery({
    queryKey: ["artifacts", params],
    queryFn: () => listArtifacts(params)
  });
}

export function useComplianceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["compliance"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
    }
  });
}
