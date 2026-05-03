#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." && pwd)"
API_IMAGE="${API_IMAGE:-ophanix-product-api:smoke}"
WORKER_IMAGE="${WORKER_IMAGE:-ophanix-product-worker:smoke}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-ophanix-product-frontend:smoke}"
API_PORT="${API_PORT:-18088}"
API_DB_URL="${API_DB_URL:-sqlite:////tmp/ophanix_product_smoke.db}"

docker info >/dev/null

docker build -f "$SCRIPT_DIR/Dockerfile.api" -t "$API_IMAGE" "$REPO_ROOT"
docker build -f "$SCRIPT_DIR/Dockerfile.worker" -t "$WORKER_IMAGE" "$REPO_ROOT"
docker build -f "$SCRIPT_DIR/Dockerfile.frontend" -t "$FRONTEND_IMAGE" "$REPO_ROOT"

docker run --rm \
  -e OPHANIX_DATABASE_URL="$API_DB_URL" \
  "$API_IMAGE" db migrate

API_CONTAINER="$(
  docker run -d \
    -e OPHANIX_DATABASE_URL="$API_DB_URL" \
    -p "$API_PORT:8088" \
    "$API_IMAGE" serve --host 0.0.0.0 --port 8088
)"

cleanup() {
  docker rm -f "$API_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

sleep 3
curl --fail "http://127.0.0.1:$API_PORT/health" >/dev/null
curl --fail "http://127.0.0.1:$API_PORT/ready" >/dev/null

docker run --rm "$WORKER_IMAGE" worker noop

printf '%s\n' "Product platform image smoke checks passed."
