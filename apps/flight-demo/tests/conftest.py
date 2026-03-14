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

    # Wait for bootstrap readiness (EKF convergence)
    deadline = time.time() + 60.0
    while time.time() < deadline:
        bs = instrumented.bootstrap_status()
        if bs.connected and bs.heartbeat_received and bs.telemetry_fresh:
            break
        time.sleep(1.0)

    yield adapter, instrumented

    # Teardown: release TCP connection
    try:
        instrumented.reset()
    except Exception:
        pass
    time.sleep(1.0)
