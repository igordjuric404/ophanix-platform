# Product Platform Local Demo

This compose stack runs the Demo Lab with the static frontend, product API,
worker health loop, demo seed/init service, Redis, PostgreSQL, a
sample MCP service, and sample support/refund/research agents.

## Start

Copy the environment template, then start the core demo stack:

```bash
cp .env.example .env
docker compose --env-file .env -f docker-compose.demo.yml up --build
```

Open the app at `http://localhost:3000` and sign in with
`admin@example.com` through dev login. The API is available at
`http://localhost:8088`.

## Optional Services

Run the policy service profile:

```bash
docker compose --env-file .env -f docker-compose.demo.yml --profile policy up --build
```

Run the observability profile:

```bash
docker compose --env-file .env -f docker-compose.demo.yml --profile observability up --build
```

Useful URLs:

- Frontend: `http://localhost:3000`
- API health: `http://localhost:8088/health`
- API readiness: `http://localhost:8088/ready`
- Sample MCP health: `http://localhost:8091/health`
- Grafana profile: `http://localhost:3001`
- Prometheus profile: `http://localhost:9090`

## Stop, Logs, And Reset

```bash
docker compose --env-file .env -f docker-compose.demo.yml logs -f api worker sample-mcp
docker compose --env-file .env -f docker-compose.demo.yml down
docker compose --env-file .env -f docker-compose.demo.yml down --volumes
```

To run the end-to-end compose smoke in a Docker-capable environment:

```bash
sh deploy/local-demo-smoke.sh
```

The smoke starts the stack, verifies `/ready`, resets Demo Lab, confirms the
baseline is healthy, and starts the customer-support refund scenario.

Reset the Demo Lab from the UI by typing `RESET` in Demo Lab -> Environment
Reset. The equivalent local CLI command for the API volume is:

```bash
docker compose --env-file .env -f docker-compose.demo.yml run --rm migrate-seed db reset-demo
docker compose --env-file .env -f docker-compose.demo.yml run --rm migrate-seed db seed
```

## Credentials

Required for the local scripted demo:

- `OPHANIX_SESSION_SECRET`
- `OPHANIX_DEV_LOGIN_ALLOWED_EMAILS`

Optional:

- Model provider API keys
- Observability tokens
- External MCP credentials

Missing optional provider credentials show a warning in Demo Lab prerequisites.
They do not fail the baseline or block the scripted local scenario.

## Troubleshooting

If ports are already in use, change `PRODUCT_FRONTEND_PORT`,
`PRODUCT_API_PORT`, `DEMO_MCP_PORT`, `POSTGRES_PORT`, or `REDIS_PORT` in
`.env`.

If Docker reports stale health checks, run:

```bash
docker compose --env-file .env -f docker-compose.demo.yml ps
docker compose --env-file .env -f docker-compose.demo.yml logs api migrate-seed
```

If Demo Lab prerequisites are degraded, run the reset from the UI or reseed:

```bash
docker compose --env-file .env -f docker-compose.demo.yml run --rm migrate-seed db seed
```

The local demo command path uses the `postgres` service as the product database.
The `product_postgres_data` volume holds local database state; use
`docker compose --env-file .env -f docker-compose.demo.yml down --volumes` to
reset it completely.
