# Product Platform Frontend Migration Notes

## Current Architecture

The active product-platform frontend is the React, TypeScript, Vite, TanStack Router, and TanStack Query app under `src/app`, `src/features`, `src/api`, `src/components`, and `src/lib`.

`index.html` loads `src/main.tsx`. The previous vanilla JavaScript modules and `node --test` legacy suite have been retired, so new product behavior should be added to the React routes and covered with Vitest, React Testing Library, Playwright, or backend tests as appropriate.

## Local Development

From `packages/product-platform/frontend`:

```sh
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

The Vite dev server proxies `/api` and `/version` to `VITE_API_PROXY_TARGET`, defaulting to `http://127.0.0.1:8088`.

From `packages/product-platform`, the no-Docker local launcher still starts the API, worker, demo services, database migrate/seed flow, and frontend proxy:

```sh
./start.sh --local
```

## Testing

From `packages/product-platform/frontend`:

```sh
npm run lint
npm run typecheck
npm test
npm run test:e2e
npm run validate
```

`npm run validate` runs lint, typecheck, Vitest, and the production frontend build. `npm run test:e2e` starts the Vite dev server through Playwright; sandboxed environments may need localhost binding permission for this command.

Backend API and workflow coverage still lives under `packages/product-platform/tests`:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Docker Demo Runtime

From `packages/product-platform`, the full local demo stack uses the checked-in compose file:

```sh
docker compose --env-file .env.example -f docker-compose.demo.yml up --build --wait --wait-timeout 120
sh deploy/local-demo-smoke.sh
```

The compose demo builds the React frontend with the product-platform demo image and serves it on the configured frontend port.

## Cloud Frontend Build

`deploy/cloud/Dockerfile.frontend` builds the React app with:

```sh
npm ci
npm run build
```

The runtime stage serves the Vite `dist` output through Nginx and exposes `/healthz`. The cloud image smoke script validates the frontend image together with the API and worker images:

```sh
sh deploy/cloud/smoke-images.sh
```

## Preserved Limitations

- `/settings` remains a registered route scaffold until the settings workspace is implemented.
- Runtime smoke tests depend on Docker daemon and registry/base-image access.
- Playwright and some backend tests bind localhost and may need elevated sandbox permission.
- Detailed historical phase notes remain in `../../../docs/frontend-refactor-execution-log/` and follow-up completion evidence lives in `../../../docs/product-platform-worktree/refactor-follow-up-execution-logs/`.
