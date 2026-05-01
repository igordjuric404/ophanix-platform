# Zero-Trust Identity

Zero-trust identity gives agents first-class, cryptographic identities instead
of treating them as anonymous scripts behind a human account or service key.
The core idea is simple: before an agent gets capabilities, trust score, or
network access, it needs an identity that can be verified, rotated, revoked,
and tied to an owner or sponsor.

## Where It Lives

- [Agent identity](../packages/agent-mesh/src/agentmesh/identity/agent_id.py)
- [Ephemeral credentials](../packages/agent-mesh/src/agentmesh/identity/credentials.py)
- [Key rotation](../packages/agent-mesh/src/agentmesh/identity/rotation.py)
- [SPIFFE support](../packages/agent-mesh/src/agentmesh/identity/spiffe.py)
- [Delegation chains](../packages/agent-mesh/src/agentmesh/identity/delegation.py)
- [Lifecycle manager](../packages/agent-mesh/src/agentmesh/lifecycle/manager.py)
- [Trust and identity tutorial](../docs/tutorials/02-trust-and-identity.md)
- [Feature deep dive](../features/zero-trust-identity/technical-deep-dive.md)

## How It Works

An agent identity is expected to have:

- a DID-like identifier, usually `did:mesh:...`,
- signing keys,
- declared capabilities,
- optional sponsor or owner context,
- registry membership,
- credentials with limited TTL.

The credential implementation is important because it is deliberately not a
long-lived service account key. A `Credential` has:

- a secure token and SHA-256 token hash,
- scoped capabilities,
- optional scoped resources,
- `issued_at` and `expires_at`,
- status: `active`, `rotated`, `revoked`, or `expired`,
- rotation metadata.

The default credential TTL is 15 minutes in the credential manager. Rotation
creates a new credential with the same scope and links it to the old credential.
Revocation flips the status immediately.

## Trust Handshake

The trust handshake verifies:

1. The peer DID is valid.
2. The peer can answer a nonce challenge with its key.
3. The peer is in the identity registry and active.
4. The peer meets the required trust score.
5. The peer has required capabilities, if the caller asked for them.

The code path is [TrustHandshake](../packages/agent-mesh/src/agentmesh/trust/handshake.py).
Successful handshakes are cached for a short TTL to avoid repeating crypto work
on every message.

## Key Rotation

`KeyRotationManager` rotates Ed25519 keys while preserving the agent's DID. The
old key signs the new public key, producing a rotation proof. Old public keys
are kept in bounded history so previous signatures can still be verified.

This is the operationally useful part: an agent can live for months, but its
keys do not have to.

## Demos To Run

```bash
cd ophanix-platform/packages/agent-mesh/examples/00-registration-hello-world
pip install -r requirements.txt
python simulated_registration.py
```

Also inspect the AgentMesh examples:

```bash
cd ophanix-platform/packages/agent-mesh/examples
cat README.md
cat QUICKSTART.md
```

The dashboard demo also shows identity and lifecycle fields in a fleet view:

```bash
cd ophanix-platform/demo/governance-dashboard
pip install -r requirements.txt
streamlit run app.py
```

## What To Remember

Identity is the anchor for everything else. A policy decision without a real
agent identity is just a local rule check. Once the agent has a verifiable DID,
Ophanix can attach owner, trust score, capabilities, audit trail, lifecycle
state, and revocation to the same object.
