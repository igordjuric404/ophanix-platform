# Policy Simulator And Evaluation Feed Execution Log

Source plan: `docs/product-platform-worktree/02-policy-governance/01-policy-management/04-policy-simulator-evaluation-feed.md`

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Evaluation Adapter | Evaluate product contexts through active policy versions and normalize decisions. | Not Started | Load active version; context mapping; decision/latency capture; backend hook. |
| Phase 2: Persisted Evaluations | Store simulator/live evaluations and emit live audit events. | Not Started | Evaluation table; mode flag; correlation id; filters. |
| Phase 3: Simulator UI | Build a form-driven policy simulator. | Not Started | Agent/action/resource form; JSON validation; decision output; reusable scenario placeholder. |
| Phase 4: Evaluation Feed UI | Build filterable decision feed with charts and live updates. | Not Started | Table; charts; detail drawer; SSE update handling. |

## Detailed Checklist

### Phase 1: Evaluation Adapter

- [ ] Implement evaluation adapter module.
- [ ] Load selected or active policy version body.
- [ ] Parse YAML/JSON policy documents.
- [ ] Convert product context to evaluator input.
- [ ] Capture decision, matched rule, reason, and latency.
- [ ] Fail closed on evaluation errors.
- [ ] Keep backend hook for OPA/Cedar.
- [ ] Test allow decision.
- [ ] Test deny decision.
- [ ] Test evaluation failure fails closed.
- [ ] Test latency captured.

### Phase 2: Persisted Evaluations

- [ ] Add `policy_evaluations` table.
- [ ] Add repository create/get/list operations.
- [ ] Persist simulator evaluations.
- [ ] Persist live evaluations.
- [ ] Emit audit event for live evaluation.
- [ ] Include correlation id in storage and API responses.
- [ ] Add `POST /api/v1/policy-evaluations/simulate`.
- [ ] Add `POST /api/v1/policy-evaluations/evaluate`.
- [ ] Add `GET /api/v1/policy-evaluations`.
- [ ] Add `GET /api/v1/policy-evaluations/{id}`.
- [ ] Test evaluation persistence.
- [ ] Test live evaluation emits audit event.
- [ ] Test API filters by decision and agent.

### Phase 3: Simulator UI

- [ ] Add frontend API client methods.
- [ ] Build simulator form for agent, action, resource, policy version, and context JSON.
- [ ] Validate JSON before submit.
- [ ] Render decision, matched rule, reason, latency, and audit preview.
- [ ] Include save-scenario placeholder without pretending persistence exists.
- [ ] Component test invalid JSON blocks submit.
- [ ] Component test deny result renders matched rule.
- [ ] Component test agent selector filters by environment.

### Phase 4: Evaluation Feed UI

- [ ] Build evaluation table with filters.
- [ ] Add decision trend summaries by time and action.
- [ ] Use shared drawer for evaluation details.
- [ ] Add live update stream hook based on existing audit streaming conventions.
- [ ] Component test feed renders rows.
- [ ] Component test decision filter calls API.
- [ ] Integration UI test receives live update when stream emits evaluation.

## Progress Notes

- 2026-05-01: Created initial execution log from the implementation plan.
