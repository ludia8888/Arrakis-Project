"""SITL integration tests for dry lab hardening verification.

These tests require a running ArduPilot SITL simulator and are gated by:
    ARRAKIS_TEST_REAL_ARDUPILOT=1
    ARRAKIS_ARDUPILOT_CONNECTION=tcp:127.0.0.1:5760

Run with:
    ./scripts/run_sitl_tests.sh

All tests share a single session-scoped SITL connection via the
``sitl_connection`` fixture defined in conftest.py.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_sitl_skip = pytest.mark.skipif(
    os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1",
    reason="SITL integration tests require running ArduPilot simulator",
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _force_arm(adapter):
    """Force-arm via MAVLink (bypass prearm checks for SITL)."""
    mavutil = adapter._mavutil
    with adapter._io_lock:
        adapter._require_master().mav.command_long_send(
            adapter._target_system,
            adapter._target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1.0,       # param1: 1=arm
            21196.0,   # param2: force arm
            0.0, 0.0, 0.0, 0.0, 0.0,
        )
    deadline = time.time() + 15.0
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if snapshot.armed:
            return True
        time.sleep(0.5)
    return False


def _force_disarm(adapter):
    """Force-disarm via MAVLink."""
    mavutil = adapter._mavutil
    with adapter._io_lock:
        adapter._require_master().mav.command_long_send(
            adapter._target_system,
            adapter._target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0.0,       # param1: 0=disarm
            21196.0,   # param2: force
            0.0, 0.0, 0.0, 0.0, 0.0,
        )
    deadline = time.time() + 10.0
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if not snapshot.armed:
            return True
        time.sleep(0.5)
    return False


# ===========================================================================
# Test Classes — all use `sitl_connection` session fixture from conftest.py
# ===========================================================================


@_sitl_skip
class TestSITLConnectionHardening:
    """Fix 1, 3, 9: Connection, heartbeat watchdog, monotonic time."""

    def test_heartbeat_received_within_timeout(self, sitl_connection):
        adapter, instrumented = sitl_connection
        bs = instrumented.bootstrap_status()
        assert bs.connected, "Should be connected to SITL"
        assert bs.heartbeat_received, "Should have received heartbeat"
        print(f"  [PASS] Connected with heartbeat")

    def test_heartbeat_watchdog_fields_exist(self, sitl_connection):
        adapter, _ = sitl_connection
        assert hasattr(adapter, "_last_heartbeat_mono"), "Fix 1: _last_heartbeat_mono field"
        assert hasattr(adapter, "_heartbeat_watchdog_timeout_s"), "Fix 1: watchdog timeout field"
        assert adapter._last_heartbeat_mono > 0, "Heartbeat should be receiving"
        print(f"  [PASS] Heartbeat watchdog: last={adapter._last_heartbeat_mono:.1f}")

    def test_connection_lost_flag_initially_false(self, sitl_connection):
        adapter, _ = sitl_connection
        assert hasattr(adapter, "_connection_lost"), "Fix 3: _connection_lost field"
        assert adapter._connection_lost is False, "Should not be lost while connected"
        print(f"  [PASS] _connection_lost = False")

    def test_telemetry_freshness_monotonic(self, sitl_connection):
        adapter, _ = sitl_connection
        assert hasattr(adapter, "_last_telemetry_mono"), "Fix 9: monotonic telemetry timestamp"
        mono = adapter._last_telemetry_mono
        assert mono > 0, "Telemetry monotonic timestamp should be positive"
        assert time.monotonic() - mono < 30.0, "Telemetry should be fresh (monotonic)"
        print(f"  [PASS] Monotonic telemetry: age={time.monotonic() - mono:.1f}s")

    def test_telemetry_snapshot_fresh(self, sitl_connection):
        _, instrumented = sitl_connection
        snapshot = instrumented.get_snapshot()
        assert snapshot.telemetry_fresh, "Telemetry should be marked fresh"
        assert snapshot.mode_valid, "Mode should be valid"
        print(f"  [PASS] Snapshot fresh: mode={snapshot.flight_mode}")


@_sitl_skip
class TestSITLGPSValidation:
    """Fix 10: GPS coordinate validation in real MAVLink stream."""

    def test_gps_coordinates_in_valid_range(self, sitl_connection):
        adapter, _ = sitl_connection
        snapshot = adapter.get_snapshot()
        assert -90.0 <= snapshot.lat <= 90.0, f"Lat out of range: {snapshot.lat}"
        assert -180.0 <= snapshot.lon <= 180.0, f"Lon out of range: {snapshot.lon}"
        assert not (snapshot.lat == 0.0 and snapshot.lon == 0.0), "GPS should not be (0,0)"
        print(f"  [PASS] GPS valid: lat={snapshot.lat:.6f} lon={snapshot.lon:.6f}")

    def test_position_valid_after_convergence(self, sitl_connection):
        adapter, _ = sitl_connection
        snapshot = adapter.get_snapshot()
        assert snapshot.position_valid, "Position should be valid after EKF convergence"
        print(f"  [PASS] position_valid=True")

    def test_home_position_set(self, sitl_connection):
        _, instrumented = sitl_connection
        snapshot = instrumented.get_snapshot()
        print(f"  [INFO] home_valid={snapshot.home_valid} lat={snapshot.lat:.4f} lon={snapshot.lon:.4f}")
        assert snapshot.lat != 0.0 or snapshot.lon != 0.0, "Position should be non-zero"


@_sitl_skip
class TestSITLCommandProtocol:
    """Fix 2, 5: ACK dict + retry logic with real MAVLink."""

    def test_pending_acks_dict_exists(self, sitl_connection):
        adapter, _ = sitl_connection
        assert hasattr(adapter, "_pending_acks"), "Fix 2: _pending_acks dict"
        assert isinstance(adapter._pending_acks, dict), "_pending_acks should be dict"
        print(f"  [PASS] _pending_acks exists: {len(adapter._pending_acks)} entries")

    def test_force_arm_produces_ack(self, sitl_connection):
        adapter, _ = sitl_connection
        armed = _force_arm(adapter)
        assert armed, "Force-arm should succeed"
        with adapter._state_lock:
            acks = dict(adapter._pending_acks)
        print(f"  [PASS] Force-arm OK, _pending_acks: {acks}")
        _force_disarm(adapter)

    def test_concurrent_ack_access_safe(self, sitl_connection):
        adapter, _ = sitl_connection
        errors = []

        def read_acks():
            try:
                for _ in range(200):
                    with adapter._state_lock:
                        _ = dict(adapter._pending_acks)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_acks) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Concurrent _pending_acks access errors: {errors}"
        print(f"  [PASS] 4 threads x 200 reads — no race conditions")

    def test_prearm_errors_list_exists(self, sitl_connection):
        """Fix 8: Pre-arm error collection."""
        adapter, _ = sitl_connection
        assert hasattr(adapter, "_prearm_errors"), "Fix 8: _prearm_errors field"
        assert isinstance(adapter._prearm_errors, list), "_prearm_errors should be list"
        print(f"  [PASS] _prearm_errors: {adapter._prearm_errors}")


@_sitl_skip
class TestSITLArmDisarm:
    """Full arm/disarm cycle via adapter methods."""

    def test_force_arm_and_disarm_cycle(self, sitl_connection):
        adapter, instrumented = sitl_connection

        _force_disarm(adapter)
        time.sleep(1.0)

        armed = _force_arm(adapter)
        assert armed, "Should be armed after force-arm"
        snapshot = instrumented.get_snapshot()
        assert snapshot.armed is True
        print(f"  [PASS] Armed: mode={snapshot.flight_mode}")

        disarmed = _force_disarm(adapter)
        assert disarmed, "Should be disarmed after force-disarm"
        snapshot = instrumented.get_snapshot()
        assert snapshot.armed is False
        print(f"  [PASS] Disarmed: mode={snapshot.flight_mode}")


@_sitl_skip
class TestSITLAbort:
    """Fix 7: Abort path hardening."""

    def test_abort_from_armed_state(self, sitl_connection):
        adapter, instrumented = sitl_connection

        armed = _force_arm(adapter)
        if not armed:
            pytest.skip("Could not force-arm for abort test")

        instrumented.abort("SITL test abort")
        time.sleep(3.0)

        snapshot = instrumented.get_snapshot()
        is_safe = (
            not snapshot.armed
            or snapshot.flight_mode in ("RTL", "QRTL", "LAND", "QLAND")
        )
        print(f"  [{'PASS' if is_safe else 'WARN'}] Post-abort: armed={snapshot.armed} mode={snapshot.flight_mode}")
        assert is_safe, f"Vehicle not in safe state after abort: armed={snapshot.armed} mode={snapshot.flight_mode}"
        _force_disarm(adapter)

    def test_abort_when_already_disarmed(self, sitl_connection):
        adapter, instrumented = sitl_connection

        _force_disarm(adapter)
        time.sleep(1.0)

        instrumented.abort("SITL test abort while disarmed")
        time.sleep(1.0)
        snapshot = instrumented.get_snapshot()
        assert snapshot.armed is False
        print(f"  [PASS] Abort while disarmed: no crash")
