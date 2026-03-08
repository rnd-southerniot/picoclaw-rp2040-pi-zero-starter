#!/usr/bin/env bash
set -euo pipefail

HOST_NAME="${1:-pi-zero.local}"

ping_once() {
  local target="$1"
  if ping -c 1 "$target" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

resolve_mdns() {
  local target="$1"
  if command -v avahi-resolve-host-name >/dev/null 2>&1; then
    avahi-resolve-host-name -4 "$target" 2>/dev/null | awk '{print $2}' | head -n1
    return 0
  fi
  return 1
}

find_from_neighbors() {
  if command -v ip >/dev/null 2>&1; then
    ip neigh 2>/dev/null | awk '/lladdr/ {print $1, $5}'
  elif command -v arp >/dev/null 2>&1; then
    arp -an | awk '{print $2, $4}' | tr -d '()'
  fi
}

if ping_once "$HOST_NAME"; then
  echo "$HOST_NAME"
  exit 0
fi

if mdns_ip="$(resolve_mdns "$HOST_NAME")" && [ -n "$mdns_ip" ]; then
  echo "$mdns_ip"
  exit 0
fi

neighbors="$(find_from_neighbors || true)"
if [ -n "$neighbors" ]; then
  # Raspberry Pi OUIs: b8:27:eb, dc:a6:32, e4:5f:01
  pi_ip="$(echo "$neighbors" | awk 'tolower($2) ~ /^(b8:27:eb|dc:a6:32|e4:5f:01)/ {print $1; exit}')"
  if [ -n "$pi_ip" ]; then
    echo "$pi_ip"
    exit 0
  fi
fi

echo "Unable to discover Pi Zero automatically." >&2
echo "Try: ping pi-zero.local or check your router DHCP leases." >&2
exit 1
