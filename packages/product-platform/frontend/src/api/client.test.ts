import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";

describe("api client", () => {
  it("includes credentials and tenant headers", async () => {
    const calls: Array<[string, RequestInit]> = [];
    const fetchImpl: typeof fetch = async (url, init) => {
      calls.push([String(url), init ?? {}]);
      return (
        new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        })
      );
    };
    const client = createApiClient({
      fetchImpl,
      getTenantContext: () => ({ organizationId: "org_1", environmentId: "env_1" })
    });

    await client.request("/agents");

    const [, init] = calls[0];
    expect(init.credentials).toBe("include");
    expect((init.headers as Headers).get("X-Organization-ID")).toBe("org_1");
    expect((init.headers as Headers).get("X-Environment-ID")).toBe("env_1");
  });

  it("raises typed errors with response payloads", async () => {
    const client = createApiClient({
      fetchImpl: vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Authentication is required." }), {
            headers: { "Content-Type": "application/json" },
            status: 401
          })
      ) as unknown as typeof fetch
    });

    await expect(client.request("/auth/me")).rejects.toMatchObject({
      name: "ApiClientError",
      status: 401,
      message: "Authentication is required."
    });
  });

  it("serializes falsy request bodies instead of dropping them", async () => {
    const calls: Array<[string, RequestInit]> = [];
    const fetchImpl: typeof fetch = async (url, init) => {
      calls.push([String(url), init ?? {}]);
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200
      });
    };
    const client = createApiClient({ fetchImpl });

    await client.request("/feature-flag", { body: false, method: "POST" });

    const [, init] = calls[0];
    expect(init.body).toBe("false");
    expect((init.headers as Headers).get("Content-Type")).toBe("application/json");
  });

  it("passes abort signals through to fetch", async () => {
    const calls: Array<[string, RequestInit]> = [];
    const fetchImpl: typeof fetch = async (url, init) => {
      calls.push([String(url), init ?? {}]);
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200
      });
    };
    const client = createApiClient({ fetchImpl });
    const controller = new AbortController();

    await client.request("/agents", { signal: controller.signal });

    expect(calls[0][1].signal).toBe(controller.signal);
  });

  it("normalizes invalid JSON responses into typed API errors", async () => {
    const client = createApiClient({
      fetchImpl: vi.fn(
        async () =>
          new Response("", {
            headers: { "Content-Type": "application/json" },
            status: 500
          })
      ) as unknown as typeof fetch
    });

    await expect(client.request("/broken")).rejects.toMatchObject({
      name: "ApiClientError",
      status: 500,
      message: "Request failed with status 500"
    });
  });

  it("returns a safe payload for successful invalid JSON responses", async () => {
    const client = createApiClient({
      fetchImpl: vi.fn(
        async () =>
          new Response("{", {
            headers: { "Content-Type": "application/json" },
            status: 200
          })
      ) as unknown as typeof fetch
    });

    await expect(client.request("/invalid-json")).resolves.toEqual({
      message: "Response contained invalid JSON."
    });
  });
});
