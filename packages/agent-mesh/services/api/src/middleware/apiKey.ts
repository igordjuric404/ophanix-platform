// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { Request, Response, NextFunction } from "express";
import { getAgentByApiKey } from "../services/registry";
import type { AgentRecord } from "../types";

declare global {
  namespace Express {
    interface Request {
      authenticatedAgent?: AgentRecord;
    }
  }
}

/** Require a valid API key in the `x-api-key` header for write endpoints. */
export function requireApiKey(req: Request, res: Response, next: NextFunction): void {
  const apiKey = req.header("x-api-key");

  if (!apiKey) {
    res.status(401).json({ error: "Missing x-api-key header" });
    return;
  }

  const agent = getAgentByApiKey(apiKey);
  if (!agent) {
    res.status(403).json({ error: "Invalid API key" });
    return;
  }

  req.authenticatedAgent = agent;
  next();
}
