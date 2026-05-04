#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/open_computer_use_mcp_server.py"
fi

exec python3 "$ROOT_DIR/scripts/open_computer_use_mcp_server.py"
