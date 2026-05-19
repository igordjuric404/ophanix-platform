// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
/**
 * AgentMesh API Integration Tests
 *
 * Run with: npx ts-node tests/api.test.ts
 * Uses Node.js built-in assert — no external test dependencies required.
 */
import * as assert from "assert";
import * as http from "http";
import express from "express";
import {
  rateLimit,
  rateLimitStoreSizeForTesting,
  resetRateLimitStore,
  seedRateLimitEntryForTesting,
} from "../src/middleware/rateLimit";
import { requireApiKey } from "../src/middleware/apiKey";
import { requireRegistrationKey } from "../src/middleware/registrationKey";
import healthRouter from "../src/routes/health";
import registerRouter from "../src/routes/register";
import verifyRouter from "../src/routes/verify";
import handshakeRouter from "../src/routes/handshake";
import scoreRouter from "../src/routes/score";
import { resetRegistry } from "../src/services/registry";
import { resetAuditLog } from "../src/services/audit";
import {
  generateKeyPair,
  registrationPayload,
  sign,
} from "../src/services/identity";

const REGISTRATION_KEY = "test-registration-key";

// ---------- helpers ----------

function createApp(): express.Express {
  const app = express();
  app.use(express.json());
  app.use(rateLimit);

  app.use("/api", healthRouter);
  app.use("/api", verifyRouter);
  app.use("/api/register", requireRegistrationKey);
  app.use("/api", registerRouter);
  app.use("/api", requireApiKey, scoreRouter);
  app.use("/api", requireApiKey, handshakeRouter);

  return app;
}

function signedRegistration(
  name: string,
  sponsor_email: string,
  capabilities: string[],
) {
  const keys = generateKeyPair();
  const registration = {
    name,
    sponsor_email,
    capabilities,
    public_key: keys.publicKey,
  };
  return {
    request: {
      ...registration,
      registration_signature: sign(registrationPayload(registration), keys.privateKey),
    },
    privateKey: keys.privateKey,
  };
}

async function registerDirect(
  name: string,
  sponsorEmail: string,
  capabilities: string[],
) {
  const { registerAgent } = await import("../src/services/registry");
  const signed = signedRegistration(name, sponsorEmail, capabilities);
  return {
    agent: registerAgent(signed.request),
    privateKey: signed.privateKey,
  };
}

function request(
  server: http.Server,
  method: string,
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<{ status: number; body: any }> {
  return new Promise((resolve, reject) => {
    const addr = server.address() as { port: number };
    const data = body ? JSON.stringify(body) : undefined;
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: addr.port,
        path,
        method,
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      },
      (res) => {
        let raw = "";
        res.on("data", (c) => (raw += c));
        res.on("end", () => {
          try {
            resolve({ status: res.statusCode!, body: JSON.parse(raw) });
          } catch {
            resolve({ status: res.statusCode!, body: raw });
          }
        });
      },
    );
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

// ---------- test runner ----------

const tests: { name: string; fn: (server: http.Server) => Promise<void> }[] = [];

function test(name: string, fn: (server: http.Server) => Promise<void>) {
  tests.push({ name, fn });
}

// ---------- tests ----------

test("GET /api/health returns ok", async (server) => {
  const res = await request(server, "GET", "/api/health");
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.status, "ok");
  assert.strictEqual(res.body.service, "agentmesh-api");
  assert.ok(res.body.timestamp);
});

test("POST /api/register requires API key", async (server) => {
  const res = await request(server, "POST", "/api/register", {
    name: "TestAgent",
    sponsor_email: "test@example.com",
    capabilities: ["read"],
    public_key: "public",
    registration_signature: "signature",
  });
  assert.strictEqual(res.status, 401);
});

test("POST /api/register validates input", async (server) => {
  const res = await request(
    server,
    "POST",
    "/api/register",
    { capabilities: ["read"] },
    { "x-registration-key": REGISTRATION_KEY },
  );
  assert.strictEqual(res.status, 400);
});

test("POST /api/register rejects runtime agent API keys", async (server) => {
  const { agent } = await registerDirect("RuntimeOnly", "runtime@example.com", ["read"]);

  const registration = signedRegistration("SecondAgent", "second@example.com", ["read"]);
  const res = await request(
    server,
    "POST",
    "/api/register",
    registration.request,
    { "x-api-key": agent.api_key },
  );

  assert.strictEqual(res.status, 401);
});

test("Full registration and verification flow", async (server) => {
  const registration = signedRegistration(
    "FlowTest",
    "flow@example.com",
    ["read", "write", "execute"],
  );

  const regRes = await request(
    server,
    "POST",
    "/api/register",
    registration.request,
    { "x-registration-key": REGISTRATION_KEY },
  );
  assert.strictEqual(regRes.status, 201);
  assert.ok(regRes.body.agent_did.startsWith("did:mesh:"));
  assert.ok(regRes.body.api_key.startsWith("amesh_"));
  assert.ok(regRes.body.public_key);
  assert.ok(regRes.body.verification_url);

  const { getAgent } = await import("../src/services/registry");
  const agent = getAgent(regRes.body.agent_did)!;

  assert.strictEqual(agent.public_key, registration.request.public_key);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(agent, "private_key"), false);

  // Now verify the agent using the public minimal endpoint.
  const verifyRes = await request(server, "GET", `/api/verify/${agent.did}`);
  assert.strictEqual(verifyRes.status, 200);
  assert.strictEqual(verifyRes.body.registered, true);
  assert.strictEqual(verifyRes.body.status, "active");
  assert.strictEqual(Object.prototype.hasOwnProperty.call(verifyRes.body, "sponsor"), false);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(verifyRes.body, "capabilities"), false);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(verifyRes.body, "trust_score"), false);
});

test("POST /api/register rejects invalid key ownership proof", async (server) => {
  const keys = generateKeyPair();
  const res = await request(
    server,
    "POST",
    "/api/register",
    {
    name: "FlowTest",
    sponsor_email: "flow@example.com",
    capabilities: ["read", "write", "execute"],
      public_key: keys.publicKey,
      registration_signature: "not-a-valid-signature",
    },
    { "x-registration-key": REGISTRATION_KEY },
  );
  assert.strictEqual(res.status, 400);
  assert.match(res.body.error, /does not verify/);
});

test("GET /api/verify/:agentDid returns 404 for unknown agent", async (server) => {
  const res = await request(server, "GET", "/api/verify/did:mesh:unknown");
  assert.strictEqual(res.status, 404);
  assert.strictEqual(res.body.registered, false);
});

test("POST /api/handshake succeeds for registered agent", async (server) => {
  const { agent, privateKey } = await registerDirect("HandshakeAgent", "hs@example.com", [
    "read",
    "write",
  ]);
  const challenge = "test-challenge-nonce-123";

  const res = await request(
    server,
    "POST",
    "/api/handshake",
    {
      agent_did: agent.did,
      challenge,
      signature: sign(challenge, privateKey),
      capabilities_requested: ["read", "admin"],
    },
    { "x-api-key": agent.api_key },
  );

  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.verified, true);
  assert.ok(res.body.trust_score > 0);
  // Should grant 'read' but not 'admin' (agent doesn't have it)
  assert.ok(res.body.capabilities_granted.includes("read"));
  assert.ok(!res.body.capabilities_granted.includes("admin"));
  assert.strictEqual(res.body.signature_verified, true);
});

test("POST /api/handshake rejects invalid possession signatures", async (server) => {
  const { agent } = await registerDirect("HandshakeAgent", "hs@example.com", ["read"]);

  const res = await request(
    server,
    "POST",
    "/api/handshake",
    {
      agent_did: agent.did,
      challenge: "test-challenge-nonce-123",
      signature: "invalid-signature",
      capabilities_requested: ["read"],
    },
    { "x-api-key": agent.api_key },
  );

  assert.strictEqual(res.status, 401);
  assert.strictEqual(res.body.verified, false);
});

test("POST /api/handshake rejects API keys for a different agent", async (server) => {
  const { agent: signer, privateKey } = await registerDirect(
    "HandshakeSigner",
    "signer@example.com",
    ["read"],
  );
  const { agent: target } = await registerDirect("HandshakeTarget", "target@example.com", [
    "admin",
  ]);

  const res = await request(
    server,
    "POST",
    "/api/handshake",
    {
      agent_did: target.did,
      challenge: "cross-agent-challenge",
      signature: sign("cross-agent-challenge", privateKey),
      capabilities_requested: ["admin"],
    },
    { "x-api-key": signer.api_key },
  );

  assert.strictEqual(res.status, 403);
  assert.strictEqual(res.body.verified, false);
  assert.match(res.body.error, /not authorized/);
});

test("POST /api/handshake rejects unknown DIDs not bound to the API key", async (server) => {
  const { agent, privateKey } = await registerDirect("KeyHolder", "kh@example.com", []);

  const res = await request(
    server,
    "POST",
    "/api/handshake",
    {
      agent_did: "did:mesh:nonexistent",
      challenge: "test",
      signature: sign("test", privateKey),
      capabilities_requested: [],
    },
    { "x-api-key": agent.api_key },
  );
  assert.strictEqual(res.status, 403);
  assert.strictEqual(res.body.verified, false);
});

test("GET /api/score/:agentDid returns trust breakdown", async (server) => {
  const { agent } = await registerDirect("ScoreAgent", "score@example.com", ["read"]);

  const res = await request(server, "GET", `/api/score/${agent.did}`, undefined, {
    "x-api-key": agent.api_key,
  });
  assert.strictEqual(res.status, 200);
  assert.ok(typeof res.body.total === "number");
  assert.ok(res.body.dimensions);
  assert.ok(typeof res.body.dimensions.policy_compliance === "number");
  assert.ok(typeof res.body.dimensions.interaction_success === "number");
  assert.ok(typeof res.body.dimensions.verification_depth === "number");
  assert.ok(typeof res.body.dimensions.community_vouching === "number");
  assert.ok(typeof res.body.dimensions.uptime_reliability === "number");
  assert.ok(res.body.tier);
  assert.ok(Array.isArray(res.body.history));
  assert.ok(res.body.history.length > 0);
});

test("GET /api/score/:agentDid rejects access to unknown non-owned agent", async (server) => {
  const { agent } = await registerDirect("ScoreAgent", "score@example.com", ["read"]);
  const res = await request(server, "GET", "/api/score/did:mesh:nope", undefined, {
    "x-api-key": agent.api_key,
  });
  assert.strictEqual(res.status, 403);
});

test("GET /api/score/:agentDid requires the owning API key", async (server) => {
  const { agent: owner } = await registerDirect("ScoreOwner", "owner@example.com", ["read"]);
  const { agent: caller } = await registerDirect("ScoreCaller", "caller@example.com", ["read"]);

  const res = await request(server, "GET", `/api/score/${owner.did}`, undefined, {
    "x-api-key": caller.api_key,
  });

  assert.strictEqual(res.status, 403);
});

test("GET /api/score/:agentDid rejects missing API key", async (server) => {
  const { agent } = await registerDirect("ScoreAgent", "score@example.com", ["read"]);
  const res = await request(server, "GET", `/api/score/${agent.did}`);
  assert.strictEqual(res.status, 401);
});

test("rate limiter prunes expired buckets before accepting new traffic", async (server) => {
  const expiredAt = Date.now() - 60_000;
  seedRateLimitEntryForTesting("ip:stale-a", {
    count: 1,
    resetAt: expiredAt,
    lastSeenAt: expiredAt,
  });
  seedRateLimitEntryForTesting("ip:stale-b", {
    count: 1,
    resetAt: expiredAt,
    lastSeenAt: expiredAt,
  });
  assert.strictEqual(rateLimitStoreSizeForTesting(), 2);

  const res = await request(server, "GET", "/api/health");

  assert.strictEqual(res.status, 200);
  assert.strictEqual(rateLimitStoreSizeForTesting(), 1);
});

// ---------- run ----------

async function run() {
  let passed = 0;
  let failed = 0;

  for (const t of tests) {
    // Reset state before each test
    resetRegistry();
    resetAuditLog();
    resetRateLimitStore();
    process.env.AGENTMESH_REGISTRATION_KEY = REGISTRATION_KEY;

    const app = createApp();
    const server = app.listen(0);

    try {
      await t.fn(server);
      console.log(`  ✓ ${t.name}`);
      passed++;
    } catch (err: any) {
      console.error(`  ✗ ${t.name}`);
      console.error(`    ${err.message}`);
      failed++;
    } finally {
      server.close();
    }
  }

  console.log(`\n${passed} passed, ${failed} failed, ${tests.length} total`);
  if (failed > 0) process.exit(1);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
