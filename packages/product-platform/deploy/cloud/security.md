# Cloud Auth, TLS, And Network Requirements

## Identity Provider

Configure the pilot IdP with:

- `OPHANIX_IDP_ISSUER_URL`
- `OPHANIX_IDP_AUDIENCE`
- Callback URL: `https://app.example.com/auth/callback`
- Logout URL: `https://app.example.com/auth/logout`

Pilot users should be assigned through IdP groups mapped to product roles.
Disable dev login by leaving `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS` empty.

## TLS

Terminate TLS at the cloud load balancer or ingress and set
`OPHANIX_TLS_CERTIFICATE_REF` to the managed certificate identifier. The API
should only receive traffic from the frontend domain and internal service
network.

## Network

Restrict API, worker, Redis, database, and secret-manager access to the private
network ranges in `OPHANIX_INTERNAL_CIDRS`. Expose only the frontend and API
load balancer ports publicly.

## CORS

Set `CORS_ALLOWED_ORIGINS` to the exact frontend HTTPS origin, for example:

```text
CORS_ALLOWED_ORIGINS=https://app.example.com
```
