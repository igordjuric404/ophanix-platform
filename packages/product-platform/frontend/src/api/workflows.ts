import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export type WorkflowParams = Record<string, string | number | boolean | null | undefined>;

export interface WorkflowDefinition {
  id: string;
  organization_id: string;
  name: string;
  workflow_type: string;
  command_ref: string;
  input_schema: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowLog {
  id: string;
  workflow_run_id: string;
  stream: string;
  line_number: number;
  message: string;
  created_at: string;
}

export interface WorkflowRun {
  id: string;
  organization_id: string;
  environment_id?: string | null;
  workflow_definition_id: string;
  workflow_type: string;
  command_ref?: string | null;
  status: string;
  inputs: Record<string, unknown>;
  started_by?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  exit_code?: number | null;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  logs: WorkflowLog[];
}

export interface ArtifactLink {
  id: string;
  artifact_id: string;
  target_type: string;
  target_id: string;
  link_type: string;
  created_at: string;
}

export interface ArtifactAttestation {
  id: string;
  artifact_id: string;
  attested_by: string;
  statement: string;
  signature_ref?: string | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  organization_id: string;
  environment_id: string;
  artifact_type: string;
  name: string;
  content_type: string;
  storage_uri: string;
  checksum: string;
  size_bytes: number;
  created_by: string;
  created_at: string;
  links: ArtifactLink[];
  attestations: ArtifactAttestation[];
}

export interface ArtifactDownload {
  artifact: Artifact;
  content_base64: string;
  metadata: Record<string, unknown>;
}

export function listWorkflows(params: WorkflowParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<WorkflowDefinition[]>(`/workflows${queryString(params)}`, {
    tenantContext
  });
}

export function createWorkflowRun(workflowId: string, body: Record<string, unknown>) {
  return apiClient.request<WorkflowRun>(`/workflows/${encodeURIComponent(workflowId)}/runs`, {
    method: "POST",
    body
  });
}

export function listWorkflowRuns(params: WorkflowParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<WorkflowRun[]>(`/workflow-runs${queryString(params)}`, {
    tenantContext
  });
}

export function getWorkflowRun(runId: string, tenantContext?: TenantContext) {
  return apiClient.request<WorkflowRun>(`/workflow-runs/${encodeURIComponent(runId)}`, {
    tenantContext
  });
}

export function cancelWorkflowRun(runId: string) {
  return apiClient.request<WorkflowRun>(`/workflow-runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST"
  });
}

export function createArtifact(body: Record<string, unknown>) {
  return apiClient.request<Artifact>("/artifacts", { method: "POST", body });
}

export function listArtifacts(params: WorkflowParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<Artifact[]>(`/artifacts${queryString(params)}`, { tenantContext });
}

export function getArtifact(artifactId: string, tenantContext?: TenantContext) {
  return apiClient.request<Artifact>(`/artifacts/${encodeURIComponent(artifactId)}`, {
    tenantContext
  });
}

export function downloadArtifact(artifactId: string) {
  return apiClient.request<ArtifactDownload>(
    `/artifacts/${encodeURIComponent(artifactId)}/download`
  );
}

export function createArtifactLink(artifactId: string, body: Record<string, unknown>) {
  return apiClient.request<ArtifactLink>(`/artifacts/${encodeURIComponent(artifactId)}/links`, {
    method: "POST",
    body
  });
}

export function attestArtifact(artifactId: string, body: Record<string, unknown>) {
  return apiClient.request<ArtifactAttestation>(
    `/artifacts/${encodeURIComponent(artifactId)}/attest`,
    { method: "POST", body }
  );
}

export function useWorkflows(params: WorkflowParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["workflows", "definitions", params], scope),
    queryFn: () => listWorkflows(params, scope.context)
  });
}

export function useWorkflowRuns(params: WorkflowParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["workflows", "runs", params], scope),
    queryFn: () => listWorkflowRuns(params, scope.context)
  });
}

export function useWorkflowRun(runId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(runId),
    queryKey: scopedQueryKey(["workflows", "runs", runId], scope),
    queryFn: () => getWorkflowRun(runId as string, scope.context)
  });
}

export function useArtifacts(params: WorkflowParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["artifacts", params], scope),
    queryFn: () => listArtifacts(params, scope.context)
  });
}

export function useArtifact(artifactId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(artifactId),
    queryKey: scopedQueryKey(["artifacts", artifactId], scope),
    queryFn: () => getArtifact(artifactId as string, scope.context)
  });
}

export function useWorkflowMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["workflows"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["artifacts"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["audit"], scope) });
    }
  });
}
