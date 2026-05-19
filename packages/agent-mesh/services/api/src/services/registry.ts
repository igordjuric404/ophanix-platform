// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { AgentRecord, RegisterRequest } from "../types";
import { generateDid, generateApiKey } from "./identity";
import { createInitialTrustScore } from "./trust";
import { appendAuditEntry } from "./audit";

/** In-memory agent registry keyed by DID. */
const agents = new Map<string, AgentRecord>();

/** API key -> DID index for fast lookup. */
const apiKeyIndex = new Map<string, string>();

export function registerAgent(req: RegisterRequest): AgentRecord {
  const did = generateDid();
  const apiKey = generateApiKey();
  const capabilities = [...new Set(req.capabilities.map((capability) => capability.trim()))]
    .filter(Boolean)
    .sort();

  const record: AgentRecord = {
    did,
    name: req.name.trim(),
    sponsor_email: req.sponsor_email.trim(),
    capabilities,
    public_key: req.public_key,
    api_key: apiKey,
    status: "active",
    trust_score: createInitialTrustScore(),
    registered_at: new Date().toISOString(),
    last_seen: new Date().toISOString(),
  };

  agents.set(did, record);
  apiKeyIndex.set(apiKey, did);

  appendAuditEntry("agent_registered", did, {
    name: record.name,
    sponsor_email: record.sponsor_email,
    capabilities: record.capabilities,
  });

  return record;
}

export function getAgent(did: string): AgentRecord | undefined {
  return agents.get(did);
}

export function getAgentByApiKey(apiKey: string): AgentRecord | undefined {
  const did = apiKeyIndex.get(apiKey);
  return did ? agents.get(did) : undefined;
}

export function isValidApiKey(apiKey: string): boolean {
  return apiKeyIndex.has(apiKey);
}

export function updateLastSeen(did: string): void {
  const agent = agents.get(did);
  if (agent) {
    agent.last_seen = new Date().toISOString();
  }
}

/** Reset registry (for testing). */
export function resetRegistry(): void {
  agents.clear();
  apiKeyIndex.clear();
}
