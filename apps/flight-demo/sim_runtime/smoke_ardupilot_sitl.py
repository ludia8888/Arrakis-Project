from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from flight_adapters.ardupilot import ArduPilotAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the ArduPilot SITL adapter path.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for callbacks after connect.")
    args = parser.parse_args()

    telemetry_events: list[object] = []
    video_events: list[object] = []

    adapter = InstrumentedFlightAdapter(ArduPilotAdapter(), logger_name="arrakis.adapter.ardupilot")
    adapter.stream_telemetry(telemetry_events.append)
    adapter.stream_video(video_events.append)

    started = time.perf_counter()
    adapter.connect()
    connect_ms = (time.perf_counter() - started) * 1000.0
    print(f"[smoke] connect ok in {connect_ms:.1f}ms")

    snapshot = adapter.get_snapshot()
    print(
        "[smoke] snapshot",
        {
            "flight_mode": snapshot.flight_mode,
            "armed": snapshot.armed,
            "battery_percent": snapshot.battery_percent,
            "lat": snapshot.lat,
            "lon": snapshot.lon,
        },
    )

    deadline = time.time() + args.timeout
    while time.time() < deadline and not telemetry_events:
        time.sleep(0.05)

    if not telemetry_events:
        raise RuntimeError("No telemetry callback received within timeout")

    print(f"[smoke] telemetry callbacks: {len(telemetry_events)}")

    video_source = getattr(importlib.import_module("config"), "ARDUPILOT_VIDEO_SOURCE", None)
    if video_source:
        deadline = time.time() + args.timeout
        while time.time() < deadline and not video_events:
            time.sleep(0.05)
        if not video_events:
            raise RuntimeError("Video source configured but no video callback received within timeout")
        print(f"[smoke] video callbacks: {len(video_events)}")
    else:
        print("[smoke] video skipped because ARRAKIS_ARDUPILOT_VIDEO_SOURCE is unset")

    print("[smoke] adapter contract path looks healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
