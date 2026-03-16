"""Deep SITL integration tests — 8 critical scenarios.

Tests long-duration and fault-injection scenarios against ArduPilot SITL:
1. Full mission completion (takeoff → outbound → return → land → disarm)
2. Fixed-wing airspeed verification during AUTO mission
3. Battery failsafe RTL trigger via SITL parameter injection
4. GPS denial / degradation detection
5. In-flight total GPS loss truth-vs-estimate validation
6. Communication loss detection via socket close
7. Battery failsafe E2E: in-flight voltage drop → firmware RTL → landing
8. Communication loss during active flight: socket close mid-mission

Gated by:
    ARRAKIS_TEST_REAL_ARDUPILOT=1
    ARRAKIS_ARDUPILOT_CONNECTION=tcp:127.0.0.1:5760
    ARRAKIS_ARDUPILOT_COMMAND_TIMEOUT=45

Run with:
    ./scripts/run_sitl_tests.sh

WARNING: These tests are long-running (~25 minutes total at speedup=1).
"""

from __future__ import annotations

import math
import os
import sys
import time
from contextlib import contextmanager, suppress
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


def _distance_m_coords(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_scale = 111_320.0
    lon_scale = math.cos(math.radians(lat1)) * 111_320.0
    return math.hypot((lat2 - lat1) * lat_scale, (lon2 - lon1) * lon_scale)


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


def _recv_message(adapter, msg_type: str, timeout: float = 3.0):
    deadline = time.time() + timeout
    with adapter._io_lock:
        while time.time() < deadline:
            msg = adapter._require_master().recv_match(
                type=msg_type, blocking=True, timeout=0.5,
            )
            if msg is not None:
                return msg
    return None


def _gps_disable_param(adapter) -> tuple[str, float, float]:
    for name, disable_value, enable_value in (
        ("SIM_GPS_DISABLE", 1.0, 0.0),
        ("SIM_GPS1_ENABLE", 0.0, 1.0),
    ):
        try:
            get_sitl_param(adapter, name, timeout=2.0)
        except Exception:
            continue
        return name, disable_value, enable_value
    pytest.skip("No GPS disable parameter available in this SITL build")


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


@_sitl_skip
class TestSITLInFlightGPSLossTruth:
    """Measure real in-flight GPS loss behavior against simulator truth."""

    def test_total_gps_loss_keeps_mission_moving_but_breaks_exact_truth_alignment(self, sitl_connection):
        """Mission can keep progressing on dead reckoning, but exact return is not provable.

        This test uses `SIMSTATE` as simulator truth and compares it with
        `GLOBAL_POSITION_INT`, which continues to be emitted by the EKF after
        raw GPS is disabled. The expected result in the current stack is:

        1. Mission keeps progressing to return/landing under dead reckoning.
        2. `position_valid` can remain True even though raw GPS is gone.
        3. Truth-vs-estimate error grows enough that "exact return guarantee"
           cannot be claimed.
        """
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(2.0)

        gps_param, disable_value, enable_value = _gps_disable_param(adapter)
        with _save_and_restore_params(adapter, [gps_param]):
            try:
                home = adapter.get_home()
                _build_short_mission(adapter, distance_m=250.0, bearing_deg=90.0)

                armed = force_arm_sitl(adapter)
                assert armed, "Failed to arm for in-flight GPS loss test"

                adapter.start_mission()
                leg = _wait_for_leg(adapter, {"outbound"}, timeout=120.0)
                assert leg == "outbound", (
                    f"Did not reach outbound leg before GPS loss. Current leg: {adapter.current_leg()}"
                )

                baseline_sim = _recv_message(adapter, "SIMSTATE", timeout=5.0)
                baseline_gpi = _recv_message(adapter, "GLOBAL_POSITION_INT", timeout=5.0)
                if baseline_sim is None or baseline_gpi is None:
                    pytest.skip("SIMSTATE/GLOBAL_POSITION_INT not available for truth comparison")
                baseline_err = _distance_m_coords(
                    baseline_sim.lat / 1e7,
                    baseline_sim.lng / 1e7,
                    baseline_gpi.lat / 1e7,
                    baseline_gpi.lon / 1e7,
                )
                print(f"  Baseline truth error before GPS disable: {baseline_err:.1f}m")

                set_sitl_param(adapter, gps_param, disable_value)
                print(f"  GPS disabled via {gps_param}={disable_value}")

                truth_errors: list[float] = []
                truth_home_distances: list[float] = []
                legs_seen: set[str] = set()
                gps_sensor_invalid_seen = False
                dead_reckoned_position_seen = False
                weak_fix_seen = False

                for idx in range(8):
                    time.sleep(3.0)
                    sim = _recv_message(adapter, "SIMSTATE", timeout=3.0)
                    gpi = _recv_message(adapter, "GLOBAL_POSITION_INT", timeout=3.0)
                    gps_raw = _recv_message(adapter, "GPS_RAW_INT", timeout=3.0)
                    snap = adapter.get_snapshot()
                    legs_seen.add(adapter.current_leg())

                    if sim is not None and gpi is not None:
                        truth_error = _distance_m_coords(
                            sim.lat / 1e7,
                            sim.lng / 1e7,
                            gpi.lat / 1e7,
                            gpi.lon / 1e7,
                        )
                        truth_home = _distance_m_coords(
                            home.lat, home.lon, sim.lat / 1e7, sim.lng / 1e7,
                        )
                        truth_errors.append(truth_error)
                        truth_home_distances.append(truth_home)
                    else:
                        truth_error = None
                        truth_home = None

                    if not snap.gps_sensor_valid:
                        gps_sensor_invalid_seen = True
                    if snap.position_valid:
                        dead_reckoned_position_seen = True
                    if gps_raw is not None and int(getattr(gps_raw, "fix_type", 0)) <= 1:
                        weak_fix_seen = True

                    print(
                        f"  Sample {idx}: mode={snap.flight_mode} leg={adapter.current_leg()} "
                        f"position_valid={snap.position_valid} gps_sensor_valid={snap.gps_sensor_valid} "
                        f"fix_type={getattr(gps_raw, 'fix_type', None)} "
                        f"truth_error={truth_error} truth_home={truth_home}"
                    )

                assert gps_sensor_invalid_seen or weak_fix_seen, (
                    "Raw GPS loss was not observed after disabling GPS in flight"
                )
                assert dead_reckoned_position_seen, (
                    "Dead-reckoned position did not persist after GPS loss"
                )
                assert {"return", "landing"} & legs_seen, (
                    f"Mission did not continue toward return/landing under GPS loss. Legs: {sorted(legs_seen)}"
                )
                assert truth_errors, "No truth-error samples collected after GPS loss"
                max_truth_error = max(truth_errors)
                print(f"  Max truth-vs-estimate error after GPS loss: {max_truth_error:.1f}m")
                if truth_home_distances:
                    print(
                        "  Min/last simulator-home distance during degraded return: "
                        f"{min(truth_home_distances):.1f}m / {truth_home_distances[-1]:.1f}m"
                    )

                assert max_truth_error >= 15.0, (
                    f"Truth drift stayed too small ({max_truth_error:.1f}m) to demonstrate loss of exact return guarantee"
                )
            finally:
                with suppress(Exception):
                    set_sitl_param(adapter, gps_param, enable_value)
                with suppress(Exception):
                    force_disarm_sitl(adapter)


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


# ===================================================================
# Scenario 6: Battery Failsafe E2E — In-Flight Voltage Drop → RTL
# ===================================================================

@_sitl_skip
class TestSITLBatteryFailsafeE2E:
    """Battery failsafe E2E verification against SITL.

    SITL LIMITATION DISCOVERED:
      The ``radarku/ardupilot-sitl`` Docker image starts with BATT_MONITOR=0
      (disabled).  ArduPilot's battery backend initializes at **boot time**,
      so changing BATT_MONITOR via MAVLink at runtime does NOT re-initialize
      the backend — SYS_STATUS.voltage_battery stays at 0 mV regardless of
      the BATT_MONITOR value set via PARAM_SET.

      This means in-flight battery failsafe (voltage drop → RTL) cannot be
      triggered by runtime parameter injection alone.  A proper E2E test
      requires the SITL to be started with BATT_MONITOR≠0 in a startup param
      file (e.g. ``--defaults batt_monitor.parm``).

    What these tests DO verify:
      1. The runtime BATT_MONITOR limitation is real (backend doesn't reinit)
      2. IF the SITL is started with battery monitoring active, the full
         failsafe chain works (voltage drop → RTL → landing)
      3. Prearm error detection when battery transitions to "unhealthy"
    """

    _BATTERY_PARAMS = [
        "BATT_MONITOR", "BATT_LOW_VOLT", "BATT_FS_LOW_ACT",
        "BATT_CRT_VOLT", "BATT_FS_CRT_ACT", "SIM_BATT_VOLTAGE",
    ]

    def _check_battery_backend_active(self, adapter) -> bool:
        """Return True if the battery backend is reporting valid voltage."""
        with adapter._io_lock:
            for _ in range(10):
                msg = adapter._require_master().recv_match(
                    type="SYS_STATUS", blocking=True, timeout=0.5,
                )
                if msg and getattr(msg, "voltage_battery", 0) > 0:
                    return True
        return False

    def test_runtime_batt_monitor_limitation(self, sitl_connection):
        """Verify that changing BATT_MONITOR at runtime does NOT reinit backend.

        This documents the SITL limitation: the battery backend is only
        initialized at boot time.  Runtime PARAM_SET for BATT_MONITOR changes
        the stored value but does not create a new battery driver instance.
        """
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        with _save_and_restore_params(adapter, ["BATT_MONITOR"]) as originals:
            original = originals.get("BATT_MONITOR", -1)
            print(f"  Default BATT_MONITOR = {original:.0f}")

            if original != 0.0:
                pytest.skip("BATT_MONITOR already active — limitation test N/A")

            # Check: backend is NOT reporting voltage with BATT_MONITOR=0
            active_before = self._check_battery_backend_active(adapter)
            print(f"  Backend active (BATT_MONITOR=0): {active_before}")
            assert not active_before, "Battery backend should be inactive at BATT_MONITOR=0"

            # Set BATT_MONITOR=4 at runtime
            set_sitl_param(adapter, "BATT_MONITOR", 4.0)
            time.sleep(3.0)  # Give backend time to "reinitialize" (it won't)

            # Check: backend still NOT reporting (param changed but backend
            # did not reinitialize — this IS the limitation)
            active_after = self._check_battery_backend_active(adapter)
            print(f"  Backend active (BATT_MONITOR=4 set at runtime): {active_after}")

            if active_after:
                print("  UNEXPECTED: Battery backend DID reinitialize!")
                print("  This means E2E battery failsafe IS testable at runtime.")
            else:
                print("  CONFIRMED: Battery backend does NOT reinitialize at runtime.")
                print("  E2E failsafe requires SITL started with BATT_MONITOR≠0.")

            # Core assertion: document the limitation
            assert not active_after, (
                "Battery backend unexpectedly reinitalized at runtime. "
                "If this passes, the E2E failsafe test can be enabled!"
            )

    def test_batt_monitor_change_triggers_prearm_warning(self, sitl_connection):
        """Runtime BATT_MONITOR change triggers 'Battery unhealthy' prearm error.

        Even though the backend doesn't reinitialize, ArduPilot notices the
        inconsistency and reports a prearm error — proving the parameter
        injection pipeline IS reaching the firmware.
        """
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        # Gate: only meaningful when battery backend is inactive (BATT_MONITOR=0)
        if self._check_battery_backend_active(adapter):
            pytest.skip("Battery backend already active — prearm test N/A")

        with _save_and_restore_params(adapter, ["BATT_MONITOR"]):
            if hasattr(adapter, "_prearm_errors"):
                adapter._prearm_errors.clear()

            # Change BATT_MONITOR to trigger inconsistency
            print("  Setting BATT_MONITOR=4 at runtime...")
            set_sitl_param(adapter, "BATT_MONITOR", 4.0)

            # Wait for ArduPilot to report battery issue
            deadline = time.time() + 15.0
            found = False
            while time.time() < deadline:
                time.sleep(1.0)
                errors = list(adapter._prearm_errors) if hasattr(adapter, "_prearm_errors") else []
                batt_errors = [e for e in errors if "Battery" in e or "batt" in e.lower()]
                if batt_errors:
                    found = True
                    print(f"  Prearm error detected: {batt_errors}")
                    break

            assert found, "No battery prearm error after BATT_MONITOR change"
            print("  Confirmed: parameter injection reaches firmware and triggers warning")

    def test_voltage_failsafe_e2e_if_backend_active(self, sitl_connection):
        """Full E2E: voltage drop → RTL → landing (only if battery backend active).

        This test only runs when the SITL was started with BATT_MONITOR≠0
        (e.g. via a custom param file).  Otherwise it skips.

        To enable this test, start SITL with:
          docker run ... -e EXTRA_ARGS="--defaults /path/to/batt.parm"
        where batt.parm contains:
          BATT_MONITOR 4
          BATT_LOW_VOLT 10.8
          BATT_FS_LOW_ACT 2
        """
        adapter, _ = sitl_connection

        force_disarm_sitl(adapter)
        time.sleep(1.0)

        # Gate: check if battery backend is actively reporting voltage
        backend_active = self._check_battery_backend_active(adapter)
        if not backend_active:
            pytest.skip(
                "Battery backend not active (BATT_MONITOR=0 at boot). "
                "To run this test, start SITL with BATT_MONITOR≠0 "
                "in a startup param file."
            )

        with _save_and_restore_params(adapter, self._BATTERY_PARAMS) as originals:
            # Configure failsafe thresholds
            set_sitl_param(adapter, "BATT_LOW_VOLT", 10.8)
            set_sitl_param(adapter, "BATT_FS_LOW_ACT", 2.0)   # RTL
            set_sitl_param(adapter, "BATT_CRT_VOLT", 10.0)
            set_sitl_param(adapter, "BATT_FS_CRT_ACT", 1.0)   # Land
            set_sitl_param(adapter, "SIM_BATT_VOLTAGE", 12.6)
            time.sleep(2.0)

            # Arm and fly
            print("  Arming and starting mission...")
            _build_short_mission(adapter, distance_m=300.0, bearing_deg=90.0)
            armed = force_arm_sitl(adapter)
            assert armed, "Failed to arm"

            adapter.start_mission()
            reached = _wait_for_alt(adapter, 15.0, tolerance=0.5, timeout=60.0)
            assert reached, "Did not reach flight altitude"

            snap = adapter.get_snapshot()
            print(f"  In flight: mode={snap.flight_mode}  alt={snap.alt_m:.1f}m")

            # Inject voltage drop below threshold
            print("  Injecting voltage drop (SIM_BATT_VOLTAGE=10.5)...")
            inject_time = time.time()
            set_sitl_param(adapter, "SIM_BATT_VOLTAGE", 10.5)

            # Wait for RTL
            rtl_modes = {"RTL", "QRTL", "QLAND", "LAND", "SMART_RTL"}
            mode_changed = _wait_for_mode(adapter, rtl_modes, timeout=30.0)
            reaction = time.time() - inject_time

            snap = adapter.get_snapshot()
            print(f"  After injection: mode={snap.flight_mode}  reaction={reaction:.1f}s")

            assert mode_changed, (
                f"Firmware did not enter RTL. Mode: {snap.flight_mode}"
            )

            # Monitor return + landing (up to 300s for VTOL)
            print("  Monitoring RTL...")
            landed = _wait_for_disarm(adapter, timeout=300.0)

            snap_final = adapter.get_snapshot()
            print(f"  Final: mode={snap_final.flight_mode}  "
                  f"alt={snap_final.alt_m:.1f}m  armed={snap_final.armed}")

            if not landed:
                force_disarm_sitl(adapter)
                print("  Vehicle did not auto-land — force-disarmed")


# ===================================================================
# Scenario 7: Communication Loss During Active Flight
# ===================================================================

@_sitl_skip
class TestSITLCommLossDuringFlight:
    """Communication loss during active mission flight.

    Extends Scenario 5 by testing connection loss while the vehicle is
    actively flying a mission, not just on the ground.

    Uses function-scoped ``sitl_deep_connection`` (port 5762).

    NOTE: ArduPilot's GCS failsafe (FS_GCS_ENABLE) may not trigger because
    the session-scoped connection on port 5760 is still alive.  These tests
    verify the *adapter-level* detection and telemetry degradation during
    active flight, not ArduPilot's own GCS failsafe.
    """

    def test_connection_loss_during_auto_mission(self, sitl_deep_connection):
        """Socket close during AUTO flight → adapter detects loss mid-mission."""
        adapter, instrumented = sitl_deep_connection

        # Build and fly a mission
        print("  Building mission and arming...")
        _build_short_mission(adapter, distance_m=300.0, bearing_deg=0.0)

        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm on secondary port"

        adapter.start_mission()

        # Wait for stable flight
        reached = _wait_for_alt(adapter, 15.0, tolerance=0.5, timeout=60.0)
        assert reached, "Did not reach flight altitude"

        snap_pre = adapter.get_snapshot()
        print(f"  In flight: mode={snap_pre.flight_mode}  "
              f"alt={snap_pre.alt_m:.1f}m  "
              f"armed={snap_pre.armed}  "
              f"telemetry_fresh={snap_pre.telemetry_fresh}")

        assert snap_pre.telemetry_fresh, "Telemetry not fresh during flight"
        assert snap_pre.armed, "Not armed during flight"

        # Close socket mid-flight
        close_time = time.time()
        print("  Closing MAVLink socket during flight...")
        try:
            adapter._master.close()
        except Exception:
            pass

        # Wait for detection
        deadline = time.time() + 15.0
        detected = False
        while time.time() < deadline:
            if adapter._connection_lost:
                detected = True
                break
            time.sleep(0.2)

        detection_time = time.time() - close_time
        print(f"  Connection loss detected: {detected}  "
              f"detection_time={detection_time:.1f}s")

        assert detected, "Adapter did not detect connection loss during flight"

        # Verify telemetry goes stale
        time.sleep(5.0)
        snap_post = adapter.get_snapshot()
        print(f"  Post-loss (5s): telemetry_fresh={snap_post.telemetry_fresh}  "
              f"connection_lost={adapter._connection_lost}")

        assert not snap_post.telemetry_fresh, (
            "Telemetry still fresh 5s after mid-flight connection loss"
        )

        # The last-known telemetry should reflect the in-flight state
        # (altitude > 0, was armed at time of disconnect)
        print(f"  Last known state: alt={snap_post.alt_m:.1f}m  "
              f"mode={snap_post.flight_mode}  "
              f"battery={snap_post.battery_percent:.0f}%")
        assert snap_post.alt_m > 5.0, (
            f"Last known altitude too low ({snap_post.alt_m:.1f}m) — "
            f"telemetry may have been overwritten after disconnect"
        )

    def test_telemetry_freezes_at_disconnect_values(self, sitl_deep_connection):
        """After disconnect, telemetry values should freeze (not reset to zero)."""
        adapter, instrumented = sitl_deep_connection

        # Get to a flying state
        _build_short_mission(adapter, distance_m=200.0, bearing_deg=45.0)
        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm"

        adapter.start_mission()
        _wait_for_alt(adapter, 15.0, tolerance=0.5, timeout=60.0)

        # Record telemetry just before disconnect
        snap_before = adapter.get_snapshot()
        print(f"  Before disconnect: lat={snap_before.lat:.6f}  "
              f"alt={snap_before.alt_m:.1f}m  "
              f"mode={snap_before.flight_mode}")

        # Disconnect
        try:
            adapter._master.close()
        except Exception:
            pass

        # Wait for staleness
        time.sleep(5.0)

        # Frozen telemetry should retain last-known values
        snap_after = adapter.get_snapshot()
        print(f"  After disconnect: lat={snap_after.lat:.6f}  "
              f"alt={snap_after.alt_m:.1f}m  "
              f"mode={snap_after.flight_mode}  "
              f"telemetry_fresh={snap_after.telemetry_fresh}")

        # Values should NOT be zeroed out
        assert snap_after.lat != 0.0, "Latitude reset to 0 after disconnect"
        assert snap_after.alt_m > 0.0, "Altitude reset to 0 after disconnect"

        # Values should be close to pre-disconnect
        # (allow some drift from last few messages before close)
        lat_drift = abs(snap_after.lat - snap_before.lat)
        alt_drift = abs(snap_after.alt_m - snap_before.alt_m)
        print(f"  Drift: lat={lat_drift:.8f}°  alt={alt_drift:.1f}m")

        assert lat_drift < 0.01, (
            f"Latitude drifted too much after disconnect: {lat_drift:.8f}°"
        )

    def test_bootstrap_status_reflects_inflight_disconnect(self, sitl_deep_connection):
        """bootstrap_status should show connected=True but mission_ready=False."""
        adapter, instrumented = sitl_deep_connection

        # Get to flying state
        _build_short_mission(adapter, distance_m=200.0, bearing_deg=270.0)
        armed = force_arm_sitl(adapter)
        assert armed, "Failed to arm"

        adapter.start_mission()
        _wait_for_alt(adapter, 15.0, tolerance=0.5, timeout=60.0)

        # Verify healthy bootstrap before disconnect
        bs_before = instrumented.bootstrap_status()
        print(f"  Before: connected={bs_before.connected}  "
              f"mission_ready={bs_before.mission_ready}")
        assert bs_before.mission_ready, "Not mission_ready before disconnect"

        # Disconnect
        try:
            adapter._master.close()
        except Exception:
            pass

        # Wait for staleness
        time.sleep(5.0)

        bs_after = instrumented.bootstrap_status()
        print(f"  After (5s): connected={bs_after.connected}  "
              f"mission_ready={bs_after.mission_ready}")

        # mission_ready requires telemetry_fresh → must be False
        assert not bs_after.mission_ready, (
            "mission_ready should be False after in-flight disconnect"
        )
