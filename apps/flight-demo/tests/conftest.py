"""Shared fixtures for flight-demo test suite.

Provides pre-configured profiles and adapters for VTOL, quadcopter,
and fault-injected scenarios.  Also provides a session-scoped SITL
adapter when ARRAKIS_TEST_REAL_ARDUPILOT=1.
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import suppress
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
    deadline = time.time() + 20.0
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if not snapshot.armed and snapshot.alt_m <= 1.0:
            break
        time.sleep(0.5)
    with suppress(Exception):
        pre_arm_mode = "QLOITER" if getattr(getattr(adapter, "_profile", None), "is_vtol", False) else "LOITER"
        adapter._set_mode(pre_arm_mode)
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


def set_sitl_param(adapter, param_name: str, param_value: float,
                   param_type: int = 9) -> None:
    """Set a SITL simulation parameter via MAVLink PARAM_SET.

    Uses MAV_PARAM_TYPE_REAL32 (type=9) by default.
    Sleeps 0.5s after sending to allow parameter propagation.
    """
    with adapter._io_lock:
        adapter._require_master().mav.param_set_send(
            adapter._target_system,
            adapter._target_component,
            param_name.encode("utf-8"),
            param_value,
            param_type,
        )
    time.sleep(0.5)


def get_sitl_param(adapter, param_name: str,
                   timeout: float = 5.0) -> float:
    """Read a SITL parameter value via MAVLink PARAM_REQUEST_READ.

    Returns the float value, or raises TimeoutError if not received.
    """
    with adapter._io_lock:
        adapter._require_master().mav.param_request_read_send(
            adapter._target_system,
            adapter._target_component,
            param_name.encode("utf-8"),
            -1,
        )
    deadline = time.time() + timeout
    while time.time() < deadline:
        with adapter._io_lock:
            msg = adapter._require_master().recv_match(
                type="PARAM_VALUE", blocking=True, timeout=0.5,
            )
        if msg is not None and msg.param_id.rstrip("\x00") == param_name:
            return float(msg.param_value)
    raise TimeoutError(
        f"PARAM_VALUE for {param_name} not received within {timeout}s"
    )


# ---------------------------------------------------------------------------
# SITL stabilization helpers
# ---------------------------------------------------------------------------

def _wait_for_ground_state(adapter, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = adapter.get_snapshot()
        if not snapshot.armed and snapshot.alt_m <= 1.0 and snapshot.groundspeed_mps <= 1.5:
            return True
        time.sleep(0.5)
    return False


def _clear_sitl_fence(adapter) -> None:
    try:
        adapter._send_command_with_retry(
            adapter._mavutil.mavlink.MAV_CMD_DO_FENCE_ENABLE,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "fence disable",
        )
    except Exception:
        pass
    try:
        set_sitl_param(adapter, "FENCE_TOTAL", 0.0)
    except Exception:
        pass


def _sync_home_to_current(adapter, timeout: float = 15.0) -> bool:
    snapshot = adapter.get_snapshot()
    if not snapshot.position_valid:
        return False
    if not hasattr(adapter, "set_home_to_current"):
        return False
    try:
        adapter.set_home_to_current(timeout=timeout)
    except Exception:
        return False
    return True


def _stabilize_sitl_vehicle(adapter, *, reset_home: bool) -> None:
    try:
        force_disarm_sitl(adapter)
    except Exception:
        return
    _wait_for_ground_state(adapter, timeout=45.0)
    with suppress(Exception):
        adapter.reset()
    with suppress(Exception):
        pre_arm_mode = "QLOITER" if getattr(getattr(adapter, "_profile", None), "is_vtol", False) else "LOITER"
        adapter._set_mode(pre_arm_mode)
    _clear_sitl_fence(adapter)
    with suppress(Exception):
        set_sitl_param(adapter, "SIM_RC_FAIL", 0.0)
    if reset_home:
        _sync_home_to_current(adapter, timeout=15.0)
    time.sleep(1.0)


def _wait_for_bootstrap_ready(adapter, instrumented, timeout: float = 180.0):
    deadline = time.time() + timeout
    next_home_sync_at = 0.0
    while time.time() < deadline:
        bs = instrumented.bootstrap_status()
        if bs.mission_ready:
            return bs
        now = time.time()
        if bs.position_ready and not bs.home_ready and now >= next_home_sync_at:
            _sync_home_to_current(adapter, timeout=8.0)
            next_home_sync_at = now + 2.0
        time.sleep(1.0)
    return instrumented.bootstrap_status()


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
    bs = _wait_for_bootstrap_ready(adapter, instrumented, timeout=180.0)
    print(f"\n[SITL fixture] mission_ready={bs.mission_ready}")

    # Fresh SITL with -w (param wipe) needs ARMING_CHECK=0
    # to bypass "3D Accel calibration needed" prearm error.
    try:
        set_sitl_param(adapter, "ARMING_CHECK", 0)
    except Exception:
        pass
    time.sleep(10.0)

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


@pytest.fixture(scope="function")
def sitl_deep_connection():
    """Function-scoped SITL adapter for destructive tests.

    Creates a fresh ArduPilotAdapter + InstrumentedFlightAdapter on each
    test invocation, connecting to the SITL **secondary** port (5762) so
    it does not compete with the session-scoped fixture on port 5760.
    Used for tests that deliberately break the connection (e.g. comm-loss).
    """
    if os.getenv("ARRAKIS_TEST_REAL_ARDUPILOT") != "1":
        pytest.skip("SITL tests require ARRAKIS_TEST_REAL_ARDUPILOT=1")

    from flight_adapters.ardupilot import ArduPilotAdapter
    from flight_adapters.instrumented import InstrumentedFlightAdapter

    # Derive secondary port from primary connection string
    primary = os.getenv("ARRAKIS_ARDUPILOT_CONNECTION", "tcp:127.0.0.1:5760")
    secondary = primary.replace(":5760", ":5762")

    adapter = ArduPilotAdapter(AirframeProfile())
    adapter._connection = secondary  # Override to secondary port
    instrumented = InstrumentedFlightAdapter(adapter, logger_name="test.sitl.deep")
    instrumented.connect()
    _wait_for_bootstrap_ready(adapter, instrumented, timeout=120.0)

    yield adapter, instrumented

    # Teardown: stop threads and close socket (connection may already be broken)
    try:
        force_disarm_sitl(adapter)
    except Exception:
        pass
    try:
        adapter._running = False
    except Exception:
        pass
    try:
        if adapter._master is not None:
            adapter._master.close()
    except Exception:
        pass
    time.sleep(1.0)


@pytest.fixture(autouse=True)
def _ensure_disarmed_after_sitl_test(request):
    """Ensure vehicle is disarmed and on ground after each SITL flight test.

    Activates for tests that use sitl_connection or sitl_deep_connection.
    Runs force_disarm + waits for ground contact after each test to
    leave vehicle in a clean state for the next test.
    """
    adapter = None
    if "sitl_connection" in request.fixturenames:
        adapter, _ = request.getfixturevalue("sitl_connection")
    elif "sitl_deep_connection" in request.fixturenames:
        adapter, _ = request.getfixturevalue("sitl_deep_connection")
    if adapter is not None:
        _stabilize_sitl_vehicle(adapter, reset_home=True)
    yield
    # Only act on tests that actually use a SITL connection
    if ("sitl_connection" not in request.fixturenames
            and "sitl_deep_connection" not in request.fixturenames):
        return
    try:
        # Try session-scoped first, then function-scoped
        if adapter is None:
            return
        _stabilize_sitl_vehicle(adapter, reset_home=False)
    except Exception:
        pass
