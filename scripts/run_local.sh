#!/bin/bash
# Run local brains connected to Render infrastructure.
# Usage: ./scripts/run_local.sh <brain_id>
# Requires: local .env with Render Redis external URL set.
#
# Example:
#   BLVCKSHELL_REDIS_URL=redis://red-xxxxx.render.com:6379
#   BLVCKSHELL_RUN_WORKERS_IN_PROCESS=false
#   BLVCKSHELL_OLLAMA_URL=http://localhost:11434
#   ./scripts/run_local.sh venture

set -euo pipefail

BRAIN_ID="${1:-venture}"

if [[ -z "${BLVCKSHELL_REDIS_URL:-}" ]]; then
  echo "Error: BLVCKSHELL_REDIS_URL is not set." >&2
  echo "Get the Redis external URL from the Render dashboard and add it to .env" >&2
  exit 1
fi

echo "Starting local brain: ${BRAIN_ID}"
echo "Connecting to Redis: ${BLVCKSHELL_REDIS_URL}"
echo "Ollama: ${BLVCKSHELL_OLLAMA_URL:-http://localhost:11434}"
echo "Valid brain ids: venture, commander, capital"

exec python3 -m scripts.run_brain "${BRAIN_ID}"
