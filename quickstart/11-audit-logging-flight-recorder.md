# Audit Logging And Flight Recorder

Audit logging is the proof layer. Policy, identity, runtime, and SRE features
all become more valuable when their decisions are recorded in a tamper-evident
form. This is how you answer "what happened?", "who allowed it?", "which rule
matched?", and "did anyone alter the record?"

## Where It Lives

- [AgentMesh audit log](../packages/agent-mesh/src/agentmesh/governance/audit.py)
- [Agent OS audit logger](../packages/agent-os/src/agent_os/audit_logger.py)
- [Hypervisor delta engine](../packages/agent-hypervisor/src/hypervisor/audit/delta.py)
- [Hypervisor commitment engine](../packages/agent-hypervisor/src/hypervisor/audit/commitment.py)
- [MAF audit middleware](../packages/agent-os/src/agent_os/integrations/maf_adapter.py)
- [Tutorial](../docs/tutorials/04-audit-and-compliance.md)
- [Feature deep dive](../features/audit-logging-flight-recorder/technical-deep-dive.md)

## Audit Entry Model

AgentMesh `AuditEntry` records:

- event type,
- agent DID,
- action,
- resource and target DID,
- sanitized data,
- outcome,
- policy decision and matched rule,
- previous hash and entry hash,
- trace id and session id.

The entry can be serialized as a CloudEvents v1.0 envelope, which is useful if
Ophanix needs to send audit events to customer SIEM or event pipelines.

## Tamper Evidence

There are two related implementations:

- `MerkleAuditChain` adds entries, sets `previous_hash`, computes each entry
  hash, and maintains a Merkle root for verification.
- `DeltaEngine` records VFS/session changes as a SHA-256 hash chain where each
  semantic delta links to the previous delta.

The commitment engine currently stores commitments locally in memory. It does
not anchor to a blockchain in Public Preview, even though some higher-level docs
describe anchoring as a future or optional architecture.

## Flight Recorder Concept

The "flight recorder" idea is broader than logging text. It means recording the
minimum useful state to reconstruct an incident:

- policy context,
- tool name and resource,
- agent identity,
- trust score,
- session id,
- saga step,
- action result,
- denial reason,
- timing,
- hash-chain proof.

For Ophanix, this is where a compliance buyer will spend time. They do not just
want an alert; they need evidence.

## Demos To Run

The live MAF demo writes real audit events:

```bash
cd ophanix-platform
python demo/maf_governance_demo.py
```

The governance dashboard has a policy feed that visualizes decisions:

```bash
cd ophanix-platform/demo/governance-dashboard
pip install -r requirements.txt
streamlit run app.py
```

The compliance CLI also uses audit/integrity concepts:

```bash
cd ophanix-platform
agt verify
agt integrity --generate integrity.json
agt integrity --manifest integrity.json
```

## What To Remember

Audit is not a byproduct. It is part of enforcement. A denied action without an
audit event is hard to explain later. An allowed privileged action without an
audit event is a liability.
