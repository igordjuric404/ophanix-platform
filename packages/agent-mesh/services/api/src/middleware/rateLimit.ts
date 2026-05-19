// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { Request, Response, NextFunction } from "express";

export interface RateLimitEntry {
  count: number;
  resetAt: number;
  lastSeenAt: number;
}

const store = new Map<string, RateLimitEntry>();
const WINDOW_MS = readPositiveInt("AGENTMESH_RATE_LIMIT_WINDOW_MS", 60_000);
const MAX_REQUESTS = readPositiveInt("AGENTMESH_RATE_LIMIT_MAX_REQUESTS", 100);
const MAX_BUCKETS = readPositiveInt("AGENTMESH_RATE_LIMIT_MAX_BUCKETS", 10_000);
let lastSweepAt = 0;

/** Bounded local rate limiter for public API backpressure. */
export function rateLimit(req: Request, res: Response, next: NextFunction): void {
  const key = rateLimitKey(req);
  const now = Date.now();
  sweepExpiredBuckets(now);

  let entry = store.get(key);
  if (!entry || now > entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS, lastSeenAt: now };
    store.set(key, entry);
  }

  entry.count++;
  entry.lastSeenAt = now;

  res.setHeader("X-RateLimit-Limit", MAX_REQUESTS);
  res.setHeader("X-RateLimit-Remaining", Math.max(0, MAX_REQUESTS - entry.count));
  res.setHeader("X-RateLimit-Reset", Math.ceil(entry.resetAt / 1000));

  if (entry.count > MAX_REQUESTS) {
    res.status(429).json({ error: "Too many requests. Try again later." });
    return;
  }

  next();
}

/** Reset rate limit store (for testing). */
export function resetRateLimitStore(): void {
  store.clear();
  lastSweepAt = 0;
}

export function rateLimitStoreSizeForTesting(): number {
  return store.size;
}

export function seedRateLimitEntryForTesting(key: string, entry: RateLimitEntry): void {
  store.set(key, entry);
}

function rateLimitKey(req: Request): string {
  const authenticatedDid = req.authenticatedAgent?.did;
  if (authenticatedDid) {
    return `agent:${authenticatedDid}`;
  }
  return `ip:${req.ip ?? req.socket.remoteAddress ?? "unknown"}`;
}

function sweepExpiredBuckets(now: number): void {
  if (now - lastSweepAt < WINDOW_MS && store.size <= MAX_BUCKETS) {
    return;
  }
  lastSweepAt = now;
  for (const [key, entry] of store.entries()) {
    if (entry.resetAt < now) {
      store.delete(key);
    }
  }
  if (store.size <= MAX_BUCKETS) {
    return;
  }
  const ordered = [...store.entries()].sort((a, b) => a[1].lastSeenAt - b[1].lastSeenAt);
  const removeCount = store.size - MAX_BUCKETS;
  for (const [key] of ordered.slice(0, removeCount)) {
    store.delete(key);
  }
}

function readPositiveInt(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
