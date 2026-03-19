from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile
from arrakis_core.controller import ArrakisController
from arrakis_core.flight_event_recorder import FlightEventRecorder
from arrakis_core.route_planner import build_route_preview
from flight_adapters.instrumented import InstrumentedFlightAdapter
from flight_adapters.mock import MockAdapter
from schemas import LatLon, RouteRequest


def _build_preview(profile: AirframeProfile):
    return build_route_preview(
        RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.5700, lon=126.9800),
                LatLon(lat=37.5750, lon=126.9850),
            ],
            cruise_alt_m=profile.altitudes.cruise_m,
        ),
        profile,
    )


class TestLinkProfiles:
    def test_sik_profile_defaults(self, monkeypatch):
        monkeypatch.setenv("ARRAKIS_LINK_PROFILE", "sik")
        monkeypatch.delenv("ARRAKIS_TELEMETRY_DEGRADED_AFTER_S", raising=False)
        monkeypatch.delenv("ARRAKIS_TELEMETRY_LOST_AFTER_S", raising=False)
        monkeypatch.delenv("ARRAKIS_TELEMETRY_STALE_DEBOUNCE", raising=False)

        import config as config_module

        reloaded = importlib.reload(config_module)
        try:
            profile = reloaded.resolve_link_profile_config()
            assert profile.name == "sik"
            assert profile.telemetry_degraded_after_s == 3.0
            assert profile.telemetry_lost_after_s == 8.0
            assert profile.telemetry_stale_debounce == 2
        finally:
            importlib.reload(config_module)


class TestControlPlaneRecovery:
    def test_start_mission_blocked_while_control_plane_fault_active(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.fault_block")
        controller = ArrakisController(adapter, profile)

        try:
            controller.set_route(_build_preview(profile))
            adapter.wrapped.force_control_plane_fault("io_fault", "simulated radio outage")

            with pytest.raises(RuntimeError, match="control plane fault"):
                controller.start_mission()

            assert controller.state_machine.phase == "IDLE"
            assert controller.adapter.bootstrap_status().control_plane_fault
        finally:
            controller.shutdown()

    def test_recover_clears_fault_and_unblocks_mission_start(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.recover")
        controller = ArrakisController(adapter, profile)

        try:
            controller.set_route(_build_preview(profile))
            adapter.wrapped.force_control_plane_fault("io_fault", "radio reconnect required")

            bootstrap = adapter.bootstrap_status()
            assert bootstrap.control_plane_fault

            with pytest.raises(RuntimeError, match="control plane fault"):
                controller.start_mission()

            recovered = controller.recover_control_plane()
            assert not recovered.control_plane_fault

            controller.start_mission()
            assert controller.state_machine.phase != "IDLE"
        finally:
            controller.shutdown()

    def test_recover_allows_fresh_mission_progress_after_fault(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.recover_progress")
        controller = ArrakisController(adapter, profile)

        try:
            controller.set_route(_build_preview(profile))
            adapter.wrapped.force_control_plane_fault("io_fault", "simulated reconnect required")

            with pytest.raises(RuntimeError, match="control plane fault"):
                controller.start_mission()

            recovered = controller.recover_control_plane()
            assert not recovered.control_plane_fault

            controller.start_mission()
            deadline = time.time() + 8.0
            while time.time() < deadline:
                if controller.state_machine.phase in {"OUTBOUND", "RETURN", "TAKEOFF_MC", "TRANSITION_FW"}:
                    break
                time.sleep(0.2)

            assert controller.state_machine.phase in {"OUTBOUND", "RETURN", "TAKEOFF_MC", "TRANSITION_FW"}
        finally:
            controller.shutdown()


class TestLinkLossRtl:
    def test_heartbeat_healthy_but_telemetry_blind_triggers_rtl_link_loss(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.linkloss")
        controller = ArrakisController(adapter, profile)

        try:
            controller.set_route(_build_preview(profile))
            controller.start_mission()

            outbound_deadline = time.time() + 8.0
            while time.time() < outbound_deadline:
                if controller.state_machine.phase == "OUTBOUND":
                    break
                time.sleep(0.2)
            assert controller.state_machine.phase == "OUTBOUND"

            adapter.wrapped.force_telemetry_age(9.0)

            rtl_deadline = time.time() + 5.0
            while time.time() < rtl_deadline:
                if controller.state_machine.phase == "RTL_LINK_LOSS":
                    break
                time.sleep(0.2)

            bootstrap = adapter.bootstrap_status()
            assert bootstrap.heartbeat_received
            assert bootstrap.telemetry_state == "lost"
            assert controller.state_machine.phase == "RTL_LINK_LOSS"
            assert controller.state_machine.abort_reason == "telemetry data lost during flight"
        finally:
            controller.shutdown()


class TestFlightEventRecorder:
    def test_event_log_flushes_and_fsyncs_every_event(self, monkeypatch, tmp_path):
        import arrakis_core.flight_event_recorder as recorder_module

        fsync_calls: list[int] = []
        monkeypatch.setattr(recorder_module, "EVENT_LOG_PATH", str(tmp_path))
        monkeypatch.setattr(recorder_module.os, "fsync", lambda fd: fsync_calls.append(fd))

        recorder = FlightEventRecorder(link_profile="sitl")
        recorder.record_event("test_event", {"value": 1})
        recorder.close(onboard_log_metadata={"attempted": False, "status": "mock"})

        event_files = list(tmp_path.glob("*.events.jsonl"))
        manifest_files = list(tmp_path.glob("*.manifest.json"))
        assert event_files
        assert manifest_files
        assert fsync_calls, "Expected fsync to be called for durable logging"

        lines = event_files[0].read_text(encoding="utf-8").strip().splitlines()
        assert any(json.loads(line)["event_type"] == "test_event" for line in lines)

        manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
        assert manifest["link_profile"] == "sitl"
        assert manifest["onboard_log_metadata"]["status"] == "mock"
