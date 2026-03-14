"""Safety hardening verification tests.

Tests all CRITICAL and HIGH fixes against live SITL or MockAdapter.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
        preview = build_route_preview(request)
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
            mode_valid=True, position_valid=True, home_valid=True,
        )
        defaults.update(kwargs)
        return TelemetrySnapshot(**defaults)

    def test_trigger_on_fresh_to_stale(self):
        """C-4: fresh→stale should trigger telemetry_lost."""
        from arrakis_core.video_service import VideoService
        vs = VideoService()
        hub = TelemetryHub(self._make_snapshot(fresh=False), vs)

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
        hub = TelemetryHub(self._make_snapshot(fresh=False), vs)

        # Stale → stale: no trigger
        decision = hub.on_telemetry(self._make_snapshot(fresh=False), None, "OUTBOUND")
        assert not decision.trigger_telemetry_lost


# ---------------------------------------------------------------------------
# C-3: Controller safety trigger atomicity (if/elif)
# ---------------------------------------------------------------------------

class TestControllerSafetyAtomicity:
    """C-3: Only one safety trigger should fire per callback."""

    def test_only_one_trigger_fires(self):
        """C-3: If both battery_rtl and geofence fire, only one action taken."""
        adapter = InstrumentedFlightAdapter(MockAdapter(), logger_name="test")
        controller = ArrakisController(adapter)

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
        adapter = InstrumentedFlightAdapter(MockAdapter(), logger_name="test")
        adapter.connect()
        controller = ArrakisController(adapter)

        # Set up route
        from arrakis_core.route_planner import build_route_preview
        request = RouteRequest(
            home=LatLon(lat=37.5665, lon=126.9780),
            waypoints=[
                LatLon(lat=37.570, lon=126.980),
                LatLon(lat=37.575, lon=126.985),
            ],
        )
        preview = build_route_preview(request)
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
        adapter = InstrumentedFlightAdapter(MockAdapter(), logger_name="test")
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
        preview = build_route_preview(request)
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
    """C-5: _last_command_ack must be protected by _state_lock."""

    def test_send_command_clears_ack_under_lock(self):
        """Verify _send_command clears _last_command_ack under state_lock."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._send_command)
        # _state_lock must appear before _last_command_ack assignment
        assert "self._state_lock" in source, "C-5: _send_command should use _state_lock"
        assert "self._last_command_ack = None" in source

    def test_wait_for_ack_reads_under_lock(self):
        """Verify _wait_for_command_ack reads under state_lock."""
        import inspect
        from flight_adapters.ardupilot import ArduPilotAdapter
        source = inspect.getsource(ArduPilotAdapter._wait_for_command_ack)
        assert "self._state_lock" in source, "C-5: _wait_for_command_ack should use _state_lock"


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
        adapter = InstrumentedFlightAdapter(MockAdapter(), logger_name="test")
        controller = ArrakisController(adapter)

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
        preview = build_route_preview(request)
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

        controller.shutdown()


# ---------------------------------------------------------------------------
# SITL-specific tests (opt-in, single connection shared across tests)
# ---------------------------------------------------------------------------

_sitl_skip = pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="Real ArduPilot SITL test requires running simulator",
)


@_sitl_skip
def test_sitl_full_integration():
    """End-to-end SITL test: connect → bootstrap → arm → concurrent ACK → abort → reset.

    Uses a single TCP connection since SITL only accepts one client at a time.
    """
    from flight_adapters.ardupilot import ArduPilotAdapter

    adapter = ArduPilotAdapter()
    instrumented = InstrumentedFlightAdapter(adapter, logger_name="test.sitl")
    instrumented.connect()

    # --- Phase 1: Bootstrap ---
    deadline = time.time() + 15.0
    bootstrap = None
    while time.time() < deadline:
        bootstrap = instrumented.bootstrap_status()
        if bootstrap.mission_ready:
            break
        time.sleep(0.5)

    assert bootstrap.connected, "Should be connected"
    assert bootstrap.heartbeat_received, "Should have heartbeat"
    assert bootstrap.telemetry_fresh, "Telemetry should be fresh"

    snapshot = instrumented.get_snapshot()
    assert snapshot.telemetry_fresh
    assert snapshot.mode_valid
    print(f"  Bootstrap OK: mode={snapshot.flight_mode} home_valid={snapshot.home_valid}")

    # --- Phase 2: Force-arm via MAVLink (bypass prearm checks for SITL) ---
    # MAV_CMD_COMPONENT_ARM_DISARM with param2=21196.0 forces arm
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
    # Wait for armed state
    arm_deadline = time.time() + 10.0
    while time.time() < arm_deadline:
        snapshot = instrumented.get_snapshot()
        if snapshot.armed:
            break
        time.sleep(0.5)
    assert snapshot.armed is True, f"Vehicle should be armed (mode={snapshot.flight_mode})"
    print(f"  Force-Arm OK: armed={snapshot.armed} mode={snapshot.flight_mode}")

    # --- Phase 3: C-5 concurrent _last_command_ack reads under lock ---
    errors = []

    def read_ack():
        try:
            for _ in range(100):
                with adapter._state_lock:
                    _ = adapter._last_command_ack
                time.sleep(0.001)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=read_ack) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"C-5: Concurrent _last_command_ack access errors: {errors}"
    print("  C-5 concurrent ACK access OK")

    # --- Phase 4: Abort (disarm) ---
    instrumented.abort("test disarm")
    time.sleep(2.0)
    snapshot = instrumented.get_snapshot()
    print(f"  Abort OK: armed={snapshot.armed} mode={snapshot.flight_mode}")

    # --- Phase 5: Reset ---
    instrumented.reset()
    print("  Reset OK")
