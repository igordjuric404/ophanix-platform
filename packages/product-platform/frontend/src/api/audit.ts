import { apiClient, queryString } from "./client";

export interface AuditEvent {
  id: string;
  event_type: string;
  source_component?: string | null;
  actor_type?: string | null;
  actor_id?: string | null;
  agent_id?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  policy_id?: string | null;
  policy_version_id?: string | null;
  decision?: string | null;
  severity?: string | null;
  correlation_id?: string | null;
  payload_json?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface AuditVerification {
  valid: boolean;
  checked_count?: number;
  reason?: string | null;
}

export function getAuditEvent(eventId: string) {
  return apiClient.request<AuditEvent>(`/audit/events/${encodeURIComponent(eventId)}`);
}

export function verifyAuditEvent(eventId: string) {
  return apiClient.request<AuditVerification>(
    `/audit/events/${encodeURIComponent(eventId)}/verify`,
    { method: "POST" }
  );
}

export function listAuditEvents(params: Record<string, unknown> = {}) {
  return apiClient.request<AuditEvent[]>(`/audit/events${queryString(params)}`);
}
