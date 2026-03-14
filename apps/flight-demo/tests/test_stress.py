"""Stress tests for long-running scenarios.

These tests run longer simulations and are marked with pytest.mark.slow
so they can be selectively executed.

Run with: python -m pytest tests/test_stress.py -v -m slow
Skip with: python -m pytest tests/ -v -m "not slow"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import AirframeProfile, load_profile
from flight_adapters.fault_injector import FaultInjector, FaultProfile
from flight_adapters.mock import MockAdapter
from schemas import TelemetrySnapshot

slow = pytest.mark.slow


@slow
class TestLongRunningMission:
    """Stress tests simulating extended mission durations."""

    def test_battery_nonlinear_full_depletion(self):
        """Battery should fully deplete through all three zones."""
        fp = FaultProfile.realistic()
        fi = FaultInjector(fp)
        current = 100.0
        steps = 0
        zone_entries = {"high": False, "mid": False, "low": False}
        while current > 0.0 and steps < 10000:
            if current > 50:
                zone_entries["high"] = True
            elif current > 20:
                zone_entries["mid"] = True
            else:
                zone_entries["low"] = True
            current = fi.compute_battery_drain(current, 1.0, 15.0)
            steps += 1
        assert current == 0.0, "Battery should reach zero"
        assert all(zone_entries.values()), "Battery should pass through all zones"

    def test_gps_noise_statistical_properties(self):
        """GPS noise over many samples should have expected statistical properties."""
        import statistics
        fp = FaultProfile(
            gps=__import__("flight_adapters.fault_injector", fromlist=["GPSNoiseConfig"]).GPSNoiseConfig(
                enabled=True, horizontal_stddev_m=2.0, dropout_probability=0.0,
            ),
        )
        fi = FaultInjector(fp)
        lat_offsets = []
        lon_offsets = []
        base_lat, base_lon = 37.5665, 126.978
        lat_scale = 111_320.0
        import math
        lon_scale = math.cos(math.radians(base_lat)) * 111_320.0

        for _ in range(5000):
            lat, lon, _, valid = fi.apply_gps_noise(base_lat, base_lon, 100.0)
            if valid:
                lat_offsets.append((lat - base_lat) * lat_scale)
                lon_offsets.append((lon - base_lon) * lon_scale)

        lat_mean = statistics.mean(lat_offsets)
        lat_std = statistics.stdev(lat_offsets)
        lon_mean = statistics.mean(lon_offsets)
        lon_std = statistics.stdev(lon_offsets)

        # Mean should be close to 0 (within ~0.3m for 5000 samples)
        assert abs(lat_mean) < 0.3, f"Lat mean {lat_mean:.3f} too far from 0"
        assert abs(lon_mean) < 0.3, f"Lon mean {lon_mean:.3f} too far from 0"
        # Stddev should be close to 2.0m (within 30% for 5000 samples)
        assert 1.4 < lat_std < 2.8, f"Lat stddev {lat_std:.2f} outside expected range"
        assert 1.4 < lon_std < 2.8, f"Lon stddev {lon_std:.2f} outside expected range"

    def test_repeated_abort_cycles(self):
        """Multiple arm-abort cycles should not leak state."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.realistic())
        adapter.connect()
        for cycle in range(10):
            adapter.arm()
            adapter.takeoff_multicopter(20.0)
            adapter.abort("stress test cycle")
            adapter.reset()
            snap = adapter.get_snapshot()
            assert snap.battery_percent == 100.0, f"Battery leaked on cycle {cycle}"
            assert not snap.armed, f"Armed leaked on cycle {cycle}"

    def test_wind_gust_statistics(self):
        """Wind gust events should occur at roughly the configured probability."""
        import math
        fp = FaultProfile(
            wind=__import__("flight_adapters.fault_injector", fromlist=["WindConfig"]).WindConfig(
                enabled=True, base_speed_mps=3.0, gust_probability=0.1,
                gust_speed_mps=5.0,
            ),
        )
        fi = FaultInjector(fp)
        speeds = []
        base_gs = 20.0
        for _ in range(1000):
            gs, _ = fi.compute_wind_effect(base_gs, math.radians(90.0))
            speeds.append(gs)

        # With gusts, some ground speeds should vary more than base wind alone
        min_gs = min(speeds)
        max_gs = max(speeds)
        assert max_gs - min_gs > 1.0, "Wind gusts should cause speed variation"

    def test_adapter_extended_telemetry(self):
        """Extended telemetry collection should not crash or degrade."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.stress())
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(30.0)

        snapshots = []
        for _ in range(50):
            snap = adapter.get_snapshot()
            snapshots.append(snap)
            time.sleep(0.05)

        assert len(snapshots) == 50
        # Battery should be draining
        first_battery = snapshots[0].battery_percent
        last_battery = snapshots[-1].battery_percent
        assert last_battery <= first_battery

    def test_stress_profile_long_run(self):
        """Stress profile running for 5 simulated seconds should not crash."""
        profile = load_profile("default-vtol")
        adapter = MockAdapter(profile, fault_profile=FaultProfile.stress())
        adapter.connect()
        adapter.arm()
        adapter.takeoff_multicopter(30.0)
        adapter.transition_to_fixedwing()
        adapter.start_mission()

        start = time.time()
        while time.time() - start < 2.0:  # 2 real seconds
            snap = adapter.get_snapshot()
            assert isinstance(snap, TelemetrySnapshot)
            time.sleep(0.1)

        adapter.return_to_home()
        adapter.land_vertical()
        # Should not have crashed
        snap = adapter.get_snapshot()
        assert isinstance(snap, TelemetrySnapshot)
