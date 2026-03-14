"""Tests for quadcopter airframe type support.

Validates that:
- airframe_type field works correctly with "vtol" and "quadcopter" values
- Physical consistency validation adapts per airframe type
- MockAdapter simulation correctly handles quadcopter mode
- Existing VTOL behavior is unchanged (backward compatibility)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from airframe_profile import (
    AirframeProfile,
    AltitudeConfig,
    RecoveryConfig,
    RecoveryThresholdsConfig,
    SafetyConfig,
    load_profile,
)
from flight_adapters.mock import MockAdapter
from flight_adapters.instrumented import InstrumentedFlightAdapter


# ---------------------------------------------------------------------------
# Profile airframe_type field
# ---------------------------------------------------------------------------


class TestAirframeTypeField:
    """Verify airframe_type field and is_vtol property."""

    def test_default_airframe_type_is_vtol(self):
        p = AirframeProfile()
        assert p.airframe_type == "vtol"
        assert p.is_vtol is True

    def test_quadcopter_airframe_type(self):
        p = AirframeProfile(airframe_type="quadcopter")
        assert p.airframe_type == "quadcopter"
        assert p.is_vtol is False

    def test_invalid_airframe_type_rejected(self):
        with pytest.raises(Exception):
            AirframeProfile(airframe_type="helicopter")

    def test_vtol_yaml_includes_airframe_type(self):
        p = load_profile("default-vtol")
        assert p.airframe_type == "vtol"
        assert p.is_vtol is True

    def test_large_vtol_yaml_includes_airframe_type(self):
        p = load_profile("large-vtol")
        assert p.airframe_type == "vtol"

    def test_backward_compatible_default(self):
        """AirframeProfile() with no args should behave exactly as before."""
        default = AirframeProfile()
        assert default.airframe_type == "vtol"
        assert default.name == "default-vtol"
        assert default.altitudes.takeoff_m == 40.0


# ---------------------------------------------------------------------------
# Quadcopter YAML profile loading
# ---------------------------------------------------------------------------


class TestQuadcopterYaml:
    """Test quadcopter YAML profile loading."""

    def test_load_quadcopter_profile(self):
        p = load_profile("default-quadcopter")
        assert p.name == "default-quadcopter"
        assert p.airframe_type == "quadcopter"
        assert p.is_vtol is False

    def test_quadcopter_has_smaller_geometry(self):
        quad = load_profile("default-quadcopter")
        vtol = AirframeProfile()
        assert quad.geometry.loiter_radius_m < vtol.geometry.loiter_radius_m
        assert quad.geometry.geofence_half_width_m < vtol.geometry.geofence_half_width_m

    def test_quadcopter_has_lower_altitudes(self):
        quad = load_profile("default-quadcopter")
        vtol = AirframeProfile()
        assert quad.altitudes.cruise_m < vtol.altitudes.cruise_m

    def test_quadcopter_has_higher_battery_threshold(self):
        quad = load_profile("default-quadcopter")
        vtol = AirframeProfile()
        assert quad.safety.battery_rtl_threshold_percent > vtol.safety.battery_rtl_threshold_percent


# ---------------------------------------------------------------------------
# Conditional validation per airframe type
# ---------------------------------------------------------------------------


class TestConditionalValidation:
    """Verify validation rules adapt by airframe type."""

    def test_vtol_altitude_ordering_enforced(self):
        """VTOL: takeoff > recovery should raise ValueError."""
        with pytest.raises(ValueError, match="altitude ordering"):
            AirframeProfile(
                airframe_type="vtol",
                altitudes=AltitudeConfig(takeoff_m=60.0, cruise_m=80.0, recovery_m=50.0),
            )

    def test_quadcopter_skips_recovery_altitude_check(self):
        """Quadcopter: takeoff > recovery is OK (recovery unused)."""
        p = AirframeProfile(
            name="test-quad",
            airframe_type="quadcopter",
            altitudes=AltitudeConfig(takeoff_m=30.0, cruise_m=50.0, recovery_m=10.0),
        )
        assert p.altitudes.recovery_m == 10.0  # No error

    def test_quadcopter_still_validates_takeoff_vs_cruise(self):
        """Quadcopter: takeoff > cruise should still raise ValueError."""
        with pytest.raises(ValueError, match="takeoff altitude"):
            AirframeProfile(
                name="test-quad",
                airframe_type="quadcopter",
                altitudes=AltitudeConfig(takeoff_m=60.0, cruise_m=40.0, recovery_m=30.0),
            )

    def test_quadcopter_skips_recovery_threshold_ordering(self):
        """Quadcopter: primary speed > fallback speed is OK (recovery unused)."""
        p = AirframeProfile(
            name="test-quad",
            airframe_type="quadcopter",
            recovery=RecoveryConfig(
                primary=RecoveryThresholdsConfig(
                    speed_threshold_mps=20.0,
                    home_distance_threshold_m=80.0,
                    altitude_deviation_m=12.0,
                    dwell_seconds=3.0,
                    timeout_seconds=25.0,
                ),
                fallback=RecoveryThresholdsConfig(
                    speed_threshold_mps=10.0,
                    home_distance_threshold_m=110.0,
                    altitude_deviation_m=18.0,
                    dwell_seconds=2.0,
                    timeout_seconds=18.0,
                ),
            ),
        )
        assert p.recovery.primary.speed_threshold_mps == 20.0

    def test_vtol_recovery_threshold_ordering_enforced(self):
        """VTOL: primary speed > fallback speed should raise ValueError."""
        with pytest.raises(ValueError, match="primary recovery"):
            AirframeProfile(
                airframe_type="vtol",
                recovery=RecoveryConfig(
                    primary=RecoveryThresholdsConfig(
                        speed_threshold_mps=20.0,
                        home_distance_threshold_m=80.0,
                        altitude_deviation_m=12.0,
                        dwell_seconds=3.0,
                        timeout_seconds=25.0,
                    ),
                    fallback=RecoveryThresholdsConfig(
                        speed_threshold_mps=10.0,
                        home_distance_threshold_m=110.0,
                        altitude_deviation_m=18.0,
                        dwell_seconds=2.0,
                        timeout_seconds=18.0,
                    ),
                ),
            )

    def test_common_validations_apply_to_quadcopter(self):
        """Quadcopter: bubble nesting, geofence, battery still enforced."""
        with pytest.raises(ValueError, match="battery_rtl_threshold"):
            AirframeProfile(
                airframe_type="quadcopter",
                safety=SafetyConfig(battery_rtl_threshold_percent=3.0),
            )


# ---------------------------------------------------------------------------
# MockAdapter quadcopter simulation
# ---------------------------------------------------------------------------


class TestMockAdapterQuadcopter:
    """Verify MockAdapter correctly simulates quadcopter mode."""

    def test_quadcopter_start_mission_stays_mc(self):
        """Quadcopter start_mission should keep vtol_state as MC."""
        profile = AirframeProfile(airframe_type="quadcopter")
        adapter = MockAdapter(profile)
        adapter.connect()
        adapter.arm()
        adapter.start_mission()
        snapshot = adapter.get_snapshot()
        assert snapshot.vtol_state == "MC"

    def test_vtol_start_mission_goes_fw(self):
        """VTOL start_mission should switch vtol_state to FW."""
        profile = AirframeProfile()
        adapter = MockAdapter(profile)
        adapter.connect()
        adapter.arm()
        adapter.start_mission()
        snapshot = adapter.get_snapshot()
        assert snapshot.vtol_state == "FW"

    def test_quadcopter_return_to_home_stays_mc(self):
        """Quadcopter return_to_home should keep vtol_state as MC."""
        profile = AirframeProfile(airframe_type="quadcopter")
        adapter = MockAdapter(profile)
        adapter.connect()
        adapter.arm()
        adapter.return_to_home()
        snapshot = adapter.get_snapshot()
        assert snapshot.vtol_state == "MC"

    def test_vtol_return_to_home_goes_fw(self):
        """VTOL return_to_home should switch vtol_state to FW."""
        profile = AirframeProfile()
        adapter = MockAdapter(profile)
        adapter.connect()
        adapter.arm()
        adapter.return_to_home()
        snapshot = adapter.get_snapshot()
        assert snapshot.vtol_state == "FW"


# ---------------------------------------------------------------------------
# Adapter contract with quadcopter profile
# ---------------------------------------------------------------------------


class TestAdapterContractQuadcopter:
    """Verify MockAdapter passes contract checks with quadcopter profile."""

    def test_mock_adapter_contract_quadcopter(self):
        from flight_adapters.base import validate_adapter_contract

        profile = AirframeProfile(airframe_type="quadcopter")
        adapter = MockAdapter(profile)
        validate_adapter_contract(adapter)

        adapter.connect()
        adapter.arm()
        snapshot = adapter.get_snapshot()
        assert snapshot.armed is True
        assert snapshot.vtol_state == "MC"

    def test_instrumented_mock_quadcopter(self):
        profile = AirframeProfile(airframe_type="quadcopter")
        adapter = InstrumentedFlightAdapter(MockAdapter(profile), logger_name="test.quad")
        adapter.connect()
        adapter.arm()
        snapshot = adapter.get_snapshot()
        assert snapshot.armed is True
