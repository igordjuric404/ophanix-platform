// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { Router, Request, Response } from "express";
import { getAgent } from "../services/registry";
import { ScoreResponse } from "../types";

const router = Router();

router.get("/score/:agentDid", (req: Request, res: Response) => {
  const { agentDid } = req.params;
  if (!req.authenticatedAgent) {
    res.status(401).json({ error: "Authentication is required" });
    return;
  }
  if (req.authenticatedAgent.did !== agentDid) {
    res.status(403).json({ error: "API key is not authorized for this agent" });
    return;
  }
  const agent = getAgent(agentDid);

  if (!agent) {
    res.status(404).json({ error: "Agent not found" });
    return;
  }

  const response: ScoreResponse = {
    schema_version: agent.trust_score.schema_version,
    score: agent.trust_score.score,
    dimensions: agent.trust_score.dimensions,
    tier: agent.trust_score.tier,
    explanation: agent.trust_score.explanation,
    history: agent.trust_score.history,
  };

  res.json(response);
});

export default router;
