# Tool Gateway Implementation Plans

## Source Problem

These implementation plans break down `tool-gateway-problem.md` into atomic, independently testable work items.

The feature goal is to let external agent runtimes call protected business APIs through Ophanix, while Ophanix owns identity verification, tool contracts, allow or deny decisions, upstream routing, audit, and operator visibility.

## Folder Structure

- `01-tool-registry`: registered tool contracts, schemas, upstream targets, and target health.
- `02-auth-policy`: gateway authentication, agent-to-tool permissions, and policy decisions.
- `03-gateway-runtime`: invocation endpoint, upstream forwarding, response handling, and redaction.
- `04-audit-ui`: persisted runtime action records and decision visibility in the product UI.
- `05-sdk-integration`: optional SDK and direct HTTP integration assets for external teams.

## Plan Boundaries

Each document is intentionally small:

- It focuses on one task or component.
- It describes the expected product behavior and implementation surface.
- It can be tested with mocks, fixtures, or seeded data.
- It has a definition of done that does not depend on completing every other gateway plan.

## Recommended Build Order

1. `01-tool-registry/01-tool-contract-registry.md`
2. `01-tool-registry/02-upstream-target-health.md`
3. `02-auth-policy/01-gateway-token-verification.md`
4. `02-auth-policy/02-agent-tool-permission-bindings.md`
5. `02-auth-policy/03-tool-policy-decision.md`
6. `03-gateway-runtime/01-tool-invocation-endpoint.md`
7. `03-gateway-runtime/02-upstream-forwarding-adapter.md`
8. `03-gateway-runtime/03-response-handling-and-redaction.md`
9. `04-audit-ui/01-runtime-action-audit-store.md`
10. `04-audit-ui/02-tool-decision-feed-ui.md`
11. `05-sdk-integration/01-python-sdk-wrapper.md`
12. `05-sdk-integration/02-direct-http-integration-examples.md`

