// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import * as crypto from "crypto";
import { Router, Request, Response } from "express";
import { getAgent } from "../services/registry";
import {
  CANONICAL_HANDSHAKE_CONTRACT_VERSION,
  canonicalHandshakePayload,
  verify,
} from "../services/identity";
import { evaluateHandshake } from "../services/trust";
import { appendAuditEntry } from "../services/audit";
import {
  HandshakeChallengeRequest,
  HandshakeChallengeResponse,
  HandshakeRequest,
  HandshakeResponse,
} from "../types";

const router = Router();

interface StoredHandshakeChallenge extends HandshakeChallengeResponse {
  consumed_at?: string;
}

const challenges = new Map<string, StoredHandshakeChallenge>();

function error(res: Response, status: number, message: string): void {
  res.status(status).json({ error: message, verified: false });
}

function authenticatedAgentMatches(req: Request, agentDid: string, res: Response): boolean {
  if (!req.authenticatedAgent) {
    error(res, 401, "Authentication is required");
    return false;
  }
  if (req.authenticatedAgent.did !== agentDid) {
    error(res, 403, "API key is not authorized for this agent");
    return false;
  }
  return true;
}

router.post("/handshake/challenges", (req: Request, res: Response) => {
  const {
    agent_did,
    target_agent_did,
    audience,
    environment_id,
    purpose = "handshake",
    capabilities_requested,
    expires_in_seconds = 30,
  } = req.body as Partial<HandshakeChallengeRequest>;

  if (!agent_did || typeof agent_did !== "string") {
    error(res, 400, "agent_did is required");
    return;
  }
  if (!audience || typeof audience !== "string") {
    error(res, 400, "audience is required");
    return;
  }
  if (!environment_id || typeof environment_id !== "string") {
    error(res, 400, "environment_id is required");
    return;
  }
  if (!Array.isArray(capabilities_requested)) {
    error(res, 400, "capabilities_requested must be an array");
    return;
  }
  if (expires_in_seconds < 5 || expires_in_seconds > 300) {
    error(res, 400, "expires_in_seconds must be between 5 and 300");
    return;
  }
  if (!authenticatedAgentMatches(req, agent_did, res)) {
    return;
  }

  const agent = getAgent(agent_did);
  if (!agent) {
    error(res, 404, "Agent not found");
    return;
  }
  if (agent.status !== "active") {
    error(res, 403, "Agent is not active");
    return;
  }

  const challengeId = `hchal_${crypto.randomUUID()}`;
  const nonce = crypto.randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + expires_in_seconds * 1000).toISOString();
  const canonicalPayload = canonicalHandshakePayload({
    challenge_id: challengeId,
    nonce,
    audience,
    environment_id,
    source_agent_id: agent_did,
    source_did: agent_did,
    target_agent_id: target_agent_did ?? null,
    target_did: target_agent_did ?? null,
    purpose,
    threshold_type: "handshake",
    target_type: "agent",
    target_id: target_agent_did ?? null,
    expires_at: expiresAt,
  });
  const challenge: StoredHandshakeChallenge = {
    challenge_id: challengeId,
    nonce,
    audience,
    environment_id,
    agent_did,
    target_agent_did,
    purpose,
    contract_version: CANONICAL_HANDSHAKE_CONTRACT_VERSION,
    signature_algorithm: "ed25519",
    expires_at: expiresAt,
    canonical_payload: canonicalPayload,
  };
  challenges.set(challengeId, challenge);
  appendAuditEntry("handshake_challenge_issued", agent_did, {
    challenge_id: challengeId,
    audience,
    environment_id,
    target_agent_did,
    expires_at: expiresAt,
  });
  res.status(201).json(challenge);
});

router.post("/handshake", (req: Request, res: Response) => {
  const {
    agent_did,
    challenge_id,
    nonce,
    audience,
    environment_id,
    expires_at,
    contract_version,
    signature_algorithm,
    signature,
    public_key,
    capabilities_requested,
  } = req.body as Partial<HandshakeRequest>;

  if (!agent_did || typeof agent_did !== "string") {
    error(res, 400, "agent_did is required");
    return;
  }
  if (!challenge_id || typeof challenge_id !== "string") {
    error(res, 400, "challenge_id is required");
    return;
  }
  if (!nonce || typeof nonce !== "string") {
    error(res, 400, "nonce is required");
    return;
  }
  if (!audience || typeof audience !== "string") {
    error(res, 400, "audience is required");
    return;
  }
  if (!environment_id || typeof environment_id !== "string") {
    error(res, 400, "environment_id is required");
    return;
  }
  if (!expires_at || typeof expires_at !== "string") {
    error(res, 400, "expires_at is required");
    return;
  }
  if (contract_version !== CANONICAL_HANDSHAKE_CONTRACT_VERSION) {
    error(res, 400, "unsupported handshake contract");
    return;
  }
  if (signature_algorithm !== "ed25519") {
    error(res, 400, "unsupported signature algorithm");
    return;
  }
  if (!signature || typeof signature !== "string") {
    error(res, 400, "signature is required");
    return;
  }
  if (!public_key || typeof public_key !== "string") {
    error(res, 400, "public_key is required");
    return;
  }
  if (!Array.isArray(capabilities_requested)) {
    error(res, 400, "capabilities_requested must be an array");
    return;
  }
  if (!authenticatedAgentMatches(req, agent_did, res)) {
    return;
  }

  const agent = getAgent(agent_did);
  if (!agent) {
    error(res, 404, "Agent not found");
    return;
  }
  if (agent.status !== "active") {
    error(res, 403, "Agent is not active");
    return;
  }

  const challenge = challenges.get(challenge_id);
  if (!challenge) {
    error(res, 404, "Challenge not found");
    return;
  }
  if (challenge.consumed_at) {
    error(res, 409, "Challenge has already been used");
    return;
  }
  if (challenge.agent_did !== agent_did) {
    error(res, 403, "Challenge is not bound to this agent");
    return;
  }
  if (challenge.nonce !== nonce) {
    error(res, 400, "nonce does not match issued challenge");
    return;
  }
  if (challenge.audience !== audience) {
    error(res, 400, "audience does not match issued challenge");
    return;
  }
  if (challenge.environment_id !== environment_id) {
    error(res, 400, "environment_id does not match issued challenge");
    return;
  }
  if (challenge.expires_at !== expires_at) {
    error(res, 400, "expires_at does not match issued challenge");
    return;
  }
  if (Date.parse(challenge.expires_at) <= Date.now()) {
    error(res, 401, "Challenge expired");
    return;
  }

  challenge.consumed_at = new Date().toISOString();

  if (public_key !== agent.public_key) {
    error(res, 401, "Public key mismatch");
    return;
  }
  if (!verify(challenge.canonical_payload, signature, agent.public_key)) {
    error(res, 401, "Signature verification failed");
    return;
  }

  const granted = evaluateHandshake(
    agent.capabilities,
    capabilities_requested,
    agent.trust_score,
  );

  appendAuditEntry("handshake", agent_did, {
    challenge_id,
    audience,
    environment_id,
    capabilities_requested,
    capabilities_granted: granted,
    contract_version,
  });

  const response: HandshakeResponse = {
    verified: true,
    trust_score: agent.trust_score.score,
    capabilities_granted: granted,
    signature_verified: true,
    challenge_id,
    contract_version,
    audience,
    expires_at,
  };

  res.json(response);
});

export function resetHandshakeChallenges(): void {
  challenges.clear();
}

export default router;
