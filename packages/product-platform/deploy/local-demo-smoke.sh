#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PACKAGE_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-.env.example}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-180}"
API_BASE="${API_BASE:-http://127.0.0.1:8088}"
COMPOSE="docker compose --env-file $ENV_FILE -f docker-compose.demo.yml"

cd "$PACKAGE_DIR"
docker info >/dev/null

$COMPOSE up --build --wait --wait-timeout "$WAIT_TIMEOUT"

cleanup() {
  $COMPOSE down >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

python - "$API_BASE" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

api_base = sys.argv[1].rstrip("/")


def request(path: str, *, method: str = "GET", token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Environment-ID": "env_default"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(api_base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        payload = response.read().decode("utf-8")
        return response.status, json.loads(payload) if payload else {}


ready_status, ready = request("/ready")
assert ready_status == 200, ready
assert ready["status"] == "ready", ready

login_status, login = request(
    "/api/v1/auth/dev-login",
    method="POST",
    body={"email": "admin@example.com"},
)
assert login_status == 200, login
token = login["access_token"]

reset_status, reset = request(
    "/api/v1/demo/reset",
    method="POST",
    token=token,
    body={"confirmation": "RESET"},
)
assert reset_status == 201, reset

baseline_status, baseline = request("/api/v1/demo/baseline-status", token=token)
assert baseline_status == 200, baseline
assert baseline["overall_status"] == "healthy", baseline

run_status, run = request(
    "/api/v1/demo/scenarios/customer-support-refund/runs",
    method="POST",
    token=token,
)
assert run_status == 201, run
assert run["scenario_id"] == "customer-support-refund", run

print("Local demo compose smoke checks passed.")
PY
