// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
export interface AgentRecord {
  did: string;
  name: string;
  sponsor_email: string;
  capabilities: string[];
  public_key: string;
  api_key: string;
  status: "active" | "suspended" | "revoked";
  trust_score: TrustScore;
  registered_at: string;
  last_seen: string;
}

export type TrustTier =
  | "verified_partner"
  | "trusted"
  | "standard"
  | "probationary"
  | "untrusted";

export type TrustDimensionName =
  | "policy_compliance"
  | "resource_efficiency"
  | "output_quality"
  | "security_posture"
  | "collaboration_health";

export interface TrustDimensionScore {
  score: number;
  signal_count: number;
}

export interface TrustScoreExplanation {
  schema_version: string;
  source_event_versions: string[];
  input_event_count: number;
  dimensions: Record<TrustDimensionName, TrustDimensionScore>;
}

export interface TrustScore {
  schema_version: string;
  score: number;
  dimensions: Record<TrustDimensionName, TrustDimensionScore>;
  tier: TrustTier;
  explanation: TrustScoreExplanation;
  history: TrustEvent[];
}

export interface TrustEvent {
  timestamp: string;
  event: string;
  dimension: TrustDimensionName;
  delta: number;
  score_before: number;
  score_after: number;
  reason: string;
  source_event_version: "audit_events.v1";
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  action: string;
  agent_did: string;
  details: Record<string, unknown>;
  previous_hash: string;
  hash: string;
}

export interface RegisterRequest {
  name: string;
  sponsor_email: string;
  capabilities: string[];
  public_key: string;
  registration_signature: string;
}

export interface RegisterResponse {
  agent_did: string;
  api_key: string;
  public_key: string;
  verification_url: string;
}

export interface VerifyResponse {
  registered: boolean;
  status: string;
  trust_score?: number;
  sponsor?: string;
  capabilities?: string[];
}

export interface HandshakeRequest {
  agent_did: string;
  challenge_id: string;
  nonce: string;
  audience: string;
  environment_id: string;
  expires_at: string;
  contract_version: string;
  signature_algorithm: "ed25519";
  signature: string;
  public_key: string;
  capabilities_requested: string[];
}

export interface HandshakeChallengeRequest {
  agent_did: string;
  target_agent_did?: string;
  audience: string;
  environment_id: string;
  purpose?: string;
  capabilities_requested: string[];
  expires_in_seconds?: number;
}

export interface HandshakeChallengeResponse {
  challenge_id: string;
  nonce: string;
  audience: string;
  environment_id: string;
  agent_did: string;
  target_agent_did?: string;
  purpose: string;
  contract_version: string;
  signature_algorithm: "ed25519";
  expires_at: string;
  canonical_payload: string;
}

export interface HandshakeResponse {
  verified: boolean;
  trust_score: number;
  capabilities_granted: string[];
  signature_verified: boolean;
  challenge_id: string;
  contract_version: string;
  audience: string;
  expires_at: string;
}

export type ScoreResponse = TrustScore;
