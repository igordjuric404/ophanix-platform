#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DB_PATH="$ROOT_DIR/ophanix_product.db"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8088}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
WORKER_INTERVAL_SECONDS="${WORKER_INTERVAL_SECONDS:-10}"
MODE="local"

usage() {
  cat <<'EOF'
Usage: ./start.sh [--local|--docker]

Starts the Ophanix Product Platform with no manual setup.

Modes:
  --local   Run API, worker, demo services, SQLite migration/seed, and frontend proxy.
            This is the default and does not require Docker.
  --docker  Run the full Docker Compose demo stack.

Environment overrides:
  API_PORT=8088 FRONTEND_PORT=3000 ./start.sh
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      MODE="local"
      ;;
    --docker)
      MODE="docker"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export OPHANIX_DATABASE_URL="${OPHANIX_DATABASE_URL:-sqlite:///$DB_PATH}"
export OPHANIX_ENVIRONMENT="${OPHANIX_ENVIRONMENT:-local-demo}"
export OPHANIX_BUILD_SHA="${OPHANIX_BUILD_SHA:-local-script}"
export OPHANIX_BUILD_TIME="${OPHANIX_BUILD_TIME:-local}"
export OPHANIX_DEFAULT_ORGANIZATION_ID="${OPHANIX_DEFAULT_ORGANIZATION_ID:-org_default}"
export OPHANIX_DEV_LOGIN_ALLOWED_EMAILS="${OPHANIX_DEV_LOGIN_ALLOWED_EMAILS:-admin@example.com,demo@example.com}"
case ",$OPHANIX_DEV_LOGIN_ALLOWED_EMAILS," in
  *,admin@example.com,*)
    ;;
  *)
    export OPHANIX_DEV_LOGIN_ALLOWED_EMAILS="admin@example.com,$OPHANIX_DEV_LOGIN_ALLOWED_EMAILS"
    ;;
esac
export OPHANIX_SESSION_SECRET="${OPHANIX_SESSION_SECRET:-replace-with-a-long-local-secret}"
export OPHANIX_SESSION_TTL_SECONDS="${OPHANIX_SESSION_TTL_SECONDS:-28800}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT}"

PIDS=""
PROXY_SCRIPT=""
CLEANED_UP=0

log() {
  printf '[product-platform] %s\n' "$*"
}

ensure_dotenv_dev_login_allowlist() {
  if [ ! -f .env ]; then
    return
  fi
  current="$(grep '^OPHANIX_DEV_LOGIN_ALLOWED_EMAILS=' .env | head -n 1 | cut -d= -f2- || true)"
  case ",$current," in
    *,admin@example.com,*)
      return
      ;;
  esac
  tmp=".env.tmp.$$"
  if [ -n "$current" ]; then
    awk '
      /^OPHANIX_DEV_LOGIN_ALLOWED_EMAILS=/ {
        print "OPHANIX_DEV_LOGIN_ALLOWED_EMAILS=admin@example.com," substr($0, index($0, "=") + 1)
        next
      }
      { print }
    ' .env > "$tmp"
    mv "$tmp" .env
  else
    printf '\nOPHANIX_DEV_LOGIN_ALLOWED_EMAILS=admin@example.com,demo@example.com\n' >> .env
  fi
  log "Ensured admin@example.com is allowed for development login"
}

cleanup() {
  status=$?
  if [ "$CLEANED_UP" -eq 1 ]; then
    exit "$status"
  fi
  CLEANED_UP=1
  if [ -n "$PIDS" ]; then
    log "Stopping local services..."
    for pid in $PIDS; do
      kill "$pid" >/dev/null 2>&1 || true
    done
    wait $PIDS >/dev/null 2>&1 || true
  fi
  if [ -n "$PROXY_SCRIPT" ] && [ -f "$PROXY_SCRIPT" ]; then
    rm -f "$PROXY_SCRIPT"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

require_python_dependencies() {
  python3 - <<'PY'
import importlib.util
import sys

missing = [
    module
    for module in ("fastapi", "uvicorn", "pydantic")
    if importlib.util.find_spec(module) is None
]
if missing:
    print(
        "Missing Python dependencies: "
        + ", ".join(missing)
        + "\nInstall them from packages/product-platform, for example:\n"
        + "  python3 -m pip install -e .",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

wait_for_url() {
  url="$1"
  label="$2"
  attempts="${3:-60}"
  python3 - "$url" "$label" "$attempts" <<'PY'
import sys
import time
import urllib.error
import urllib.request

url, label, attempts = sys.argv[1], sys.argv[2], int(sys.argv[3])
for _ in range(attempts):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            if response.status < 500:
                raise SystemExit(0)
    except (OSError, urllib.error.URLError):
        time.sleep(1)

print(f"{label} did not become ready at {url}", file=sys.stderr)
raise SystemExit(1)
PY
}

start_process() {
  label="$1"
  shift
  log "Starting $label..."
  "$@" &
  pid=$!
  PIDS="$PIDS $pid"
}

create_frontend_proxy() {
  PROXY_SCRIPT="$(mktemp "${TMPDIR:-/tmp}/ophanix-frontend-proxy.XXXXXX.py")"
  cat > "$PROXY_SCRIPT" <<'PY'
from __future__ import annotations

import argparse
import http.client
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class FrontendProxy(BaseHTTPRequestHandler):
    frontend_dir: Path
    api_host: str
    api_port: int

    def do_GET(self) -> None:
        if self.path.startswith("/api/") or self.path == "/version":
            self.proxy_to_api()
            return
        self.serve_static()

    def do_POST(self) -> None:
        self.proxy_to_api()

    def do_PATCH(self) -> None:
        self.proxy_to_api()

    def do_DELETE(self) -> None:
        self.proxy_to_api()

    def proxy_to_api(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        headers["Host"] = f"{self.api_host}:{self.api_port}"
        connection = http.client.HTTPConnection(self.api_host, self.api_port, timeout=30)
        try:
            connection.request(self.command, self.path, body=body or None, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in {"connection", "transfer-encoding"}:
                    self.send_header(key, value)
            self.end_headers()
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            connection.close()

    def serve_static(self) -> None:
        path = urlsplit(self.path).path
        candidate = (self.frontend_dir / path.lstrip("/")).resolve()
        if not str(candidate).startswith(str(self.frontend_dir.resolve())):
            self.send_error(403)
            return
        if path == "/" or not candidate.exists() or candidate.is_dir():
            candidate = self.frontend_dir / "index.html"
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[frontend] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8088)
    args = parser.parse_args()

    FrontendProxy.frontend_dir = Path(args.frontend_dir)
    FrontendProxy.api_host = args.api_host
    FrontendProxy.api_port = args.api_port
    server = ThreadingHTTPServer((args.host, args.port), FrontendProxy)
    print(f"Frontend proxy serving http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
PY
}

run_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Run ./start.sh --local instead." >&2
    exit 1
  fi
  if [ ! -f .env ]; then
    cp .env.example .env
    log "Created .env from .env.example"
  fi
  ensure_dotenv_dev_login_allowlist
  log "Starting Docker Compose demo stack..."
  log "Frontend: http://localhost:${PRODUCT_FRONTEND_PORT:-3000}"
  log "API:      http://localhost:${PRODUCT_API_PORT:-8088}"
  exec docker compose --env-file .env -f docker-compose.demo.yml up --build
}

run_local() {
  require_python_dependencies
  create_frontend_proxy

  log "Applying migrations..."
  python3 -m product_platform.cli db migrate
  log "Seeding demo data..."
  python3 -m product_platform.cli db seed

  start_process "API on http://$API_HOST:$API_PORT" \
    python3 -m product_platform.cli serve --host "$API_HOST" --port "$API_PORT"
  wait_for_url "http://$API_HOST:$API_PORT/ready" "API"

  start_process "worker loop" \
    python3 -m product_platform.cli worker loop --interval-seconds "$WORKER_INTERVAL_SECONDS"
  start_process "sample MCP service on http://$API_HOST:8091" \
    python3 -m product_platform.cli demo-service serve --service mcp --host "$API_HOST" --port 8091
  start_process "support agent on http://$API_HOST:8092" \
    python3 -m product_platform.cli demo-service serve --service agent --agent-id agent_demo_support --host "$API_HOST" --port 8092
  start_process "refund agent on http://$API_HOST:8093" \
    python3 -m product_platform.cli demo-service serve --service agent --agent-id agent_demo_refund --host "$API_HOST" --port 8093
  start_process "research agent on http://$API_HOST:8094" \
    python3 -m product_platform.cli demo-service serve --service agent --agent-id agent_demo_research --host "$API_HOST" --port 8094

  start_process "frontend on http://$FRONTEND_HOST:$FRONTEND_PORT" \
    python3 "$PROXY_SCRIPT" \
      --frontend-dir "$FRONTEND_DIR" \
      --host "$FRONTEND_HOST" \
      --port "$FRONTEND_PORT" \
      --api-host "$API_HOST" \
      --api-port "$API_PORT"
  wait_for_url "http://$FRONTEND_HOST:$FRONTEND_PORT" "Frontend"

  cat <<EOF

Ophanix Product Platform is running.

Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT
API:      http://$API_HOST:$API_PORT
Health:   http://$API_HOST:$API_PORT/health
Ready:    http://$API_HOST:$API_PORT/ready

Dev login email: admin@example.com

Press Ctrl-C to stop everything.
EOF

  wait
}

case "$MODE" in
  docker)
    run_docker
    ;;
  local)
    run_local
    ;;
esac
