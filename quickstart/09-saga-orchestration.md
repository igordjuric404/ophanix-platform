# Saga Orchestration

Saga orchestration is how the runtime handles multi-step agent workflows that
can partially fail. If an agent books a flight, reserves a hotel, charges a
card, and then fails the final step, you need a structured way to undo what was
already committed.

## Where It Lives

- [Saga orchestrator](../packages/agent-hypervisor/src/hypervisor/saga/orchestrator.py)
- [Saga state machine](../packages/agent-hypervisor/src/hypervisor/saga/state_machine.py)
- [Saga DSL parser](../packages/agent-hypervisor/src/hypervisor/saga/dsl.py)
- [Checkpoint manager](../packages/agent-hypervisor/src/hypervisor/saga/checkpoint.py)
- [Fan-out support](../packages/agent-hypervisor/src/hypervisor/saga/fan_out.py)
- [Saga tutorial](../docs/tutorials/11-saga-orchestration.md)
- [Feature deep dive](../features/saga-orchestration/technical-deep-dive.md)

## The Problem It Solves

AI agents often perform business workflows made of tool calls. Normal exception
handling is too weak because each tool call can mutate external state. Saga
orchestration gives each step:

- an `execute_api`,
- optional `undo_api`,
- timeout,
- retry count,
- state transition history.

If a later step fails, committed steps are compensated in reverse order.

## State Machines

Step states:

- `pending`
- `executing`
- `committed`
- `compensating`
- `compensated`
- `compensation_failed`
- `failed`

Saga states:

- `running`
- `compensating`
- `completed`
- `failed`
- `escalated`

Invalid transitions raise `SagaStateError`. That matters because the workflow
state is evidence, not just control flow.

## Orchestrator Flow

1. Create a saga for a session.
2. Add ordered steps.
3. Execute a step with timeout and retry support.
4. Mark successful steps as committed.
5. If a step fails after retries, call `compensate()`.
6. Compensation walks committed steps in reverse order.
7. Missing or failing undo APIs produce `compensation_failed`.
8. If compensation fails, the saga moves to `escalated`.

In the comments, escalation is where joint liability or human intervention
would be triggered.

## DSL And Checkpoints

The DSL parser accepts a dict with `name`, `session_id`, and `steps`. It validates
basic fields and converts definitions into `SagaStep` objects. Fan-out groups
are parsed in some docs, but the current public-preview parser treats execution
as sequential.

The checkpoint manager records semantic checkpoints, but replay/skip logic is
stubbed in Public Preview. It stores checkpoints for visibility; it does not yet
skip completed goals during replay.

## Demos To Run

The hypervisor README has an end-to-end saga snippet:

```bash
cd ophanix-platform
cat packages/agent-hypervisor/README.md
```

For a deeper tutorial:

```bash
cd ophanix-platform
cat docs/tutorials/11-saga-orchestration.md
```

The smallest code path to read is [orchestrator.py](../packages/agent-hypervisor/src/hypervisor/saga/orchestrator.py).

## What To Remember

Sagas make agent workflows product-safe by requiring an undo story. For Ophanix,
this can become a strong differentiator: before an agent gets permission for a
multi-step workflow, require the workflow to declare its compensation paths.
