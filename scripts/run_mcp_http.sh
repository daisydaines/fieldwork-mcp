#!/usr/bin/env bash
# Run Fieldwork MCP over Streamable HTTP (local "remote" mode).
# Clients connect to: http://127.0.0.1:8000/mcp
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/.venv/bin/fieldwork-mcp"

if [[ ! -x "$BIN" ]]; then
  echo "fieldwork-mcp: missing $BIN" >&2
  echo "Run: cd \"$ROOT\" && python3 -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 1
fi

cd "$ROOT"
export FIELDWORK_MCP_TRANSPORT="${FIELDWORK_MCP_TRANSPORT:-streamable-http}"
export FIELDWORK_MCP_HOSTED="${FIELDWORK_MCP_HOSTED:-1}"
export FIELDWORK_MCP_HOST="${FIELDWORK_MCP_HOST:-127.0.0.1}"
export FIELDWORK_MCP_PORT="${FIELDWORK_MCP_PORT:-8000}"
# Dev convenience: allow env API key without bearer. Disable in shared deploys.
export FIELDWORK_MCP_ALLOW_ENV_FALLBACK="${FIELDWORK_MCP_ALLOW_ENV_FALLBACK:-1}"
exec "$BIN" "$@"