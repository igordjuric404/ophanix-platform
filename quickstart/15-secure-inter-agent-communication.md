# Secure Inter-Agent Communication

Secure inter-agent communication governs what happens when one agent talks to
another. In a multi-agent product, this is a trust boundary. The receiving
agent may be built by a different team, run in a different runtime, hold
different capabilities, or act on behalf of a different user.

The platform's communication model is: verify peer identity, check trust,
check capabilities, translate protocols if needed, then send.

## Where It Lives

- [Trust bridge](../packages/agent-mesh/src/agentmesh/trust/bridge.py)
- [Trust handshake](../packages/agent-mesh/src/agentmesh/trust/handshake.py)
- [WebSocket transport](../packages/agent-mesh/src/agentmesh/transport/websocket.py)
- [MCP message signer](../packages/agent-os/src/agent_os/mcp_message_signer.py)
- [MCP session auth](../packages/agent-os/src/agent_os/mcp_session_auth.py)
- [Feature deep dive](../features/secure-inter-agent-communication/technical-deep-dive.md)
- [Multi-vendor example](../packages/agent-mesh/examples/07-multi-vendor-collaboration/README.md)

## Main Pieces

`TrustHandshake` verifies a peer before communication. It checks:

- DID shape, currently expecting `did:mesh:...`,
- registry membership,
- Ed25519 challenge/response,
- trust score threshold,
- required capabilities,
- cache freshness,
- timeout limits.

`TrustBridge` stores verified peers and checks cached peer records before reuse.
It protects cached peer records with an HMAC over critical fields so a tampered
trust score or capability list is rejected.

`ProtocolBridge` wraps sending. Before sending a message, it checks whether the
peer is trusted. If not, it attempts verification. If verification fails, it
raises `PermissionError`.

`WebSocketTransport` is a lower-level transport for real-time messaging. It
adds connection state, heartbeat pings, reconnect logic, receive queues, and
trust-update subscriptions.

For MCP-specific communication, Agent OS also includes:

- HMAC message signing,
- timestamp and nonce checks,
- replay protection,
- short-lived session tokens,
- concurrent-session limits.

## What The Trust Bridge Actually Does

At a high level:

```python
from agentmesh.trust.bridge import TrustBridge

bridge = TrustBridge(agent_did="did:mesh:agent-a", registry=registry)

result = await bridge.verify_peer(
    peer_did="did:mesh:agent-b",
    protocol="iatp",
    required_trust_score=700,
    required_capabilities=["read:customer"],
)

if result.verified:
    print(result.trust_level, result.capabilities)
```

After verification, `is_peer_trusted()` checks:

- the peer exists,
- the peer was verified,
- the HMAC-protected cached record has not been modified,
- the score still meets the threshold.

If the cached record fails integrity verification, the bridge deletes it and
rejects the peer.

## Protocol Translation

`ProtocolBridge` supports the protocol names:

- `a2a`,
- `mcp`,
- `iatp`,
- `acp`.

The current implementation is a basic public-preview bridge. It preserves the
API surface and includes simple protocol conversion hooks, but you should
inspect [bridge.py](../packages/agent-mesh/src/agentmesh/trust/bridge.py)
before assuming it performs a full production-grade translation between all
protocol semantics.

## WebSocket Transport

The WebSocket transport is useful for live agent meshes where peers need
streaming updates:

- connect to `ws://` or `wss://`,
- send JSON messages by topic,
- receive queued messages,
- subscribe to trust updates for a DID,
- reconnect with exponential backoff,
- restore trust subscriptions after reconnect.

Install the optional dependency first:

```bash
pip install websockets
```

## Demos To Run

The best demo for this feature is the multi-vendor collaboration example. It is
mocked, so no API keys are required:

```bash
cd ophanix-platform/packages/agent-mesh/examples/07-multi-vendor-collaboration
python demo.py
```

It runs multiple rounds where agents hand off work, trust changes based on
outcomes, and a low-trust handoff is denied.

For MCP-specific signing and scanning, use the MCP security guide:

```bash
cd ophanix-platform
cat quickstart/03-mcp-security-gateway-and-scanner.md
```

## What To Remember

Inter-agent communication is not just networking. It is delegation. Every
handoff should answer:

- who is this peer?
- is it registered?
- what is its trust score?
- what capabilities does it claim?
- is it allowed to receive this message?
- can we prove what happened later?
