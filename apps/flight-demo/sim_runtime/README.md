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
- `ARRAKIS_GZ_CAMERA_ENABLE_TOPIC` if you want to enable simulator camera streaming

Bootstrap macOS runtime prerequisites:

```bash
cd apps/flight-demo/sim_runtime
./bootstrap_macos_runtime.sh
```

Open a dedicated Rosetta shell when you need an x86_64 session:

```bash
cd apps/flight-demo/sim_runtime
./open_rosetta_shell.sh
```

Build `ardupilot_gazebo` after Gazebo itself is installed:

```bash
cd apps/flight-demo/sim_runtime
./build_ardupilot_gazebo.sh
```

Install Gazebo Harmonic from the official macOS Homebrew tap:

```bash
cd apps/flight-demo/sim_runtime
./install_gz_harmonic.sh
```

Important:
- On this machine, Homebrew does not currently expose a straightforward `gz` formula by the simple names we checked.
- The official macOS path is the OSRF tap: `brew tap osrf/simulation && brew install gz-harmonic`
- Treat Gazebo installation as a separate official install step, not something guaranteed by `bootstrap_macos_runtime.sh`.
- If Gazebo Harmonic install or rendering becomes messy on macOS, switch to the Ubuntu VM fallback early.

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

Terminal 3, enable camera stream if your world/model requires an explicit toggle:

```bash
cd apps/flight-demo/sim_runtime
./enable_camera_stream.sh
```

Terminal 4, backend on the real adapter:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

Terminal 5, adapter smoke:

```bash
cd apps/flight-demo/sim_runtime
../../.venv/bin/python smoke_ardupilot_sitl.py
```

If Rosetta/Gazebo becomes unstable:
- keep the backend/app layer on macOS
- move Gazebo + SITL into Ubuntu VM
- point `ARRAKIS_ARDUPILOT_CONNECTION` and `ARRAKIS_ARDUPILOT_VIDEO_SOURCE` at the VM-exposed endpoints

## Ubuntu VM fallback

Use this path when any of the following happens on macOS:
- `gz-harmonic` fails to install cleanly
- `ardupilot_gazebo` plugin build flakes under Rosetta
- camera transport is unstable enough to break adapter smoke
- GUI/RTF stays below the thresholds in the architecture document

VM bootstrap:

```bash
cd apps/flight-demo/sim_runtime
./bootstrap_ubuntu_vm_runtime.sh
```

Inside the VM, verify the runtime after cloning/building ArduPilot and `ardupilot_gazebo`:

```bash
cd apps/flight-demo/sim_runtime
./check_ubuntu_vm_runtime.sh
```

Recommended split:
- Ubuntu VM:
  - `gz sim`
  - `sim_vehicle.py`
  - `ardupilot_gazebo` plugin
- macOS host:
  - backend
  - frontend
  - detector/perception stack

Host `runtime.env` for VM mode should point at the VM IP:

```bash
ARRAKIS_ARDUPILOT_CONNECTION=udp:<vm-ip>:14550
ARRAKIS_ARDUPILOT_VIDEO_SOURCE=udp://<vm-ip>:5600
```

The backend launcher does not need to change:

```bash
cd apps/flight-demo/sim_runtime
./run_backend_ardupilot.sh
```

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
