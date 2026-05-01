# Framework Integrations

Framework integrations are how the toolkit gets into the hot path of real
agents. The toolkit does not replace LangChain, CrewAI, AutoGen, Microsoft Agent
Framework, OpenAI Agents, or Google ADK. It wraps their execution points:
agent invocations, tool calls, handoffs, streaming events, and middleware hooks.

## Where It Lives

- [MAF adapter](../packages/agent-os/src/agent_os/integrations/maf_adapter.py)
- [OpenAI Agents adapter](../packages/agent-os/src/agent_os/integrations/openai_agents_sdk.py)
- [LangChain adapter](../packages/agent-os/src/agent_os/integrations/langchain_adapter.py)
- [CrewAI adapter](../packages/agent-os/src/agent_os/integrations/crewai_adapter.py)
- [AutoGen adapter](../packages/agent-os/src/agent_os/integrations/autogen_adapter.py)
- [Google ADK adapter](../packages/agent-os/src/agent_os/integrations/google_adk_adapter.py)
- [Framework quickstart examples](../examples/quickstart/README.md)
- [Framework integration tutorial](../docs/tutorials/03-framework-integrations.md)

## The Core Pattern

Every integration follows the same shape:

1. Load or create a governance policy.
2. Install a wrapper or middleware around the framework.
3. Convert framework-specific events into a common governance context.
4. Ask the policy engine, capability guard, trust layer, or SRE detector for a
   decision.
5. Continue if allowed, short-circuit if denied, and write an audit event.

The adapter is mostly translation glue. The important product idea is that the
agent author keeps using the framework they already know while Ophanix gets a
deterministic decision point before risky behavior happens.

## Microsoft Agent Framework Adapter

The MAF adapter is the clearest implementation to read. It exposes four
middleware classes:

- `GovernancePolicyMiddleware`: evaluates declarative policy before the agent
  runs.
- `CapabilityGuardMiddleware`: allows or denies individual function/tool calls.
- `AuditTrailMiddleware`: records pre-execution and post-execution audit events.
- `RogueDetectionMiddleware`: feeds tool behavior into the rogue-agent detector
  and can quarantine high-risk agents.

The live demo in [demo/maf_governance_demo.py](../demo/maf_governance_demo.py)
uses those layers together.

## OpenAI Agents Adapter

The OpenAI Agents integration wraps an agent and runner. It tracks:

- total tool calls,
- handoff count,
- execution timeout,
- blocked tools,
- blocked content patterns,
- optional human approval,
- audit events in an execution context.

The code is intentionally lightweight, which makes it useful as a template for
your own adapters.

## Demos To Run

```bash
cd ophanix-platform

python examples/quickstart/langchain_governed.py
python examples/quickstart/crewai_governed.py
python examples/quickstart/autogen_governed.py
python examples/quickstart/google_adk_governed.py
python examples/quickstart/openai_agents_governed.py
```

Some of those examples may require provider credentials depending on the
framework path they exercise. The root example README calls this out:
[examples/quickstart/README.md](../examples/quickstart/README.md).

For Microsoft Agent Framework scenarios:

```bash
cd ophanix-platform
python demo/maf_governance_demo.py
```

There are also scenario-specific MAF examples:

```bash
cd ophanix-platform/examples/maf-integration/01-loan-processing/python
pip install -r requirements.txt
python main.py
```

The same scenario set has .NET projects under each `dotnet/` folder.

## How To Think About Ophanix Integration Work

When adding Ophanix to a new framework, look for the narrowest hook that sees
the action before it happens. For chat-only frameworks, that might be a message
middleware. For tool-heavy frameworks, it should be the function invocation
hook. For multi-agent frameworks, you also need handoff and peer-message hooks.
The adapter should avoid owning business logic; it should normalize context,
call governance, and enforce the result.
