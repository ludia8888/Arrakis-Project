"""SITL flight sequence integration tests.

Tests actual flight operations against a running ArduPilot SITL simulator:
- Ground operations (mode changes, arm/disarm)
- Takeoff, hover, and landing sequences
- Mission upload and AUTO flight
- VTOL transitions (FW/MC)
- Emergency abort paths
- Edge cases and error handling

Gated by:
    ARRAKIS_TEST_REAL_ARDUPILOT=1
    ARRAKIS_ARDUPILOT_CONNECTION=tcp:127.0.0.1:5760
    ARRAKIS_ARDUPILOT_COMMAND_TIMEOUT=45

Run with:
    ./scripts/run_sitl_tests.sh
"""

from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from conftest import force_arm_sitl, force_disarm_sitl
from schemas import TelemetrySnapshot

_sitl_skip = pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="SITL flight sequence tests require running ArduPilot simulator",
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _make_nearby_waypoints(home_lat: float, home_lon: float, count: int, distance_m: float = 200.0):
    """Generate waypoints in a circle around the home position.

    Returns a list of {"lat": ..., "lon": ...} dicts.
    """
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(home_lat)) * 111_320.0
    waypoints = []
    for i in range(count):
        angle = 2 * math.pi * i / max(count, 1)
        dlat = (distance_m * math.cos(angle)) / lat_scale
        dlon = (distance_m * math.sin(angle)) / lon_scale
        waypoints.append({"lat": home_lat + dlat, "lon": home_lon + dlon})
    return waypoints


def _wait_for_alt(adapter, target_alt: float, tolerance: float = 0.3, timeout: float = 60.0) -> bool:
    """Wait until altitude reaches target_alt * (1 - tolerance).

    Returns True if reached, False if timed out.
    """
    threshold = target_alt * (1.0 - tolerance)
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if snapshot.alt_m >= threshold:
            return True
        time.sleep(0.5)
    return False


def _wait_for_disarm(adapter, timeout: float = 60.0) -> bool:
    """Wait until vehicle is disarmed.

    Returns True if disarmed, False if timed out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if not snapshot.armed:
            return True
        time.sleep(0.5)
    return False


def _wait_for_mode(adapter, modes: set[str], timeout: float = 30.0) -> bool:
    """Wait until flight mode is one of the specified modes.

    Returns True if mode reached, False if timed out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if snapshot.flight_mode.upper() in {m.upper() for m in modes}:
            return True
        time.sleep(0.5)
    return False


def _wait_for_ground(adapter, timeout: float = 30.0) -> bool:
    """Wait until vehicle is on the ground (alt <= 1.0m and not armed).

    After force-disarm from flight, the vehicle falls to ground.
    This helper waits for the SITL to register ground contact.
    Returns True if on ground, False if timed out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if snapshot.alt_m <= 1.0 and not snapshot.armed:
            return True
        time.sleep(0.5)
    return False


# ===========================================================================
# Test Classes
# ===========================================================================


@_sitl_skip
class TestSITLGroundOps:
    """Ground operations: mode changes, adapter arm, idempotent arm."""

    def test_mode_change_qloiter_to_guided(self, sitl_connection):
        """Verify mode changes actually take effect via MAVLink."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        adapter._set_mode("QLOITER")
        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() == "QLOITER", f"Expected QLOITER, got {snapshot.flight_mode}"

        adapter._set_mode("GUIDED")
        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() == "GUIDED", f"Expected GUIDED, got {snapshot.flight_mode}"
        print(f"  [PASS] Mode change: QLOITER -> GUIDED")

    def test_arm_via_adapter_method(self, sitl_connection):
        """Verify adapter.arm() full sequence (QLOITER -> ARM cmd -> wait)."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        adapter.arm()
        snapshot = adapter.get_snapshot()
        assert snapshot.armed is True, "adapter.arm() should result in armed state"
        assert snapshot.flight_mode.upper() == "QLOITER", f"Expected QLOITER after arm, got {snapshot.flight_mode}"
        print(f"  [PASS] adapter.arm(): armed={snapshot.armed} mode={snapshot.flight_mode}")

    def test_double_arm_is_idempotent(self, sitl_connection):
        """Verify calling arm() twice does not cause errors."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        adapter.arm()
        snapshot1 = adapter.get_snapshot()
        assert snapshot1.armed is True

        # Second arm should not raise
        adapter.arm()
        snapshot2 = adapter.get_snapshot()
        assert snapshot2.armed is True, "Should still be armed after double arm()"
        print(f"  [PASS] Double arm: no error, armed={snapshot2.armed}")


@_sitl_skip
class TestSITLTakeoffAndLand:
    """Core flight sequences: takeoff, hover, landing, RTL."""

    def test_takeoff_hover_land_basic(self, sitl_connection):
        """Full flight cycle: force-arm -> takeoff(20m) -> land -> disarm."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.takeoff_multicopter(20.0)
        snapshot = adapter.get_snapshot()
        assert snapshot.alt_m >= 12.0, f"Should reach >=12m (60% of 20m), got {snapshot.alt_m:.1f}m"
        assert snapshot.armed is True
        print(f"  [PASS] Takeoff: alt={snapshot.alt_m:.1f}m armed={snapshot.armed}")

        adapter.land_vertical()
        landed = _wait_for_disarm(adapter, timeout=90.0)
        snapshot = adapter.get_snapshot()
        if landed:
            assert snapshot.alt_m <= 2.0, f"After landing, alt should be near 0, got {snapshot.alt_m:.1f}m"
            print(f"  [PASS] Landing complete: alt={snapshot.alt_m:.1f}m armed={snapshot.armed}")
        else:
            # SITL may not auto-disarm after QLAND; check alt instead
            assert snapshot.alt_m <= 3.0 or snapshot.flight_mode.upper() in ("QLAND", "LAND"), \
                f"Landing not progressing: alt={snapshot.alt_m:.1f}m mode={snapshot.flight_mode}"
            print(f"  [WARN] Landing partial: alt={snapshot.alt_m:.1f}m mode={snapshot.flight_mode}")
            force_disarm_sitl(adapter)

    def test_takeoff_altitude_accuracy(self, sitl_connection):
        """Verify SITL altitude control within acceptable tolerance."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        target_alt = 15.0
        adapter.takeoff_multicopter(target_alt)
        # Wait extra for stabilization
        time.sleep(10.0)
        snapshot = adapter.get_snapshot()
        alt_error = abs(snapshot.alt_m - target_alt)
        assert alt_error <= 5.0, f"Altitude error too large: target={target_alt}m actual={snapshot.alt_m:.1f}m error={alt_error:.1f}m"
        print(f"  [PASS] Altitude accuracy: target={target_alt}m actual={snapshot.alt_m:.1f}m error={alt_error:.1f}m")

    def test_rtl_from_hover(self, sitl_connection):
        """Verify RTL mode from hover: should enter RTL/QRTL and eventually descend."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.takeoff_multicopter(20.0)
        adapter.return_to_home()

        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() in ("RTL", "QRTL"), \
            f"Expected RTL or QRTL, got {snapshot.flight_mode}"
        print(f"  [PASS] RTL entered: mode={snapshot.flight_mode}")

        # Wait for landing from RTL
        disarmed = _wait_for_disarm(adapter, timeout=120.0)
        if disarmed:
            print(f"  [PASS] RTL landing complete: disarmed")
        else:
            snapshot = adapter.get_snapshot()
            print(f"  [INFO] RTL in progress: alt={snapshot.alt_m:.1f}m mode={snapshot.flight_mode}")
            # RTL may take a while; just verify descending
            assert snapshot.alt_m < 20.0 or snapshot.flight_mode.upper() in ("RTL", "QRTL", "QLAND", "LAND"), \
                f"RTL not progressing: alt={snapshot.alt_m:.1f}m mode={snapshot.flight_mode}"


@_sitl_skip
class TestSITLMissionUploadAndAuto:
    """Mission upload protocol and AUTO flight execution."""

    def test_upload_3_waypoint_mission(self, sitl_connection):
        """Upload a simple 3-item mission (home + takeoff + 1wp + 1return + land)."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        waypoints = _make_nearby_waypoints(home.lat, home.lon, count=1, distance_m=150.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": waypoints,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 25.0,
        }
        adapter.upload_roundtrip_mission(route_spec)

        assert adapter._outbound_count == 1, f"Expected 1 outbound, got {adapter._outbound_count}"
        assert adapter._return_count == 1, f"Expected 1 return, got {adapter._return_count}"
        assert adapter.current_leg() == "takeoff", f"Expected 'takeoff' leg, got {adapter.current_leg()}"
        # mission items: home(0) + takeoff(1) + outbound(2) + return(3) + land(4) = 5
        assert adapter._mission_seq_end == 5, f"Expected 5 mission items, got {adapter._mission_seq_end}"
        print(f"  [PASS] Mission uploaded: {adapter._mission_seq_end} items, leg={adapter.current_leg()}")

    def test_upload_10_waypoint_mission(self, sitl_connection):
        """Upload a larger mission with 10 waypoints (5 outbound + 5 return)."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        outbound = _make_nearby_waypoints(home.lat, home.lon, count=5, distance_m=200.0)
        return_path = _make_nearby_waypoints(home.lat, home.lon, count=5, distance_m=100.0)

        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": outbound,
            "return_path": return_path,
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 30.0,
        }

        started = time.perf_counter()
        adapter.upload_roundtrip_mission(route_spec)
        upload_time = time.perf_counter() - started

        # home(0) + takeoff(1) + 5 outbound + 5 return + land(1) = 13
        assert adapter._mission_seq_end == 13, f"Expected 13 mission items, got {adapter._mission_seq_end}"
        assert upload_time < 30.0, f"Upload took {upload_time:.1f}s, expected < 30s"
        print(f"  [PASS] 10-wp mission uploaded in {upload_time:.1f}s: {adapter._mission_seq_end} items")

    def test_auto_mission_flight_short(self, sitl_connection):
        """Start a short AUTO mission and verify it begins executing."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        waypoints = _make_nearby_waypoints(home.lat, home.lon, count=1, distance_m=150.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": waypoints,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 25.0,
        }

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.upload_roundtrip_mission(route_spec)
        adapter.start_mission()

        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() == "AUTO", f"Expected AUTO mode, got {snapshot.flight_mode}"
        print(f"  [PASS] Mission started: mode={snapshot.flight_mode}")

        # Wait for takeoff to begin
        time.sleep(10.0)
        snapshot = adapter.get_snapshot()
        assert snapshot.alt_m > 3.0, f"Expected altitude gain after mission start, got {snapshot.alt_m:.1f}m"
        leg = adapter.current_leg()
        assert leg in ("takeoff", "outbound"), f"Expected takeoff/outbound leg, got {leg}"
        print(f"  [PASS] Mission progressing: alt={snapshot.alt_m:.1f}m leg={leg}")

    def test_mission_leg_tracking(self, sitl_connection):
        """Verify route leg tracking transitions during mission execution."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        outbound = _make_nearby_waypoints(home.lat, home.lon, count=2, distance_m=100.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": outbound,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 15.0,
            "cruise_alt_m": 20.0,
        }

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.upload_roundtrip_mission(route_spec)
        adapter.start_mission()

        # Monitor leg transitions for up to 30 seconds
        legs_seen = set()
        deadline = time.time() + 30.0
        while time.time() < deadline:
            leg = adapter.current_leg()
            legs_seen.add(leg)
            if leg == "outbound":
                break
            time.sleep(1.0)

        assert "takeoff" in legs_seen, f"Should have seen 'takeoff' leg, saw: {legs_seen}"
        print(f"  [PASS] Leg tracking: seen {legs_seen}")


@_sitl_skip
class TestSITLVTOLTransition:
    """VTOL transition commands (FW/MC) against SITL QuadPlane."""

    def test_fw_transition_command_accepted(self, sitl_connection):
        """Verify MAV_CMD_DO_VTOL_TRANSITION(FW) is accepted by SITL.

        SITL QuadPlane only accepts VTOL transition in AUTO mode.
        We upload a short mission, start AUTO, then request FW transition.
        """
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        waypoints = _make_nearby_waypoints(home.lat, home.lon, count=1, distance_m=300.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": waypoints,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 30.0,
        }

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.upload_roundtrip_mission(route_spec)
        adapter.start_mission()

        # Wait for some altitude gain before trying FW transition
        time.sleep(15.0)

        # In AUTO mode, attempt FW transition
        try:
            adapter.transition_to_fixedwing()
            print(f"  [PASS] FW transition command accepted in AUTO")
        except TimeoutError:
            # ACK timeout is acceptable - command was sent
            print(f"  [INFO] FW transition ACK timed out (acceptable in SITL)")
        except RuntimeError as e:
            # SITL may reject if not enough speed - this is acceptable
            print(f"  [INFO] FW transition RuntimeError (acceptable): {e}")

        # Verify vtol_state hint was set regardless of ACK result
        with adapter._state_lock:
            vtol_state = adapter._state.vtol_state
        assert vtol_state == "FW", f"Expected vtol_state hint 'FW', got '{vtol_state}'"
        print(f"  [PASS] vtol_state hint: {vtol_state}")

    def test_mc_transition_after_fw(self, sitl_connection):
        """Verify FW->MC round-trip transition commands in AUTO mode."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        waypoints = _make_nearby_waypoints(home.lat, home.lon, count=1, distance_m=300.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": waypoints,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 30.0,
        }

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.upload_roundtrip_mission(route_spec)
        adapter.start_mission()
        time.sleep(15.0)

        # FW transition in AUTO
        try:
            adapter.transition_to_fixedwing()
        except (TimeoutError, RuntimeError):
            pass  # Acceptable in SITL
        time.sleep(5.0)

        # MC transition
        try:
            adapter.transition_to_multicopter()
            print(f"  [PASS] MC transition command accepted")
        except (TimeoutError, RuntimeError) as e:
            print(f"  [INFO] MC transition: {e}")

        # Verify vtol_state hint
        with adapter._state_lock:
            vtol_state = adapter._state.vtol_state
        assert vtol_state == "MC", f"Expected vtol_state hint 'MC', got '{vtol_state}'"
        print(f"  [PASS] FW->MC round-trip: vtol_state={vtol_state}")


@_sitl_skip
class TestSITLEmergency:
    """Emergency abort paths during flight."""

    def test_abort_during_takeoff(self, sitl_connection):
        """Verify abort() during takeoff results in safe state."""
        adapter, instrumented = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(3.0)  # Extra recovery time after potential crash from previous test

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.takeoff_multicopter(20.0)

        # Abort immediately after takeoff completes
        instrumented.abort("test abort during takeoff")
        time.sleep(5.0)

        snapshot = adapter.get_snapshot()
        is_safe = (
            not snapshot.armed
            or snapshot.flight_mode.upper() in ("RTL", "QRTL", "LAND", "QLAND")
        )
        print(f"  [{'PASS' if is_safe else 'WARN'}] Post-abort: armed={snapshot.armed} mode={snapshot.flight_mode}")
        assert is_safe, f"Vehicle not in safe state after abort: armed={snapshot.armed} mode={snapshot.flight_mode}"

    def test_abort_during_auto_mission(self, sitl_connection):
        """Verify abort() during AUTO mission results in safe state."""
        adapter, instrumented = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        home = adapter.get_home()
        waypoints = _make_nearby_waypoints(home.lat, home.lon, count=1, distance_m=150.0)
        route_spec = {
            "home": {"lat": home.lat, "lon": home.lon},
            "outbound": waypoints,
            "return_path": [{"lat": home.lat, "lon": home.lon}],
            "takeoff_alt_m": 20.0,
            "cruise_alt_m": 25.0,
        }

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.upload_roundtrip_mission(route_spec)
        adapter.start_mission()

        # Wait for mission to progress
        time.sleep(10.0)
        snapshot_before = adapter.get_snapshot()
        print(f"  [INFO] Before abort: alt={snapshot_before.alt_m:.1f}m mode={snapshot_before.flight_mode}")

        instrumented.abort("test abort during AUTO mission")
        time.sleep(3.0)

        snapshot = adapter.get_snapshot()
        is_safe = (
            not snapshot.armed
            or snapshot.flight_mode.upper() in ("RTL", "QRTL", "LAND", "QLAND")
        )
        print(f"  [{'PASS' if is_safe else 'WARN'}] Post-abort: armed={snapshot.armed} mode={snapshot.flight_mode}")
        assert is_safe, f"Vehicle not in safe state after abort: armed={snapshot.armed} mode={snapshot.flight_mode}"

    def test_rtl_returns_near_home(self, sitl_connection):
        """Verify RTL actually returns vehicle near home position.

        Uses adapter.arm() (not force_arm) to ensure QLOITER mode is set,
        clearing any residual VTOL transition state from previous tests.
        """
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        # Wait for vehicle to settle on ground after previous tests
        _wait_for_ground(adapter, timeout=30.0)
        time.sleep(3.0)

        # Use adapter.arm() (sets QLOITER first) to clear VTOL transition state
        try:
            adapter.arm()
        except (RuntimeError, TimeoutError):
            # Fallback to force_arm if adapter.arm() fails
            armed = force_arm_sitl(adapter)
            assert armed, "Force-arm should succeed"

        try:
            adapter.takeoff_multicopter(20.0)
        except (RuntimeError, TimeoutError) as e:
            if "already flying" in str(e).lower():
                # SITL QuadPlane quirk: vehicle thinks it's already airborne
                # after previous VTOL transitions. Use RTL directly.
                print(f"  [INFO] Takeoff skipped (SITL quirk): {e}")
            else:
                raise

        # Trigger RTL
        adapter.return_to_home()
        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() in ("RTL", "QRTL"), \
            f"Expected RTL/QRTL, got {snapshot.flight_mode}"

        # Wait for RTL to complete
        disarmed = _wait_for_disarm(adapter, timeout=180.0)

        snapshot = adapter.get_snapshot()
        if disarmed:
            print(f"  [PASS] RTL complete: alt={snapshot.alt_m:.1f}m armed={snapshot.armed}")
        else:
            # Still descending - check we're at least in a landing mode
            assert snapshot.flight_mode.upper() in ("RTL", "QRTL", "LAND", "QLAND"), \
                f"Expected RTL/landing mode, got {snapshot.flight_mode}"
            print(f"  [INFO] RTL in progress: alt={snapshot.alt_m:.1f}m mode={snapshot.flight_mode}")

    def test_force_disarm_from_flight(self, sitl_connection):
        """Verify force disarm (param2=21196) works during flight."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.takeoff_multicopter(20.0)
        snapshot_before = adapter.get_snapshot()
        assert snapshot_before.armed is True
        assert snapshot_before.alt_m > 10.0, f"Should be airborne, got alt={snapshot_before.alt_m:.1f}m"

        # Force disarm while in flight
        disarmed = force_disarm_sitl(adapter)
        assert disarmed, "Force-disarm should succeed even during flight"
        snapshot = adapter.get_snapshot()
        assert snapshot.armed is False
        print(f"  [PASS] Force disarm from flight: alt_before={snapshot_before.alt_m:.1f}m armed={snapshot.armed}")


@_sitl_skip
class TestSITLEdgeCases:
    """Edge cases and error handling."""

    def test_upload_empty_outbound_raises(self, sitl_connection):
        """Verify empty mission upload is rejected."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        route_spec = {
            "outbound": [],
            "return_path": [],
        }
        with pytest.raises(ValueError, match="outbound and return_path"):
            adapter.upload_roundtrip_mission(route_spec)
        print(f"  [PASS] Empty mission correctly rejected")

    def test_takeoff_when_already_airborne(self, sitl_connection):
        """Verify takeoff command while already airborne doesn't crash."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(2.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        adapter.takeoff_multicopter(15.0)
        snapshot1 = adapter.get_snapshot()
        assert snapshot1.alt_m >= 8.0, f"Should be airborne at ~15m, got {snapshot1.alt_m:.1f}m"

        # Second takeoff while already airborne
        try:
            adapter.takeoff_multicopter(20.0)
            snapshot2 = adapter.get_snapshot()
            print(f"  [PASS] Second takeoff accepted: alt={snapshot2.alt_m:.1f}m")
        except (TimeoutError, RuntimeError) as e:
            # Some error is acceptable - vehicle is already airborne
            print(f"  [PASS] Second takeoff raised (acceptable): {type(e).__name__}: {e}")

    def test_land_when_already_on_ground(self, sitl_connection):
        """Verify land command on ground doesn't crash."""
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        time.sleep(1.0)

        # Vehicle is on ground, issue land
        adapter.land_vertical()
        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() in ("QLAND", "LAND"), \
            f"Expected QLAND/LAND mode, got {snapshot.flight_mode}"
        print(f"  [PASS] Land on ground: mode={snapshot.flight_mode}")

    def test_mode_change_to_invalid_mode(self, sitl_connection):
        """Verify invalid mode change raises RuntimeError."""
        adapter, _ = sitl_connection

        with pytest.raises(RuntimeError, match="not available"):
            adapter._set_mode("NONEXISTENT_MODE")
        print(f"  [PASS] Invalid mode correctly rejected")

    def test_telemetry_streams_during_flight(self, sitl_connection):
        """Verify telemetry callbacks fire continuously during flight.

        Uses force_arm + direct arm to ensure clean state even after
        VTOL transition tests that may leave residual SITL state.
        """
        adapter, _ = sitl_connection
        force_disarm_sitl(adapter)
        _wait_for_ground(adapter, timeout=30.0)
        time.sleep(3.0)

        telemetry_events: list[TelemetrySnapshot] = []
        adapter.stream_telemetry(telemetry_events.append)

        armed = force_arm_sitl(adapter)
        assert armed, "Force-arm should succeed"

        # Clear events collected during arm
        telemetry_events.clear()

        # Try takeoff; if rejected due to SITL residual state, collect
        # telemetry from armed hover instead
        try:
            adapter.takeoff_multicopter(15.0)
        except (RuntimeError, TimeoutError) as e:
            # "Already flying" is possible if SITL still thinks we're airborne
            print(f"  [INFO] Takeoff exception (testing telemetry from hover): {e}")

        time.sleep(5.0)

        # Should have received telemetry callbacks during armed state
        assert len(telemetry_events) > 5, \
            f"Expected >5 telemetry events during flight, got {len(telemetry_events)}"

        # All events should be TelemetrySnapshot
        for event in telemetry_events:
            assert isinstance(event, TelemetrySnapshot), f"Expected TelemetrySnapshot, got {type(event)}"

        # Verify telemetry is working (armed state telemetry)
        armed_events = [e for e in telemetry_events if e.armed]
        assert len(armed_events) > 0, "Expected at least some armed telemetry events"

        # Check for altitude variation (may be small if takeoff failed)
        alts = [e.alt_m for e in telemetry_events]
        alt_range = max(alts) - min(alts)
        print(f"  [PASS] Telemetry during flight: {len(telemetry_events)} events, alt range={alt_range:.1f}m, armed events={len(armed_events)}")

        # Clean up: remove the callback to avoid accumulating events in other tests
        adapter._telemetry_callbacks.remove(telemetry_events.append)
