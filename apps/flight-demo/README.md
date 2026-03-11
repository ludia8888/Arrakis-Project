# Arrakis Flight Demo

This app is a separate demo from the existing YOLO browser overlay.

## What ships in this v1

- Separate backend and frontend app under `apps/flight-demo`
- Arrakis-owned mission/state-machine layer
- Flight controller adapter boundary
- Working mock adapter path for local UI/demo development
- ArduPilot-first adapter placeholder
- MJPEG camera stream
- WebSocket state feed at 5 Hz
- Route-derived geofence generation
- Person/vehicle detector service with model fallback
- Reset endpoint for repeatable demo runs

## Architecture spec

- Canonical design document: [`ARCHITECTURE_V2_2.md`](/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/ARCHITECTURE_V2_2.md)
- This includes the v2.2 architecture contract and the critical review addendum for:
  - ArduPilot + Gazebo + Apple Silicon Rosetta risks
  - MAVSDK vs `pymavlink` fallback strategy
  - video latency and copy-overhead management

## Current scope boundary

- v1 ships a working Arrakis architecture and a full mock-demo path first.
- Real ArduPilot SITL integration is intentionally the next step, not something hidden behind the current mock adapter.
- The architecture already assumes:
  - ArduPilot first
  - PX4-compatible adapter boundary later
  - simulator video entering only through the adapter
  - `MAVSDK` as the first control client, with `pymavlink` available as the fallback path for ArduPilot-specific VTOL commands if needed

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

## Runtime notes

- Simulator runtime docs live under `apps/flight-demo/sim_runtime`
- `POST /api/mission/reset` clears mission state, route preview, detector events, and adapter state for repeatable demos
- Rosetta/Gazebo/ArduPilot risk notes and VM fallback policy are documented in `apps/flight-demo/sim_runtime/README.md`
