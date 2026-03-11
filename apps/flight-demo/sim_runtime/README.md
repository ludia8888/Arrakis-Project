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
