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
    listAgents: (params = {}) => {
      const search = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          search.set(key, value);
        }
      }
      return request(`/agents${search.size > 0 ? `?${search.toString()}` : ""}`);
    },
    getAgent: (agentId) => request(`/agents/${encodeURIComponent(agentId)}`),
    getAgentTimeline: (agentId) => request(`/agents/${encodeURIComponent(agentId)}/timeline`),
    getAgentAudit: (agentId) => request(`/agents/${encodeURIComponent(agentId)}/audit`),
    listAgentCredentials: (agentId, params = {}) => {
      const query = queryString(params);
      return request(`/agents/${encodeURIComponent(agentId)}/credentials${query}`);
    },
    issueAgentCredential: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/credentials`, { method: "POST", body }),
    rotateCredential: (credentialId, body = {}) =>
      request(`/credentials/${encodeURIComponent(credentialId)}/rotate`, {
        method: "POST",
        body
      }),
    revokeCredential: (credentialId, body = {}) =>
      request(`/credentials/${encodeURIComponent(credentialId)}/revoke`, {
        method: "POST",
        body
      }),
    verifyCredential: (credentialId, body = {}) =>
      request(`/credentials/${encodeURIComponent(credentialId)}/verify`, {
        method: "POST",
        body
      }),
    listExpiringCredentials: (params = {}) => request(`/credentials/expiring${queryString(params)}`),
    createAgentRegistrationDraft: (body) =>
      request("/agents/registration-drafts", { method: "POST", body }),
    updateAgentRegistrationDraft: (draftId, body) =>
      request(`/agents/registration-drafts/${encodeURIComponent(draftId)}`, {
        method: "PATCH",
        body
      }),
    createAgentIdentity: (draftId) =>
      request(`/agents/registration-drafts/${encodeURIComponent(draftId)}/identity`, {
        method: "POST"
      }),
    simulateAgentRegistrationDraft: (draftId) =>
      request(`/agents/registration-drafts/${encodeURIComponent(draftId)}/simulate`, {
        method: "POST"
      }),
    submitAgentRegistrationDraft: (draftId) =>
      request(`/agents/registration-drafts/${encodeURIComponent(draftId)}/submit`, {
        method: "POST"
      }),
    approveAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/approve`, { method: "POST", body }),
    activateAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/activate`, { method: "POST", body }),
    rejectAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/reject`, { method: "POST", body }),
    suspendAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/suspend`, { method: "POST", body }),
    resumeAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/resume`, { method: "POST", body }),
    changeAgentOwner: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/change-owner`, { method: "POST", body }),
    decommissionAgent: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/decommission`, { method: "POST", body }),
    recordAgentHeartbeat: (agentId, body = {}) =>
      request(`/agents/${encodeURIComponent(agentId)}/heartbeat`, { method: "POST", body }),
    runOrphanDetection: (body = {}) =>
      request("/agents/orphan-detection/run", { method: "POST", body }),
    listDiscoveryScanners: () => request("/discovery/scanners"),
    listDiscoveryTargets: () => request("/discovery/targets"),
    createDiscoveryTarget: (body) => request("/discovery/targets", { method: "POST", body }),
    patchDiscoveryTargetSchedule: (targetId, body) =>
      request(`/discovery/targets/${encodeURIComponent(targetId)}/schedule`, {
        method: "PATCH",
        body
      }),
    createDiscoveryRun: (body) => request("/discovery/runs", { method: "POST", body }),
    listDiscoveryRuns: () => request("/discovery/runs"),
    getDiscoveryRun: (runId) => request(`/discovery/runs/${encodeURIComponent(runId)}`),
    listDiscoveryFindings: (params = {}) => request(`/discovery/findings${queryString(params)}`),
    getDiscoveryFinding: (findingId) =>
      request(`/discovery/findings/${encodeURIComponent(findingId)}`),
    reconcileDiscoveryRun: (runId) =>
      request(`/discovery/reconcile-run/${encodeURIComponent(runId)}`, { method: "POST" }),
    assignDiscoveryFindingOwner: (findingId, body) =>
      request(`/discovery/findings/${encodeURIComponent(findingId)}/assign-owner`, {
        method: "POST",
        body
      }),
    registerDiscoveryFindingAgent: (findingId, body) =>
      request(`/discovery/findings/${encodeURIComponent(findingId)}/register-agent`, {
        method: "POST",
        body
      }),
    suppressDiscoveryFinding: (findingId, body) =>
      request(`/discovery/findings/${encodeURIComponent(findingId)}/suppress`, {
        method: "POST",
        body
      }),
    markDiscoveryFindingDecommissioned: (findingId) =>
      request(`/discovery/findings/${encodeURIComponent(findingId)}/mark-decommissioned`, {
        method: "POST"
      }),
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

function queryString(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  }
  return search.size > 0 ? `?${search.toString()}` : "";
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
