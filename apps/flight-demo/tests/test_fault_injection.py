"""Unit tests for FaultInjector and FaultProfile.

Validates GPS noise distributions, wind model, non-linear battery discharge,
communication fault simulation, and sensor noise.
"""
from __future__ import annotations

import math
import statistics
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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


# ---------------------------------------------------------------------------
# FaultProfile class method tests
# ---------------------------------------------------------------------------

class TestFaultProfilePresets:
    def test_default_all_disabled(self):
        """Default FaultProfile has all faults disabled."""
        fp = FaultProfile()
        assert not fp.gps.enabled
        assert not fp.sensors.enabled
        assert not fp.wind.enabled
        assert not fp.comm.enabled
        assert not fp.battery.enabled
        assert not fp.takeoff.enabled

    def test_realistic_enables_all(self):
        """Realistic preset enables all fault categories."""
        fp = FaultProfile.realistic()
        assert fp.gps.enabled
        assert fp.sensors.enabled
        assert fp.wind.enabled
        assert fp.comm.enabled
        assert fp.battery.enabled
        assert fp.takeoff.enabled

    def test_stress_enables_all(self):
        """Stress preset enables all fault categories."""
        fp = FaultProfile.stress()
        assert fp.gps.enabled
        assert fp.sensors.enabled
        assert fp.wind.enabled
        assert fp.comm.enabled
        assert fp.battery.enabled
        assert fp.takeoff.enabled

    def test_comm_loss_only_enables_comm_only(self):
        """comm_loss_only preset enables only comm faults."""
        fp = FaultProfile.comm_loss_only()
        assert not fp.gps.enabled
        assert not fp.sensors.enabled
        assert not fp.wind.enabled
        assert fp.comm.enabled
        assert not fp.battery.enabled
        assert not fp.takeoff.enabled

    def test_gps_denial_enables_gps_only(self):
        """gps_denial preset enables only GPS faults."""
        fp = FaultProfile.gps_denial()
        assert fp.gps.enabled
        assert not fp.sensors.enabled
        assert not fp.wind.enabled
        assert not fp.comm.enabled
        assert not fp.battery.enabled
        assert not fp.takeoff.enabled

    def test_stress_more_aggressive_than_realistic(self):
        """Stress profile has higher noise/loss values than realistic."""
        r = FaultProfile.realistic()
        s = FaultProfile.stress()
        assert s.gps.horizontal_stddev_m > r.gps.horizontal_stddev_m
        assert s.gps.dropout_probability > r.gps.dropout_probability
        assert s.wind.base_speed_mps > r.wind.base_speed_mps
        assert s.comm.loss_probability > r.comm.loss_probability


# ---------------------------------------------------------------------------
# GPS noise tests
# ---------------------------------------------------------------------------

class TestGPSNoise:
    def test_disabled_returns_exact_position(self):
        """When GPS noise disabled, returns exact input."""
        fi = FaultInjector(FaultProfile())
        lat, lon, alt, valid = fi.apply_gps_noise(37.5665, 126.978, 100.0)
        assert lat == 37.5665
        assert lon == 126.978
        assert alt == 100.0
        assert valid is True

    def test_enabled_adds_noise(self):
        """When GPS noise enabled, position is perturbed."""
        fp = FaultProfile(gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=2.0))
        fi = FaultInjector(fp)
        lat, lon, alt, valid = fi.apply_gps_noise(37.5665, 126.978, 100.0)
        # Position should be slightly different (noise applied)
        assert valid is True
        # At least one coordinate should differ (with very high probability)
        assert lat != 37.5665 or lon != 126.978

    def test_noise_distribution_statistics(self):
        """GPS noise has approximately correct standard deviation."""
        fp = FaultProfile(gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=2.0, dropout_probability=0.0))
        fi = FaultInjector(fp)
        lat_offsets_m = []
        base_lat, base_lon = 37.5665, 126.978
        lat_scale = 111_320.0
        for _ in range(1000):
            lat, _lon, _alt, valid = fi.apply_gps_noise(base_lat, base_lon, 100.0)
            if valid:
                lat_offsets_m.append((lat - base_lat) * lat_scale)

        assert len(lat_offsets_m) >= 900  # no dropouts configured
        stddev = statistics.stdev(lat_offsets_m)
        # Should be roughly 2.0m (within 50% tolerance for 1000 samples)
        assert 1.0 < stddev < 4.0, f"GPS noise stddev {stddev:.2f}m outside expected range"

    def test_altitude_clamped_non_negative(self):
        """GPS noise on altitude never goes below 0."""
        fp = FaultProfile(gps=GPSNoiseConfig(enabled=True, vertical_stddev_m=50.0, dropout_probability=0.0))
        fi = FaultInjector(fp)
        for _ in range(100):
            _lat, _lon, alt, _ = fi.apply_gps_noise(37.0, 127.0, 1.0)
            assert alt >= 0.0

    def test_dropout_returns_invalid(self):
        """GPS dropout makes position invalid."""
        fp = FaultProfile(gps=GPSNoiseConfig(enabled=True, dropout_probability=1.0, dropout_duration_s=10.0))
        fi = FaultInjector(fp)
        _lat, _lon, _alt, valid = fi.apply_gps_noise(37.0, 127.0, 100.0)
        assert valid is False

    def test_seed_deterministic(self):
        """Same seed produces identical GPS noise sequence."""
        fp = FaultProfile(gps=GPSNoiseConfig(enabled=True, horizontal_stddev_m=2.0, dropout_probability=0.0))
        fi1 = FaultInjector(fp)
        fi1.seed(123)
        fi2 = FaultInjector(fp)
        fi2.seed(123)
        for _ in range(20):
            r1 = fi1.apply_gps_noise(37.5, 127.0, 100.0)
            r2 = fi2.apply_gps_noise(37.5, 127.0, 100.0)
            assert r1[0] == r2[0]
            assert r1[1] == r2[1]


# ---------------------------------------------------------------------------
# Sensor noise tests
# ---------------------------------------------------------------------------

class TestSensorNoise:
    def test_disabled_returns_exact(self):
        fi = FaultInjector(FaultProfile())
        alt, airspeed = fi.apply_sensor_noise(100.0, 15.0)
        assert alt == 100.0
        assert airspeed == 15.0

    def test_enabled_adds_noise(self):
        fp = FaultProfile(sensors=SensorNoiseConfig(enabled=True, altitude_stddev_m=1.0, airspeed_stddev_mps=0.5))
        fi = FaultInjector(fp)
        alt, airspeed = fi.apply_sensor_noise(100.0, 15.0)
        assert alt != 100.0 or airspeed != 15.0

    def test_airspeed_clamped_non_negative(self):
        fp = FaultProfile(sensors=SensorNoiseConfig(enabled=True, airspeed_stddev_mps=50.0))
        fi = FaultInjector(fp)
        for _ in range(100):
            _alt, airspeed = fi.apply_sensor_noise(100.0, 1.0)
            assert airspeed >= 0.0


# ---------------------------------------------------------------------------
# Wind model tests
# ---------------------------------------------------------------------------

class TestWindModel:
    def test_disabled_no_effect(self):
        fi = FaultInjector(FaultProfile())
        gs, drift = fi.compute_wind_effect(20.0, 0.0)
        assert gs == 20.0
        assert drift == 0.0

    def test_headwind_reduces_groundspeed(self):
        """Headwind should reduce ground speed."""
        fp = FaultProfile(wind=WindConfig(
            enabled=True, base_speed_mps=10.0, base_heading_deg=0.0,
            gust_probability=0.0,
        ))
        fi = FaultInjector(fp)
        gs, _drift = fi.compute_wind_effect(20.0, math.radians(0.0))  # flying into the wind
        assert gs < 20.0

    def test_tailwind_increases_groundspeed(self):
        """Tailwind should increase ground speed."""
        fp = FaultProfile(wind=WindConfig(
            enabled=True, base_speed_mps=10.0, base_heading_deg=180.0,
            gust_probability=0.0,
        ))
        fi = FaultInjector(fp)
        gs, _drift = fi.compute_wind_effect(20.0, math.radians(0.0))  # wind from behind
        assert gs > 20.0

    def test_groundspeed_never_negative(self):
        """Ground speed should never go below zero."""
        fp = FaultProfile(wind=WindConfig(
            enabled=True, base_speed_mps=100.0, gust_probability=0.0,
        ))
        fi = FaultInjector(fp)
        gs, _drift = fi.compute_wind_effect(5.0, 0.0)
        assert gs >= 0.0

    def test_crosswind_produces_drift(self):
        """Crosswind should produce non-zero heading drift."""
        fp = FaultProfile(wind=WindConfig(
            enabled=True, base_speed_mps=10.0, base_heading_deg=90.0,
            gust_probability=0.0,
        ))
        fi = FaultInjector(fp)
        _gs, drift = fi.compute_wind_effect(20.0, math.radians(0.0))
        assert abs(drift) > 0.0


# ---------------------------------------------------------------------------
# Communication fault tests
# ---------------------------------------------------------------------------

class TestCommFaults:
    def test_disabled_never_drops(self):
        fi = FaultInjector(FaultProfile())
        for _ in range(100):
            assert fi.should_drop_command() is False

    def test_disabled_zero_delay(self):
        fi = FaultInjector(FaultProfile())
        for _ in range(100):
            assert fi.command_delay() == 0.0

    def test_guaranteed_drop(self):
        fp = FaultProfile(comm=CommConfig(enabled=True, loss_probability=1.0))
        fi = FaultInjector(fp)
        assert fi.should_drop_command() is True

    def test_guaranteed_no_drop(self):
        fp = FaultProfile(comm=CommConfig(enabled=True, loss_probability=0.0))
        fi = FaultInjector(fp)
        for _ in range(100):
            assert fi.should_drop_command() is False

    def test_delay_is_non_negative(self):
        fp = FaultProfile(comm=CommConfig(enabled=True, base_delay_s=0.05, jitter_s=0.1))
        fi = FaultInjector(fp)
        for _ in range(100):
            assert fi.command_delay() >= 0.0

    def test_sustained_comm_loss_window(self):
        """Sustained comm loss window should keep dropping for duration."""
        fp = FaultProfile(comm=CommConfig(enabled=True, loss_probability=1.0, loss_duration_s=100.0))
        fi = FaultInjector(fp)
        fi.should_drop_command()  # triggers loss window
        # Subsequent calls during window should also drop
        assert fi.should_drop_command() is True
        assert fi.should_drop_command() is True


# ---------------------------------------------------------------------------
# Battery model tests
# ---------------------------------------------------------------------------

class TestBatteryModel:
    def test_disabled_returns_same_percent(self):
        fi = FaultInjector(FaultProfile())
        result = fi.compute_battery_drain(80.0, 1.0, 10.0)
        assert result == 80.0

    def test_drains_over_time(self):
        fp = FaultProfile(battery=BatteryConfig(enabled=True))
        fi = FaultInjector(fp)
        result = fi.compute_battery_drain(80.0, 1.0, 10.0)
        assert result < 80.0

    def test_never_negative(self):
        fp = FaultProfile(battery=BatteryConfig(enabled=True))
        fi = FaultInjector(fp)
        result = fi.compute_battery_drain(0.1, 100.0, 30.0)
        assert result >= 0.0

    def test_nonlinear_three_zones(self):
        """Battery drains faster below 20% than above 50%."""
        fp = FaultProfile(battery=BatteryConfig(enabled=True))
        fi = FaultInjector(fp)
        # High zone drain
        high_after = fi.compute_battery_drain(80.0, 1.0, 10.0)
        high_drain = 80.0 - high_after

        # Low zone drain
        low_after = fi.compute_battery_drain(15.0, 1.0, 10.0)
        low_drain = 15.0 - low_after

        assert low_drain > high_drain, "Battery should drain faster below 20% than above 50%"

    def test_maneuvering_drains_faster(self):
        """Maneuvering adds voltage sag penalty."""
        fp = FaultProfile(battery=BatteryConfig(enabled=True, voltage_sag_factor=0.2))
        fi = FaultInjector(fp)
        normal = fi.compute_battery_drain(60.0, 1.0, 10.0)
        maneuvering = fi.compute_battery_drain(60.0, 1.0, 10.0, is_maneuvering=True)
        assert maneuvering < normal

    def test_mid_zone_between_high_and_low(self):
        """Mid zone (20-50%) drains faster than high (>50%) but slower than low (<20%)."""
        fp = FaultProfile(battery=BatteryConfig(enabled=True))
        fi = FaultInjector(fp)
        high_drain = 80.0 - fi.compute_battery_drain(80.0, 1.0, 10.0)
        mid_drain = 35.0 - fi.compute_battery_drain(35.0, 1.0, 10.0)
        low_drain = 15.0 - fi.compute_battery_drain(15.0, 1.0, 10.0)
        assert mid_drain > high_drain
        assert low_drain > mid_drain


# ---------------------------------------------------------------------------
# Takeoff dynamics tests
# ---------------------------------------------------------------------------

class TestTakeoffDynamics:
    def test_disabled_instant_jump(self):
        fi = FaultInjector(FaultProfile())
        alt, reached = fi.compute_takeoff_altitude(50.0, 0.0, 1.0)
        assert alt == 50.0
        assert reached is True

    def test_enabled_gradual_climb(self):
        fp = FaultProfile(takeoff=TakeoffDynamicsConfig(
            enabled=True, initial_climb_rate_mps=2.0, max_climb_rate_mps=5.0,
        ))
        fi = FaultInjector(fp)
        alt, reached = fi.compute_takeoff_altitude(50.0, 0.0, 1.0)
        assert alt < 50.0, "First step should not reach target"
        assert reached is False

    def test_reaches_target_eventually(self):
        fp = FaultProfile(takeoff=TakeoffDynamicsConfig(
            enabled=True, initial_climb_rate_mps=2.0, max_climb_rate_mps=5.0,
        ))
        fi = FaultInjector(fp)
        current = 0.0
        for _ in range(100):
            current, reached = fi.compute_takeoff_altitude(50.0, current, 1.0)
            if reached:
                break
        assert reached, "Should reach target altitude within 100 steps"
        assert current == 50.0

    def test_reset_allows_new_takeoff(self):
        fp = FaultProfile(takeoff=TakeoffDynamicsConfig(enabled=True))
        fi = FaultInjector(fp)
        fi.compute_takeoff_altitude(10.0, 0.0, 1.0)
        fi.reset_takeoff()
        # After reset, internal state cleared
        alt, reached = fi.compute_takeoff_altitude(10.0, 0.0, 1.0)
        assert not reached  # should start climbing again from initial rate
