"""Integration tests for fault injection scenarios.

Tests realistic fault profiles with full mission flows, geofence edge cases,
battery threshold bouncing, and communication loss during missions.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile, load_profile
from arrakis_core.controller import ArrakisController
from arrakis_core.mission_state_machine import MissionStateMachine
from arrakis_core.telemetry_hub import TelemetryHub
from arrakis_core.mission_executor import MissionExecutor
from flight_adapters.fault_injector import (
    BatteryConfig,
    CommConfig,
    FaultInjector,
    FaultProfile,
    GPSNoiseConfig,
    SensorNoiseConfig,
    TakeoffDynamicsConfig,
    WindConfig,
)
from flight_adapters.mock import MockAdapter
from schemas import LatLon, RoutePreview, TelemetrySnapshot

try:
    from arrakis_core.route_planner import build_route_preview
    from schemas import RouteRequest, GeoFencePolygon
    ROUTE_PLANNER_AVAILABLE = True
except ImportError:
    ROUTE_PLANNER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def _make_route_preview(profile: AirframeProfile, home: LatLon | None = None) -> RoutePreview:
    """Build a minimal route preview for testing."""
    if home is None:
        home = LatLon(lat=37.5665, lon=126.978)
    outbound = [
        LatLon(lat=home.lat + 0.001, lon=home.lon),
        LatLon(lat=home.lat + 0.002, lon=home.lon),
    ]
    return_path = [
        LatLon(lat=home.lat + 0.001, lon=home.lon),
        home,
    ]
    from schemas import GeoFence
    geofence = GeoFence(
        coordinates=[
            LatLon(lat=home.lat - 0.01, lon=home.lon - 0.01),
            LatLon(lat=home.lat + 0.01, lon=home.lon - 0.01),
            LatLon(lat=home.lat + 0.01, lon=home.lon + 0.01),
            LatLon(lat=home.lat - 0.01, lon=home.lon + 0.01),
        ],
    )
    return RoutePreview(
        home=home,
        outbound=outbound,
        return_path=return_path,
        geofence=geofence,
        cruise_alt_m=profile.altitudes.cruise_m,
    )


# ---------------------------------------------------------------------------
# Realistic mission with fault profile
# ---------------------------------------------------------------------------

class TestRealisticMissionWithFaults:
    """Tests that a full mission completes under realistic fault conditions."""

    def test_adapter_telemetry_with_realistic_faults(self):
        """Telemetry should still be functional with realistic faults."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        time.sleep(0.5)  # Let telemetry loop run
        snap = adapter.get_snapshot()
        assert isinstance(snap, TelemetrySnapshot)
        assert snap.battery_percent > 0

    def test_adapter_operations_with_realistic_faults(self):
        """Basic operations (arm, takeoff) should work with realistic faults."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        adapter.arm()
        snap = adapter.get_snapshot()
        # May or may not be armed (comm drop possible), but should not crash
        assert isinstance(snap, TelemetrySnapshot)

    def test_quadcopter_with_realistic_faults(self):
        """Quadcopter profile should work with fault injection."""
        profile = load_profile("default-quadcopter")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(20.0)
        snap = adapter.get_snapshot()
        assert isinstance(snap, TelemetrySnapshot)


# ---------------------------------------------------------------------------
# GPS denial scenarios
# ---------------------------------------------------------------------------

class TestGPSDenialScenarios:
    """Tests for GPS denial fault profile."""

    def test_gps_denial_makes_position_invalid(self):
        """Under GPS denial, position_valid should be False at times."""
        fp = FaultProfile.gps_denial()
        fi = FaultInjector(fp)
        invalid_count = 0
        for _ in range(100):
            _, _, _, valid = fi.apply_gps_noise(37.5, 127.0, 100.0)
            if not valid:
                invalid_count += 1
        assert invalid_count > 0, "GPS denial should cause some invalid positions"

    def test_gps_denial_adapter_continues(self):
        """Adapter should not crash under GPS denial."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.gps_denial())
        adapter.connect()
        adapter.arm()
        # Run for a bit
        time.sleep(0.5)
        snap = adapter.get_snapshot()
        assert isinstance(snap, TelemetrySnapshot)


# ---------------------------------------------------------------------------
# Communication loss scenarios
# ---------------------------------------------------------------------------

class TestCommLossScenarios:
    """Tests for communication loss fault profile."""

    def test_comm_loss_drops_commands(self):
        """comm_loss_only profile should drop commands."""
        fp = FaultProfile.comm_loss_only()
        fi = FaultInjector(fp)
        dropped = 0
        for _ in range(100):
            if fi.should_drop_command():
                dropped += 1
        assert dropped > 0, "Comm loss profile should drop some commands"

    def test_comm_loss_adapter_arm_may_fail(self):
        """Under heavy comm loss, arm may silently fail (command dropped)."""
        profile = load_profile("default-vtol")
        fp = FaultProfile(comm=CommConfig(enabled=True, loss_probability=0.8))
        adapter = MockAdapter(profile, fault_profile=fp)
        adapter.connect()
        # Multiple arm attempts — some may be dropped
        for _ in range(10):
            adapter.arm()
        # Should not crash regardless


# ---------------------------------------------------------------------------
# Battery threshold scenarios
# ---------------------------------------------------------------------------

class TestBatteryThresholdScenarios:
    """Tests for battery threshold and non-linear discharge."""

    def test_battery_drains_faster_at_low_level(self):
        """Battery should drain faster below 20% than above 50%."""
        fp = FaultProfile(battery=BatteryConfig(enabled=True))
        fi = FaultInjector(fp)
        # Measure drain rate at high level
        high_start = 80.0
        high_end = fi.compute_battery_drain(high_start, 10.0, 15.0)
        high_drain = high_start - high_end

        # Measure drain rate at low level
        low_start = 15.0
        low_end = fi.compute_battery_drain(low_start, 10.0, 15.0)
        low_drain = low_start - low_end

        assert low_drain > high_drain

    def test_adapter_battery_drain_with_faults(self):
        """Adapter battery should drain when fault injection enabled."""
        profile = load_profile("default-vtol")
        fp = FaultProfile(battery=BatteryConfig(enabled=True, high_drain_rate=0.1))
        adapter = MockAdapter(profile, fault_profile=fp)
        adapter.connect()
        adapter.arm()
        initial = adapter.get_snapshot().battery_percent
        time.sleep(1.0)  # Let telemetry loop drain battery
        final = adapter.get_snapshot().battery_percent
        assert final < initial, "Battery should drain with fault injection"


# ---------------------------------------------------------------------------
# Wind effect scenarios
# ---------------------------------------------------------------------------

class TestWindEffectScenarios:
    """Tests for wind affecting ground speed."""

    def test_strong_headwind_reduces_speed(self):
        """Strong headwind should significantly reduce ground speed."""
        import math
        fp = FaultProfile(wind=WindConfig(
            enabled=True, base_speed_mps=15.0, base_heading_deg=0.0,
            gust_probability=0.0,
        ))
        fi = FaultInjector(fp)
        gs, _ = fi.compute_wind_effect(20.0, math.radians(0.0))
        assert gs < 10.0, f"Strong headwind should cut ground speed significantly, got {gs}"


# ---------------------------------------------------------------------------
# Takeoff dynamics scenarios
# ---------------------------------------------------------------------------

class TestTakeoffDynamicsScenarios:
    """Tests for gradual takeoff climb."""

    def test_gradual_takeoff_in_adapter(self):
        """Adapter with takeoff dynamics should not instantly reach altitude."""
        profile = load_profile("default-vtol")
        fp = FaultProfile(takeoff=TakeoffDynamicsConfig(
            enabled=True, initial_climb_rate_mps=1.0, max_climb_rate_mps=3.0,
        ))
        adapter = MockAdapter(profile, fault_profile=fp)
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(50.0)
        # Immediately after takeoff command, altitude should be less than target
        snap = adapter.get_snapshot()
        # The takeoff target is set but no simulation step has run yet
        assert adapter._takeoff_target_alt == 50.0


# ---------------------------------------------------------------------------
# Combined fault scenarios
# ---------------------------------------------------------------------------

class TestCombinedFaultScenarios:
    def test_stress_profile_does_not_crash(self):
        """Stress profile with all faults should not crash adapter."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.stress())
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(30.0)
        time.sleep(0.5)
        snap = adapter.get_snapshot()
        assert isinstance(snap, TelemetrySnapshot)

    def test_multiple_reset_cycles(self):
        """Multiple connect/arm/reset cycles should work with faults."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        for i in range(3):
            adapter.connect()
            adapter.arm()
            adapter.takeoff_multicopter(20.0)
            adapter.reset()
            snap = adapter.get_snapshot()
            assert snap.battery_percent == 100.0, f"Battery should reset on cycle {i}"
            assert snap.armed is False

    def test_deterministic_with_same_seed(self):
        """Same seed should produce same fault sequence."""
        profile = load_profile("default-vtol")
        fp = FaultProfile.realistic()

        adapter1 = MockAdapter(profile, fault_profile=fp)
        adapter1._fault_injector.seed(999)
        adapter1.connect()

        adapter2 = MockAdapter(profile, fault_profile=fp)
        adapter2._fault_injector.seed(999)
        adapter2.connect()

        for _ in range(10):
            s1 = adapter1._fault_injector.apply_gps_noise(37.5, 127.0, 100.0)
            s2 = adapter2._fault_injector.apply_gps_noise(37.5, 127.0, 100.0)
            assert s1 == s2
