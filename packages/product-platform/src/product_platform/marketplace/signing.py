"""Demo plugin signature helpers."""

from __future__ import annotations

import hmac
import json
from hashlib import sha256
from typing import Any


def sign_plugin_manifest_for_demo(manifest: dict[str, Any], public_key: str) -> str:
    """Return a deterministic demo signature for a manifest."""

    payload = _signable_manifest(manifest)
    digest = hmac.new(public_key.encode(), canonical_json(payload).encode(), sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def verify_plugin_signature_with_key(
    manifest: dict[str, Any],
    *,
    public_key: str,
    key_status: str,
) -> bool:
    """Verify a manifest signature with an active demo key."""

    if key_status != "active":
        return False
    signature = manifest.get("signature")
    if not isinstance(signature, str) or not signature.strip():
        return False
    expected = sign_plugin_manifest_for_demo(manifest, public_key)
    return hmac.compare_digest(signature.strip(), expected)


def _signable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in manifest.items()
        if key not in {"signature", "signature_status"}
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
