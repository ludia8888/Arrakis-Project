#!/bin/bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "[sim-runtime] Homebrew is required but not installed" >&2
  exit 1
fi

echo "[sim-runtime] tapping osrf/simulation"
brew tap osrf/simulation

echo "[sim-runtime] installing Gazebo Harmonic"
brew install gz-harmonic

echo "[sim-runtime] Gazebo Harmonic install complete"
echo "[sim-runtime] verify with: gz sim -s"
