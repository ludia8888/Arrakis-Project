# Arrakis Flight Demo

This app is a separate demo from the existing YOLO browser overlay.

## What ships in this v1

- Separate backend and frontend app under `apps/flight-demo`
- Arrakis-owned mission/state-machine layer
- Dedicated mission executor for round-trip orchestration
- Dedicated state payload assembler for frontend-facing state JSON
- Dedicated video service for camera/detector/JPEG state
- Flight controller adapter boundary
- Working mock adapter path for local UI/demo development
- ArduPilot-first real adapter scaffold with `pymavlink` control path
- MJPEG camera stream
- WebSocket state feed at 5 Hz
- Route-derived geofence generation
- Person/vehicle detector service with model fallback
- Reset endpoint for repeatable demo runs
- Module-scoped `arrakis.*` loggers for core, adapters, and perception backends
- Optional JSONL state snapshot dump via `ARRAKIS_STATE_DUMP_PATH`
- Adapter contract smoke test at `tests/test_adapter_contract.py`
- Health endpoint at `GET /api/health`
- Local CI script at [`check.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/check.sh)

## Architecture spec

- Canonical design document: [`ARCHITECTURE_V2_2.md`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/ARCHITECTURE_V2_2.md)
- This includes the v2.2 architecture contract and the critical review addendum for:
  - ArduPilot + Gazebo + Apple Silicon Rosetta risks
  - MAVSDK vs `pymavlink` fallback strategy
  - video latency and copy-overhead management
  - provisional detector degrade thresholds pending SITL/Jetson profiling

## Perception model swapping

- Image inference backends are now treated as swappable components behind the detector service.
- Backend notes live at [`arrakis_core/perception_backends/README.md`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/backend/arrakis_core/perception_backends/README.md)
- To override the active model path explicitly, set `ARRAKIS_DETECTOR_MODEL_PATH`

## Logging and state dump

- Set `ARRAKIS_LOG_LEVEL` to control backend log verbosity
- Set `ARRAKIS_STATE_DUMP_PATH` to persist `StatePayload` snapshots as JSONL for postmortem analysis
- Adapter calls are instrumented through a wrapper so logs include call/return timing per public adapter method

## Current scope boundary

- v1 ships a working Arrakis architecture and a full mock-demo path first.
- Real ArduPilot SITL execution is now wired through a first `pymavlink` adapter implementation, but still needs SITL-on-this-machine validation.
- The architecture already assumes:
  - ArduPilot first
  - PX4-compatible adapter boundary later
  - simulator video entering only through the adapter
  - the first concrete ArduPilot control client is `pymavlink`, keeping room for a future MAVSDK-backed adapter if it proves reliable enough

## Backend

```bash
cd apps/flight-demo/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8010
```

Use `ARRAKIS_FLIGHT_ADAPTER=mock` for the mock demo path.

## Frontend

```bash
cd apps/flight-demo/frontend
npm install
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8010`.

## Adapter contract smoke test

```bash
cd apps/flight-demo
../../.venv/bin/python -m pytest tests/test_adapter_contract.py
```

- `test_mock_adapter_contract_smoke` runs by default
- `test_ardupilot_adapter_contract_smoke` is opt-in via `ARRAKIS_TEST_REAL_ARDUPILOT=1`
- Adapter contract is guarded both by `ABC` and runtime validation via `FlightControllerAdapterContract`

## Local CI

```bash
cd apps/flight-demo
./check.sh
```

- Runs backend `py_compile`
- Builds the frontend
- Runs adapter contract smoke tests
- Runs a mock full round trip and verifies state dump output

## Health endpoint

- `GET /api/health` returns adapter status, detector mode, last telemetry timestamp, simulator status, and process memory high-water mark

## Runtime notes

- Simulator runtime docs live under `apps/flight-demo/sim_runtime`
- Environment probe: [`sim_runtime/check_environment.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/check_environment.sh)
- macOS bootstrap: [`sim_runtime/bootstrap_macos_runtime.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/bootstrap_macos_runtime.sh)
- Gazebo Harmonic installer: [`sim_runtime/install_gz_harmonic.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/install_gz_harmonic.sh)
- Rosetta shell helper: [`sim_runtime/open_rosetta_shell.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/open_rosetta_shell.sh)
- Ubuntu VM bootstrap: [`sim_runtime/bootstrap_ubuntu_vm_runtime.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/bootstrap_ubuntu_vm_runtime.sh)
- Ubuntu VM workspace provisioner: [`sim_runtime/provision_ubuntu_vm_workspace.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/provision_ubuntu_vm_workspace.sh)
- Ubuntu VM runtime check: [`sim_runtime/check_ubuntu_vm_runtime.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/check_ubuntu_vm_runtime.sh)
- Host runtime.env writer for VM mode: [`sim_runtime/write_vm_host_runtime_env.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/write_vm_host_runtime_env.sh)
- ardupilot_gazebo build helper: [`sim_runtime/build_ardupilot_gazebo.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/build_ardupilot_gazebo.sh)
- Runtime env template: [`sim_runtime/runtime.env.example`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/runtime.env.example)
- Gazebo launcher: [`sim_runtime/run_gazebo_zephyr.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/run_gazebo_zephyr.sh)
- SITL launcher: [`sim_runtime/run_ardupilot_zephyr.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/run_ardupilot_zephyr.sh)
- Camera enable helper: [`sim_runtime/enable_camera_stream.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/enable_camera_stream.sh)
- Real adapter backend launcher: [`sim_runtime/run_backend_ardupilot.sh`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/run_backend_ardupilot.sh)
- Real ArduPilot adapter smoke once SITL is up: [`sim_runtime/smoke_ardupilot_sitl.py`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/smoke_ardupilot_sitl.py)
- `POST /api/mission/reset` clears mission state, route preview, detector events, and adapter state for repeatable demos
- `POST /api/mission/reset` first cancels any active mission execution thread before clearing adapter/video/state
- FastAPI creates and tears down the controller through app lifespan rather than an import-time global
- Rosetta/Gazebo/ArduPilot risk notes and VM fallback policy are documented in `apps/flight-demo/sim_runtime/README.md`
