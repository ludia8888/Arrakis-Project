# Arrakis VTOL Sim Runtime

This demo is built to keep the Arrakis mission/state machine independent from the flight stack.

## v1 runtime strategy

- App layer: macOS arm64 native
- Flight stack: ArduPilot first
- Simulator path:
  1. Rosetta x86_64 shell on Apple Silicon
  2. If frame rate / RTF is unstable, move SITL + sim into UTM Ubuntu

## Apple Silicon risk notes

- ArduPilot SITL + Gazebo on Apple Silicon is the first hard risk in this stack.
- `ardupilot_gazebo` and its rendering/plugin path must be smoke-tested before any mission work is considered valid.
- On M4, Rosetta is only the first attempt, not the long-term assumption.
- If Gazebo plugin build, GUI rendering, or camera transport becomes unstable under Rosetta:
  - stop debugging the local graphics stack
  - move Gazebo/SITL into Ubuntu VM
  - keep the Arrakis app layer on macOS
  - bring video/telemetry back over the adapter boundary

## Success criteria

- SITL boots
- Simulator camera can be consumed by the adapter
- 5 minute round-trip run completes without severe RTF collapse
- Gazebo plugin path stays stable enough to provide camera frames continuously

## Local smoke commands

Environment probe:

```bash
cd apps/flight-demo/sim_runtime
./check_environment.sh
```

Runtime env template:

```bash
cd apps/flight-demo/sim_runtime
cp runtime.env.example runtime.env
```

Update `runtime.env` so these paths match your machine:
- `ARRAKIS_ARDUPILOT_DIR`
- `ARRAKIS_ARDUPILOT_GAZEBO_DIR`

Adapter smoke once SITL is already running:

```bash
cd apps/flight-demo/sim_runtime
../../.venv/bin/python smoke_ardupilot_sitl.py
```

Optional camera verification:

```bash
ARRAKIS_ARDUPILOT_VIDEO_SOURCE=0 ../../.venv/bin/python smoke_ardupilot_sitl.py
```

Notes:
- `smoke_ardupilot_sitl.py` only verifies the adapter contract path on top of a running SITL connection.
- It does not launch SITL or Gazebo for you.
- Video is only checked if `ARRAKIS_ARDUPILOT_VIDEO_SOURCE` is set.

## Local run sequence

Terminal 1, Gazebo:

```bash
cd apps/flight-demo/sim_runtime
./run_gazebo_zephyr.sh
```

Terminal 2, ArduPilot SITL:

```bash
cd apps/flight-demo/sim_runtime
./run_ardupilot_zephyr.sh
```

Terminal 3, backend on the real adapter:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

Terminal 4, adapter smoke:

```bash
cd apps/flight-demo/sim_runtime
../../.venv/bin/python smoke_ardupilot_sitl.py
```

If Rosetta/Gazebo becomes unstable:
- keep the backend/app layer on macOS
- move Gazebo + SITL into Ubuntu VM
- point `ARRAKIS_ARDUPILOT_CONNECTION` and `ARRAKIS_ARDUPILOT_VIDEO_SOURCE` at the VM-exposed endpoints

## Failure triggers for Rosetta path

- GUI FPS stays below 20
- RTF stays below 0.7
- Camera stream repeatedly stalls
- Gazebo plugin compile/runtime instability on x86_64 Rosetta
- Camera transport drops or freezes often enough to break detector cadence

## Adapter contract reminder

The simulator implementation is not allowed to leak into the Arrakis core directly.
Video, telemetry, and command execution must enter through the flight adapter boundary.

## ArduPilot adapter notes

- VTOL transition commands must not assume MAVSDK feature parity with PX4.
- `DO_VTOL_TRANSITION` support and mission-item behavior must be verified against ArduPilot SITL first.
- If MAVSDK does not map the needed VTOL operations cleanly, the adapter should use `pymavlink` for the low-level command path while preserving the same Arrakis adapter interface.
- Video should enter Arrakis through `stream_video(callback)` only.
- The first implementation may use a latest-frame queue with OpenCV frames, but if latency grows the next step is shared memory or another single-copy transport inside the adapter/video worker boundary.
