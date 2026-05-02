# Frontend Framework Refactor Plan

## Foundation Scope

The shared foundation replaces the active vanilla JavaScript entry point with a React, TypeScript, and Vite application while keeping the existing backend API contracts intact.

## Inventory

- Active frontend package: `packages/product-platform/frontend`.
- Previous entry point: `index.html` loaded `src/app.js`; new entry point loads `src/main.tsx`.
- Previous local serving: `packages/product-platform/start.sh` served static files with a Python API proxy.
- New local serving: Vite dev server with `/api` and `/version` proxying to FastAPI.
- Docker demo serving: Nginx serves built Vite assets and proxies `/api` to the API container.
- Cloud serving: frontend Dockerfile builds Vite assets and serves `dist/` through Nginx.
- EventSource endpoint: `/api/v1/policy-evaluations/stream`.
- Durable browser preference key: `ophanix.selectedEnvironmentId`.

## Route Foundation

The route registry preserves the existing top-level routes:

- `/overview`
- `/agents`
- `/policies`
- `/trust`
- `/mcp`
- `/mesh`
- `/runtime`
- `/discovery`
- `/marketplace`
- `/compliance`
- `/observability`
- `/integrations`
- `/workflows`
- `/demo-lab`
- `/settings`

## Migration Rules

- Use TanStack Router for client-side routes.
- Use TanStack Query for server data and mutations.
- Use `credentials: "include"` on API requests to preserve `ophanix_session`.
- Keep old JavaScript modules present during feature migration but inactive from the app entry point.
- Migrate feature folders one worktree phase at a time after the framework foundation commit.

