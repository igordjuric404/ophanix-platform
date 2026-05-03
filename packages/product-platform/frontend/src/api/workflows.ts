import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

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

export function listWorkflows(params: WorkflowParams = {}) {
  return apiClient.request<WorkflowDefinition[]>(`/workflows${queryString(params)}`);
}

export function createWorkflowRun(workflowId: string, body: Record<string, unknown>) {
  return apiClient.request<WorkflowRun>(`/workflows/${encodeURIComponent(workflowId)}/runs`, {
    method: "POST",
    body
  });
}

export function listWorkflowRuns(params: WorkflowParams = {}) {
  return apiClient.request<WorkflowRun[]>(`/workflow-runs${queryString(params)}`);
}

export function getWorkflowRun(runId: string) {
  return apiClient.request<WorkflowRun>(`/workflow-runs/${encodeURIComponent(runId)}`);
}

export function cancelWorkflowRun(runId: string) {
  return apiClient.request<WorkflowRun>(`/workflow-runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST"
  });
}

export function createArtifact(body: Record<string, unknown>) {
  return apiClient.request<Artifact>("/artifacts", { method: "POST", body });
}

export function listArtifacts(params: WorkflowParams = {}) {
  return apiClient.request<Artifact[]>(`/artifacts${queryString(params)}`);
}

export function getArtifact(artifactId: string) {
  return apiClient.request<Artifact>(`/artifacts/${encodeURIComponent(artifactId)}`);
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
  return useQuery({
    queryKey: ["workflows", "definitions", params],
    queryFn: () => listWorkflows(params)
  });
}

export function useWorkflowRuns(params: WorkflowParams = {}) {
  return useQuery({
    queryKey: ["workflows", "runs", params],
    queryFn: () => listWorkflowRuns(params)
  });
}

export function useWorkflowRun(runId: string | null) {
  return useQuery({
    enabled: Boolean(runId),
    queryKey: ["workflows", "runs", runId],
    queryFn: () => getWorkflowRun(runId as string)
  });
}

export function useArtifacts(params: WorkflowParams = {}) {
  return useQuery({
    queryKey: ["artifacts", params],
    queryFn: () => listArtifacts(params)
  });
}

export function useArtifact(artifactId: string | null) {
  return useQuery({
    enabled: Boolean(artifactId),
    queryKey: ["artifacts", artifactId],
    queryFn: () => getArtifact(artifactId as string)
  });
}

export function useWorkflowMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workflows"] });
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    }
  });
}
