#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

runtime_detect_python_user_bin() {
  if ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  python3 - <<'PY'
import os
import site

print(os.path.join(site.getuserbase(), "bin"))
PY
}

runtime_load_env() {
  local env_file="$1"
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    value="${value//\$\{HOME\}/$HOME}"
    value="${value//\$HOME/$HOME}"
    if [[ "$value" == ~/* ]]; then
      value="$HOME/${value#~/}"
    fi
    printf -v "$key" '%s' "$value"
    export "$key"
  done < "$env_file"
}

if [[ -f "$SIM_ROOT/runtime.env" ]]; then
  runtime_load_env "$SIM_ROOT/runtime.env"
fi

if [[ -d "$HOME/.local/bin" ]]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

PYTHON_USER_BIN="$(runtime_detect_python_user_bin 2>/dev/null || true)"
if [[ -n "$PYTHON_USER_BIN" && -d "$PYTHON_USER_BIN" ]]; then
  export PATH="$PYTHON_USER_BIN:$PATH"
fi

: "${ARRAKIS_GZ_VERSION:=harmonic}"
: "${ARRAKIS_ARDUPILOT_DIR:=$HOME/Developer/ardupilot}"
: "${ARRAKIS_ARDUPILOT_GAZEBO_DIR:=$HOME/Developer/ardupilot_gazebo}"
: "${ARRAKIS_GZ_WORLD:=zephyr_runway.sdf}"
: "${ARRAKIS_GZ_VERBOSE:=4}"
: "${ARRAKIS_GZ_CAMERA_ENABLE_TOPIC:=}"
: "${ARRAKIS_ARDUPILOT_VEHICLE:=ArduPlane}"
: "${ARRAKIS_ARDUPILOT_FRAME:=quadplane}"
: "${ARRAKIS_ARDUPILOT_MODEL:=}"
: "${ARRAKIS_ARDUPILOT_DEFAULTS:=apps/flight-demo/sim_runtime/params/quadplane_demo.parm}"
: "${ARRAKIS_ARDUPILOT_MAP:=1}"
: "${ARRAKIS_ARDUPILOT_CONSOLE:=1}"
: "${ARRAKIS_ARDUPILOT_WIPE:=1}"
: "${ARRAKIS_ARDUPILOT_OUT:=127.0.0.1:14550}"
: "${ARRAKIS_MAVPROXY_ARGS:=}"
: "${ARRAKIS_MAVPROXY_BIN:=}"
: "${ARRAKIS_FLIGHTGEAR_SCRIPT:=$ARRAKIS_ARDUPILOT_DIR/Tools/autotest/fg_quad_view.sh}"
: "${ARRAKIS_FLIGHTGEAR_BIN:=/Applications/FlightGear.app/Contents/MacOS/FlightGear}"
: "${ARRAKIS_FLIGHTGEAR_VIEW_NUMBER:=2}"
: "${ARRAKIS_FLIGHTGEAR_INTERNAL_VIEW:=0}"
: "${ARRAKIS_FLIGHTGEAR_CHASE_DISTANCE_M:=-18}"
: "${ARRAKIS_FLIGHTGEAR_EXTRA_ARGS:=}"

runtime_require_dir() {
  local path="$1"
  local label="$2"
  if [[ ! -d "$path" ]]; then
    echo "[sim-runtime] missing $label at $path" >&2
    echo "[sim-runtime] copy runtime.env.example to runtime.env and set the correct path" >&2
    exit 1
  fi
}

runtime_export_gazebo_env() {
  runtime_require_dir "$ARRAKIS_ARDUPILOT_GAZEBO_DIR" "ardupilot_gazebo dir"

  export GZ_VERSION="$ARRAKIS_GZ_VERSION"
  export GZ_SIM_SYSTEM_PLUGIN_PATH="${ARRAKIS_ARDUPILOT_GAZEBO_DIR}/build:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
  export GZ_SIM_RESOURCE_PATH="${ARRAKIS_ARDUPILOT_GAZEBO_DIR}/models:${ARRAKIS_ARDUPILOT_GAZEBO_DIR}/worlds:${GZ_SIM_RESOURCE_PATH:-}"
}

runtime_resolve_mavproxy_bin() {
  if [[ -n "$ARRAKIS_MAVPROXY_BIN" && -x "$ARRAKIS_MAVPROXY_BIN" ]]; then
    echo "$ARRAKIS_MAVPROXY_BIN"
    return 0
  fi

  if command -v mavproxy.py >/dev/null 2>&1; then
    command -v mavproxy.py
    return 0
  fi

  local candidate
  for candidate in \
    "$HOME/.local/bin/mavproxy.py" \
    "$PYTHON_USER_BIN/mavproxy.py" \
    "$HOME/Library/Python/3.12/bin/mavproxy.py"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

runtime_require_mavproxy() {
  local mavproxy_bin
  if ! mavproxy_bin="$(runtime_resolve_mavproxy_bin)"; then
    echo "[sim-runtime] mavproxy.py not found on PATH" >&2
    echo "[sim-runtime] install MAVProxy and future into the active Python user environment" >&2
    echo "[sim-runtime] example: python3 -m pip install --user --break-system-packages MAVProxy future" >&2
    exit 1
  fi

  export ARRAKIS_MAVPROXY_BIN="$mavproxy_bin"
  export PATH="$(dirname "$mavproxy_bin"):$PATH"
}

runtime_print_summary() {
  echo "[sim-runtime] GZ_VERSION=$ARRAKIS_GZ_VERSION"
  echo "[sim-runtime] ARDUPILOT_DIR=$ARRAKIS_ARDUPILOT_DIR"
  echo "[sim-runtime] ARDUPILOT_GAZEBO_DIR=$ARRAKIS_ARDUPILOT_GAZEBO_DIR"
  echo "[sim-runtime] GZ_WORLD=$ARRAKIS_GZ_WORLD"
  echo "[sim-runtime] GZ_CAMERA_ENABLE_TOPIC=${ARRAKIS_GZ_CAMERA_ENABLE_TOPIC:-<unset>}"
  echo "[sim-runtime] VEHICLE=$ARRAKIS_ARDUPILOT_VEHICLE FRAME=$ARRAKIS_ARDUPILOT_FRAME MODEL=$ARRAKIS_ARDUPILOT_MODEL"
  echo "[sim-runtime] DEFAULTS=$ARRAKIS_ARDUPILOT_DEFAULTS"
  echo "[sim-runtime] OUT=$ARRAKIS_ARDUPILOT_OUT"
  echo "[sim-runtime] MAVPROXY_BIN=${ARRAKIS_MAVPROXY_BIN:-<auto>}"
  echo "[sim-runtime] MAVPROXY_ARGS=${ARRAKIS_MAVPROXY_ARGS:-<unset>}"
  echo "[sim-runtime] FLIGHTGEAR_SCRIPT=$ARRAKIS_FLIGHTGEAR_SCRIPT"
  echo "[sim-runtime] FLIGHTGEAR_BIN=$ARRAKIS_FLIGHTGEAR_BIN"
  echo "[sim-runtime] FLIGHTGEAR_VIEW_NUMBER=$ARRAKIS_FLIGHTGEAR_VIEW_NUMBER"
  echo "[sim-runtime] FLIGHTGEAR_INTERNAL_VIEW=$ARRAKIS_FLIGHTGEAR_INTERNAL_VIEW"
  echo "[sim-runtime] FLIGHTGEAR_CHASE_DISTANCE_M=$ARRAKIS_FLIGHTGEAR_CHASE_DISTANCE_M"
  echo "[sim-runtime] FLIGHTGEAR_EXTRA_ARGS=${ARRAKIS_FLIGHTGEAR_EXTRA_ARGS:-<unset>}"
}
