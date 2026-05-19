// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import * as crypto from "crypto";
import { Request, Response, NextFunction } from "express";

const REGISTRATION_KEY_HEADER = "x-registration-key";

function configuredRegistrationKey(): string | undefined {
  return process.env.AGENTMESH_REGISTRATION_KEY?.trim() || undefined;
}

function safeEqual(actual: string, expected: string): boolean {
  const actualBuffer = Buffer.from(actual);
  const expectedBuffer = Buffer.from(expected);
  if (actualBuffer.length !== expectedBuffer.length) {
    return false;
  }
  return crypto.timingSafeEqual(actualBuffer, expectedBuffer);
}

/** Require the out-of-band enrollment key for agent registration. */
export function requireRegistrationKey(req: Request, res: Response, next: NextFunction): void {
  const expected = configuredRegistrationKey();
  if (!expected) {
    res.status(503).json({ error: "Agent registration is not configured" });
    return;
  }

  const provided = req.header(REGISTRATION_KEY_HEADER);
  if (!provided) {
    res.status(401).json({ error: `Missing ${REGISTRATION_KEY_HEADER} header` });
    return;
  }

  if (!safeEqual(provided, expected)) {
    res.status(403).json({ error: "Invalid registration key" });
    return;
  }

  next();
}
