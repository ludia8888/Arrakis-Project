from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile
from flight_adapters.mock import MockAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter
from flight_adapters.base import validate_adapter_contract
from schemas import TelemetrySnapshot


def assert_adapter_contract(adapter, timeout_seconds: float = 2.0) -> None:
    validate_adapter_contract(adapter)
    telemetry_events: list[TelemetrySnapshot] = []
    video_events: list[object] = []

    adapter.stream_telemetry(telemetry_events.append)
    adapter.stream_video(video_events.append)

    started = time.perf_counter()
    adapter.connect()
    connect_elapsed = time.perf_counter() - started
    assert connect_elapsed <= timeout_seconds

    started = time.perf_counter()
    adapter.arm()
    arm_elapsed = time.perf_counter() - started
    assert arm_elapsed <= timeout_seconds

    started = time.perf_counter()
    snapshot = adapter.get_snapshot()
    snapshot_elapsed = time.perf_counter() - started

    assert snapshot_elapsed <= timeout_seconds
    assert isinstance(snapshot, TelemetrySnapshot)
    assert snapshot.armed is True
    assert adapter.current_leg() in {"idle", "outbound", "return"}
    bootstrap = adapter.bootstrap_status()
    assert bootstrap.connected is True
    assert bootstrap.mission_ready is True

    deadline = time.time() + timeout_seconds
    while time.time() < deadline and (not telemetry_events or not video_events):
        time.sleep(0.05)

    assert telemetry_events, "Expected telemetry callback within timeout"
    assert video_events, "Expected video callback within timeout"
    frame = video_events[-1]
    assert getattr(frame, "frame_bgr", None) is not None
    assert getattr(frame, "fps", 0) > 0

    adapter.reset()


def test_mock_adapter_contract_smoke() -> None:
    profile = AirframeProfile()
    assert_adapter_contract(InstrumentedFlightAdapter(MockAdapter(profile), logger_name="arrakis.adapter.mock"))


@pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="Real ArduPilot adapter smoke test is opt-in and requires a wired implementation",
)
def test_ardupilot_adapter_contract_smoke() -> None:
    from flight_adapters.ardupilot import ArduPilotAdapter

    assert_adapter_contract(ArduPilotAdapter(AirframeProfile()), timeout_seconds=5.0)
