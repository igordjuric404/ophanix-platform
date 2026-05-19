// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import express from "express";
import { rateLimit } from "./middleware/rateLimit";
import { requireApiKey } from "./middleware/apiKey";
import { requireRegistrationKey } from "./middleware/registrationKey";
import healthRouter from "./routes/health";
import registerRouter from "./routes/register";
import verifyRouter from "./routes/verify";
import handshakeRouter from "./routes/handshake";
import scoreRouter from "./routes/score";

const app = express();
const PORT = process.env.PORT ?? 3000;
const TRUST_PROXY_HOPS = process.env.AGENTMESH_TRUST_PROXY_HOPS;

if (TRUST_PROXY_HOPS) {
  const parsedHops = Number.parseInt(TRUST_PROXY_HOPS, 10);
  app.set("trust proxy", TRUST_PROXY_HOPS === "true" ? true : Number.isFinite(parsedHops) ? parsedHops : false);
}

app.use(express.json());
app.use(rateLimit);

// Public read endpoints
app.use("/api", healthRouter);
app.use("/api", verifyRouter);

// Enrollment requires an out-of-band registration key, not a runtime agent key.
app.use("/api/register", requireRegistrationKey);
app.use("/api", registerRouter);

// Runtime/private endpoints require an agent API key.
app.use("/api", requireApiKey, scoreRouter);
app.use("/api", requireApiKey, handshakeRouter);

app.listen(PORT, () => {
  console.log(`AgentMesh API listening on port ${PORT}`);
});

export default app;
