#!/bin/bash
set -euo pipefail

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "[sim-runtime] host is not Apple Silicon; Rosetta shell is not needed"
  exec "$SHELL" -l
fi

if ! /usr/bin/pgrep oahd >/dev/null 2>&1; then
  echo "[sim-runtime] Rosetta does not appear to be installed" >&2
  echo "Run: softwareupdate --install-rosetta --agree-to-license" >&2
  exit 1
fi

echo "[sim-runtime] opening x86_64 shell via Rosetta"
exec arch -x86_64 "$SHELL" -l
