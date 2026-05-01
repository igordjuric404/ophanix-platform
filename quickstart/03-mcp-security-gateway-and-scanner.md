# MCP Security Gateway And Scanner

MCP security is about protecting the tool layer. MCP servers describe tools to
agents, and those descriptions become part of the model's operating context.
That makes tool metadata a supply-chain surface: a malicious server can hide
instructions, change schemas between runs, impersonate another tool, or expose
dangerous commands.

## Where It Lives

- [MCP security scanner](../packages/agent-os/src/agent_os/mcp_security.py)
- [MCP scan CLI](../packages/agent-os/src/agent_os/cli/mcp_scan.py)
- [MCP gateway](../packages/agent-os/src/agent_os/mcp_gateway.py)
- [MCP message signer](../packages/agent-os/src/agent_os/mcp_message_signer.py)
- [MCP session authenticator](../packages/agent-os/src/agent_os/mcp_session_auth.py)
- [MCP trusted server example](../examples/mcp-trust-verified-server/README.md)
- [MCP security tutorial](../docs/tutorials/07-mcp-security-gateway.md)
- [MCP scan CLI tutorial](../docs/tutorials/27-mcp-scan-cli.md)

## What It Checks

The scanner looks for several classes of MCP-specific risk:

- hidden instructions in descriptions,
- invisible Unicode and bidirectional text tricks,
- Markdown or HTML comments carrying instructions,
- encoded payloads,
- schema abuse, such as instruction-bearing defaults,
- data exfiltration language,
- privilege escalation wording,
- tool impersonation or typosquatting,
- rug pulls, where a tool's fingerprint changes after registration.

The simpler CLI scanner reads MCP config files and checks server command,
arguments, sensitive environment variable names, and fingerprints. The deeper
`MCPSecurityScanner` works at the tool-definition level.

## Session And Message Security

The MCP security layer is not just static scanning:

- `MCPSessionAuthenticator` issues short-lived tokens bound to an agent id and
  optional user id.
- It enforces session TTLs and max concurrent sessions per agent.
- `MCPMessageSigner` signs payloads with HMAC, timestamps, and nonces.
- Verification checks replay windows, duplicate nonces, and signatures, and
  fails closed on unexpected errors.

For Ophanix, this is a useful base for "governed MCP" as a product surface:
customers want to connect agents to tools, but they need visibility into what
those tools claim, what changed, and who was authorized to call them.

## Demos To Run

Install Agent OS locally first:

```bash
cd ophanix-platform
pip install -e packages/agent-os
```

Scan an MCP config:

```bash
python -m agent_os.cli.mcp_scan scan path/to/mcp.json
python -m agent_os.cli.mcp_scan report path/to/mcp.json --format markdown
python -m agent_os.cli.mcp_scan fingerprint path/to/mcp.json --output fingerprints.json
python -m agent_os.cli.mcp_scan fingerprint path/to/mcp.json --compare fingerprints.json
```

Try the trusted MCP example:

```bash
cd ophanix-platform/examples/mcp-trust-verified-server
cat README.md
```

That example README is the best entry point because MCP server setup is usually
environment-specific.

## What To Remember

MCP governance has two halves. The first half is "is this server/tool definition
safe enough to register?" The second half is "is this specific caller allowed
to invoke this specific tool right now?" Ophanix should treat both as first
class product flows.
