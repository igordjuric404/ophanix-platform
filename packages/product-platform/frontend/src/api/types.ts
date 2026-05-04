export interface ApiErrorPayload {
  detail?: string;
  message?: string;
  [key: string]: unknown;
}

export interface UserPrincipal {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
  scopes?: string[];
  organization_id?: string | null;
  environment_id?: string | null;
  actor_type?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_at: number;
  user: UserPrincipal;
}

export interface DevLoginRequest {
  email: string;
  display_name?: string;
  roles?: string[];
  organization_id?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug?: string;
}

export interface Environment {
  id: string;
  name: string;
  organization_id: string;
  slug?: string;
}

export interface SystemDependency {
  name: string;
  status: string;
  required: boolean;
  message?: string | null;
  details?: string | null;
  latency_ms?: number | null;
}

export interface VersionInfo {
  app_name?: string;
  build_sha?: string;
  build_time?: string;
  environment?: string;
  version?: string;
}
