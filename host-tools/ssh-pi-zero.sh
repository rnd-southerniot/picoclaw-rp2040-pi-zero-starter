#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${1:-arif}"
TARGET="${2:-}"

if [ -z "$TARGET" ]; then
  TARGET="$($SCRIPT_DIR/find-pi-zero.sh)"
fi

exec ssh "$USER_NAME@$TARGET"
