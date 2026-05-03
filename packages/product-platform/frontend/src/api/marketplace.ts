import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type MarketplaceParams = Record<string, string | number | boolean | null | undefined>;

export interface PluginVersion {
  id: string;
  plugin_id: string;
  version: string;
  manifest: Record<string, unknown>;
  package_ref: string;
  signature_status: string;
  quality_score: number;
  trust_tier: string;
  required_capabilities: string[];
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface MarketplacePlugin {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  publisher: string;
  plugin_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  versions: PluginVersion[];
}

export interface PluginPolicyResult {
  id: string;
  plugin_version_id: string;
  result: string;
  findings: Array<Record<string, unknown>>;
  created_at: string;
}

export interface PluginInstallation {
  id: string;
  plugin_version_id: string;
  plugin_name: string;
  version: string;
  environment_id: string;
  target_agent_id?: string | null;
  target_agent_name?: string | null;
  status: string;
  installed_by: string;
  installed_at: string;
  uninstalled_at?: string | null;
}

export interface PluginReview {
  id: string;
  plugin_version_id: string;
  plugin_name?: string | null;
  version?: string | null;
  status: string;
  reviewer_id?: string | null;
  findings: Array<Record<string, unknown>>;
  decision_reason?: string | null;
  created_at: string;
  decided_at?: string | null;
}

export interface PluginSigningKey {
  id: string;
  organization_id: string;
  name: string;
  public_key: string;
  status: string;
  created_by: string;
  created_at: string;
  revoked_at?: string | null;
}

export interface PluginQualityAssessment {
  id: string;
  plugin_version_id: string;
  score: number;
  dimensions: Record<string, unknown>;
  findings: Array<Record<string, unknown>>;
  created_at: string;
}

export interface PluginTrustEvent {
  id: string;
  plugin_version_id: string;
  source_event_id?: string | null;
  delta: number;
  reason: string;
  score_before: number;
  score_after: number;
  trust_tier: string;
  created_at: string;
}

export function importMarketplacePlugin(body: Record<string, unknown>) {
  return apiClient.request<MarketplacePlugin>("/marketplace/plugins/import", {
    method: "POST",
    body
  });
}

export function listMarketplacePlugins(params: MarketplaceParams = {}) {
  return apiClient.request<MarketplacePlugin[]>(`/marketplace/plugins${queryString(params)}`);
}

export function getMarketplacePlugin(pluginId: string) {
  return apiClient.request<MarketplacePlugin>(
    `/marketplace/plugins/${encodeURIComponent(pluginId)}`
  );
}

export function checkMarketplacePluginPolicy(versionId: string, body: Record<string, unknown>) {
  return apiClient.request<PluginPolicyResult>(
    `/marketplace/plugins/${encodeURIComponent(versionId)}/check-policy`,
    { method: "POST", body }
  );
}

export function submitMarketplacePluginReview(versionId: string, body: Record<string, unknown>) {
  return apiClient.request<PluginReview>(
    `/marketplace/plugins/${encodeURIComponent(versionId)}/submit-review`,
    { method: "POST", body }
  );
}

export function listMarketplaceReviews(params: MarketplaceParams = {}) {
  return apiClient.request<PluginReview[]>(`/marketplace/reviews${queryString(params)}`);
}

export function approveMarketplaceReview(reviewId: string, body: Record<string, unknown>) {
  return apiClient.request<PluginReview>(
    `/marketplace/reviews/${encodeURIComponent(reviewId)}/approve`,
    { method: "POST", body }
  );
}

export function rejectMarketplaceReview(reviewId: string, body: Record<string, unknown>) {
  return apiClient.request<PluginReview>(
    `/marketplace/reviews/${encodeURIComponent(reviewId)}/reject`,
    { method: "POST", body }
  );
}

export function createMarketplaceSigningKey(body: Record<string, unknown>) {
  return apiClient.request<PluginSigningKey>("/marketplace/signing-keys", {
    method: "POST",
    body
  });
}

export function listMarketplaceSigningKeys() {
  return apiClient.request<PluginSigningKey[]>("/marketplace/signing-keys");
}

export function revokeMarketplaceSigningKey(keyId: string) {
  return apiClient.request<PluginSigningKey>(
    `/marketplace/signing-keys/${encodeURIComponent(keyId)}/revoke`,
    { method: "POST" }
  );
}

export function assessMarketplacePluginQuality(versionId: string) {
  return apiClient.request<PluginQualityAssessment>(
    `/marketplace/plugins/${encodeURIComponent(versionId)}/assess-quality`,
    { method: "POST" }
  );
}

export function recomputeMarketplacePluginTrust(versionId: string, body: Record<string, unknown>) {
  return apiClient.request<PluginTrustEvent>(
    `/marketplace/plugins/${encodeURIComponent(versionId)}/recompute-trust`,
    { method: "POST", body }
  );
}

export function createMarketplaceInstallation(body: Record<string, unknown>) {
  return apiClient.request<PluginInstallation>("/marketplace/installations", {
    method: "POST",
    body
  });
}

export function listMarketplaceInstallations(params: MarketplaceParams = {}) {
  return apiClient.request<PluginInstallation[]>(
    `/marketplace/installations${queryString(params)}`
  );
}

export function uninstallMarketplaceInstallation(installationId: string) {
  return apiClient.request<PluginInstallation>(
    `/marketplace/installations/${encodeURIComponent(installationId)}/uninstall`,
    { method: "POST" }
  );
}

export function useMarketplacePlugins(params: MarketplaceParams = {}) {
  return useQuery({
    queryKey: ["marketplace", "plugins", params],
    queryFn: () => listMarketplacePlugins(params)
  });
}

export function useMarketplacePlugin(pluginId: string | null) {
  return useQuery({
    enabled: Boolean(pluginId),
    queryKey: ["marketplace", "plugins", pluginId],
    queryFn: () => getMarketplacePlugin(pluginId as string)
  });
}

export function useMarketplaceInstallations(params: MarketplaceParams = {}) {
  return useQuery({
    queryKey: ["marketplace", "installations", params],
    queryFn: () => listMarketplaceInstallations(params)
  });
}

export function useMarketplaceReviews(params: MarketplaceParams = {}) {
  return useQuery({
    queryKey: ["marketplace", "reviews", params],
    queryFn: () => listMarketplaceReviews(params)
  });
}

export function useMarketplaceSigningKeys() {
  return useQuery({
    queryKey: ["marketplace", "signing-keys"],
    queryFn: listMarketplaceSigningKeys
  });
}

export function useMarketplaceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["marketplace"] });
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    }
  });
}
