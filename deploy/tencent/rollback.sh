#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/tencent/docker-compose.cloud.yml"

cd "$ROOT_DIR/deploy/tencent"

docker compose -f "$COMPOSE_FILE" down
docker image tag vibe-trading:cloud-three-page-previous vibe-trading:cloud-three-page
docker compose -f "$COMPOSE_FILE" up -d
docker compose -f "$COMPOSE_FILE" ps
