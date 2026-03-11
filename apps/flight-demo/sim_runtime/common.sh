#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
: "${ARRAKIS_FLIGHTGEAR_SCRIPT:=$ARRAKIS_ARDUPILOT_DIR/Tools/autotest/fg_plane_view.sh}"
: "${ARRAKIS_FLIGHTGEAR_BIN:=/Applications/FlightGear.app/Contents/MacOS/FlightGear}"

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

runtime_print_summary() {
  echo "[sim-runtime] GZ_VERSION=$ARRAKIS_GZ_VERSION"
  echo "[sim-runtime] ARDUPILOT_DIR=$ARRAKIS_ARDUPILOT_DIR"
  echo "[sim-runtime] ARDUPILOT_GAZEBO_DIR=$ARRAKIS_ARDUPILOT_GAZEBO_DIR"
  echo "[sim-runtime] GZ_WORLD=$ARRAKIS_GZ_WORLD"
  echo "[sim-runtime] GZ_CAMERA_ENABLE_TOPIC=${ARRAKIS_GZ_CAMERA_ENABLE_TOPIC:-<unset>}"
  echo "[sim-runtime] VEHICLE=$ARRAKIS_ARDUPILOT_VEHICLE FRAME=$ARRAKIS_ARDUPILOT_FRAME MODEL=$ARRAKIS_ARDUPILOT_MODEL"
  echo "[sim-runtime] DEFAULTS=$ARRAKIS_ARDUPILOT_DEFAULTS"
  echo "[sim-runtime] OUT=$ARRAKIS_ARDUPILOT_OUT"
  echo "[sim-runtime] MAVPROXY_ARGS=${ARRAKIS_MAVPROXY_ARGS:-<unset>}"
  echo "[sim-runtime] FLIGHTGEAR_SCRIPT=$ARRAKIS_FLIGHTGEAR_SCRIPT"
  echo "[sim-runtime] FLIGHTGEAR_BIN=$ARRAKIS_FLIGHTGEAR_BIN"
}
