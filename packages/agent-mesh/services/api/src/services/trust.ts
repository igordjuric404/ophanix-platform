// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import {
  TrustDimensionName,
  TrustDimensionScore,
  TrustScore,
  TrustTier,
} from "../types";

export const TRUST_SCORE_SCHEMA_VERSION = "trust.score.v1";
export const TRUST_SCORE_MIN = 0;
export const TRUST_SCORE_MAX = 1000;
export const TRUST_SCORE_BASELINE = 500;

export const TRUST_SCORE_DIMENSIONS: TrustDimensionName[] = [
  "policy_compliance",
  "resource_efficiency",
  "output_quality",
  "security_posture",
  "collaboration_health",
];

export const TRUST_SCORE_DIMENSION_LABELS: Record<TrustDimensionName, string> = {
  policy_compliance: "Policy Compliance",
  resource_efficiency: "Resource Efficiency",
  output_quality: "Output Quality",
  security_posture: "Security Posture",
  collaboration_health: "Collaboration Health",
};

export const TRUST_SCORE_TIER_THRESHOLDS: [TrustTier, number][] = [
  ["verified_partner", 900],
  ["trusted", 700],
  ["standard", 500],
  ["probationary", 300],
  ["untrusted", 0],
];

export const TRUST_SCORE_THRESHOLDS = [
  {
    threshold_type: "handoff",
    target_type: "environment",
    target_id: null,
    min_score: 700,
    required_tier: "trusted",
  },
  {
    threshold_type: "mcp_tool_use",
    target_type: "environment",
    target_id: null,
    min_score: 650,
    required_tier: "standard",
  },
  {
    threshold_type: "privileged_runtime_action",
    target_type: "environment",
    target_id: null,
    min_score: 850,
    required_tier: "trusted",
  },
  {
    threshold_type: "marketplace_install",
    target_type: "environment",
    target_id: null,
    min_score: 600,
    required_tier: "standard",
  },
] as const;

export function clampTrustScore(value: number): number {
  return Math.max(TRUST_SCORE_MIN, Math.min(TRUST_SCORE_MAX, Math.trunc(value)));
}

export function tierFromScore(score: number): TrustTier {
  const normalized = clampTrustScore(score);
  for (const [tier, threshold] of TRUST_SCORE_TIER_THRESHOLDS) {
    if (normalized >= threshold) return tier;
  }
  return "untrusted";
}

function baselineDimensions(): Record<TrustDimensionName, TrustDimensionScore> {
  return Object.fromEntries(
    TRUST_SCORE_DIMENSIONS.map((dimension) => [
      dimension,
      { score: TRUST_SCORE_BASELINE, signal_count: 0 },
    ]),
  ) as Record<TrustDimensionName, TrustDimensionScore>;
}

function explanationFor(
  dimensions: Record<TrustDimensionName, TrustDimensionScore>,
): TrustScore["explanation"] {
  return {
    schema_version: TRUST_SCORE_SCHEMA_VERSION,
    source_event_versions: ["audit_events.v1"],
    input_event_count: Object.values(dimensions).reduce(
      (total, dimension) => total + dimension.signal_count,
      0,
    ),
    dimensions,
  };
}

export function trustScoreContract() {
  return {
    schema_version: TRUST_SCORE_SCHEMA_VERSION,
    score_range: {
      min: TRUST_SCORE_MIN,
      max: TRUST_SCORE_MAX,
      baseline: TRUST_SCORE_BASELINE,
    },
    dimensions: TRUST_SCORE_DIMENSIONS.map((dimension) => ({
      name: dimension,
      label: TRUST_SCORE_DIMENSION_LABELS[dimension],
      default_score: TRUST_SCORE_BASELINE,
    })),
    tiers: TRUST_SCORE_TIER_THRESHOLDS.map(([name, min_score]) => ({
      name,
      min_score,
    })),
    thresholds: TRUST_SCORE_THRESHOLDS.map((threshold) => ({ ...threshold })),
  };
}

/** Create a default trust score for a newly registered agent. */
export function createInitialTrustScore(): TrustScore {
  const dimensions = baselineDimensions();
  return {
    schema_version: TRUST_SCORE_SCHEMA_VERSION,
    score: TRUST_SCORE_BASELINE,
    dimensions,
    tier: tierFromScore(TRUST_SCORE_BASELINE),
    explanation: explanationFor(dimensions),
    history: [
      {
        timestamp: new Date().toISOString(),
        event: "initial_registration",
        dimension: "security_posture",
        delta: 0,
        score_before: TRUST_SCORE_BASELINE,
        score_after: TRUST_SCORE_BASELINE,
        reason: "Initial trust score baseline.",
        source_event_version: "audit_events.v1",
      },
    ],
  };
}

/** Evaluate trust for a handshake: return granted capabilities. */
export function evaluateHandshake(
  agentCapabilities: string[],
  requestedCapabilities: string[],
  trustScore: TrustScore,
): string[] {
  const capSet = new Set(agentCapabilities);
  const eligible = requestedCapabilities.filter((capability) => capSet.has(capability));

  if (trustScore.score < 500) return [];

  return eligible;
}

/** Apply a trust event and recompute totals. */
export function applyTrustEvent(
  score: TrustScore,
  event: string,
  dimensionKey: TrustDimensionName,
  delta: number,
): TrustScore {
  const boundedDelta = Math.trunc(delta);
  const dimensions = {
    ...score.dimensions,
    [dimensionKey]: {
      score: clampTrustScore(score.dimensions[dimensionKey].score + boundedDelta),
      signal_count: score.dimensions[dimensionKey].signal_count + 1,
    },
  };
  const total = clampTrustScore(score.score + boundedDelta);
  return {
    schema_version: TRUST_SCORE_SCHEMA_VERSION,
    score: total,
    dimensions,
    tier: tierFromScore(total),
    explanation: explanationFor(dimensions),
    history: [
      ...score.history,
      {
        timestamp: new Date().toISOString(),
        event,
        dimension: dimensionKey,
        delta: boundedDelta,
        score_before: score.score,
        score_after: total,
        reason: `Mapped ${event} to trust signal.`,
        source_event_version: "audit_events.v1",
      },
    ],
  };
}
