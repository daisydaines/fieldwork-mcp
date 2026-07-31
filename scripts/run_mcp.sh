#!/usr/bin/env bash
# Stable launcher for Cursor / Claude Desktop / any MCP client.
# Loads the project venv binary and keeps cwd on the repo (for .env).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/.venv/bin/fieldwork-mcp"

if [[ ! -x "$BIN" ]]; then
  echo "fieldwork-mcp: missing $BIN" >&2
  echo "Run: cd \"$ROOT\" && python3 -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 1
fi

cd "$ROOT"
exec "$BIN" "$@"