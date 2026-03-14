"""Tests for the airframe profile system.

Validates profile loading, YAML parsing, physical consistency checks,
and environment variable resolution.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import (
    AirframeProfile,
    AltitudeConfig,
    GeometryConfig,
    RecoveryConfig,
    RecoveryThresholdsConfig,
    SafetyConfig,
    SpeedConfig,
    TimingConfig,
    load_profile,
)


# ---------------------------------------------------------------------------
# Default profile matches original hardcoded values
# ---------------------------------------------------------------------------


class TestDefaultProfileValues:
    """Verify that AirframeProfile() defaults match original hardcoded constants."""

    def test_altitude_defaults(self):
        p = AirframeProfile()
        assert p.altitudes.takeoff_m == 40.0
        assert p.altitudes.cruise_m == 60.0
        assert p.altitudes.recovery_m == 50.0

    def test_geometry_defaults(self):
        p = AirframeProfile()
        assert p.geometry.loiter_radius_m == 35.0
        assert p.geometry.home_bubble_radius_m == 80.0
        assert p.geometry.home_operation_bubble_radius_m == 160.0
        assert p.geometry.outbound_startup_bubble_radius_m == 220.0
        assert p.geometry.geofence_half_width_m == 120.0
        assert p.geometry.waypoint_turn_bubble_radius_m == 155.0
        assert p.geometry.home_arrival_radius_m == 120.0

    def test_safety_defaults(self):
        p = AirframeProfile()
        assert p.safety.battery_rtl_threshold_percent == 20.0

    def test_recovery_defaults(self):
        p = AirframeProfile()
        assert p.recovery.primary.speed_threshold_mps == 14.0
        assert p.recovery.primary.home_distance_threshold_m == 80.0
        assert p.recovery.primary.altitude_deviation_m == 12.0
        assert p.recovery.primary.dwell_seconds == 3.0
        assert p.recovery.primary.timeout_seconds == 25.0

        assert p.recovery.fallback.speed_threshold_mps == 17.0
        assert p.recovery.fallback.home_distance_threshold_m == 110.0
        assert p.recovery.fallback.altitude_deviation_m == 18.0
        assert p.recovery.fallback.dwell_seconds == 2.0
        assert p.recovery.fallback.timeout_seconds == 18.0

    def test_timing_defaults(self):
        p = AirframeProfile()
        assert p.timing.takeoff_timeout_seconds == 45.0
        assert p.timing.transition_timeout_seconds == 25.0
        assert p.timing.landing_timeout_seconds == 90.0
        assert p.timing.vtol_landing_approach_min_m == 140.0

    def test_speed_defaults(self):
        p = AirframeProfile()
        assert p.speeds.cruise_airspeed_mps == 22.0
        assert p.speeds.cruise_groundspeed_mps == 20.0
        assert p.speeds.takeoff_airspeed_mps == 4.0
        assert p.speeds.landing_descent_mps == 6.0
        assert p.speeds.battery_drain_rate == 0.02

    def test_name_and_description(self):
        p = AirframeProfile()
        assert p.name == "default-vtol"
        assert p.description == "Default VTOL quadplane profile"


# ---------------------------------------------------------------------------
# YAML profile loading
# ---------------------------------------------------------------------------


class TestYamlLoading:
    """Test profile loading from YAML files."""

    def test_load_default_vtol_yaml(self):
        """default-vtol.yaml should produce identical values to built-in defaults."""
        loaded = load_profile("default-vtol")
        default = AirframeProfile()
        assert loaded.altitudes == default.altitudes
        assert loaded.geometry == default.geometry
        assert loaded.safety == default.safety
        assert loaded.recovery == default.recovery
        assert loaded.timing == default.timing
        assert loaded.speeds == default.speeds
        assert loaded.name == default.name

    def test_load_large_vtol_yaml(self):
        """large-vtol.yaml should load with different (larger) values."""
        loaded = load_profile("large-vtol")
        default = AirframeProfile()
        assert loaded.name == "large-vtol"
        # Large VTOL should have wider geometry
        assert loaded.geometry.loiter_radius_m > default.geometry.loiter_radius_m
        # And higher altitudes
        assert loaded.altitudes.cruise_m > default.altitudes.cruise_m

    def test_load_nonexistent_profile(self):
        """Loading a nonexistent profile should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_profile("nonexistent-vtol-xyz")

    def test_load_none_returns_default(self):
        """load_profile(None) should return built-in default."""
        # Clear env var to ensure default path
        original = os.environ.pop("ARRAKIS_AIRFRAME_PROFILE", None)
        try:
            p = load_profile()
            assert p.name == "default-vtol"
            assert p == AirframeProfile()
        finally:
            if original is not None:
                os.environ["ARRAKIS_AIRFRAME_PROFILE"] = original

    def test_load_by_file_path(self):
        """load_profile with a file path should load that file."""
        yaml_path = BACKEND_DIR / "airframes" / "default-vtol.yaml"
        loaded = load_profile(str(yaml_path))
        assert loaded.name == "default-vtol"

    def test_env_var_resolution(self):
        """ARRAKIS_AIRFRAME_PROFILE env var should select profile."""
        original = os.environ.get("ARRAKIS_AIRFRAME_PROFILE")
        try:
            os.environ["ARRAKIS_AIRFRAME_PROFILE"] = "large-vtol"
            p = load_profile()
            assert p.name == "large-vtol"
        finally:
            if original is not None:
                os.environ["ARRAKIS_AIRFRAME_PROFILE"] = original
            else:
                os.environ.pop("ARRAKIS_AIRFRAME_PROFILE", None)

    def test_partial_yaml_fills_defaults(self):
        """A YAML with only some fields should fill remaining from defaults."""
        partial_yaml = "name: custom-test\naltitudes:\n  cruise_m: 80.0\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(partial_yaml)
            f.flush()
            try:
                p = load_profile(f.name)
                assert p.name == "custom-test"
                assert p.altitudes.cruise_m == 80.0
                # Remaining defaults filled in
                assert p.altitudes.takeoff_m == 40.0
                assert p.geometry.loiter_radius_m == 35.0
                assert p.speeds.cruise_airspeed_mps == 22.0
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# Physical consistency validation
# ---------------------------------------------------------------------------


class TestPhysicalConsistencyValidation:
    """Test that the model_validator catches invalid parameter combinations."""

    def test_altitude_ordering_violation(self):
        """takeoff > recovery should raise ValueError."""
        with pytest.raises(ValueError, match="altitude ordering"):
            AirframeProfile(
                altitudes=AltitudeConfig(takeoff_m=60.0, cruise_m=80.0, recovery_m=50.0)
            )

    def test_altitude_recovery_above_cruise(self):
        """recovery > cruise should raise ValueError."""
        with pytest.raises(ValueError, match="altitude ordering"):
            AirframeProfile(
                altitudes=AltitudeConfig(takeoff_m=30.0, cruise_m=50.0, recovery_m=60.0)
            )

    def test_home_bubble_exceeds_operation(self):
        """home_bubble > home_operation_bubble should raise ValueError."""
        with pytest.raises(ValueError, match="home_bubble_radius"):
            AirframeProfile(
                geometry=GeometryConfig(
                    home_bubble_radius_m=200.0,
                    home_operation_bubble_radius_m=100.0,
                )
            )

    def test_operation_bubble_exceeds_outbound(self):
        """home_operation_bubble > outbound_startup_bubble should raise ValueError."""
        with pytest.raises(ValueError, match="home_operation_bubble_radius"):
            AirframeProfile(
                geometry=GeometryConfig(
                    home_operation_bubble_radius_m=300.0,
                    outbound_startup_bubble_radius_m=200.0,
                )
            )

    def test_geofence_narrower_than_loiter(self):
        """geofence_half_width < loiter_radius should raise ValueError."""
        with pytest.raises(ValueError, match="geofence_half_width"):
            AirframeProfile(
                geometry=GeometryConfig(
                    loiter_radius_m=100.0,
                    geofence_half_width_m=50.0,
                )
            )

    def test_primary_recovery_less_strict_than_fallback(self):
        """primary speed_threshold > fallback should raise ValueError."""
        with pytest.raises(ValueError, match="primary recovery"):
            AirframeProfile(
                recovery=RecoveryConfig(
                    primary=RecoveryThresholdsConfig(
                        speed_threshold_mps=20.0,
                        home_distance_threshold_m=80.0,
                        altitude_deviation_m=12.0,
                        dwell_seconds=3.0,
                        timeout_seconds=25.0,
                    ),
                    fallback=RecoveryThresholdsConfig(
                        speed_threshold_mps=15.0,
                        home_distance_threshold_m=110.0,
                        altitude_deviation_m=18.0,
                        dwell_seconds=2.0,
                        timeout_seconds=18.0,
                    ),
                )
            )

    def test_battery_threshold_too_low(self):
        """Battery threshold < 5% should raise ValueError."""
        with pytest.raises(ValueError, match="battery_rtl_threshold"):
            AirframeProfile(safety=SafetyConfig(battery_rtl_threshold_percent=3.0))

    def test_battery_threshold_too_high(self):
        """Battery threshold > 50% should raise ValueError."""
        with pytest.raises(ValueError, match="battery_rtl_threshold"):
            AirframeProfile(safety=SafetyConfig(battery_rtl_threshold_percent=60.0))

    def test_valid_custom_profile_passes(self):
        """A physically consistent custom profile should pass validation."""
        p = AirframeProfile(
            name="test-valid",
            altitudes=AltitudeConfig(takeoff_m=30.0, cruise_m=80.0, recovery_m=60.0),
            geometry=GeometryConfig(
                loiter_radius_m=50.0,
                home_bubble_radius_m=100.0,
                home_operation_bubble_radius_m=200.0,
                outbound_startup_bubble_radius_m=300.0,
                geofence_half_width_m=150.0,
                waypoint_turn_bubble_radius_m=200.0,
                home_arrival_radius_m=150.0,
            ),
            safety=SafetyConfig(battery_rtl_threshold_percent=25.0),
        )
        assert p.name == "test-valid"
        assert p.altitudes.cruise_m == 80.0


# ---------------------------------------------------------------------------
# Frozen model immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    """Verify that profile objects cannot be mutated after construction."""

    def test_profile_frozen(self):
        p = AirframeProfile()
        with pytest.raises(Exception):
            p.name = "mutated"

    def test_altitude_frozen(self):
        p = AirframeProfile()
        with pytest.raises(Exception):
            p.altitudes.takeoff_m = 999.0

    def test_geometry_frozen(self):
        p = AirframeProfile()
        with pytest.raises(Exception):
            p.geometry.loiter_radius_m = 999.0

    def test_speed_frozen(self):
        p = AirframeProfile()
        with pytest.raises(Exception):
            p.speeds.cruise_airspeed_mps = 999.0
