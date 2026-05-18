interface StatusLike {
  status?: string | null;
}

interface RuntimeSessionLike {
  ended_at?: string | null;
  state?: string | null;
}

const activeCredentialStatuses = new Set(["active"]);
const terminalRuntimeSessionStates = new Set([
  "archived",
  "cancelled",
  "canceled",
  "completed",
  "ended",
  "failed",
  "terminated"
]);
const terminalSagaStatuses = new Set([
  "cancelled",
  "compensated",
  "compensation_failed",
  "completed",
  "failed"
]);
const executingSagaStatuses = new Set(["compensating", "running"]);
const blockedRolloutStatuses = new Set(["cancelled", "canceled", "complete", "completed", "rolled_back"]);

export function canApproveAgent(agent: StatusLike | null | undefined) {
  return normalizedStatus(agent?.status) === "pending_approval";
}

export function canActivateAgent(agent: StatusLike | null | undefined) {
  return normalizedStatus(agent?.status) === "provisioned";
}

export function canSuspendAgent(agent: StatusLike | null | undefined) {
  return normalizedStatus(agent?.status) === "active";
}

export function canIssueAgentCredential(agent: StatusLike | null | undefined) {
  return normalizedStatus(agent?.status) === "active";
}

export function canRotateCredential(credential: StatusLike | null | undefined) {
  return activeCredentialStatuses.has(normalizedStatus(credential?.status));
}

export function canRevokeCredential(credential: StatusLike | null | undefined) {
  return activeCredentialStatuses.has(normalizedStatus(credential?.status));
}

export function canEndRuntimeSession(session: RuntimeSessionLike | null | undefined) {
  return Boolean(session && !session.ended_at && !terminalRuntimeSessionStates.has(normalizedStatus(session.state)));
}

export function canAddRuntimeSagaStep(saga: StatusLike | null | undefined) {
  return normalizedStatus(saga?.status) === "draft";
}

export function canExecuteRuntimeSaga(saga: StatusLike | null | undefined) {
  const status = normalizedStatus(saga?.status);
  return Boolean(saga && !executingSagaStatuses.has(status) && !terminalSagaStatuses.has(status));
}

export function canCancelRuntimeSaga(saga: StatusLike | null | undefined) {
  return Boolean(saga && !terminalSagaStatuses.has(normalizedStatus(saga.status)));
}

export function canRevokeTrustCard(card: StatusLike | null | undefined) {
  return Boolean(card && normalizedStatus(card.status) !== "revoked");
}

export function canRunChaosExperiment(experiment: StatusLike | null | undefined) {
  return ["active", "ready"].includes(normalizedStatus(experiment?.status));
}

export function canAdvanceRollout(rollout: StatusLike | null | undefined) {
  return Boolean(rollout && !blockedRolloutStatuses.has(normalizedStatus(rollout.status)));
}

export function canRollbackRollout(rollout: StatusLike | null | undefined) {
  return Boolean(rollout && !["cancelled", "canceled", "rolled_back"].includes(normalizedStatus(rollout.status)));
}

function normalizedStatus(value: string | null | undefined) {
  return String(value ?? "").trim().toLowerCase();
}
