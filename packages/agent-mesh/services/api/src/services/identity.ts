// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import * as crypto from "crypto";

export interface RegistrationPayloadInput {
  name: string;
  sponsor_email: string;
  capabilities: string[];
  public_key: string;
}

export interface KeyPair {
  publicKey: string;
  privateKey: string;
}

/** Generate an Ed25519 keypair, returned as base64-encoded raw keys. */
export function generateKeyPair(): KeyPair {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519", {
    publicKeyEncoding: { type: "spki", format: "der" },
    privateKeyEncoding: { type: "pkcs8", format: "der" },
  });
  return {
    publicKey: publicKey.toString("base64"),
    privateKey: privateKey.toString("base64"),
  };
}

/** Generate a DID in the form `did:mesh:<uuid>`. */
export function generateDid(): string {
  return `did:mesh:${crypto.randomUUID()}`;
}

/** Generate an API key prefixed with `amesh_`. */
export function generateApiKey(): string {
  return `amesh_${crypto.randomBytes(24).toString("hex")}`;
}

/** Sign a payload with an Ed25519 private key (DER, base64). */
export function sign(payload: string, privateKeyBase64: string): string {
  const privateKeyDer = Buffer.from(privateKeyBase64, "base64");
  const keyObject = crypto.createPrivateKey({
    key: privateKeyDer,
    format: "der",
    type: "pkcs8",
  });
  const signature = crypto.sign(null, Buffer.from(payload), keyObject);
  return signature.toString("base64");
}

/** Canonical payload agents sign to prove key possession during registration. */
export function registrationPayload(input: RegistrationPayloadInput): string {
  return JSON.stringify({
    name: input.name,
    sponsor_email: input.sponsor_email,
    capabilities: [...input.capabilities].sort(),
    public_key: input.public_key,
  });
}

/** Verify a signature with an Ed25519 public key (DER, base64). */
export function verify(
  payload: string,
  signatureBase64: string,
  publicKeyBase64: string,
): boolean {
  try {
    const publicKeyDer = Buffer.from(publicKeyBase64, "base64");
    const keyObject = crypto.createPublicKey({
      key: publicKeyDer,
      format: "der",
      type: "spki",
    });
    return crypto.verify(
      null,
      Buffer.from(payload),
      keyObject,
      Buffer.from(signatureBase64, "base64"),
    );
  } catch {
    return false;
  }
}
