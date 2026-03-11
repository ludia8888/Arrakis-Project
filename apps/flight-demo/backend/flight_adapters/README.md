# Flight Adapter Notes

This folder exists to isolate flight-stack-specific behavior from the Arrakis mission/state machine.

## v1 policy

- ArduPilot is the first real integration target.
- PX4 remains a planned second adapter target, but the Arrakis core must not depend on PX4 semantics.
- All control, telemetry, and simulator camera handling must enter through the adapter boundary.

## ArduPilot implementation direction

- Start with `MAVSDK` for connection, telemetry, arm/takeoff, and mission execution where it works cleanly.
- Do not assume PX4-level feature parity for VTOL operations.
- Validate these behaviors explicitly in ArduPilot SITL:
  - fixed-wing transition
  - multicopter recovery transition
  - mission-level VTOL landing behavior
  - return-to-home behavior during VTOL phases
- If ArduPilot VTOL transitions are not exposed reliably through MAVSDK, keep the adapter API unchanged and use `pymavlink` internally for:
  - `DO_VTOL_TRANSITION`
  - mode changes
  - any recovery/landing command sequence that needs lower-level control

## Video transport direction

- `stream_video(callback)` is the single public entry point for camera frames.
- The first implementation can use a latest-frame overwrite queue with OpenCV frames.
- If latency or copy overhead becomes visible, upgrade inside the adapter/video worker layer to:
  - shared memory, or
  - another single-copy transport
- The Arrakis core and frontend should not change when the transport is upgraded.
