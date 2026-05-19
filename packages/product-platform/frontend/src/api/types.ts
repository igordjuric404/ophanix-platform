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
  environment_ids?: string[];
  idp_subject?: string | null;
  idp_issuer?: string | null;
  token_id?: string | null;
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
  environment_ids?: string[];
}

export interface Organization {
  id: string;
  name: string;
  slug?: string;
  created_at?: string;
}

export interface Environment {
  id: string;
  name: string;
  organization_id: string;
  slug?: string;
  type?: string;
  created_at?: string;
}

export interface EnvironmentCreateRequest {
  name: string;
  slug: string;
  type: string;
}

export interface ApiKey {
  id: string;
  organization_id: string;
  name: string;
  scopes: string[];
  kind: string;
  environment_ids: string[];
  expires_at: number | null;
  last_used_at: number | null;
  revoked_at: number | null;
  created_at: number;
}

export interface ApiKeyCreateRequest {
  name: string;
  scopes: string[];
  kind: string;
  expires_at?: number | null;
  environment_ids?: string[];
}

export interface ApiKeyCreateResponse {
  key: ApiKey;
  secret: string;
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
