import { describe, expect, it } from "vitest";

import {
  canActivateAgent,
  canAddRuntimeSagaStep,
  canAdvanceRollout,
  canArchiveAgent,
  canApproveAgent,
  canCancelRuntimeSaga,
  canEndRuntimeSession,
  canExecuteRuntimeSaga,
  canQuarantineAgent,
  canRestrictAgent,
  canRevokeAgent,
  canRevokeCredential,
  canRevokeTrustCard,
  canRollbackRollout,
  canRunChaosExperiment,
  canSuspendAgent
} from "./actionAvailability";

describe("action availability", () => {
  it("matches backend agent lifecycle transitions", () => {
    expect(canApproveAgent({ status: "pending_approval" })).toBe(true);
    expect(canApproveAgent({ status: "active" })).toBe(false);
    expect(canActivateAgent({ status: "provisioned" })).toBe(true);
    expect(canActivateAgent({ status: "pending_approval" })).toBe(false);
    expect(canSuspendAgent({ status: "active" })).toBe(true);
    expect(canSuspendAgent({ status: "suspended" })).toBe(false);
    expect(canRestrictAgent({ status: "active" })).toBe(true);
    expect(canRestrictAgent({ status: "revoked" })).toBe(false);
    expect(canQuarantineAgent({ status: "restricted" })).toBe(true);
    expect(canQuarantineAgent({ status: "revoked" })).toBe(false);
    expect(canRevokeAgent({ status: "quarantined" })).toBe(true);
    expect(canRevokeAgent({ status: "archived" })).toBe(false);
    expect(canArchiveAgent({ status: "revoked" })).toBe(true);
    expect(canArchiveAgent({ status: "active" })).toBe(false);
  });

  it("blocks non-actionable credential and trust-card operations", () => {
    expect(canRevokeCredential({ status: "active" })).toBe(true);
    expect(canRevokeCredential({ status: "expiring_soon" })).toBe(false);
    expect(canRevokeCredential({ status: "revoked" })).toBe(false);
    expect(canRevokeTrustCard({ status: "active" })).toBe(true);
    expect(canRevokeTrustCard({ status: "revoked" })).toBe(false);
  });

  it("blocks terminal runtime session and saga actions", () => {
    expect(canEndRuntimeSession({ state: "active", ended_at: null })).toBe(true);
    expect(canEndRuntimeSession({ state: "archived", ended_at: "2026-05-01T00:00:00Z" })).toBe(false);
    expect(canAddRuntimeSagaStep({ status: "draft" })).toBe(true);
    expect(canAddRuntimeSagaStep({ status: "running" })).toBe(false);
    expect(canExecuteRuntimeSaga({ status: "running" })).toBe(false);
    expect(canExecuteRuntimeSaga({ status: "failed" })).toBe(false);
    expect(canExecuteRuntimeSaga({ status: "draft" })).toBe(true);
    expect(canCancelRuntimeSaga({ status: "running" })).toBe(true);
    expect(canCancelRuntimeSaga({ status: "completed" })).toBe(false);
  });

  it("gates observability operations by operational state", () => {
    expect(canRunChaosExperiment({ status: "ready" })).toBe(true);
    expect(canRunChaosExperiment({ status: "disabled" })).toBe(false);
    expect(canAdvanceRollout({ status: "active" })).toBe(true);
    expect(canAdvanceRollout({ status: "complete" })).toBe(false);
    expect(canAdvanceRollout({ status: "completed" })).toBe(false);
    expect(canRollbackRollout({ status: "completed" })).toBe(true);
    expect(canRollbackRollout({ status: "rolled_back" })).toBe(false);
  });
});
