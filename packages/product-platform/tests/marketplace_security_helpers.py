from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from product_platform.marketplace.signing import (
    SIGNATURE_ALGORITHM_ED25519,
    sign_plugin_manifest_for_test,
)


def ed25519_key_pair() -> tuple[ed25519.Ed25519PrivateKey, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, f"ed25519:{base64.b64encode(public_key).decode('ascii')}"


def signed_manifest(
    manifest: dict[str, Any],
    private_key: ed25519.Ed25519PrivateKey,
    *,
    include_artifact_evidence: bool = True,
    artifact_evidence: dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    body = {**manifest, **overrides}
    body.pop("signature", None)
    body.pop("signature_status", None)
    if include_artifact_evidence:
        evidence = artifact_evidence or passing_artifact_evidence(body["name"], body["version"])
        body["artifact_evidence"] = evidence
        body["package_digest"] = evidence["artifact_digest"]
    else:
        body.pop("artifact_evidence", None)
        body.pop("artifact", None)
        if "package_digest" not in overrides:
            body.pop("package_digest", None)
    body["signature_algorithm"] = SIGNATURE_ALGORITHM_ED25519
    body["signature"] = sign_plugin_manifest_for_test(body, private_key)
    return body


def passing_artifact_evidence(name: str, version: str) -> dict[str, Any]:
    digest = hashlib.sha256(f"{name}:{version}".encode("utf-8")).hexdigest()
    return {
        "artifact_digest": digest,
        "digest_algorithm": "sha256",
        "provenance": {
            "source_repository": "https://example.invalid/ophanix/plugins",
            "builder": "ophanix-test-builder",
            "attestation_ref": f"attestation://{name}/{version}",
        },
        "sbom": {
            "format": "cyclonedx-json",
            "ref": f"sbom://{name}/{version}",
            "component_count": 3,
        },
        "license": {
            "status": "pass",
            "expression": "MIT",
        },
        "vulnerability_scan": {
            "status": "pass",
            "critical": 0,
            "high": 0,
            "findings": [],
        },
        "malware_scan": {
            "status": "pass",
            "engine": "ophanix-test-malware-scan",
            "findings": [],
        },
    }
