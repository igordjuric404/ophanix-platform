export class ApiClientError extends Error {
  constructor(message, { status, payload }) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

export function createApiClient({
  baseUrl = "/api/v1",
  fetchImpl = globalThis.fetch,
  getTenantContext = () => ({ organizationId: null, environmentId: null })
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.");
  }

  async function request(path, options = {}) {
    const tenant = getTenantContext();
    const headers = new Headers(options.headers ?? {});
    headers.set("Accept", "application/json");
    if (tenant.organizationId) {
      headers.set("X-Organization-ID", tenant.organizationId);
    }
    if (tenant.environmentId) {
      headers.set("X-Environment-ID", tenant.environmentId);
    }

    const init = {
      ...options,
      headers,
      credentials: options.credentials ?? "include"
    };
    if (options.body && typeof options.body !== "string") {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(options.body);
    }

    const response = await fetchImpl(resolveUrl(baseUrl, path), init);
    if (response.status === 204) {
      return null;
    }
    const payload = await parseResponse(response);
    if (!response.ok) {
      throw new ApiClientError(payload?.message || `Request failed with status ${response.status}`, {
        status: response.status,
        payload
      });
    }
    return payload;
  }

  return {
    request,
    getCurrentUser: () => request("/auth/me"),
    listOrganizations: () => request("/organizations"),
    listEnvironments: () => request("/environments"),
    listSystemDependencies: () => request("/system/dependencies"),
    getVersion: () => request("/version"),
    getAuditEvent: (eventId) => request(`/audit/events/${encodeURIComponent(eventId)}`),
    verifyAuditEvent: (eventId) => request(`/audit/events/${encodeURIComponent(eventId)}/verify`, {
      method: "POST"
    }),
    listAuditEvents: (params = {}) => {
      const search = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          search.set(key, value);
        }
      }
      return request(`/audit/events${search.size > 0 ? `?${search.toString()}` : ""}`);
    }
  };
}

function resolveUrl(baseUrl, path) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  if (path.startsWith("/api/")) {
    return path;
  }
  if (path === "/version") {
    return path;
  }
  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

async function parseResponse(response) {
  const contentType = response.headers?.get?.("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text ? { message: text } : {};
}
