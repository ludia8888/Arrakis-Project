"""Shared fixtures for flight-demo test suite.

Provides pre-configured profiles and adapters for VTOL, quadcopter,
and fault-injected scenarios.
"""
from __future__ import annotations

import sys
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
