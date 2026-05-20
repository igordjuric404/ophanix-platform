"""Plugin signature verification helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


SIGNATURE_ALGORITHM_ED25519 = "ed25519"
_SIGNABLE_MANIFEST_FIELDS = (
    "name",
    "version",
    "description",
    "author",
    "plugin_type",
    "capabilities",
    "dependencies",
    "min_agentmesh_version",
    "organization",
    "package_ref",
    "package_digest",
)


class PluginSignatureError(ValueError):
    """Raised when plugin signature material is malformed."""


def sign_plugin_manifest_for_test(
    manifest: dict[str, Any],
    private_key: ed25519.Ed25519PrivateKey,
) -> str:
    """Sign a marketplace manifest with Ed25519 for deterministic tests."""

    signature = private_key.sign(signable_manifest_bytes(manifest))
    return base64.b64encode(signature).decode("ascii")


def verify_plugin_signature_with_key(
    manifest: dict[str, Any],
    *,
    public_key: str,
    key_status: str,
    key_type: str = SIGNATURE_ALGORITHM_ED25519,
) -> bool:
    """Verify a manifest signature with an active trusted Ed25519 public key."""

    if key_status != "active":
        return False
    if key_type != SIGNATURE_ALGORITHM_ED25519:
        return False
    declared_algorithm = manifest.get("signature_algorithm")
    if declared_algorithm is not None and str(declared_algorithm).strip().lower() != SIGNATURE_ALGORITHM_ED25519:
        return False
    signature = manifest.get("signature")
    if not isinstance(signature, str) or not signature.strip():
        return False
    try:
        decoded_signature = base64.b64decode(signature.strip(), validate=True)
        trusted_key = load_ed25519_public_key(public_key)
        trusted_key.verify(decoded_signature, signable_manifest_bytes(manifest))
    except (PluginSignatureError, InvalidSignature, ValueError, binascii.Error):
        return False
    return True


def ed25519_public_key_fingerprint(public_key: str) -> str:
    """Return the SHA-256 fingerprint for a trusted Ed25519 public key."""

    decoded_key = load_ed25519_public_key(public_key)
    raw_public_key = decoded_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw_public_key).hexdigest()


def load_ed25519_public_key(public_key: str) -> ed25519.Ed25519PublicKey:
    """Load an Ed25519 public key from PEM, raw base64, or ed25519:base64 text."""

    value = public_key.strip()
    if not value:
        raise PluginSignatureError("public_key must not be blank.")
    if value.startswith("-----BEGIN"):
        loaded = serialization.load_pem_public_key(value.encode("utf-8"))
        if not isinstance(loaded, ed25519.Ed25519PublicKey):
            raise PluginSignatureError("public_key must contain an Ed25519 public key.")
        return loaded
    if value.startswith("ed25519:"):
        value = value.removeprefix("ed25519:").strip()
    try:
        raw_key = base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise PluginSignatureError("public_key must be PEM or base64-encoded Ed25519 bytes.") from exc
    if len(raw_key) != 32:
        raise PluginSignatureError("Ed25519 public keys must be 32 raw bytes.")
    return ed25519.Ed25519PublicKey.from_public_bytes(raw_key)


def signable_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Return canonical SDK-compatible bytes for manifest signature checks."""

    payload = _sdk_signable_manifest(manifest)
    return canonical_json(payload).encode("utf-8")


def _sdk_signable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    author = manifest.get("author", manifest.get("publisher"))
    payload = {
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "description": manifest.get("description"),
        "author": author,
        "plugin_type": manifest.get("plugin_type"),
        "capabilities": manifest.get("capabilities", manifest.get("required_capabilities", [])),
        "dependencies": manifest.get("dependencies", []),
        "min_agentmesh_version": manifest.get("min_agentmesh_version"),
        "organization": manifest.get("organization"),
        "package_ref": manifest.get("package_ref"),
        "package_digest": manifest.get("package_digest"),
    }
    return {field: payload[field] for field in _SIGNABLE_MANIFEST_FIELDS}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
