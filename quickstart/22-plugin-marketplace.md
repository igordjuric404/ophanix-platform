# Plugin Marketplace

The plugin marketplace is the supply-chain layer for agent ecosystems. It lets
you discover, register, validate, sign, install, evaluate, and eventually
deprecate plugins that extend agent behavior.

For a governance product, this is a major feature. Plugins are code and tool
surface. If they are not governed, they become an easy way around the platform.

## Where It Lives

- [Marketplace package README](../packages/agent-marketplace/README.md)
- [Manifest schema](../packages/agent-marketplace/src/agent_marketplace/manifest.py)
- [Registry](../packages/agent-marketplace/src/agent_marketplace/registry.py)
- [Installer](../packages/agent-marketplace/src/agent_marketplace/installer.py)
- [Signing](../packages/agent-marketplace/src/agent_marketplace/signing.py)
- [Marketplace policy](../packages/agent-marketplace/src/agent_marketplace/marketplace_policy.py)
- [Batch evaluation](../packages/agent-marketplace/src/agent_marketplace/batch.py)
- [AgentMesh plugin sandbox](../packages/agent-mesh/src/agentmesh/marketplace/sandbox.py)
- [Plugin marketplace tutorial](../docs/tutorials/10-plugin-marketplace.md)
- [GitHub marketplace governance example](../examples/marketplace-governance/README.md)
- [Feature deep dive](../features/plugin-marketplace/technical-deep-dive.md)

## Plugin Manifest

Every plugin uses an `agent-plugin.yaml` manifest. The implemented
`PluginManifest` fields are:

- `name`,
- `version`,
- `description`,
- `author`,
- `plugin_type`,
- `capabilities`,
- `dependencies`,
- `min_agentmesh_version`,
- `signature`,
- `organization`.

Supported plugin types:

- `policy_template`,
- `integration`,
- `agent`,
- `validator`.

The manifest validates:

- name is non-empty and only alphanumeric, hyphen, or underscore,
- version is `MAJOR.MINOR` or `MAJOR.MINOR.PATCH`,
- author is non-empty.

## Registry And Installer

`PluginRegistry` stores plugin manifests and supports search, version tracking,
and persistence to a JSON file.

`PluginInstaller` installs plugins from the registry into a plugin directory.
The marketplace package also includes dependency, policy, trust-tier, usage
trust, quality, and signing modules.

## Signing

The signing module uses Ed25519. The manifest has a deterministic
`signable_bytes()` representation that excludes the signature field. That is
important because signatures must be stable across serialization.

Production marketplace policy should usually require signatures for plugins
that run code or expose tools.

## Policy Evaluation

Marketplace policy is split across two useful layers:

1. Manifest-level checks.
   - required signatures,
   - allowed plugin types,
   - required capabilities,
   - dependency limits,
   - description quality.
2. Marketplace governance checks.
   - allowed or blocked MCP servers,
   - tool safety rules,
   - token budgets,
   - environment-specific requirements.

The [marketplace-governance example](../examples/marketplace-governance/README.md)
shows how to use this in a GitHub-based plugin marketplace with pull request
validation.

## Programmatic Quickstart

```python
from pathlib import Path
from agent_marketplace import (
    PluginInstaller,
    PluginManifest,
    PluginRegistry,
    PluginType,
)

registry = PluginRegistry(storage_path=Path(".agentmesh/registry.json"))

manifest = PluginManifest(
    name="sentiment-analyzer",
    version="1.0.0",
    description="Sentiment analysis for support responses",
    author="founders@ophanix.ai",
    plugin_type=PluginType.VALIDATOR,
    capabilities=["sentiment-scoring", "toxicity-detection"],
)

registry.register(manifest)
print([plugin.name for plugin in registry.search("sentiment")])

installer = PluginInstaller(
    plugins_dir=Path(".agentmesh/plugins"),
    registry=registry,
)
path = installer.install("sentiment-analyzer")
print(path)
```

## CLI Reality In This Checkout

There are Click command groups for plugin management in source, including:

- install,
- uninstall,
- list,
- search,
- verify,
- publish,
- evaluate,
- trust,
- evaluate-batch.

However, in this checkout the standalone `agent-marketplace` package does not
declare a console script in `pyproject.toml`, and the `agentmesh` CLI does not
appear to wire the marketplace command group into the main app. Treat the CLI
docs as intended integration unless you wire the command group yourself.

The programmatic API and GitHub example are the safest paths to run locally.

## Demos To Run

Install the packages:

```bash
cd ophanix-platform
pip install -e "packages/agent-marketplace[cli]"
pip install -e packages/agent-mesh
```

Read the tutorial:

```bash
cat docs/tutorials/10-plugin-marketplace.md
```

Inspect the GitHub governance example:

```bash
cat examples/marketplace-governance/README.md
cat examples/marketplace-governance/policies/marketplace-policy.yaml
cat examples/marketplace-governance/policies/plugin-safety.yaml
```

Run a small programmatic batch evaluation after creating `agent-plugin.yaml`
manifests, or adapt the example plugins from `plugin.json` into the canonical
manifest format.

## What To Remember

Plugins are part of the agent attack surface. A governed marketplace should
check identity, signature, capabilities, dependencies, policy compliance,
sandbox behavior, and runtime telemetry before trusting a plugin.
