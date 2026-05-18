import type { ApiErrorPayload } from "./types";

export class ApiClientError extends Error {
  status: number;
  payload: ApiErrorPayload | null;

  constructor(
    message: string,
    { status, payload }: { status: number; payload: ApiErrorPayload | null }
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

export interface TenantContext {
  organizationId: string | null;
  environmentId: string | null;
}

export interface ApiClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  getTenantContext?: () => TenantContext;
}

export type ApiRequestInit = Omit<RequestInit, "body"> & {
  body?: unknown;
  tenantContext?: TenantContext;
};

let activeTenantContext: TenantContext = { organizationId: null, environmentId: null };
const tenantContextSubscribers = new Set<() => void>();

export function setApiTenantContext(context: TenantContext) {
  if (
    activeTenantContext.organizationId === context.organizationId &&
    activeTenantContext.environmentId === context.environmentId
  ) {
    return;
  }

  activeTenantContext = context;
  tenantContextSubscribers.forEach((notify) => notify());
}

export function getApiTenantContext() {
  return activeTenantContext;
}

export function subscribeApiTenantContext(notify: () => void) {
  tenantContextSubscribers.add(notify);
  return () => tenantContextSubscribers.delete(notify);
}

export function createApiClient({
  baseUrl = "/api/v1",
  fetchImpl,
  getTenantContext = () => activeTenantContext
}: ApiClientOptions = {}) {
  const resolvedFetch: typeof fetch =
    fetchImpl ?? ((input, init) => globalThis.fetch(input, init));

  if (typeof resolvedFetch !== "function") {
    throw new Error("A fetch implementation is required.");
  }

  async function request<TResponse>(path: string, options: ApiRequestInit = {}): Promise<TResponse> {
    const { body, tenantContext, ...requestOptions } = options;
    const tenant = tenantContext ?? getTenantContext();
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (tenant.organizationId) {
      headers.set("X-Organization-ID", tenant.organizationId);
    }
    if (tenant.environmentId) {
      headers.set("X-Environment-ID", tenant.environmentId);
    }

    const init: RequestInit = {
      ...requestOptions,
      headers,
      credentials: options.credentials ?? "include"
    };

    if (body !== undefined && typeof body !== "string") {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(body);
    } else if (typeof body === "string") {
      init.body = body;
    }

    const response = await resolvedFetch(resolveUrl(baseUrl, path), init);
    if (response.status === 204) {
      return null as TResponse;
    }
    const payload = await parseResponse(response);
    if (!response.ok) {
      const message =
        payload?.message || payload?.detail || `Request failed with status ${response.status}`;
      throw new ApiClientError(message, { status: response.status, payload });
    }
    return payload as TResponse;
  }

  return { request };
}

export const apiClient = createApiClient();

async function parseResponse(response: Response): Promise<ApiErrorPayload | null> {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    return text ? { message: text } : null;
  }
  const text = await response.text();
  if (!text.trim()) {
    return null;
  }
  try {
    return JSON.parse(text) as ApiErrorPayload;
  } catch {
    return {
      message: response.ok ? "Response contained invalid JSON." : "Request failed with invalid JSON."
    };
  }
}

export function queryString(params: Record<string, unknown> = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  return search.size > 0 ? `?${search.toString()}` : "";
}

export function resolveUrl(baseUrl: string, path: string) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}
