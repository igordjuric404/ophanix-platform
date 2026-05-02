# Ophanix Product Platform

FastAPI control plane and static application shell for the productized Ophanix governance platform.

## One-command Startup

Run the local platform without manual migrations, seeding, or server setup:

```bash
./start.sh
```

The script starts the API, worker loop, sample MCP/agent services, SQLite migrations/seed, and a local frontend proxy.

Open `http://127.0.0.1:3000` and sign in with `admin@example.com`.

To run the Docker Compose demo stack instead:

```bash
./start.sh --docker
```

## Local API

```bash
python3 -m product_platform.cli serve --host 127.0.0.1 --port 8088
```

The legacy shorthand still works because omitting a subcommand starts the API:

```bash
python3 -m product_platform.cli --host 127.0.0.1 --port 8088
```

## Database Migrations

Local database migrations use the standard library SQLite driver. Set `OPHANIX_DATABASE_URL` to a `sqlite:///...` URL or use the default `sqlite:///ophanix_product.db`.

```bash
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db migrate
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db rollback
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db seed
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db python3 -m product_platform.cli db reset-demo
```

## Tests

The foundation implementation uses Python's standard `unittest` runner so the package can be validated in the current workspace without installing test-only dependencies:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
