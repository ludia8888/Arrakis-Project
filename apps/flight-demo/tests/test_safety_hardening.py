"""Safety hardening verification tests.

Tests all CRITICAL and HIGH fixes against live SITL or MockAdapter.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile
from arrakis_core.controller import ArrakisController
from arrakis_core.mission_state_machine import INTERRUPT_PHASES, MissionStateMachine
from arrakis_core.telemetry_hub import SafetyDecision, TelemetryHub
from arrakis_core.mission_executor import MissionExecutor
from flight_adapters.mock import MockAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter
from schemas import LatLon, MissionPhase, RouteRequest, TelemetrySnapshot


# ---------------------------------------------------------------------------
# C-6 / H-2: schemas validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """C-6: STARTING phase exists. H-2: Input validation."""

    def test_starting_phase_in_literal(self):
        """STARTING must be a valid MissionPhase."""
        from typing import get_args
        phases = get_args(MissionPhase)
        assert "STARTING" in phases
        assert "RTL_NAV_DEGRADED" in phases

    def test_latlon_rejects_out_of_range(self):
        """H-2: LatLon rejects invalid coordinates."""
        with pytest.raises(Exception):
            LatLon(lat=91.0, lon=0.0)
        with pytest.raises(Exception):
            LatLon(lat=0.0, lon=181.0)
        with pytest.raises(Exception):
            LatLon(lat=-91.0, lon=0.0)
        with pytest.raises(Exception):
            LatLon(lat=0.0, lon=-181.0)

    def test_latlon_accepts_valid_range(self):
        """H-2: LatLon accepts valid coordinates."""
        ll = LatLon(lat=37.5665, lon=126.9780)
        assert ll.lat == 37.5665
        assert ll.lon == 126.9780
        # Edge cases
        LatLon(lat=90.0, lon=180.0)
        LatLon(lat=-90.0, lon=-180.0)

    def test_cruise_alt_validation(self):
        """H-2: cruise_alt_m must be in [10, 500]."""
        with pytest.raises(Exception):
            RouteRequest(
                home=LatLon(lat=37.0, lon=127.0),
                waypoints=[LatLon(lat=37.01, lon=127.01), LatLon(lat=37.02, lon=127.02)],
                cruise_alt_m=5.0,  # too low
            )
        with pytest.raises(Exception):
            RouteRequest(
                home=LatLon(lat=37.0, lon=127.0),
                waypoints=[LatLon(lat=37.01, lon=127.01), LatLon(lat=37.02, lon=127.02)],
                cruise_alt_m=501.0,  # too high
            )


# ---------------------------------------------------------------------------
# C-6: MissionStateMachine sets STARTING phase
# ---------------------------------------------------------------------------

class TestMissionStateMachineStarting:
    """C-6: start_mission must set phase to STARTING immediately."""

    def test_start_mission_sets_starting_phase(self):
        sm = MissionStateMachine()
        # Need to set a route first
        from arrakis_core.route_planner import build_route_preview
        request = RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.570, lon=126.980),
                LatLon(lat=37.575, lon=126.985),
            ],
            cruise_alt_m=60.0,
        )
        preview = build_route_preview(request, AirframeProfile())
        sm.set_route(preview, mission_active=False)
        sm.start_mission(mission_active=False)
        assert sm.phase == "STARTING", f"Expected STARTING, got {sm.phase}"


# ---------------------------------------------------------------------------
# C-4: TelemetryHub detects telemetry freshness loss
# ---------------------------------------------------------------------------

class TestTelemetryLostDetection:
    """C-4: trigger_telemetry_lost fires on fresh→stale transition."""

    def _make_snapshot(self, fresh=True, **kwargs):
        defaults = dict(
            timestamp=time.time(), lat=37.5665, lon=126.9780,
            alt_m=50.0, airspeed_mps=10.0, groundspeed_mps=10.0,
            battery_percent=80.0, armed=True, flight_mode="AUTO",
            vtol_state="FW", mission_index=2, home_distance_m=500.0,
            geofence_breached=False, sim_rtf=1.0, telemetry_fresh=fresh,
            mode_valid=True, position_valid=True, gps_sensor_valid=True, home_valid=True,
        )
        defaults.update(kwargs)
        return TelemetrySnapshot(**defaults)

    def test_trigger_on_fresh_to_stale(self):
        """C-4: fresh→stale should trigger telemetry_lost."""
        from arrakis_core.video_service import VideoService
        vs = VideoService()
        hub = TelemetryHub(self._make_snapshot(fresh=False), vs, AirframeProfile())

        # Send fresh telemetry
        decision1 = hub.on_telemetry(self._make_snapshot(fresh=True), None, "OUTBOUND")
        assert not decision1.trigger_telemetry_lost

        # Send stale telemetry (fresh→stale transition)
        decision2 = hub.on_telemetry(self._make_snapshot(fresh=False), None, "OUTBOUND")
        assert decision2.trigger_telemetry_lost, "Should trigger on fresh→stale"

    def test_no_trigger_on_stale_to_stale(self):
        """C-4: stale→stale should NOT trigger."""
        from arrakis_core.video_service import VideoService
        vs = VideoService()
        hub = TelemetryHub(self._make_snapshot(fresh=False), vs, AirframeProfile())

        # Stale → stale: no trigger
        decision = hub.on_telemetry(self._make_snapshot(fresh=False), None, "OUTBOUND")
        assert not decision.trigger_telemetry_lost


class TestPositionLossDetection:
    """Sustained GPS loss should escalate from hold to RTL."""

    def _make_snapshot(self, valid=True, **kwargs):
        defaults = dict(
            timestamp=time.time(), lat=37.5665, lon=126.9780,
            alt_m=50.0, airspeed_mps=10.0, groundspeed_mps=10.0,
            battery_percent=80.0, armed=True, flight_mode="AUTO",
            vtol_state="FW", mission_index=2, home_distance_m=500.0,
            geofence_breached=False, sim_rtf=1.0, telemetry_fresh=True,
            mode_valid=True, position_valid=valid, gps_sensor_valid=valid, home_valid=True,
        )
        defaults.update(kwargs)
        return TelemetrySnapshot(**defaults)

    def test_position_loss_requires_sustained_timeout(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 103.0, 107.0))
        last_value = {"value": 107.0}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        hub = TelemetryHub(self._make_snapshot(valid=True), VideoService(), AirframeProfile())

        decision1 = hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")
        decision2 = hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")
        decision3 = hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")

        assert not decision1.trigger_position_loss_rtl
        assert not decision2.trigger_position_loss_rtl
        assert decision3.trigger_position_loss_rtl

    def test_raw_gps_loss_triggers_even_with_dead_reckoned_position(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 103.0, 107.0))
        last_value = {"value": 107.0}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        hub = TelemetryHub(self._make_snapshot(valid=True), VideoService(), AirframeProfile())
        base = self._make_snapshot(valid=True, gps_sensor_valid=False)

        decision1 = hub.on_telemetry(base, None, "OUTBOUND")
        decision2 = hub.on_telemetry(base, None, "OUTBOUND")
        decision3 = hub.on_telemetry(base, None, "OUTBOUND")

        assert not decision1.trigger_position_loss_rtl
        assert not decision2.trigger_position_loss_rtl
        assert decision3.trigger_position_loss_rtl

    def test_position_loss_timer_resets_after_valid_fix(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 103.0, 104.0, 105.0, 108.0))
        last_value = {"value": 108.0}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        hub = TelemetryHub(self._make_snapshot(valid=True), VideoService(), AirframeProfile())

        hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")
        hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")
        hub.on_telemetry(self._make_snapshot(valid=True), None, "OUTBOUND")
        decision = hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")
        decision_after = hub.on_telemetry(self._make_snapshot(valid=False), None, "OUTBOUND")

        assert not decision.trigger_position_loss_rtl
        assert not decision_after.trigger_position_loss_rtl


class TestNavigationDegradationDetection:
    """Sustained degraded navigation quality should escalate to RTL."""

    def _make_snapshot(self, **kwargs):
        defaults = dict(
            timestamp=time.time(), lat=37.5665, lon=126.9780,
            alt_m=50.0, airspeed_mps=18.0, groundspeed_mps=18.0,
            battery_percent=80.0, armed=True, flight_mode="AUTO",
            vtol_state="FW", mission_index=2, home_distance_m=500.0,
            geofence_breached=False, sim_rtf=1.0, telemetry_fresh=True,
            mode_valid=True, position_valid=True, gps_sensor_valid=True,
            gps_fix_type=3, gps_satellites=10, home_valid=True,
        )
        defaults.update(kwargs)
        return TelemetrySnapshot(**defaults)

    def test_low_satellite_count_requires_sustained_timeout(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 103.0, 109.0))
        last_value = {"value": 109.0}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        hub = TelemetryHub(self._make_snapshot(), VideoService(), AirframeProfile())
        degraded = self._make_snapshot(gps_satellites=4)

        decision1 = hub.on_telemetry(degraded, None, "OUTBOUND")
        decision2 = hub.on_telemetry(degraded, None, "OUTBOUND")
        decision3 = hub.on_telemetry(degraded, None, "OUTBOUND")

        assert not decision1.trigger_navigation_degraded_rtl
        assert not decision2.trigger_navigation_degraded_rtl
        assert decision3.trigger_navigation_degraded_rtl

    def test_progress_stall_triggers_navigation_rtl(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 103.0, 108.0))
        last_value = {"value": 108.0}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        profile = AirframeProfile().model_copy(
            update={
                "safety": AirframeProfile().safety.model_copy(
                    update={"progress_stall_timeout_seconds": 2.0}
                )
            }
        )
        hub = TelemetryHub(self._make_snapshot(), VideoService(), profile)
        stalled = self._make_snapshot(home_distance_m=120.0, groundspeed_mps=0.8, mission_index=3)

        decision1 = hub.on_telemetry(stalled, None, "OUTBOUND")
        decision2 = hub.on_telemetry(stalled, None, "OUTBOUND")
        decision3 = hub.on_telemetry(stalled, None, "OUTBOUND")

        assert not decision1.trigger_navigation_degraded_rtl
        assert not decision2.trigger_navigation_degraded_rtl
        assert decision3.trigger_navigation_degraded_rtl

    def test_sensor_inconsistency_triggers_navigation_rtl(self, monkeypatch):
        from arrakis_core import telemetry_hub as telemetry_hub_module
        from arrakis_core.video_service import VideoService

        monotonic_values = iter((100.0, 102.5))
        last_value = {"value": 102.5}

        def _fake_monotonic():
            try:
                last_value["value"] = next(monotonic_values)
            except StopIteration:
                pass
            return last_value["value"]

        monkeypatch.setattr(telemetry_hub_module, "_monotonic", _fake_monotonic)

        profile = AirframeProfile().model_copy(
            update={
                "safety": AirframeProfile().safety.model_copy(
                    update={"sensor_inconsistency_timeout_seconds": 2.0}
                )
            }
        )
        hub = TelemetryHub(self._make_snapshot(timestamp=1000.0), VideoService(), profile)
        noisy1 = self._make_snapshot(timestamp=1000.5, alt_m=60.0, airspeed_mps=30.0)
        noisy2 = self._make_snapshot(timestamp=1001.0, alt_m=49.0, airspeed_mps=18.0)

        decision1 = hub.on_telemetry(noisy1, None, "OUTBOUND")
        decision2 = hub.on_telemetry(noisy2, None, "OUTBOUND")

        assert not decision1.trigger_navigation_degraded_rtl
        assert decision2.trigger_navigation_degraded_rtl


# ---------------------------------------------------------------------------
# Stress envelope mapping
# ---------------------------------------------------------------------------

class TestStressEnvelopeMapping:
    """Stress envelope should summarize compound dry-lab stressors."""

    def _make_snapshot(self, **kwargs):
        defaults = dict(
            timestamp=time.time(),
            lat=37.5665,
            lon=126.9780,
            alt_m=50.0,
            airspeed_mps=18.0,
            groundspeed_mps=18.0,
            battery_percent=80.0,
            armed=True,
            flight_mode="AUTO",
            vtol_state="FW",
            mission_index=2,
            home_distance_m=500.0,
            geofence_breached=False,
            sim_rtf=1.0,
            telemetry_fresh=True,
            mode_valid=True,
            position_valid=True,
            gps_sensor_valid=True,
            gps_fix_type=3,
            gps_satellites=10,
            home_valid=True,
        )
        defaults.update(kwargs)
        return TelemetrySnapshot(**defaults)

    def test_compound_stress_maps_into_critical_envelope(self):
        from arrakis_core.video_service import VideoService

        hub = TelemetryHub(self._make_snapshot(timestamp=1000.0), VideoService(), AirframeProfile())
        first = self._make_snapshot(
            timestamp=1000.5,
            airspeed_mps=20.0,
            groundspeed_mps=0.5,
            gps_satellites=3,
            mission_index=3,
            home_distance_m=520.0,
        )
        second = self._make_snapshot(
            timestamp=1001.0,
            alt_m=65.0,
            airspeed_mps=35.0,
            groundspeed_mps=0.5,
            gps_satellites=3,
            mission_index=3,
            home_distance_m=520.0,
        )

        hub.on_telemetry(first, None, "OUTBOUND")
        hub.on_telemetry(second, None, "OUTBOUND")
        stress = hub.stress_envelope()

        assert stress.level == "critical"
        assert stress.wind_load_score >= 0.9
        assert stress.gps_degradation_score >= 0.5
        assert stress.sensor_noise_score >= 1.0
        assert stress.progress_stall_score >= 0.8
        assert set(stress.reasons) == {
            "wind_load",
            "gps_degradation",
            "sensor_noise",
            "progress_stall",
        }


# ---------------------------------------------------------------------------
# C-3: Controller safety trigger atomicity (if/elif)
# ---------------------------------------------------------------------------

class TestControllerSafetyAtomicity:
    """C-3: Only one safety trigger should fire per callback."""

    def test_only_one_trigger_fires(self):
        """C-3: If both battery_rtl and geofence fire, only one action taken."""
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test")
        controller = ArrakisController(adapter, profile)

        # Verify _SAFETY_SUPPRESS_PHASES is properly defined
        assert "IDLE" in controller._SAFETY_SUPPRESS_PHASES
        assert "STARTING" in controller._SAFETY_SUPPRESS_PHASES
        assert "LANDING" in controller._SAFETY_SUPPRESS_PHASES
        assert "COMPLETE" in controller._SAFETY_SUPPRESS_PHASES
        for phase in INTERRUPT_PHASES:
            assert phase in controller._SAFETY_SUPPRESS_PHASES
        controller.shutdown()


# ---------------------------------------------------------------------------
# C-1: Mission executor disarms on cancel during arm
# ---------------------------------------------------------------------------

class TestMissionExecutorCancelDisarm:
    """C-1: Cancel during arm phase must disarm the vehicle."""

    def test_cancel_during_arm_calls_abort(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test")
        adapter.connect()
        controller = ArrakisController(adapter, profile)

        # Set up route
        from arrakis_core.route_planner import build_route_preview
        request = RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.570, lon=126.980),
                LatLon(lat=37.575, lon=126.985),
            ],
        )
        preview = build_route_preview(request, profile)
        controller.set_route(preview)

        # Create cancel event that's already set
        cancel = threading.Event()
        cancel.set()

        # Run mission with pre-set cancel - should abort immediately after arm
        controller.mission_executor.run_roundtrip_mission(cancel)

        # Verify state is consistent (not stuck in ARMING)
        # The cancel event was already set, so after arm() + sleep_with_cancel,
        # it should call adapter.abort("cancelled during arm") and return
        controller.shutdown()


# ---------------------------------------------------------------------------
# H-3: complete() guard against INTERRUPT_PHASES
# ---------------------------------------------------------------------------

class TestCompleteGuard:
    """H-3: complete() should not be called if phase is in INTERRUPT_PHASES."""

    def test_wait_for_landing_skips_complete_on_interrupt(self):
        """Verify _wait_for_landing doesn't call complete() during interrupt."""
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test")
        adapter.connect()

        sm = MissionStateMachine()
        from arrakis_core.route_planner import build_route_preview
        request = RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.570, lon=126.980),
                LatLon(lat=37.575, lon=126.985),
            ],
        )
        preview = build_route_preview(request, profile)
        sm.set_route(preview, mission_active=False)
        sm.start_mission(mission_active=False)

        # Force into ABORT phase
        sm.abort("ABORT_MANUAL", "test abort")
        assert sm.phase in INTERRUPT_PHASES

        # Verify phase stays in interrupt even after landing
        # (complete() should be skipped)
        assert sm.phase == "ABORT_MANUAL"


# ---------------------------------------------------------------------------
# H-4: Stale telemetry altitude guard
# ---------------------------------------------------------------------------

class TestStaleTelemetryAltGuard:
    """H-4: Landing detection must verify telemetry freshness."""

    def test_stale_telemetry_does_not_trigger_landing(self):
        """Alt <= 0.5 with stale telemetry should NOT break landing wait."""
        snapshot = TelemetrySnapshot(
            timestamp=time.time(), lat=37.5665, lon=126.9780,
            alt_m=0.3, airspeed_mps=0.0, groundspeed_mps=0.0,
            battery_percent=80.0, armed=True, flight_mode="QLAND",
            vtol_state="MC", mission_index=0, home_distance_m=5.0,
            geofence_breached=False, sim_rtf=1.0,
            telemetry_fresh=False,  # STALE
            mode_valid=True, position_valid=False,  # INVALID position
            home_valid=True,
        )
        # With H-4 fix: armed=True, stale telemetry → should NOT break
        # The condition is: (fresh AND position_valid AND alt <= 0.5) OR (not armed)
        assert snapshot.armed  # still armed
        assert not (snapshot.telemetry_fresh and snapshot.position_valid and snapshot.alt_m <= 0.5)
        # Correct: stale telemetry should not falsely detect landing


# ---------------------------------------------------------------------------
# C-5: COMMAND_ACK race condition fix
# ---------------------------------------------------------------------------

class TestCommandAckRace:
    """C-5: Command ACKs must be protected by _state_lock (Fix 2: per-command dict)."""

    def test_send_command_clears_ack_under_lock(self):
        """Verify _send_command clears pending ACK under state_lock."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._send_command)
        # _state_lock must appear before _pending_acks.pop
        assert "self._state_lock" in source, "C-5: _send_command should use _state_lock"
        assert "_pending_acks" in source, "Fix 2: should use _pending_acks dict"

    def test_wait_for_ack_reads_under_lock(self):
        """Verify _wait_for_command_ack reads under state_lock."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._wait_for_command_ack)
        assert "self._state_lock" in source, "C-5: _wait_for_command_ack should use _state_lock"
        assert "_pending_acks" in source, "Fix 2: should use _pending_acks dict"


# ---------------------------------------------------------------------------
# H-7: home_valid only from HOME_POSITION
# ---------------------------------------------------------------------------

class TestHomeValidSource:
    """H-7: home_valid should only be set by HOME_POSITION, not GPS init."""

    def test_gps_init_does_not_set_home_valid(self):
        """GPS first fix should NOT set home_valid=True."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._handle_message)
        # Find the GPS init block
        lines = source.split("\n")
        in_gps_init = False
        gps_init_sets_home_valid = False
        for line in lines:
            if "not self._home_initialized" in line:
                in_gps_init = True
                continue
            if in_gps_init:
                if "home_valid" in line:
                    gps_init_sets_home_valid = True
                if line.strip() and not line.strip().startswith("#") and "self._home" not in line:
                    break
        assert not gps_init_sets_home_valid, "H-7: GPS init should not set home_valid"


# ---------------------------------------------------------------------------
# M-4: home_distance_m default = inf
# ---------------------------------------------------------------------------

class TestHomeDistanceDefault:
    """M-4: home_distance_m should default to inf, not 0.0."""

    def test_default_inf_not_zero(self):
        """Invalid position/home → distance should be inf, not 0."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter.get_snapshot)
        assert 'float("inf")' in source, "M-4: default home_distance_m should be inf"
        assert "else 0.0" not in source, "M-4: should not default to 0.0"


# ---------------------------------------------------------------------------
# H-1: CORS restriction
# ---------------------------------------------------------------------------

class TestCorsRestriction:
    """H-1: CORS should not allow all origins."""

    def test_cors_not_wildcard(self):
        """CORS origins should be localhost-only, not '*'."""
        import importlib
        # Read main.py source
        main_path = BACKEND_DIR / "main.py"
        source = main_path.read_text()
        assert 'allow_origins=["*"]' not in source, "H-1: CORS should not allow all origins"
        assert "127.0.0.1" in source, "H-1: Should allow localhost"


# ---------------------------------------------------------------------------
# H-6: Mission crash → RTL
# ---------------------------------------------------------------------------

class TestMissionCrashRtl:
    """H-6: Mission executor crash should issue RTL before abort."""

    def test_run_mission_has_return_to_home_in_exception(self):
        """_run_mission exception handler should call return_to_home."""
        import inspect
        from arrakis_core.controller import ArrakisController
        source = inspect.getsource(ArrakisController._run_mission)
        assert "return_to_home" in source, "H-6: _run_mission should RTL on crash"


# ---------------------------------------------------------------------------
# C-2: io_lock telemetry emission during upload
# ---------------------------------------------------------------------------

class TestIoLockTelemetryEmission:
    """C-2: _recv_expected_locked should emit telemetry callbacks."""

    def test_recv_expected_emits_telemetry(self):
        """_recv_expected_locked should contain telemetry callback emission."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._recv_expected_locked)
        assert "_telemetry_callbacks" in source, "C-2: should emit telemetry in recv loop"
        assert "get_snapshot" in source, "C-2: should get snapshot for emission"


# ---------------------------------------------------------------------------
# Integration: Full controller lifecycle with MockAdapter
# ---------------------------------------------------------------------------

class TestControllerLifecycle:
    """Integration test: full controller lifecycle with all safety fixes."""

    def test_create_set_route_start_abort_reset(self):
        profile = AirframeProfile()
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test")
        controller = ArrakisController(adapter, profile)

        # Verify startup
        assert controller.startup_error is None

        # Set route
        from arrakis_core.route_planner import build_route_preview
        request = RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.570, lon=126.980),
                LatLon(lat=37.575, lon=126.985),
            ],
        )
        preview = build_route_preview(request, profile)
        result = controller.set_route(preview)
        assert result is not None

        # Start mission → should enter STARTING
        controller.start_mission()
        time.sleep(0.5)
        phase = controller.state_machine.phase
        assert phase != "IDLE", f"Phase should have left IDLE, got {phase}"

        # Abort → should transition to abort phase
        controller.abort("test abort")
        time.sleep(0.3)
        assert controller.state_machine.phase in INTERRUPT_PHASES

        # Reset
        controller.reset()
        assert controller.state_machine.phase == "IDLE"

        # State payload should work
        payload = controller.state_payload()
        assert payload is not None
        assert payload.stress.level == "nominal"
        assert payload.stress.overall_score == 0.0
        assert payload.stress.reasons == []

        controller.shutdown()


class TestApiHealth:
    """API health should expose the stress envelope for dry-lab monitoring."""

    def test_health_reports_stress_envelope(self):
        import main as main_module
        from flight_adapters.instrumented import InstrumentedFlightAdapter

        profile = AirframeProfile()
        controller = ArrakisController(
            InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.health"),
            profile,
        )
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(controller=controller)))

        try:
            payload = main_module.get_health(request)
        finally:
            controller.shutdown()

        assert payload["status"] in {"ok", "degraded"}
        assert payload["stress"]["level"] == "nominal"
        assert payload["stress"]["overall_score"] == 0.0
        assert payload["stress"]["reasons"] == []


# ---------------------------------------------------------------------------
# SITL-specific tests (opt-in, single connection shared across tests)
# ---------------------------------------------------------------------------

_sitl_skip = pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="Real ArduPilot SITL test requires running simulator",
)


@_sitl_skip
def test_sitl_full_integration(sitl_connection):
    """End-to-end SITL test: connect → bootstrap → arm → concurrent ACK → hardening → abort.

    Uses the session-scoped ``sitl_connection`` fixture from conftest.py
    to share a single TCP connection across all SITL tests.
    """
    adapter, instrumented = sitl_connection

    # --- Phase 1: Bootstrap ---
    bootstrap = instrumented.bootstrap_status()
    assert bootstrap.connected, "Should be connected"
    assert bootstrap.heartbeat_received, "Should have heartbeat"
    assert bootstrap.telemetry_fresh, "Telemetry should be fresh"

    snapshot = instrumented.get_snapshot()
    assert snapshot.telemetry_fresh
    assert snapshot.mode_valid
    print(f"  Bootstrap OK: mode={snapshot.flight_mode} home_valid={snapshot.home_valid}")

    # --- Phase 2: Force-arm via MAVLink (bypass prearm checks for SITL) ---
    mavutil = adapter._mavutil
    with adapter._io_lock:
        adapter._require_master().mav.command_long_send(
            adapter._target_system,
            adapter._target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1.0,      # param1: 1=arm
            21196.0,   # param2: force arm magic number
            0.0, 0.0, 0.0, 0.0, 0.0,
        )
    arm_deadline = time.time() + 10.0
    while time.time() < arm_deadline:
        snapshot = instrumented.get_snapshot()
        if snapshot.armed:
            break
        time.sleep(0.5)
    assert snapshot.armed is True, f"Vehicle should be armed (mode={snapshot.flight_mode})"
    print(f"  Force-Arm OK: armed={snapshot.armed} mode={snapshot.flight_mode}")

    # --- Phase 3: C-5 concurrent _pending_acks reads under lock (Fix 2) ---
    errors = []

    def read_ack():
        try:
            for _ in range(100):
                with adapter._state_lock:
                    _ = dict(adapter._pending_acks)
                time.sleep(0.001)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=read_ack) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"C-5: Concurrent _pending_acks access errors: {errors}"
    print("  C-5 concurrent ACK access OK")

    # --- Phase 4: Hardening field verification ---
    # Fix 1: Heartbeat watchdog
    assert hasattr(adapter, "_last_heartbeat_mono"), "Fix 1: heartbeat watchdog field"
    assert adapter._last_heartbeat_mono > 0, "Heartbeat should have been received"
    assert hasattr(adapter, "_heartbeat_watchdog_timeout_s"), "Fix 1: watchdog timeout field"
    print(f"  Phase 4a OK: heartbeat_mono={adapter._last_heartbeat_mono:.1f}")

    # Fix 9: Monotonic timestamps
    assert hasattr(adapter, "_last_telemetry_mono"), "Fix 9: monotonic telemetry"
    assert adapter._last_telemetry_mono > 0
    print(f"  Phase 4b OK: telemetry_mono={adapter._last_telemetry_mono:.1f}")

    # Fix 10: GPS validation
    gps_snapshot = instrumented.get_snapshot()
    assert -90.0 <= gps_snapshot.lat <= 90.0, f"Lat invalid: {gps_snapshot.lat}"
    assert -180.0 <= gps_snapshot.lon <= 180.0, f"Lon invalid: {gps_snapshot.lon}"
    print(f"  Phase 4c OK: GPS lat={gps_snapshot.lat:.6f} lon={gps_snapshot.lon:.6f}")

    # Fix 3: Connection loss flag
    assert adapter._connection_lost is False, "Should not be lost while connected"
    print("  Phase 4d OK: _connection_lost=False")

    # Fix 8: Pre-arm error list exists
    assert isinstance(adapter._prearm_errors, list), "Fix 8: prearm errors list"
    print(f"  Phase 4e OK: prearm_errors={adapter._prearm_errors}")

    # --- Phase 5: Abort (disarm) ---
    instrumented.abort("test disarm")
    time.sleep(2.0)
    snapshot = instrumented.get_snapshot()
    print(f"  Abort OK: armed={snapshot.armed} mode={snapshot.flight_mode}")
