// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { Router, Request, Response } from "express";
import { registerAgent } from "../services/registry";
import { registrationPayload, verify } from "../services/identity";
import { RegisterRequest, RegisterResponse } from "../types";

const router = Router();

router.post("/register", (req: Request, res: Response) => {
  const { name, sponsor_email, capabilities, public_key, registration_signature } =
    req.body as Partial<RegisterRequest>;

  if (!name || typeof name !== "string") {
    res.status(400).json({ error: "name is required and must be a string" });
    return;
  }
  if (!sponsor_email || typeof sponsor_email !== "string") {
    res.status(400).json({ error: "sponsor_email is required and must be a string" });
    return;
  }
  if (!Array.isArray(capabilities)) {
    res.status(400).json({ error: "capabilities is required and must be an array" });
    return;
  }
  const normalizedCapabilities = capabilities
    .map((capability) => (typeof capability === "string" ? capability.trim() : ""))
    .filter(Boolean);
  if (normalizedCapabilities.length !== capabilities.length) {
    res.status(400).json({ error: "capabilities must contain non-empty strings" });
    return;
  }
  if (!public_key || typeof public_key !== "string") {
    res.status(400).json({ error: "public_key is required and must be a string" });
    return;
  }
  if (!registration_signature || typeof registration_signature !== "string") {
    res.status(400).json({
      error: "registration_signature is required and must be a string",
    });
    return;
  }

  const registration = {
    name: name.trim(),
    sponsor_email: sponsor_email.trim(),
    capabilities: normalizedCapabilities,
    public_key: public_key.trim(),
  };
  const signatureValid = verify(
    registrationPayload(registration),
    registration_signature.trim(),
    registration.public_key,
  );
  if (!signatureValid) {
    res.status(400).json({ error: "registration_signature does not verify public_key ownership" });
    return;
  }

  const agent = registerAgent({
    ...registration,
    registration_signature: registration_signature.trim(),
  });

  const response: RegisterResponse = {
    agent_did: agent.did,
    api_key: agent.api_key,
    public_key: agent.public_key,
    verification_url: `/api/verify/${agent.did}`,
  };

  res.status(201).json(response);
});

export default router;
