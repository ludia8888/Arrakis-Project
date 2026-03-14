"""Shared fixtures for flight-demo test suite.

Provides pre-configured profiles and adapters for VTOL, quadcopter,
and fault-injected scenarios.  Also provides a session-scoped SITL
adapter when ARRAKIS_TEST_REAL_ARDUPILOT=1.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile, load_profile
from flight_adapters.fault_injector import FaultProfile
from flight_adapters.mock import MockAdapter


@pytest.fixture
def vtol_profile() -> AirframeProfile:
    """Default VTOL profile."""
    return load_profile("default-vtol")


@pytest.fixture
def quad_profile() -> AirframeProfile:
    """Default quadcopter profile."""
    return load_profile("default-quadcopter")


@pytest.fixture
def mock_adapter(vtol_profile: AirframeProfile) -> MockAdapter:
    """MockAdapter with no fault injection (backward-compatible default)."""
    return MockAdapter(vtol_profile)


@pytest.fixture
def realistic_adapter(vtol_profile: AirframeProfile) -> MockAdapter:
    """MockAdapter with realistic outdoor fault profile."""
    return MockAdapter(vtol_profile, fault_profile=FaultProfile.realistic())


@pytest.fixture
def stress_adapter(vtol_profile: AirframeProfile) -> MockAdapter:
    """MockAdapter with extreme stress fault profile."""
    return MockAdapter(vtol_profile, fault_profile=FaultProfile.stress())


@pytest.fixture
def quad_mock_adapter(quad_profile: AirframeProfile) -> MockAdapter:
    """MockAdapter for quadcopter with no fault injection."""
    return MockAdapter(quad_profile)


@pytest.fixture
def quad_realistic_adapter(quad_profile: AirframeProfile) -> MockAdapter:
    """MockAdapter for quadcopter with realistic fault profile."""
    return MockAdapter(quad_profile, fault_profile=FaultProfile.realistic())


# ---------------------------------------------------------------------------
# SITL helper functions (shared across all SITL test files)
# ---------------------------------------------------------------------------

def force_arm_sitl(adapter) -> bool:
    """Force-arm via MAVLink (bypass prearm checks for SITL).

    Sends MAV_CMD_COMPONENT_ARM_DISARM with param2=21196.0 (force arm magic).
    Returns True if armed within 15s, False otherwise.
    """
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


def force_disarm_sitl(adapter) -> bool:
    """Force-disarm via MAVLink.

    Sends MAV_CMD_COMPONENT_ARM_DISARM with param1=0, param2=21196.0.
    Returns True if disarmed within 10s, False otherwise.
    """
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


# ---------------------------------------------------------------------------
# Session-scoped SITL adapter (shared across ALL SITL test files)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sitl_connection():
    """Session-scoped SITL adapter + instrumented wrapper.

    Yields (adapter, instrumented) tuple.
    Properly disconnects on teardown so the TCP port is released.

    Only created when ARRAKIS_TEST_REAL_ARDUPILOT=1.
    """
    if os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1":
        pytest.skip("SITL tests require ARRAKIS_TEST_REAL_ARDUPILOT=1")

    from flight_adapters.ardupilot import ArduPilotAdapter
    from flight_adapters.instrumented import InstrumentedFlightAdapter

    adapter = ArduPilotAdapter(AirframeProfile())
    instrumented = InstrumentedFlightAdapter(adapter, logger_name="test.sitl.session")
    instrumented.connect()

    # Wait for full bootstrap readiness (EKF convergence + GPS + home)
    deadline = time.time() + 90.0
    while time.time() < deadline:
        bs = instrumented.bootstrap_status()
        if bs.mission_ready:
            break
        time.sleep(1.0)

    yield adapter, instrumented

    # Teardown: ensure disarmed + release TCP connection
    try:
        force_disarm_sitl(adapter)
    except Exception:
        pass
    try:
        instrumented.reset()
    except Exception:
        pass
    time.sleep(1.0)


@pytest.fixture(autouse=True)
def _ensure_disarmed_after_sitl_test(request):
    """Ensure vehicle is disarmed and on ground after each SITL flight test.

    Only activates for tests that use the sitl_connection fixture.
    Runs force_disarm + waits for ground contact after each test to
    leave vehicle in a clean state for the next test.
    """
    yield
    # Only act on tests that actually use the SITL connection
    if "sitl_connection" not in request.fixturenames:
        return
    try:
        adapter, _ = request.getfixturevalue("sitl_connection")
        snapshot = adapter.get_snapshot()
        if snapshot.armed:
            force_disarm_sitl(adapter)
        # Wait for vehicle to reach ground (after force-disarm from flight)
        if snapshot.alt_m > 2.0:
            deadline = time.time() + 15.0
            while time.time() < deadline:
                s = adapter.get_snapshot()
                if s.alt_m <= 1.0:
                    break
                time.sleep(0.5)
        time.sleep(1.0)
    except Exception:
        pass
