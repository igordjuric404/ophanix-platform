# SDK-AUDIT-019 Research: Live Installed-Wheel-To-Running-Gateway CI Harness

## Problem

Current tests use in-process FastAPI `TestClient`, package-local SDK tests, and mocked transports. No CI job builds the standalone SDK wheel, installs it into a clean environment, starts a real product-platform gateway process, and calls it over a real socket.

Current limitations:

- Packaging errors can be missed.
- Import and dependency resolution from a built wheel are under-tested.
- ASGI server startup, sockets, middleware, and real HTTP behavior are not covered.
- SDK/server contract can drift while in-process tests still pass.
- No release gate proves a consumer can install the wheel and use it against a running gateway.

## Industry Pattern

Production SDKs usually have contract and smoke tests that:

- Build the distributable artifact.
- Install it into a clean virtual environment.
- Start the real server or a production-like test fixture.
- Exercise discovery, success, denial, errors, retries, headers, and auth over HTTP.
- Run in CI before publish.

AWS can host this in CodeBuild or GitHub Actions. For the current repo, GitHub Actions is already used, while AWS CodeBuild can later run the same script for release provenance.

## Options

### Option A: More Unit Tests

Benefits:

- Fast and simple.

Tradeoffs:

- Does not test wheel installation or real process networking.
- Does not catch server startup issues.

Decision: insufficient.

### Option B: Docker Compose Integration Test

Benefits:

- Real process isolation.
- Easy to include gateway, mock upstream, and PostgreSQL.

Tradeoffs:

- Slightly slower.
- Requires robust port allocation and cleanup.

Decision: adopt for local and CI integration.

### Option C: AWS CodeBuild-Only Harness

Benefits:

- AWS-native, clean ephemeral environment.
- Good release provenance.

Tradeoffs:

- Slower feedback than normal PR CI.
- Harder for contributors to run locally.

Decision: add later as release mirror. The first harness should run locally and in GitHub Actions.

## Final Architecture

Create a deterministic Python harness script that:

1. Builds the SDK wheel.
2. Creates a temporary virtual environment.
3. Installs the wheel with dependencies.
4. Starts the product-platform API with local test settings on a random port.
5. Seeds or provisions a gateway token, tool definition, permission, upstream target, and response policy.
6. Starts a local mock upstream HTTP server on a random port.
7. Runs SDK calls over a real TCP socket:
   - discovery;
   - successful tool invocation;
   - policy denial;
   - bad payload/schema error;
   - upstream failure;
   - redacted response;
   - idempotency replay after SDK-AUDIT-006.
8. Exits non-zero on any mismatch and always cleans up child processes.

## AWS Fit

AWS is not required for the core harness, because the goal is artifact-to-process contract validation. AWS-managed CI can run it unchanged:

- GitHub Actions for PR gating now.
- AWS CodeBuild as an optional release-stage runner later.
- Amazon ECR/ECS is not needed for this specific test.

No non-AWS service is selected. Local process orchestration is the industry-standard choice for SDK smoke tests.
