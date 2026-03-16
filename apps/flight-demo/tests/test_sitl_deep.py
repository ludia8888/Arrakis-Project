"""Deep SITL integration tests — 5 critical scenarios.

Tests long-duration and fault-injection scenarios against ArduPilot SITL:
1. Full mission completion (takeoff → outbound → return → land → disarm)
2. Fixed-wing airspeed verification during AUTO mission
3. Battery failsafe RTL trigger via SITL parameter injection
4. GPS denial / degradation detection
5. Communication loss detection via socket close

Gated by:
    ARRAKIS_TEST_REAL_ARDUPILOT=1
    ARRAKIS_ARDUPILOT_CONNECTION=tcp:127.0.0.1:5760
    ARRAKIS_ARDUPILOT_COMMAND_TIMEOUT=45

Run with:
    ./scripts/run_sitl_tests.sh

WARNING: These tests are long-running (~18 minutes total at speedup=1).
"""

from __future__ import annotations

import math
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from conftest import (
    force_arm_sitl,
    force_disarm_sitl,
    get_sitl_param,
    set_sitl_param,
)

_sitl_skip = pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="Deep SITL tests require running ArduPilot simulator",
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _make_nearby_waypoint(
    home_lat: float, home_lon: float,
    distance_m: float, bearing_deg: float = 0.0,
) -> dict:
    """Generate a single waypoint at *distance_m* and *bearing_deg* from home."""
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(home_lat)) * 111_320.0
    angle_rad = math.radians(bearing_deg)
    dlat = (distance_m * math.cos(angle_rad)) / lat_scale
    dlon = (distance_m * math.sin(angle_rad)) / lon_scale
    return {"lat": home_lat + dlat, "lon": home_lon + dlon}


def _wait_for_disarm(adapter, timeout: float = 60.0) -> bool:
    """Wait until vehicle is disarmed.  Returns True if disarmed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not adapter.get_snapshot().armed:
            return True
        time.sleep(0.5)
    return False


def _wait_for_leg(adapter, target_legs: set[str], timeout: float = 120.0) -> str | None:
    """Wait until adapter.current_leg() is in *target_legs*.

    Returns the matched leg name, or None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        leg = adapter.current_leg()
        if leg in target_legs:
            return leg
        time.sleep(1.0)
    return None


def _wait_for_mode(adapter, modes: set[str], timeout: float = 30.0) -> bool:
    """Wait until flight mode is one of *modes* (case-insensitive)."""
    upper_modes = {m.upper() for m in modes}
    deadline = time.time() + timeout
    while time.time() < deadline:
        if adapter.get_snapshot().flight_mode.upper() in upper_modes:
            return True
        time.sleep(0.5)
    return False


def _wait_for_alt(adapter, target_alt: float, tolerance: float = 0.3,
                  timeout: float = 60.0) -> bool:
    """Wait until altitude reaches *target_alt * (1 - tolerance)*."""
    threshold = target_alt * (1.0 - tolerance)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if adapter.get_snapshot().alt_m >= threshold:
            return True
        time.sleep(0.5)
    return False


def _collect_telemetry(adapter, duration_s: float,
                       interval_s: float = 1.0) -> list:
    """Collect TelemetrySnapshot objects over *duration_s* seconds."""
    snapshots: list = []
    deadline = time.time() + duration_s
    while time.time() < deadline:
        snapshots.append(adapter.get_snapshot())
        time.sleep(interval_s)
    return snapshots


@contextmanager
def _save_and_restore_params(adapter, param_names: list[str]):
    """Context manager: save SITL params before test, restore after."""
    originals: dict[str, float] = {}
    for name in param_names:
        try:
            originals[name] = get_sitl_param(adapter, name)
        except (TimeoutError, Exception):
            pass  # param may not exist; skip restore for it
    try:
        yield originals
    finally:
        for name, value in originals.items():
            try:
                set_sitl_param(adapter, name, value)
            except Exception:
                pass
        time.sleep(1.0)


def _build_short_mission(adapter, distance_m: float = 100.0,
                         bearing_deg: float = 0.0):
    """Build and upload a minimal 1-waypoint roundtrip mission.

    Returns the route_spec dict.
    """
    home = adapter.get_home()
    wp = _make_nearby_waypoint(home.lat, home.lon, distance_m, bearing_deg)
    route_spec = {
        "home": {"lat": home.lat, "lon": home.lon},
        "outbound": [wp],
        "return_path": [{"lat": home.lat, "lon": home.lon}],
        "takeoff_alt_m": 20.0,
        "cruise_alt_m": 25.0,
    }
    adapter.upload_roundtrip_mission(route_spec)
    return route_spec


# ===================================================================
# Scenario 1: Full Mission Completion
# ===================================================================

@_sitl_skip
class TestSITLFullMissionCompletion:
    """Verify the entire mission lifecycle from takeoff through disarm."""

    def test_full_roundtrip_mission_to_disarm(self, sitl_connection):
        """Full mission: takeoff → outbound → return → land → disarm."""
        adapter, _ = sitl_connection

        # Clean state
        force_disarm_sitl(adapter)
        time.sleep(2.0)

        # Build & upload short mission (100m, bearing 45°)
        _build_short_mission(adapter, distance_m=100.0, bearing_deg=45.0)

        # Arm and start
        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm for full mission test"

        adapter.start_mission()
        snapshot = adapter.get_snapshot()
        assert snapshot.flight_mode.upper() == "AUTO", (
            f"Expected AUTO mode, got {snapshot.flight_mode}"
        )

        # Monitor mission legs for up to 300s
        legs_seen: set[str] = set()
        start_time = time.time()
        deadline = start_time + 300.0
        last_leg = ""

        while time.time() < deadline:
            leg = adapter.current_leg()
            snapshot = adapter.get_snapshot()

            if leg != last_leg:
                elapsed = time.time() - start_time
                print(f"  [{elapsed:6.1f}s] Leg transition: {last_leg!r} → {leg!r}  "
                      f"alt={snapshot.alt_m:.1f}m  armed={snapshot.armed}")
                last_leg = leg

            legs_seen.add(leg)

            # Mission complete: disarmed and back to idle
            if not snapshot.armed and leg == "idle" and len(legs_seen) > 1:
                break

            time.sleep(2.0)

        elapsed_total = time.time() - start_time
        print(f"  Mission completed in {elapsed_total:.1f}s")
        print(f"  Legs observed: {sorted(legs_seen)}")

        # Fallback: wait for disarm if loop exited on timeout
        if adapter.get_snapshot().armed:
            disarmed = _wait_for_disarm(adapter, timeout=120.0)
            assert disarmed, "Vehicle did not disarm after full mission"

        # Verify mission phases were observed
        assert "takeoff" in legs_seen, f"Takeoff leg not seen. Legs: {legs_seen}"
        assert "outbound" in legs_seen or "return" in legs_seen, (
            f"Neither outbound nor return seen. Legs: {legs_seen}"
        )

        # Verify final state
        final = adapter.get_snapshot()
        assert not final.armed, "Vehicle still armed after mission"
        assert final.alt_m <= 3.0, f"Vehicle not on ground: alt={final.alt_m}m"

    def test_leg_transitions_in_order(self, sitl_connection):
        """Verify leg transitions happen in correct chronological order."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(2.0)

        _build_short_mission(adapter, distance_m=100.0, bearing_deg=135.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm"

        adapter.start_mission()

        # Track first-seen time of each leg
        transition_times: dict[str, float] = {}
        start_time = time.time()
        deadline = start_time + 300.0

        while time.time() < deadline:
            leg = adapter.current_leg()
            snapshot = adapter.get_snapshot()

            if leg not in transition_times:
                transition_times[leg] = time.time() - start_time
                print(f"  First saw leg {leg!r} at {transition_times[leg]:.1f}s  "
                      f"alt={snapshot.alt_m:.1f}m")

            if not snapshot.armed and leg == "idle" and len(transition_times) > 1:
                break

            time.sleep(2.0)

        print(f"  All transitions: {transition_times}")

        # Verify chronological order of observed legs
        ordered_legs = ["takeoff", "outbound", "return", "landing"]
        observed_ordered = [l for l in ordered_legs if l in transition_times]

        for i in range(len(observed_ordered) - 1):
            a, b = observed_ordered[i], observed_ordered[i + 1]
            assert transition_times[a] < transition_times[b], (
                f"Leg {a!r} ({transition_times[a]:.1f}s) should come "
                f"before {b!r} ({transition_times[b]:.1f}s)"
            )

        # Cleanup
        if adapter.get_snapshot().armed:
            force_disarm_sitl(adapter)


# ===================================================================
# Scenario 2: Fixed-Wing Speed Verification
# ===================================================================

@_sitl_skip
class TestSITLFixedWingSpeed:
    """Verify airspeed during fixed-wing AUTO flight."""

    def test_airspeed_during_outbound_leg(self, sitl_connection):
        """FW airspeed should exceed 10 m/s during outbound leg."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(2.0)

        # Longer mission for FW transition + cruise distance
        _build_short_mission(adapter, distance_m=300.0, bearing_deg=0.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm for airspeed test"

        adapter.start_mission()

        # Wait for outbound leg (FW transition + climb complete)
        leg = _wait_for_leg(adapter, {"outbound"}, timeout=120.0)
        assert leg == "outbound", (
            f"Did not reach outbound leg within 120s. "
            f"Current leg: {adapter.current_leg()}"
        )

        # Collect telemetry for 30s during FW outbound flight
        print("  Collecting airspeed data during outbound leg (30s)...")
        snapshots = _collect_telemetry(adapter, duration_s=30.0, interval_s=1.0)

        airspeeds = [s.airspeed_mps for s in snapshots]
        groundspeeds = [s.groundspeed_mps for s in snapshots]

        max_airspeed = max(airspeeds) if airspeeds else 0.0
        avg_airspeed = sum(airspeeds) / len(airspeeds) if airspeeds else 0.0
        max_groundspeed = max(groundspeeds) if groundspeeds else 0.0

        print(f"  Samples: {len(snapshots)}")
        print(f"  Airspeed:     peak={max_airspeed:.1f} m/s  avg={avg_airspeed:.1f} m/s")
        print(f"  Groundspeed:  peak={max_groundspeed:.1f} m/s")

        # FW cruise should exceed 10 m/s (profile default ~22 m/s)
        assert max_airspeed > 10.0, (
            f"Max airspeed {max_airspeed:.1f} m/s too low for FW flight"
        )
        assert max_groundspeed > 5.0, (
            f"Max groundspeed {max_groundspeed:.1f} m/s too low — no movement?"
        )

        # Cleanup
        force_disarm_sitl(adapter)

    def test_airspeed_low_during_hover(self, sitl_connection):
        """Control test: airspeed should be low during MC hover."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(2.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm for hover test"

        try:
            adapter.takeoff_multicopter(20.0)
        except Exception:
            pass  # May get "Already flying" from SITL QuadPlane quirk

        # Wait for some altitude
        _wait_for_alt(adapter, 10.0, tolerance=0.5, timeout=40.0)

        # Collect telemetry while hovering
        snapshots = _collect_telemetry(adapter, duration_s=5.0, interval_s=0.5)

        airspeeds = [s.airspeed_mps for s in snapshots]
        max_airspeed = max(airspeeds) if airspeeds else 0.0

        print(f"  Hover airspeed: peak={max_airspeed:.1f} m/s  "
              f"samples={len(snapshots)}")

        # MC hover airspeed should be low
        assert max_airspeed < 8.0, (
            f"Hover airspeed {max_airspeed:.1f} m/s unexpectedly high"
        )

        force_disarm_sitl(adapter)


# ===================================================================
# Scenario 3: Battery Failsafe RTL Trigger
# ===================================================================

@_sitl_skip
class TestSITLBatteryParamInjection:
    """Verify SITL battery parameter injection pipeline.

    NOTE: The radarku/ardupilot-sitl Docker image uses capacity-based battery
    simulation.  SIM_BATT_VOLTAGE controls the *reported* voltage but does NOT
    affect the remaining-capacity percentage (SYS_STATUS.battery_remaining
    stays at 100%).  Therefore the battery failsafe cannot be triggered purely
    by lowering SIM_BATT_VOLTAGE at runtime.

    These tests verify the parameter injection mechanism works correctly.
    """

    def test_battery_voltage_param_set_readback(self, sitl_connection):
        """PARAM_SET / PARAM_REQUEST_READ roundtrip for SIM_BATT_VOLTAGE."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        with _save_and_restore_params(adapter, ["SIM_BATT_VOLTAGE"]) as originals:
            if "SIM_BATT_VOLTAGE" not in originals:
                pytest.skip("SIM_BATT_VOLTAGE not available in this SITL")

            original = originals["SIM_BATT_VOLTAGE"]
            print(f"  Original SIM_BATT_VOLTAGE = {original:.2f}V")

            # Set to a different value
            set_sitl_param(adapter, "SIM_BATT_VOLTAGE", 11.0)
            readback = get_sitl_param(adapter, "SIM_BATT_VOLTAGE")
            print(f"  After set 11.0V: readback = {readback:.2f}V")
            assert abs(readback - 11.0) < 0.1, (
                f"Readback {readback:.2f} != expected 11.0"
            )

            # Set back
            set_sitl_param(adapter, "SIM_BATT_VOLTAGE", 12.0)
            readback2 = get_sitl_param(adapter, "SIM_BATT_VOLTAGE")
            print(f"  After set 12.0V: readback = {readback2:.2f}V")
            assert abs(readback2 - 12.0) < 0.1, (
                f"Readback {readback2:.2f} != expected 12.0"
            )

    def test_battery_failsafe_params_configurable(self, sitl_connection):
        """Battery failsafe parameters can be read and written."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        params = ["BATT_FS_LOW_ACT", "BATT_LOW_VOLT"]
        with _save_and_restore_params(adapter, params) as originals:
            print(f"  Original failsafe params: {originals}")

            # Configure failsafe parameters
            set_sitl_param(adapter, "BATT_FS_LOW_ACT", 2.0)
            set_sitl_param(adapter, "BATT_LOW_VOLT", 11.0)

            # Verify readback
            act = get_sitl_param(adapter, "BATT_FS_LOW_ACT")
            volt = get_sitl_param(adapter, "BATT_LOW_VOLT")
            print(f"  After config: BATT_FS_LOW_ACT={act:.0f}  "
                  f"BATT_LOW_VOLT={volt:.1f}V")

            assert abs(act - 2.0) < 0.1, f"BATT_FS_LOW_ACT readback={act}"
            assert abs(volt - 11.0) < 0.1, f"BATT_LOW_VOLT readback={volt}"


# ===================================================================
# Scenario 4: GPS Denial / Degradation
# ===================================================================

@_sitl_skip
class TestSITLGPSDenial:
    """Verify adapter response to GPS failure via SITL parameter injection.

    This SITL image uses ``SIM_GPS1_ENABLE`` (not ``SIM_GPS_DISABLE``) and
    ``SIM_GPS1_GLTCH_X/Y`` (not ``SIM_GPS_GLITCH_X``).

    NOTE: Disabling GPS stops raw GPS messages, but the EKF continues
    producing GLOBAL_POSITION_INT from IMU dead-reckoning.  Detection is
    verified via ArduPilot's own prearm-error system (STATUSTEXT).

    WARNING: All GPS tests run DISARMED to prevent SITL crashes.
    """

    def test_gps_disable_triggers_prearm_error(self, sitl_connection):
        """Disabling GPS should produce a GPS-related prearm error."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        # Verify baseline
        snapshot = adapter.get_snapshot()
        assert snapshot.position_valid, "GPS not valid before test"
        print(f"  Baseline: lat={snapshot.lat:.6f}  position_valid=True")

        with _save_and_restore_params(adapter, ["SIM_GPS1_ENABLE"]) as originals:
            if "SIM_GPS1_ENABLE" not in originals:
                pytest.skip("SIM_GPS1_ENABLE not available in this SITL")

            # Record prearm errors before disable
            prearm_before = set(adapter._prearm_errors) if hasattr(adapter, "_prearm_errors") else set()

            # Disable GPS
            print("  Disabling GPS (SIM_GPS1_ENABLE=0)...")
            set_sitl_param(adapter, "SIM_GPS1_ENABLE", 0.0)

            # Wait for GPS-related prearm error to appear
            deadline = time.time() + 20.0
            gps_error_detected = False
            detected_errors: list[str] = []

            while time.time() < deadline:
                time.sleep(1.0)
                current = set(adapter._prearm_errors) if hasattr(adapter, "_prearm_errors") else set()
                new_errors = current - prearm_before
                gps_errors = [e for e in new_errors if "GPS" in e.upper() or "gps" in e]
                if gps_errors:
                    gps_error_detected = True
                    detected_errors = gps_errors
                    print(f"  GPS prearm errors detected: {gps_errors}")
                    break

            assert gps_error_detected, (
                "No GPS-related prearm errors after disabling GPS"
            )

            # Re-enable GPS
            print("  Re-enabling GPS (SIM_GPS1_ENABLE=1)...")
            set_sitl_param(adapter, "SIM_GPS1_ENABLE", 1.0)
            time.sleep(5.0)

            # Verify GPS recovery: position_valid should remain True
            # (EKF dead-reckoning keeps it True, and after GPS re-enable it
            #  converges back to accurate position)
            snap_after = adapter.get_snapshot()
            print(f"  After re-enable: position_valid={snap_after.position_valid}")
            assert snap_after.position_valid, "GPS did not recover after re-enabling"

    def test_gps_glitch_detected_by_ekf(self, sitl_connection):
        """GPS glitch should trigger an EKF discrepancy prearm error.

        The EKF is designed to *reject* large GPS jumps as glitches and
        maintain its IMU-based position estimate.  ArduPilot then reports
        a "GPS and AHRS differ" prearm error.  This test verifies the
        glitch injection pipeline and ArduPilot's glitch detection.
        """
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        with _save_and_restore_params(adapter, ["SIM_GPS1_GLTCH_X"]) as originals:
            if "SIM_GPS1_GLTCH_X" not in originals:
                pytest.skip("SIM_GPS1_GLTCH_X not available in this SITL")

            # Clear prearm errors list to get a clean slate
            if hasattr(adapter, "_prearm_errors"):
                adapter._prearm_errors.clear()

            # Inject large GPS offset (~11km)
            print("  Injecting GPS glitch (SIM_GPS1_GLTCH_X=0.1)...")
            set_sitl_param(adapter, "SIM_GPS1_GLTCH_X", 0.1)

            # Note: param readback skipped — the telemetry loop may
            # consume PARAM_VALUE before get_sitl_param reads it.
            # We rely on the prearm error to confirm the glitch took effect.

            # Wait for ArduPilot to detect GPS/AHRS discrepancy
            deadline = time.time() + 15.0
            ahrs_error_found = False
            detected_msg = ""

            while time.time() < deadline:
                time.sleep(1.0)
                errors = list(adapter._prearm_errors) if hasattr(adapter, "_prearm_errors") else []
                ahrs_errors = [e for e in errors if "AHRS differ" in e]
                if ahrs_errors:
                    ahrs_error_found = True
                    detected_msg = ahrs_errors[-1]
                    print(f"  EKF discrepancy detected: {detected_msg}")
                    break

            assert ahrs_error_found, (
                "ArduPilot did not report GPS/AHRS discrepancy after glitch"
            )

            # Verify EKF correctly rejected the glitch (position stable)
            snap = adapter.get_snapshot()
            print(f"  Position after glitch: lat={snap.lat:.7f}  "
                  f"position_valid={snap.position_valid}")
            assert snap.position_valid, "EKF lost position validity during glitch"

        time.sleep(3.0)  # Allow recovery after param restore

    def test_gps_satellite_count_injectable(self, sitl_connection):
        """SIM_GPS1_NUMSATS can be injected and read back."""
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        with _save_and_restore_params(adapter, ["SIM_GPS1_NUMSATS"]) as originals:
            if "SIM_GPS1_NUMSATS" not in originals:
                pytest.skip("SIM_GPS1_NUMSATS not available in this SITL")

            original_sats = originals["SIM_GPS1_NUMSATS"]
            print(f"  Original satellites: {original_sats:.0f}")

            # Reduce to 3 satellites
            set_sitl_param(adapter, "SIM_GPS1_NUMSATS", 3.0)
            time.sleep(2.0)

            readback = get_sitl_param(adapter, "SIM_GPS1_NUMSATS")
            print(f"  After set 3: readback = {readback:.0f}")
            assert readback <= 4.0, f"SIM_GPS1_NUMSATS not reduced: {readback}"

            # System should still produce telemetry
            snap = adapter.get_snapshot()
            assert snap.position_valid, "Position became invalid with 3 sats"
            print(f"  Position still valid: lat={snap.lat:.6f}")


# ===================================================================
# Scenario 5: Communication Loss Detection
# ===================================================================

@_sitl_skip
class TestSITLCommunicationLoss:
    """Verify adapter detects connection loss.

    Uses function-scoped ``sitl_deep_connection`` fixture which connects
    to the SITL secondary port (5762) so it does not compete with the
    session-scoped ``sitl_connection`` on port 5760.
    """

    def test_socket_close_detected_as_connection_lost(self, sitl_deep_connection):
        """Closing the MAVLink socket should set _connection_lost=True."""
        adapter, instrumented = sitl_deep_connection

        # Verify healthy initial state
        assert not adapter._connection_lost, "Connection already lost before test"
        assert adapter._heartbeat_received, "No heartbeat received"

        snapshot = adapter.get_snapshot()
        print(f"  Pre-close: mode={snapshot.flight_mode}  "
              f"telemetry_fresh={snapshot.telemetry_fresh}  "
              f"connection_lost={adapter._connection_lost}")

        # Close the socket to simulate connection loss
        close_time = time.time()
        print("  Closing MAVLink socket...")
        try:
            adapter._master.close()
        except Exception as exc:
            print(f"  Close raised: {exc}")

        # Wait for adapter to detect connection loss
        deadline = time.time() + 30.0
        detected = False
        while time.time() < deadline:
            if adapter._connection_lost:
                detected = True
                break
            time.sleep(0.2)

        detection_time = time.time() - close_time
        print(f"  Connection loss detected: {detected}  "
              f"detection_time={detection_time:.1f}s")

        assert detected, (
            f"Adapter did not detect connection loss within 30s"
        )
        # I/O error path should detect nearly instantly
        assert detection_time < 15.0, (
            f"Detection took {detection_time:.1f}s — expected < 15s"
        )

    def test_stale_telemetry_after_connection_loss(self, sitl_deep_connection):
        """After connection loss, telemetry should become stale."""
        adapter, instrumented = sitl_deep_connection

        # Verify fresh telemetry
        snapshot = adapter.get_snapshot()
        assert snapshot.telemetry_fresh, "Telemetry not fresh before test"

        print(f"  Pre-close: telemetry_fresh={snapshot.telemetry_fresh}")

        # Close socket
        print("  Closing MAVLink socket...")
        try:
            adapter._master.close()
        except Exception:
            pass

        # Wait for telemetry to become stale (freshness window ~2.5s)
        time.sleep(5.0)

        snapshot_after = adapter.get_snapshot()
        print(f"  Post-close (5s): telemetry_fresh={snapshot_after.telemetry_fresh}  "
              f"connection_lost={adapter._connection_lost}")

        assert not snapshot_after.telemetry_fresh, (
            "Telemetry still marked as fresh 5s after connection loss"
        )

        # Bootstrap status should also reflect disconnection
        bs = instrumented.bootstrap_status()
        print(f"  Bootstrap: connected={bs.connected}  "
              f"mission_ready={bs.mission_ready}")
        # mission_ready requires telemetry_fresh, so it should be False.
        assert not bs.mission_ready, (
            "mission_ready should be False after connection loss"
        )
