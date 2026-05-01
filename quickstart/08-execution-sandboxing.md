# Execution Sandboxing

Execution sandboxing is the defense-in-depth layer for agent code and tool
execution. It deals with the uncomfortable reality that a governed agent can
still try to bypass the nice path: import `subprocess`, call `os.system`, open a
socket, or generate code that does something outside policy.

## Where It Lives

- [Agent OS sandbox](../packages/agent-os/src/agent_os/sandbox.py)
- [Sandbox provider interface](../packages/agent-os/src/agent_os/sandbox_provider.py)
- [Runtime deployers](../packages/agent-runtime/src/agent_runtime/deploy.py)
- [Execution sandboxing tutorial](../docs/tutorials/06-execution-sandboxing.md)
- [Feature deep dive](../features/execution-sandboxing/technical-deep-dive.md)

## Current Implementation

There are two related pieces:

1. Agent OS static/runtime checks:
   - blocks dangerous imports with an import hook,
   - scans Python AST for blocked modules and builtins,
   - detects calls like `eval`, `exec`, `compile`, `__import__`, and
     `os.system`,
   - loads sandbox security settings from YAML.
2. Pluggable execution providers:
   - `SandboxProvider` defines `run()` and `is_available()`,
   - `SubprocessSandboxProvider` captures output and enforces timeout, but is
     not strong security isolation,
   - `NoOpSandboxProvider` is for tests.

The feature deep dive describes stronger OS/container isolation patterns such as
namespaces, cgroups, seccomp, AppArmor, SELinux, containers, and gVisor. Treat
those as target architecture unless you see the provider implemented in
`packages/`.

## Deployment Runtime

`agent_runtime.deploy` adds practical deployment controls for Docker and
Kubernetes:

- Docker deployer drops all Linux capabilities,
- enables `no-new-privileges`,
- uses read-only root filesystem,
- mounts `/tmp` as tmpfs with `noexec,nosuid`,
- injects governance config through environment variables,
- labels containers with `agt.agent-id` and `agt.managed`.

The Kubernetes deployer builds pods with non-root security context, dropped
capabilities, read-only root filesystem, resource requests, and governance env
vars.

## How It Fits With Rings

Rings decide what kind of action an agent may attempt. Sandboxing constrains
what happens if the process tries to do more than the approved action. You want
both:

- Ring 3 says "read-only research."
- Sandbox says "no subprocess, no socket, no write path, no arbitrary import."
- Audit says "record the attempt if the agent tries anyway."

## Demos To Run

Read the tutorial first:

```bash
cd ophanix-platform
cat docs/tutorials/06-execution-sandboxing.md
```

Try the AST/import-hook path in a Python shell after installing Agent OS:

```python
from agent_os.sandbox import ExecutionSandbox, SandboxConfig

sandbox = ExecutionSandbox(SandboxConfig())
print(sandbox.validate_code("print('safe')"))
print(sandbox.validate_code("import subprocess"))
```

`validate_code()` returns a list of `SecurityViolation` objects. An empty list
means no static violation was found.

## What To Remember

Do not overclaim the current sandbox. The public-preview subprocess provider is
not a secure isolation boundary. The useful Ophanix product framing is layered:
static checks, policy checks, ring checks, process/container controls, and
auditable denial.
