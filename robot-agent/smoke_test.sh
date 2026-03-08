#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ -x "$SCRIPT_DIR/../.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/../.venv/bin/python"
fi

echo "[1/3] Syntax check"
"$PYTHON_BIN" -m py_compile \
  "$SCRIPT_DIR/protocol.py" \
  "$SCRIPT_DIR/serial_bridge.py" \
  "$SCRIPT_DIR/telemetry_logger.py" \
  "$SCRIPT_DIR/cli.py"

echo "[2/3] Protocol unit tests"
"$PYTHON_BIN" -m unittest discover -s "$SCRIPT_DIR/tests"

echo "[3/3] Dry-run command smoke"
"$PYTHON_BIN" "$SCRIPT_DIR/cli.py" --dry-run PING
"$PYTHON_BIN" "$SCRIPT_DIR/cli.py" --dry-run GET_STATE
"$PYTHON_BIN" "$SCRIPT_DIR/cli.py" --dry-run STOP

echo "Smoke test passed (no movement commands executed)."
